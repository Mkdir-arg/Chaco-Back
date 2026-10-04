"""Adjuntos del ciudadano y del legajo: capacidad y dueño (SEC-10, auditoría oct-2026).

Antes de este PR, `DELETE /legajos/archivos/<id>/eliminar/` hacía **hard delete**
de cualquier `Adjunto` del sistema —`get_object_or_404(Adjunto, id=…).delete()`,
sin mirar de quién era, sin papelera y sin auditoría— para **cualquier** cuenta
de backoffice autenticada: un rol de Becas, uno de Dispositivos, el usuario
recién creado sin un solo rol. El barrido de RED-89 lo midió el 04-oct-2026:
200 `{"success": true}` y la fila dejaba de existir. Listar y subir estaban
igual de abiertos, y el archivo físico quedaba huérfano en `MEDIA_ROOT`.

Ahora: `ciudadano.ver` para listar, `ciudadano.editar` para subir y borrar, y el
dueño en la URL, así un adjunto de otro ciudadano no existe para la vista.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core import rbac
from legajos.models import Adjunto, Ciudadano, LegajoAtencion
from legajos.services import eliminar_archivo_de_objeto
from users.models import Capacidad, RolMeta


def usuario_con(*codigos, username=None):
    """Usuario de backoffice con exactamente esas capacidades (ninguna = sin rol)."""
    usuario = User.objects.create_user(username or f"u-{'-'.join(codigos) or 'sin-rol'}", password="Clave-Seg-2026x")
    if not codigos:
        return usuario
    grupo, _ = Group.objects.get_or_create(name="Rol " + "-".join(codigos))
    RolMeta.objects.get_or_create(grupo=grupo, defaults={"categoria": rbac.CATEGORIA_BACKOFFICE, "activo": True})
    ct = ContentType.objects.get_for_model(Capacidad)
    for codigo in codigos:
        grupo.permissions.add(Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct))
    usuario.groups.add(grupo)
    return usuario


def adjunto_de(instance, nombre="dni.pdf"):
    return Adjunto.objects.create(
        content_type=ContentType.objects.get_for_model(type(instance)),
        object_id=instance.id,
        archivo=SimpleUploadedFile(nombre, b"%PDF-1.4 contenido", content_type="application/pdf"),
        etiqueta=nombre,
    )


class AdjuntosRbacTests(TestCase):
    """Quién puede listar, subir y borrar adjuntos."""

    @classmethod
    def setUpTestData(cls):
        cls.mirta = Ciudadano.objects.create(dni="21333444", nombre="Mirta", apellido="Quiroga")
        cls.otro = Ciudadano.objects.create(dni="29888777", nombre="Raúl", apellido="Ponce")

    def setUp(self):
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        contexto = override_settings(MEDIA_ROOT=self.media.name)
        contexto.enable()
        self.addCleanup(contexto.disable)

    def _cliente(self, usuario):
        cliente = Client()
        cliente.force_login(usuario)
        return cliente

    def _url_borrar(self, ciudadano, adjunto):
        return reverse("legajos:eliminar_archivo_ciudadano", args=[ciudadano.id, adjunto.id])

    # ------------------------------------------------------------------ #
    # El agujero medido: borrar el documento de cualquiera, sin rol
    # ------------------------------------------------------------------ #
    def test_un_usuario_sin_rol_no_borra_un_adjunto_ajeno(self):
        adjunto = adjunto_de(self.mirta)
        cliente = self._cliente(usuario_con())

        respuesta = cliente.delete(self._url_borrar(self.mirta, adjunto))

        self.assertNotEqual(respuesta.status_code, 200)
        self.assertTrue(Adjunto.objects.filter(pk=adjunto.pk).exists())

    def test_la_ruta_sin_dueno_ya_no_existe(self):
        """`/legajos/archivos/<id>/eliminar/` borraba por id, sin dueño ni capacidad."""
        adjunto = adjunto_de(self.mirta)
        cliente = self._cliente(usuario_con())

        respuesta = cliente.delete(f"/legajos/archivos/{adjunto.id}/eliminar/")

        self.assertEqual(respuesta.status_code, 404)
        self.assertTrue(Adjunto.objects.filter(pk=adjunto.pk).exists())

    def test_sin_rol_no_lista_ni_sube(self):
        cliente = self._cliente(usuario_con())

        for url in (
            reverse("legajos:archivos_ciudadano", args=[self.mirta.id]),
            reverse("legajos:subir_archivos_ciudadano", args=[self.mirta.id]),
        ):
            with self.subTest(url=url):
                respuesta = cliente.get(url, headers={"x-requested-with": "XMLHttpRequest"})
                self.assertEqual(respuesta.status_code, 403)

    def test_solo_ver_no_alcanza_para_borrar_ni_subir(self):
        """`ciudadano.ver` lee; escribir pide `ciudadano.editar`."""
        adjunto = adjunto_de(self.mirta)
        cliente = self._cliente(usuario_con("ciudadano.ver"))

        borrado = cliente.delete(self._url_borrar(self.mirta, adjunto), headers={"x-requested-with": "XMLHttpRequest"})
        self.assertEqual(borrado.status_code, 403)
        self.assertTrue(Adjunto.objects.filter(pk=adjunto.pk).exists())

        subida = cliente.post(
            reverse("legajos:subir_archivos_ciudadano", args=[self.mirta.id]),
            {"archivo": SimpleUploadedFile("x.pdf", b"x")},
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        self.assertEqual(subida.status_code, 403)

    def test_con_ciudadano_ver_lista(self):
        adjunto_de(self.mirta)
        cliente = self._cliente(usuario_con("ciudadano.ver"))

        respuesta = cliente.get(reverse("legajos:archivos_ciudadano", args=[self.mirta.id]))

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["count"], 1)

    def test_con_ciudadano_editar_borra_el_propio(self):
        adjunto = adjunto_de(self.mirta)
        cliente = self._cliente(usuario_con("ciudadano.ver", "ciudadano.editar"))

        respuesta = cliente.delete(self._url_borrar(self.mirta, adjunto))

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.json()["success"])
        self.assertFalse(Adjunto.objects.filter(pk=adjunto.pk).exists())

    def test_el_superusuario_borra(self):
        adjunto = adjunto_de(self.mirta)
        cliente = self._cliente(User.objects.create_superuser("root-adj", "root@example.test", "x"))

        self.assertEqual(cliente.delete(self._url_borrar(self.mirta, adjunto)).status_code, 200)
        self.assertFalse(Adjunto.objects.filter(pk=adjunto.pk).exists())

    def test_el_anonimo_va_al_login(self):
        adjunto = adjunto_de(self.mirta)

        respuesta = Client().delete(self._url_borrar(self.mirta, adjunto))

        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(Adjunto.objects.filter(pk=adjunto.pk).exists())

    def test_el_ciudadano_del_portal_no_entra(self):
        """`PortalCiudadanoMiddleware`: las dos superficies son excluyentes."""
        adjunto = adjunto_de(self.mirta)
        portal = User.objects.create_user("30111444", password="Clave-Seg-2026x")
        portal.groups.add(Group.objects.create(name=rbac.GRUPO_CIUDADANO_PORTAL))

        respuesta = self._cliente(portal).delete(self._url_borrar(self.mirta, adjunto))

        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(Adjunto.objects.filter(pk=adjunto.pk).exists())


class AdjuntosAcotadosAlDuenoTests(TestCase):
    """El id solo no alcanza: el adjunto tiene que colgar del objeto de la URL."""

    @classmethod
    def setUpTestData(cls):
        cls.mirta = Ciudadano.objects.create(dni="21333555", nombre="Mirta", apellido="Quiroga")
        cls.otro = Ciudadano.objects.create(dni="29888666", nombre="Raúl", apellido="Ponce")
        cls.responsable = User.objects.create_user("responsable-legajo", password="Clave-Seg-2026x")
        cls.legajo = LegajoAtencion.objects.create(responsable=cls.responsable)

    def setUp(self):
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        contexto = override_settings(MEDIA_ROOT=self.media.name)
        contexto.enable()
        self.addCleanup(contexto.disable)
        self.cliente = Client()
        self.cliente.force_login(usuario_con("ciudadano.ver", "ciudadano.editar", username="editor-adjuntos"))

    def test_borrar_el_adjunto_de_otro_ciudadano_da_404_y_no_borra(self):
        ajeno = adjunto_de(self.otro)

        respuesta = self.cliente.delete(reverse("legajos:eliminar_archivo_ciudadano", args=[self.mirta.id, ajeno.id]))

        self.assertEqual(respuesta.status_code, 404)
        self.assertTrue(Adjunto.objects.filter(pk=ajeno.pk).exists())

    def test_borrar_por_la_ruta_de_legajo_un_adjunto_de_ciudadano_da_404(self):
        del_ciudadano = adjunto_de(self.mirta)

        respuesta = self.cliente.delete(
            reverse("legajos:eliminar_archivo_legajo", args=[self.legajo.id, del_ciudadano.id])
        )

        self.assertEqual(respuesta.status_code, 404)
        self.assertTrue(Adjunto.objects.filter(pk=del_ciudadano.pk).exists())

    def test_el_adjunto_del_legajo_se_borra_por_su_ruta(self):
        del_legajo = adjunto_de(self.legajo)

        respuesta = self.cliente.delete(
            reverse("legajos:eliminar_archivo_legajo", args=[self.legajo.id, del_legajo.id])
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Adjunto.objects.filter(pk=del_legajo.pk).exists())

    def test_el_archivo_fisico_se_borra_al_confirmar_la_transaccion(self):
        """`archivo.delete()` borra la fila pero deja el blob: quedaba huérfano."""
        adjunto = adjunto_de(self.mirta, nombre="huerfano.pdf")
        ruta = adjunto.archivo.path
        self.assertTrue(adjunto.archivo.storage.exists(adjunto.archivo.name))

        with self.captureOnCommitCallbacks(execute=True):
            self.cliente.delete(reverse("legajos:eliminar_archivo_ciudadano", args=[self.mirta.id, adjunto.id]))

        self.assertFalse(Path(ruta).exists(), "el archivo físico quedó huérfano en MEDIA_ROOT")

    def test_si_la_transaccion_se_revierte_el_archivo_sigue(self):
        """El storage no participa de la transacción.

        Borrar el blob *antes* que la fila deja, si algo revierte después, un
        `Adjunto` apuntando a un archivo que ya no existe: el documento del
        ciudadano desaparece igual, que es el daño que SEC-10 vino a evitar. Por
        eso el borrado físico va en `transaction.on_commit`.
        """
        adjunto = adjunto_de(self.mirta, nombre="sobrevive.pdf")
        ruta = adjunto.archivo.path

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            with self.assertRaises(RuntimeError), transaction.atomic():
                eliminar_archivo_de_objeto(self.mirta, adjunto.id)
                raise RuntimeError("algo falló después del borrado")

        self.assertEqual(callbacks, [], "el borrado físico se agendó para una transacción revertida")
        self.assertTrue(Adjunto.objects.filter(pk=adjunto.pk).exists())
        self.assertTrue(Path(ruta).exists(), "el archivo se borró y la fila volvió: el adjunto quedó roto")


class AdjuntosErroresTests(TestCase):
    """Los errores no publican el detalle interno (SEC-10 / A3-17)."""

    @classmethod
    def setUpTestData(cls):
        cls.mirta = Ciudadano.objects.create(dni="21333666", nombre="Mirta", apellido="Quiroga")

    def setUp(self):
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        contexto = override_settings(MEDIA_ROOT=self.media.name)
        contexto.enable()
        self.addCleanup(contexto.disable)
        self.cliente = Client()
        self.cliente.force_login(usuario_con("ciudadano.ver", "ciudadano.editar", username="editor-errores"))

    def test_un_formato_no_permitido_avisa_con_400(self):
        respuesta = self.cliente.post(
            reverse("legajos:subir_archivos_ciudadano", args=[self.mirta.id]),
            {"archivo": SimpleUploadedFile("peligro.html", b"<script>")},
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("Formato no permitido", respuesta.json()["error"])

    def test_un_error_inesperado_no_expone_el_mensaje(self):
        from unittest.mock import patch

        from legajos.views.mensajes import ERROR_GENERICO

        with patch(
            "legajos.views.contactos_api.build_ciudadano_archivos_payload",
            side_effect=RuntimeError("SELECT * FROM legajos_adjunto: connection refused"),
        ):
            respuesta = self.cliente.get(reverse("legajos:archivos_ciudadano", args=[self.mirta.id]))

        self.assertEqual(respuesta.status_code, 500)
        self.assertEqual(respuesta.json()["error"], ERROR_GENERICO)
        self.assertNotIn("connection refused", respuesta.content.decode())


class AdjuntosUiTests(TestCase):
    """La UI no ofrece lo que el guard va a rechazar (SEC-10).

    Con solo `ciudadano.ver`, «Subir archivo» y la papelera llevaban a un 403: la
    pantalla prometía una acción que la vista niega.
    """

    @classmethod
    def setUpTestData(cls):
        cls.mirta = Ciudadano.objects.create(dni="21333777", nombre="Mirta", apellido="Quiroga")

    def _html(self, usuario):
        cliente = Client()
        cliente.force_login(usuario)
        return cliente.get(reverse("legajos:ciudadano_detalle", args=[self.mirta.id])).content.decode()

    def test_con_solo_ver_no_se_ofrece_subir_ni_borrar(self):
        html = self._html(usuario_con("ciudadano.ver", username="ui-solo-ve"))

        # El botón, no la función: `abrirModalArchivos` sigue declarada en el script.
        self.assertNotIn('onclick="abrirModalArchivos()"', html)
        self.assertNotIn('id="modalArchivos"', html)
        self.assertIn("const puedeEditarArchivos = false;", html)

    def test_con_ciudadano_editar_se_ofrecen_las_dos(self):
        html = self._html(usuario_con("ciudadano.ver", "ciudadano.editar", username="ui-edita"))

        self.assertIn('onclick="abrirModalArchivos()"', html)
        self.assertIn('id="modalArchivos"', html)
        self.assertIn("const puedeEditarArchivos = true;", html)


class CampanaDeAlertasEnElNavbarTests(TestCase):
    """La campana del navbar sigue a `ciudadano.ver` (SEC-18).

    El bloque se renderizaba para todo usuario de backoffice. Con las capacidades
    puestas, a un rol de Becas o de Dispositivos el contador le contestaba un
    rebote, `response.json()` reventaba y el dropdown quedaba en «Cargando
    alertas...» para siempre; los dos links iban al inicio.
    """

    def _html(self, usuario):
        cliente = Client()
        cliente.force_login(usuario)
        return cliente.get(reverse("core:inicio")).content.decode()

    def test_un_rol_sin_ciudadano_ver_no_ve_la_campana(self):
        html = self._html(usuario_con("becas.relevamiento.ver", username="rol-de-becas"))

        self.assertNotIn('id="alertas-counter"', html)
        self.assertNotIn('id="alertas-preview"', html)
        self.assertNotIn('id="websocket-status"', html)
        # Los dos links que rebotaban a `/inicio/`. Se busca el `href` y no el texto:
        # «Dashboard de Alertas» aparece también en un comentario del CSS del navbar,
        # y `/legajos/alertas/<id>/cerrar-ajax/` en el componente de eventos críticos,
        # que renderiza una lista siempre vacía (nadie provee su contexto).
        self.assertNotIn(f'href="{reverse("legajos:alertas_dashboard")}"', html)

    def test_con_ciudadano_ver_la_campana_esta(self):
        html = self._html(usuario_con("ciudadano.ver", username="ve-ciudadanos"))

        self.assertIn('id="alertas-counter"', html)
        self.assertIn('id="alertas-preview"', html)
        self.assertIn(f'href="{reverse("legajos:alertas_dashboard")}"', html)

    def test_el_superusuario_ve_la_campana(self):
        html = self._html(User.objects.create_superuser("root-navbar", "root-n@example.test", "x"))

        self.assertIn('id="alertas-counter"', html)
