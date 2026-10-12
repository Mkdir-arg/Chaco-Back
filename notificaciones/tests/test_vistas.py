"""Pantallas y acciones de las campañas: permisos, flujos y render (RF-007-01 a RF-007-19)."""

from unittest.mock import patch

from django.core import mail
from django.test import override_settings
from django.urls import reverse

from notificaciones.models import Campana, Descartado, Destinatario
from notificaciones.services import envio
from notificaciones.tests.utils import TODAS, ConMediaTemporal, crear_campana, html, usuario_con, xlsx
from notificaciones.views.campanas import CSP_VISTA_PREVIA, PRUEBAS_POR_HORA


def _sincronico(campana, **_kwargs):
    """``lanzar`` sin hilo: corre el envío en el mismo request."""
    envio.correr(Campana.objects.get(pk=campana.pk))


def url(nombre, *args):
    return reverse(f"notificaciones:{nombre}", args=args)


@override_settings(NOTIF_PAUSA_SEG=0)
class PermisosTests(ConMediaTemporal):
    def setUp(self):
        super().setUp()
        self.campana = crear_campana()

    def test_sin_ver_las_pantallas_redirigen(self):
        self.client.force_login(usuario_con(username="nadie"))
        for destino in (
            url("campanas"),
            url("campana_detalle", self.campana.pk),
            url("campana_vista_previa", self.campana.pk),
        ):
            with self.subTest(destino=destino):
                respuesta = self.client.get(destino)
                self.assertEqual(respuesta.status_code, 302)
                self.assertEqual(respuesta["Location"], reverse("core:inicio"))

    def test_solo_ver_mira_pero_no_gestiona_ni_envia(self):
        self.client.force_login(usuario_con("notificacion.ver", username="ve"))
        self.assertEqual(self.client.get(url("campanas")).status_code, 200)
        detalle = self.client.get(url("campana_detalle", self.campana.pk))
        self.assertEqual(detalle.status_code, 200)
        contenido = detalle.content.decode()
        self.assertNotIn(url("campana_enviar", self.campana.pk), contenido)
        self.assertNotIn(url("campana_editar", self.campana.pk), contenido)
        self.assertNotIn(url("campana_prueba", self.campana.pk), contenido)
        self.assertEqual(self.client.get(url("campana_crear")).status_code, 302)
        self.assertEqual(self.client.get(url("campana_editar", self.campana.pk)).status_code, 302)

    def test_post_directo_sin_capacidad_responde_403(self):
        self.client.force_login(usuario_con("notificacion.ver", username="ve"))
        for nombre in (
            "campana_enviar",
            "campana_detener",
            "campana_reanudar",
            "campana_eliminar",
            "campana_duplicar",
            "campana_prueba",
        ):
            with self.subTest(accion=nombre):
                self.assertEqual(self.client.post(url(nombre, self.campana.pk)).status_code, 403)
        self.campana.refresh_from_db()
        self.assertEqual(self.campana.estado, Campana.Estado.A_ENVIAR)

    def test_gestionar_no_alcanza_para_enviar(self):
        self.client.force_login(usuario_con("notificacion.ver", "notificacion.gestionar", username="gestiona"))
        contenido = self.client.get(url("campana_detalle", self.campana.pk)).content.decode()
        self.assertIn(url("campana_editar", self.campana.pk), contenido)
        self.assertNotIn(url("campana_enviar", self.campana.pk), contenido)
        self.assertEqual(self.client.post(url("campana_enviar", self.campana.pk)).status_code, 403)

    def test_enviar_sin_gestionar_ve_el_boton_enviar(self):
        self.client.force_login(usuario_con("notificacion.ver", "notificacion.enviar", username="envia"))
        contenido = self.client.get(url("campana_detalle", self.campana.pk)).content.decode()
        self.assertIn(url("campana_enviar", self.campana.pk), contenido)
        self.assertNotIn(url("campana_editar", self.campana.pk), contenido)


@override_settings(NOTIF_PAUSA_SEG=0, EMAIL_ASUNTO_PREFIJO="[QA] ")
class FlujoTests(ConMediaTemporal):
    def setUp(self):
        super().setUp()
        self.usuario = usuario_con(*TODAS, username="comunicaciones", email="romina@ejemplo.com")
        self.client.force_login(self.usuario)

    def _post_alta(self, filas, cuerpo="<p>Hola</p>", **datos):
        return self.client.post(
            url("campana_crear"),
            {
                "nombre": "Apertura",
                "asunto": "Ya podés inscribirte",
                "archivo_excel": xlsx(filas),
                "archivo_html": html(cuerpo),
                **datos,
            },
        )

    def test_alta_lee_el_excel_y_redirige_a_la_previsualizacion(self):
        filas = [
            "email",
            "a@x.com",
            "b@x.com",
            "malo",
            "c@x.com",
            "A@x.com",
            "d@x.com",
            "e@x.com",
            "f@x.com",
            "g@",
            "g@x.com",
        ]
        respuesta = self._post_alta(filas)
        campana = Campana.objects.get()
        self.assertRedirects(respuesta, url("campana_detalle", campana.pk), fetch_redirect_response=False)
        self.assertEqual(campana.estado, Campana.Estado.A_ENVIAR)
        self.assertEqual((campana.total, campana.invalidos, campana.duplicados, campana.leidas), (7, 2, 1, 10))
        self.assertEqual(campana.destinatarios.count(), 7)
        self.assertEqual(campana.descartados.filter(motivo=Descartado.Motivo.DUPLICADO).count(), 1)
        self.assertEqual(campana.creada_por, self.usuario)
        self.assertTrue(campana.archivo_excel.name.startswith("notificaciones/excel/"))
        self.assertEqual(campana.nombre_excel, "lista.xlsx")

        detalle = self.client.get(url("campana_detalle", campana.pk)).content.decode()
        self.assertIn("[QA] Ya podés inscribirte", detalle)
        self.assertIn("a@x.com", detalle)

    def test_alta_sin_correos_validos_no_crea_y_muestra_el_error_en_el_campo(self):
        respuesta = self._post_alta(["email", "nada"])
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Campana.objects.exists())
        self.assertIn("archivo_excel", respuesta.context["form"].errors)

    def test_alta_con_mas_de_5000_no_crea(self):
        respuesta = self._post_alta(["email", *[f"p{i}@x.com" for i in range(5001)]])
        self.assertFalse(Campana.objects.exists())
        self.assertIn("5.000", " ".join(respuesta.context["form"].errors["archivo_excel"]))

    def test_vista_previa_va_aparte_con_csp_y_sin_script(self):
        self._post_alta(["email", "a@x.com"], cuerpo="<p>Hola</p><script>alert('x')</script>")
        campana = Campana.objects.get()
        detalle = self.client.get(url("campana_detalle", campana.pk)).content.decode()
        self.assertIn(f'<iframe sandbox src="{url("campana_vista_previa", campana.pk)}"', detalle)
        self.assertNotIn("alert('x')", detalle)

        previa = self.client.get(url("campana_vista_previa", campana.pk))
        self.assertEqual(previa.status_code, 200)
        self.assertEqual(previa["Content-Security-Policy"], CSP_VISTA_PREVIA)
        self.assertEqual(previa["X-Frame-Options"], "SAMEORIGIN")
        self.assertIn("Hola", previa.content.decode())
        self.assertNotIn("<script", previa.content.decode())

    def test_editar_reemplaza_el_excel_y_recalcula(self):
        campana = crear_campana(emails=["a@x.com"])
        respuesta = self.client.post(
            url("campana_editar", campana.pk),
            {
                "nombre": "Nuevo nombre",
                "asunto": "Nuevo asunto",
                "archivo_excel": xlsx(["email", "b@x.com", "c@x.com"]),
            },
        )
        self.assertRedirects(respuesta, url("campana_detalle", campana.pk), fetch_redirect_response=False)
        campana.refresh_from_db()
        self.assertEqual(campana.nombre, "Nuevo nombre")
        self.assertEqual(sorted(campana.destinatarios.values_list("email", flat=True)), ["b@x.com", "c@x.com"])
        self.assertEqual(campana.total, 2)

    def test_editar_sin_archivos_conserva_lista_y_html(self):
        campana = crear_campana(emails=["a@x.com"])
        html_antes = campana.html_sanitizado
        self.client.post(url("campana_editar", campana.pk), {"nombre": "Otro", "asunto": "Otro"})
        campana.refresh_from_db()
        self.assertEqual(campana.html_sanitizado, html_antes)
        self.assertEqual(campana.total, 1)

    def test_enviada_no_se_edita_ni_se_elimina(self):
        campana = crear_campana()
        Campana.objects.filter(pk=campana.pk).update(estado=Campana.Estado.ENVIADA)
        self.assertRedirects(
            self.client.get(url("campana_editar", campana.pk)),
            url("campana_detalle", campana.pk),
            fetch_redirect_response=False,
        )
        self.client.post(url("campana_eliminar", campana.pk))
        self.assertTrue(Campana.objects.filter(pk=campana.pk).exists())
        detalle = self.client.get(url("campana_detalle", campana.pk)).content.decode()
        self.assertNotIn(url("campana_editar", campana.pk), detalle)
        self.assertNotIn(url("campana_eliminar", campana.pk), detalle)

    def test_eliminar_en_a_enviar_borra_todo(self):
        campana = crear_campana()
        respuesta = self.client.post(url("campana_eliminar", campana.pk))
        self.assertRedirects(respuesta, url("campanas"), fetch_redirect_response=False)
        self.assertFalse(Campana.objects.exists())
        self.assertFalse(Destinatario.objects.exists())

    def test_duplicar_una_enviada(self):
        original = crear_campana(emails=["a@x.com", "b@x.com", "malo"], nombre="Original", asunto="Asunto X")
        Campana.objects.filter(pk=original.pk).update(estado=Campana.Estado.ENVIADA)
        respuesta = self.client.post(url("campana_duplicar", original.pk))
        copia = Campana.objects.exclude(pk=original.pk).get()
        self.assertRedirects(respuesta, url("campana_editar", copia.pk), fetch_redirect_response=False)
        self.assertEqual(copia.nombre, "Copia de Original")
        self.assertEqual(copia.asunto, "Asunto X")
        self.assertEqual(copia.estado, Campana.Estado.A_ENVIAR)
        self.assertEqual((copia.total, copia.invalidos), (2, 1))
        self.assertEqual(copia.html_sanitizado, original.html_sanitizado)
        self.assertNotEqual(copia.archivo_excel.name, original.archivo_excel.name)
        original.refresh_from_db()
        self.assertEqual(original.estado, Campana.Estado.ENVIADA)
        self.assertEqual(original.nombre, "Original")

    def test_enviar_pasa_a_enviando_y_manda_uno_por_destinatario(self):
        campana = crear_campana(emails=["a@x.com", "b@x.com"])
        with patch("notificaciones.views.campanas.envio.lanzar", side_effect=_sincronico) as lanzar:
            respuesta = self.client.post(url("campana_enviar", campana.pk))
        lanzar.assert_called_once()
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(len(mail.outbox), 2)
        self.assertTrue(all(len(m.to) == 1 for m in mail.outbox))
        campana.refresh_from_db()
        self.assertEqual(campana.estado, Campana.Estado.ENVIADA)
        self.assertEqual(campana.enviada_por, self.usuario)

    def test_enviar_dos_veces_no_lanza_dos_hilos(self):
        campana = crear_campana()
        with patch("notificaciones.views.campanas.envio.lanzar") as lanzar:
            self.client.post(url("campana_enviar", campana.pk))
            self.client.post(url("campana_enviar", campana.pk))
        lanzar.assert_called_once()

    def test_prueba_por_el_popup(self):
        campana = crear_campana(asunto="Ya podés inscribirte")
        respuesta = self.client.post(
            url("campana_prueba", campana.pk), {"email": "prueba@gmail.com"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["ok"], True)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["prueba@gmail.com"])
        self.assertEqual(mail.outbox[0].subject, "[QA] [PRUEBA] Ya podés inscribirte")
        campana.refresh_from_db()
        self.assertEqual(campana.estado, Campana.Estado.A_ENVIAR)

    def test_prueba_con_correo_invalido_devuelve_el_error_del_campo(self):
        campana = crear_campana()
        respuesta = self.client.post(url("campana_prueba", campana.pk), {"email": "no-es-correo"})
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("email", respuesta.json()["errors"])
        self.assertEqual(mail.outbox, [])

    def test_prueba_tiene_limite_por_hora(self):
        campana = crear_campana()
        for _ in range(PRUEBAS_POR_HORA):
            self.assertEqual(
                self.client.post(url("campana_prueba", campana.pk), {"email": "p@gmail.com"}).status_code, 200
            )
        respuesta = self.client.post(url("campana_prueba", campana.pk), {"email": "p@gmail.com"})
        self.assertEqual(respuesta.status_code, 429)
        self.assertEqual(len(mail.outbox), PRUEBAS_POR_HORA)

    def test_exportar_y_plantilla(self):
        campana = crear_campana()
        resultado = self.client.get(url("campana_exportar", campana.pk))
        self.assertEqual(resultado.status_code, 200)
        self.assertIn("attachment;", resultado["Content-Disposition"])
        plantilla = self.client.get(url("plantilla_excel"))
        self.assertEqual(plantilla.status_code, 200)
        self.assertTrue(plantilla.content.startswith(b"PK"))


@override_settings(NOTIF_PAUSA_SEG=0)
class RenderTests(ConMediaTemporal):
    """Las pantallas renderizan en todos los estados (el template no rompe con datos reales)."""

    def setUp(self):
        super().setUp()
        self.client.force_login(usuario_con(*TODAS, username="todo"))

    def test_listado_vacio_y_con_datos(self):
        self.assertContains(self.client.get(url("campanas")), "Todavía no hay campañas")
        crear_campana(nombre="Campaña uno")
        respuesta = self.client.get(url("campanas"))
        self.assertContains(respuesta, "Campaña uno")
        self.assertContains(respuesta, "A enviar")
        filtrada = self.client.get(url("campanas"), {"estado": "ENVIADA"})
        self.assertContains(filtrada, "Ninguna campaña coincide con los filtros")

    def test_listado_y_detalle_no_crecen_con_las_filas(self):
        """Las consultas no dependen de cuántas campañas o destinatarios hay (sin N+1)."""
        creadora = usuario_con("notificacion.gestionar", username="creadora")
        chica = crear_campana(nombre="Una", usuario=creadora, emails=["a@x.com"])
        self._consultas(url("campanas"))  # calienta sesión y caches del shell
        con_una = self._consultas(url("campanas"))
        detalle_chico = self._consultas(url("campana_detalle", chica.pk))
        for i in range(4):
            crear_campana(nombre=f"Otra {i}", usuario=creadora, emails=[f"x{i}@x.com", f"y{i}@x.com"])
        grande = crear_campana(nombre="Grande", usuario=creadora, emails=[f"p{i}@x.com" for i in range(30)])
        self.assertEqual(self._consultas(url("campanas")), con_una)
        self.assertEqual(self._consultas(url("campana_detalle", grande.pk)), detalle_chico)

    def _consultas(self, destino):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as capturadas:
            self.assertEqual(self.client.get(destino).status_code, 200)
        return len(capturadas)

    def test_formulario_de_alta(self):
        respuesta = self.client.get(url("campana_crear"))
        self.assertContains(respuesta, "Nueva campaña")
        self.assertContains(respuesta, url("plantilla_excel"))
        self.assertContains(respuesta, 'enctype="multipart/form-data"')

    def test_detalle_en_cada_estado(self):
        campana = crear_campana(emails=["a@x.com", "b@x.com"])
        for estado in Campana.Estado.values:
            with self.subTest(estado=estado):
                Campana.objects.filter(pk=campana.pk).update(estado=estado)
                respuesta = self.client.get(url("campana_detalle", campana.pk))
                self.assertEqual(respuesta.status_code, 200)

    def test_detalle_interrumpido_ofrece_reanudar(self):
        from datetime import timedelta

        from django.utils import timezone

        campana = crear_campana()
        envio.iniciar_envio(campana, usuario=None)
        Campana.objects.filter(pk=campana.pk).update(latido=timezone.now() - timedelta(minutes=6))
        respuesta = self.client.get(url("campana_detalle", campana.pk))
        self.assertContains(respuesta, "El envío se interrumpió")
        self.assertContains(respuesta, url("campana_reanudar", campana.pk))
        self.assertContains(respuesta, url("campana_detener", campana.pk))
