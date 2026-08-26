"""Tests del aviso por correo de la resolución de un formulario (Cambio 44).

Se ejercita el servicio directo, sin el test client: bajo Python 3.14 +
Django 4.2 el render de plantillas dentro del client rompe por el bug conocido
de ``Context.__copy__`` (mismo criterio que ``portal/tests/test_inscripcion_correo``).
"""

from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase

from legajos.models import Ciudadano
from programas.models import Convocatoria, Formulario, Relevamiento, Segmento
from programas.services.avisos_resolucion import enviar_aviso_resolucion


class _BaseAvisoTest(TestCase):
    def setUp(self):
        self.segmento = Segmento.objects.create(nombre="Becas Secundario", cupo_maximo=100)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Becas 2026",
            segmento=self.segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        self.territorial = User.objects.create_user("terri", password="x")
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            tipo=Relevamiento.Tipo.PUBLICO,
            fecha_asignada=date(2026, 6, 1),
            confirmar_por_email=True,
        )

    def _relevamiento_territorial(self, *, confirmar_por_email):
        return Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            tipo=Relevamiento.Tipo.TERRITORIAL,
            territorial=self.territorial,
            zona="Resistencia",
            fecha_asignada=date(2026, 6, 1),
            confirmar_por_email=confirmar_por_email,
        )

    def _formulario(self, relevamiento=None, **extra):
        datos = {
            "relevamiento": relevamiento or self.relevamiento,
            "celular": "3624123456",
            "email_contacto": "maria.gomez@correo.com",
            "datos_identificacion": {"dni": "30123456", "nombre": "MARIA LUJAN", "apellido": "GOMEZ"},
        }
        datos.update(extra)
        return Formulario.objects.create(**datos)


class DesenlacesTests(_BaseAvisoTest):
    """Un test por cada uno de los cuatro momentos de aviso."""

    def test_aprobado(self):
        formulario = self._formulario()

        self.assertTrue(enviar_aviso_resolucion(formulario, "aprobado"))

        correo = mail.outbox[0]
        self.assertEqual(correo.to, ["maria.gomez@correo.com"])
        self.assertEqual(correo.subject, "Tu inscripción fue aprobada — Becas 2026")
        html = correo.alternatives[0][0]
        for cuerpo in (correo.body, html):
            self.assertIn("fue aprobada", cuerpo)
            self.assertIn(f"Formulario Nº {formulario.numero}", cuerpo)
            self.assertIn("Becas Secundario", cuerpo)
            self.assertNotIn("lista de espera", cuerpo)

    def test_lista_espera(self):
        formulario = self._formulario()

        self.assertTrue(enviar_aviso_resolucion(formulario, "lista_espera"))

        correo = mail.outbox[0]
        self.assertEqual(correo.subject, "Tu inscripción quedó en lista de espera — Becas 2026")
        html = correo.alternatives[0][0]
        for cuerpo in (correo.body, html):
            self.assertIn("lista de espera", cuerpo)
            self.assertIn("no hay cupo disponible", cuerpo)
            # Quien cayó en lista de espera no puede leer que fue aprobado.
            self.assertNotIn("fue aprobada", cuerpo)

    def test_rechazado(self):
        formulario = self._formulario()

        self.assertTrue(enviar_aviso_resolucion(formulario, "rechazado", motivo="No adjuntó el certificado."))

        correo = mail.outbox[0]
        self.assertEqual(correo.subject, "Novedades sobre tu inscripción — Becas 2026")
        html = correo.alternatives[0][0]
        for cuerpo in (correo.body, html):
            self.assertIn("no fue aprobada", cuerpo)

    def test_promovido(self):
        formulario = self._formulario()

        self.assertTrue(enviar_aviso_resolucion(formulario, "promovido"))

        correo = mail.outbox[0]
        # Para el ciudadano es el mismo hecho que la aprobación directa.
        self.assertEqual(correo.subject, "Tu inscripción fue aprobada — Becas 2026")
        html = correo.alternatives[0][0]
        for cuerpo in (correo.body, html):
            self.assertIn("Se liberó un lugar", cuerpo)
            self.assertIn("fue aprobada", cuerpo)


class MotivoDelRechazoTests(_BaseAvisoTest):
    def test_el_motivo_textual_aparece_en_el_cuerpo(self):
        """Va tal cual lo escribió el técnico: decisión del cliente."""
        formulario = self._formulario()
        motivo = "El certificado de alumno regular está vencido, vence el 01/03/2026."

        self.assertTrue(enviar_aviso_resolucion(formulario, "rechazado", motivo=motivo))

        correo = mail.outbox[0]
        self.assertIn(motivo, correo.body)
        self.assertIn(motivo, correo.alternatives[0][0])

    def test_el_motivo_se_escapa_en_el_html(self):
        formulario = self._formulario()

        self.assertTrue(enviar_aviso_resolucion(formulario, "rechazado", motivo='Falta el <b>DNI</b> & el "CUIL"'))

        html = mail.outbox[0].alternatives[0][0]
        self.assertNotIn("<b>DNI</b>", html)
        self.assertIn("&lt;b&gt;DNI&lt;/b&gt;", html)

    def test_el_motivo_no_se_filtra_a_los_otros_desenlaces(self):
        formulario = self._formulario()

        self.assertTrue(enviar_aviso_resolucion(formulario, "aprobado", motivo="nota interna"))

        correo = mail.outbox[0]
        self.assertNotIn("nota interna", correo.body)
        self.assertNotIn("nota interna", correo.alternatives[0][0])

    def test_rechazo_sin_motivo_no_deja_el_bloque_vacio(self):
        formulario = self._formulario()

        self.assertTrue(enviar_aviso_resolucion(formulario, "rechazado"))

        correo = mail.outbox[0]
        self.assertNotIn("Motivo:", correo.body)
        self.assertNotIn("Motivo</p>", correo.alternatives[0][0])


class ToggleYDestinatarioTests(_BaseAvisoTest):
    def test_toggle_apagado_no_manda_en_publico(self):
        self.relevamiento.confirmar_por_email = False
        self.relevamiento.save(update_fields=["confirmar_por_email"])
        formulario = self._formulario()

        self.assertFalse(enviar_aviso_resolucion(formulario, "aprobado"))
        self.assertEqual(len(mail.outbox), 0)

    def test_toggle_apagado_no_manda_en_territorial(self):
        formulario = self._formulario(self._relevamiento_territorial(confirmar_por_email=False))

        self.assertFalse(enviar_aviso_resolucion(formulario, "aprobado"))
        self.assertEqual(len(mail.outbox), 0)

    def test_territorial_con_toggle_encendido_manda(self):
        """La regresión que habilita el Cambio 44: el aviso no distingue origen."""
        formulario = self._formulario(self._relevamiento_territorial(confirmar_por_email=True))

        self.assertTrue(enviar_aviso_resolucion(formulario, "aprobado"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["maria.gomez@correo.com"])

    def test_sin_email_de_contacto_no_manda(self):
        formulario = self._formulario(email_contacto="")

        self.assertFalse(enviar_aviso_resolucion(formulario, "aprobado"))
        self.assertEqual(len(mail.outbox), 0)

    def test_resultado_desconocido_no_manda(self):
        formulario = self._formulario()

        with self.assertLogs("programas.services.avisos_resolucion", level="ERROR"):
            self.assertFalse(enviar_aviso_resolucion(formulario, "dado_de_baja"))
        self.assertEqual(len(mail.outbox), 0)


class FallaDeSmtpTests(_BaseAvisoTest):
    def test_smtp_caido_devuelve_false_y_no_propaga(self):
        formulario = self._formulario()

        with patch(
            "programas.services.avisos_resolucion.EmailMultiAlternatives.send",
            side_effect=OSError("smtp caído"),
        ):
            with self.assertLogs("programas.services.avisos_resolucion", level="ERROR"):
                # Si propagara, la aprobación del técnico se caería con el correo.
                self.assertFalse(enviar_aviso_resolucion(formulario, "aprobado"))

        self.assertEqual(len(mail.outbox), 0)
        self.assertTrue(Formulario.objects.filter(pk=formulario.pk).exists())

    def test_smtp_caido_tampoco_propaga_en_el_rechazo(self):
        formulario = self._formulario()

        with patch(
            "programas.services.avisos_resolucion.EmailMultiAlternatives.send",
            side_effect=OSError("smtp caído"),
        ):
            with self.assertLogs("programas.services.avisos_resolucion", level="ERROR"):
                self.assertFalse(enviar_aviso_resolucion(formulario, "rechazado", motivo="Faltan datos."))

        self.assertEqual(len(mail.outbox), 0)


class MarcaYSaludoTests(_BaseAvisoTest):
    def test_manda_texto_y_html_de_marca(self):
        formulario = self._formulario()

        self.assertTrue(enviar_aviso_resolucion(formulario, "aprobado", domain="datanach.example"))

        correo = mail.outbox[0]
        self.assertEqual(len(correo.alternatives), 1, "falta la versión HTML")
        html, tipo = correo.alternatives[0]
        self.assertEqual(tipo, "text/html")
        # Saludo con el nombre de pila, no con el nombre completo.
        self.assertIn("Hola MARIA,", html)
        self.assertIn("Hola MARIA,", correo.body)
        for cuerpo in (html, correo.body):
            self.assertIn("30123456", cuerpo)
        # Marca del portal, no la del backoffice, y logo con URL absoluta.
        self.assertIn("Portal Ciudadano", html)
        self.assertNotIn("Backoffice", html)
        self.assertIn("https://datanach.example/static/", html)

    def test_toma_el_nombre_del_ciudadano_vinculado(self):
        """Al aprobar el legajo ya está resuelto y ``datos_identificacion`` vacío."""
        ciudadano = Ciudadano.objects.create(dni="27888999", nombre="JUAN CARLOS", apellido="PÉREZ")
        formulario = self._formulario(ciudadano=ciudadano, datos_identificacion=None)

        self.assertTrue(enviar_aviso_resolucion(formulario, "aprobado"))

        correo = mail.outbox[0]
        self.assertIn("Hola JUAN,", correo.body)
        self.assertIn("27888999", correo.body)

    def test_sin_nombre_el_saludo_no_queda_colgado(self):
        formulario = self._formulario(datos_identificacion={"dni": "30123456"})

        self.assertTrue(enviar_aviso_resolucion(formulario, "aprobado"))

        self.assertIn("Hola,", mail.outbox[0].body)
        self.assertIn("Hola,", mail.outbox[0].alternatives[0][0])
