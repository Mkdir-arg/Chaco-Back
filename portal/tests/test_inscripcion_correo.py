"""Tests del correo de confirmación de la inscripción pública (#296, RN-P10)."""

from unittest.mock import patch

from django.core import mail
from django.urls import reverse

from portal.services.inscripcion import clave_sesion
from portal.tests.test_inscripcion_envio import _BasePaso2Test, _identificacion
from programas.models import Formulario, Relevamiento
from programas.services.inscripcion_publica import enmascarar_email, enviar_confirmacion_inscripcion
from programas.tests.test_becas_api import _BaseApiTest


class EnviarConfirmacionTests(_BasePaso2Test):
    def _formulario(self):
        return Formulario.objects.create(
            relevamiento=self.relevamiento,
            celular="3624123456",
            email_contacto="maria.gomez@correo.com",
            datos_identificacion={"dni": "30123456"},
        )

    def test_toggle_activo_envia_comprobante(self):
        self.relevamiento.confirmar_por_email = True
        self.relevamiento.save(update_fields=["confirmar_por_email"])
        formulario = self._formulario()
        self.assertTrue(enviar_confirmacion_inscripcion(formulario))
        self.assertEqual(len(mail.outbox), 1)
        correo = mail.outbox[0]
        self.assertEqual(correo.to, ["maria.gomez@correo.com"])
        self.assertIn("Becas 2026", correo.subject)
        self.assertIn(f"Formulario Nº {formulario.numero}", correo.body)
        self.assertIn("Becas 2026", correo.body)

    def test_manda_texto_y_html_de_marca(self):
        self.relevamiento.confirmar_por_email = True
        self.relevamiento.save(update_fields=["confirmar_por_email"])
        formulario = self._formulario()
        formulario.datos_identificacion = {"dni": "30123456", "nombre": "MARIA LUJAN", "apellido": "GOMEZ"}
        formulario.save(update_fields=["datos_identificacion"])

        self.assertTrue(enviar_confirmacion_inscripcion(formulario, domain="datanach.example"))

        correo = mail.outbox[0]
        self.assertEqual(len(correo.alternatives), 1, "falta la versión HTML")
        html, tipo = correo.alternatives[0]
        self.assertEqual(tipo, "text/html")
        # Saludo con el nombre de pila, no con el nombre completo.
        self.assertIn("Hola MARIA,", html)
        self.assertIn("Hola MARIA,", correo.body)
        # Los datos del comprobante, en las dos versiones.
        for cuerpo in (html, correo.body):
            self.assertIn(str(formulario.numero), cuerpo)
            self.assertIn("30123456", cuerpo)
            self.assertIn("Becas 2026", cuerpo)
        # Marca del portal, no la del backoffice, y logo con URL absoluta.
        self.assertIn("Portal Ciudadano", html)
        self.assertNotIn("Backoffice", html)
        self.assertIn("https://datanach.example/static/", html)

    def test_sin_nombre_el_saludo_no_queda_colgado(self):
        self.relevamiento.confirmar_por_email = True
        self.relevamiento.save(update_fields=["confirmar_por_email"])
        formulario = self._formulario()  # datos_identificacion sin nombre

        self.assertTrue(enviar_confirmacion_inscripcion(formulario))

        html = mail.outbox[0].alternatives[0][0]
        self.assertIn("Hola,", html)

    def test_toggle_apagado_no_envia(self):
        formulario = self._formulario()
        self.assertFalse(enviar_confirmacion_inscripcion(formulario))
        self.assertEqual(len(mail.outbox), 0)

    def test_falla_de_smtp_no_rompe(self):
        self.relevamiento.confirmar_por_email = True
        self.relevamiento.save(update_fields=["confirmar_por_email"])
        formulario = self._formulario()
        with patch(
            "programas.services.inscripcion_publica.EmailMultiAlternatives.send",
            side_effect=OSError("smtp caído"),
        ):
            self.assertFalse(enviar_confirmacion_inscripcion(formulario))
        self.assertTrue(Formulario.objects.filter(pk=formulario.pk).exists())

    def test_enmascarar_email(self):
        self.assertEqual(enmascarar_email("maria.gomez@correo.com"), "ma•••@correo.com")
        self.assertEqual(enmascarar_email("a@x.com"), "a•••@x.com")
        self.assertEqual(enmascarar_email(""), "")


class CorreoEnLaVistaTests(_BasePaso2Test):
    def _enviar(self):
        session = self.client.session
        session[clave_sesion(self.relevamiento)] = _identificacion()
        session.save()
        url = reverse("portal:inscripcion_paso2", kwargs={"token": self.relevamiento.token_publico})
        return self.client.post(url, {**self._data(), **self._files()})

    def test_envio_con_toggle_manda_correo_y_lo_marca_en_el_comprobante(self):
        self.relevamiento.confirmar_por_email = True
        self.relevamiento.save(update_fields=["confirmar_por_email"])
        # El cuerpo del correo se renderiza con un template; bajo el test client
        # de este entorno (Python 3.14 + Django 4.2) ese render rompe por el bug
        # conocido de Context.__copy__, así que acá se fija el cuerpo y el
        # template se cubre en EnviarConfirmacionTests (sin client).
        with patch("programas.services.inscripcion_publica.render_to_string", return_value="Comprobante"):
            resp = self._enviar()
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        comprobante = self.client.session[f"inscripcion_ok_{self.relevamiento.pk}"]
        self.assertTrue(comprobante["correo_enviado"])
        self.assertEqual(comprobante["email"], "ma•••@correo.com")

    def test_envio_sin_toggle_no_manda(self):
        resp = self._enviar()
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(self.client.session[f"inscripcion_ok_{self.relevamiento.pk}"]["correo_enviado"])

    def test_smtp_caido_no_impide_la_inscripcion(self):
        self.relevamiento.confirmar_por_email = True
        self.relevamiento.save(update_fields=["confirmar_por_email"])
        with patch(
            "programas.services.inscripcion_publica.EmailMultiAlternatives.send",
            side_effect=OSError("smtp caído"),
        ):
            resp = self._enviar()
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.relevamiento.formularios.count(), 1)
        self.assertFalse(self.client.session[f"inscripcion_ok_{self.relevamiento.pk}"]["correo_enviado"])


class ElFlujoDeCampoNoMandaCorreoTests(_BaseApiTest):
    def test_sync_desde_la_app_no_dispara_correo(self):
        # Aunque el toggle estuviera encendido en un territorial (la UI no lo
        # permite), la API de campo jamás manda el correo: es del flujo público.
        self.rel.estado = Relevamiento.Estado.EN_CURSO
        self.rel.confirmar_por_email = True
        self.rel.save(update_fields=["estado", "confirmar_por_email"])
        self.autenticar(self.terri)
        resp = self.client.post(
            reverse("becas_api:relevamiento-formularios", args=[self.rel.pk]),
            {
                "datos_identificacion": {
                    "dni": "20111222",
                    "nombre": "Ana",
                    "apellido": "Paz",
                    "fecha_nacimiento": "1990-01-01",
                },
                "celular": "3624000000",
                "email_contacto": "ana@correo.com",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(len(mail.outbox), 0)
