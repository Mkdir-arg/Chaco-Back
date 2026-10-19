"""Las páginas de error no heredan una conexión de MySQL muerta (Cambio 342).

En PRD (daphne/ASGI, MariaDB) Django 5.2 arma la respuesta de error con
`sync_to_async(response_for_exception, thread_sensitive=False)`: corre en un hilo del
pool que no pasó por `close_old_connections`, y si ese hilo guardaba una conexión que
MariaDB cerró por inactividad el render de `404.html`/`500.html` moría con
`OperationalError (2006, 'Server has gone away')`: el 404 terminaba en 500.

No se puede reproducir la conexión muerta de verdad en SQLite en memoria (no hay
servidor que la cierre ni hilo del pool con conexión propia), así que se simula con un
render que falla mientras nadie haya llamado a `cerrar_conexiones_viejas` en esa petición.
"""

from unittest import mock

from django.contrib.auth.models import AnonymousUser
from django.db import OperationalError, connection
from django.test import RequestFactory, TestCase, override_settings

from config import views

CLOSE = "config.views.cerrar_conexiones_viejas"


def _request():
    request = RequestFactory().get("/meta.json")
    request.user = AnonymousUser()
    return request


class HandlersCierranConexionesViejasTest(TestCase):
    def _assert_cierra_antes_de_renderizar(self, llamar, attr_render):
        orden = []
        with (
            mock.patch(CLOSE, side_effect=lambda: orden.append("close")),
            mock.patch(attr_render, side_effect=lambda *a, **k: orden.append("render") or mock.Mock()),
        ):
            llamar()
        self.assertEqual(orden[0], "close")
        self.assertIn("render", orden)
        self.assertEqual(orden[-1], "close")  # y otra vez en el finally

    def test_404_cierra_antes_de_renderizar(self):
        self._assert_cierra_antes_de_renderizar(
            lambda: views.page_not_found(_request(), Exception("x")), "django.views.defaults.loader.get_template"
        )

    def test_403_cierra_antes_de_renderizar(self):
        self._assert_cierra_antes_de_renderizar(
            lambda: views.permission_denied(_request(), Exception("x")), "django.views.defaults.loader.get_template"
        )

    def test_400_cierra_antes_de_renderizar(self):
        self._assert_cierra_antes_de_renderizar(
            lambda: views.bad_request(_request(), Exception("x")), "django.views.defaults.loader.get_template"
        )

    def test_500_cierra_antes_de_renderizar(self):
        self._assert_cierra_antes_de_renderizar(lambda: views.server_error(_request()), "config.views.render")

    def test_404_real_sigue_respondiendo_con_su_template(self):
        with mock.patch(CLOSE) as cerrar:
            r = self.client.get("/meta.json")
        self.assertEqual(r.status_code, 404)
        self.assertTemplateUsed(r, "404.html")
        self.assertGreaterEqual(cerrar.call_count, 2)

    def test_500_responde_con_su_template_y_status(self):
        with mock.patch(CLOSE) as cerrar:
            r = views.server_error(_request())
        self.assertEqual(r.status_code, 500)
        self.assertIn(b"<html", r.content.lower())
        self.assertEqual(cerrar.call_count, 2)

    def test_conexion_muerta_el_404_no_termina_en_500(self):
        """Patrón real: el render falla con 2006 mientras la conexión no se haya cerrado."""
        viva = {"ok": False}
        original = views.defaults.page_not_found

        def render_con_conexion(request, exception, template_name="404.html"):
            if not viva["ok"]:
                raise OperationalError(2006, "Server has gone away")
            return original(request, exception, template_name=template_name)

        def cerrar():
            viva["ok"] = True

        with (
            mock.patch(CLOSE, side_effect=cerrar),
            mock.patch("config.views.defaults.page_not_found", render_con_conexion),
        ):
            r = views.page_not_found(_request(), Exception("x"))
        self.assertEqual(r.status_code, 404)


class ServerErrorSinBaseTest(TestCase):
    def test_render_con_operational_error_devuelve_500_minimo(self):
        with mock.patch("config.views.render", side_effect=OperationalError(2006, "Server has gone away")):
            r = views.server_error(_request())
        self.assertEqual(r.status_code, 500)
        self.assertIn("Error del servidor", r.content.decode())


class RequestNormalNoTocaConexionesTest(TestCase):
    def test_vista_que_no_falla_no_ejecuta_los_handlers(self):
        with mock.patch(CLOSE) as cerrar:
            self.client.get("/health/")
        cerrar.assert_not_called()


@override_settings(DEBUG=False)
class UrlsRegistranLosHandlersTest(TestCase):
    def test_handlers_registrados_y_csrf_intacto(self):
        from django.conf import settings

        from config import urls

        self.assertEqual(urls.handler400, "config.views.bad_request")
        self.assertEqual(urls.handler403, "config.views.permission_denied")
        self.assertEqual(urls.handler404, "config.views.page_not_found")
        self.assertEqual(urls.handler500, "config.views.server_error")
        self.assertEqual(settings.CSRF_FAILURE_VIEW, "config.views.csrf_failure")


class DentroDeUnAtomicNoCierraTest(TestCase):
    """`TestCase` ya corre dentro de un atomic: el handler no puede cerrar esa conexión."""

    def test_dentro_de_un_atomic_no_se_cierra_la_conexion(self):
        self.assertTrue(connection.in_atomic_block)
        with mock.patch.object(connection, "close_if_unusable_or_obsolete") as cerrar:
            r = views.page_not_found(_request(), Exception("x"))
        self.assertEqual(r.status_code, 404)
        cerrar.assert_not_called()

    def test_fuera_de_un_atomic_si_se_evalua_la_conexion(self):
        with (
            mock.patch.object(connection, "in_atomic_block", False),
            mock.patch.object(connection, "close_if_unusable_or_obsolete") as cerrar,
        ):
            views.cerrar_conexiones_viejas()
        cerrar.assert_called_once()
