"""El traceback de un 500 llega a stdout (OPS-03).

Es el PoC `A804LoggingTests` de la auditoría dado vuelta. Aquel solo imprimía la
configuración; acá se afirma lo que hay que conservar:

- la cadena de `django.request` **alcanza un `StreamHandler`**, que es lo que recogen
  `docker compose logs` y `kubectl logs`. Con `propagate: False` y handlers solo de
  archivo —lo que había— el traceback de cada 500 moría en `logs/<fecha>/error.log`, que
  en Kubernetes es efímero;
- los archivos se escriben **solo** con `LOG_TO_FILES=True`, y con retención.

Ninguno toca el disco salvo el de la purga, que trabaja sobre un directorio temporal.
"""

import logging
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.http import HttpResponse
from django.test import Client, SimpleTestCase, TestCase
from django.urls import path

from config.urls import urlpatterns as _urls_del_proyecto
from core.logging_config import construir_logging, purgar_logs_viejos


def _cadena(nombre):
    """Los loggers desde `nombre` hasta root, respetando `propagate`."""
    actual = logging.getLogger(nombre)
    while actual:
        yield actual
        if not actual.propagate:
            return
        actual = actual.parent


def _alcanza_un_stream_handler(nombre):
    return any(
        isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler)
        for logger in _cadena(nombre)
        for handler in logger.handlers
    )


class CadenaHastaStdoutTests(SimpleTestCase):
    """El contrato que mide la ficha, sobre la configuración viva del proceso."""

    def test_django_request_llega_a_un_stream_handler(self):
        self.assertTrue(
            _alcanza_un_stream_handler("django.request"),
            "el traceback de los 500 no llega a stdout: `kubectl logs` no lo va a mostrar",
        )

    def test_core_requests_llega_a_un_stream_handler(self):
        self.assertTrue(_alcanza_un_stream_handler("core.requests"))

    def test_django_request_propaga(self):
        """Con `propagate: False` el logger se desconecta de root y vuelve el bug."""
        self.assertTrue(logging.getLogger("django.request").propagate)

    def test_la_configuracion_declarada_no_le_pone_handlers_de_archivo(self):
        declarado = settings.LOGGING["loggers"]["django.request"]

        self.assertEqual(declarado["handlers"], [])
        self.assertTrue(declarado["propagate"])


def _vista_que_revienta(request):
    raise RuntimeError("500 de prueba")


def _500_pelado(request):
    """La `500.html` del proyecto espera `user` en el contexto, que el handler no le da.

    Lo que acá se mide es el **registro**, no la plantilla: con el handler de Django la
    prueba fallaría por un `VariableDoesNotExist` que no tiene nada que ver con OPS-03.
    """
    return HttpResponse("500", status=500)


handler500 = f"{__name__}._500_pelado"

# Las URLs de verdad más la que revienta: así el URLconf de la prueba no cambia nada más
# que la ruta nueva.
urlpatterns = [path("revienta/", _vista_que_revienta), *_urls_del_proyecto]


class TracebackDeUn500Tests(TestCase):
    """Un 500 de verdad tiene que emitir un ERROR en `django.request`."""

    def test_el_500_emite_el_traceback(self):
        cliente = Client(raise_request_exception=False)

        with self.settings(ROOT_URLCONF=__name__):
            with self.assertLogs("django.request", "ERROR") as registro:
                respuesta = cliente.get("/revienta/")

        self.assertEqual(respuesta.status_code, 500)
        self.assertIn("RuntimeError", "\n".join(registro.output), "el traceback tiene que estar en el registro")


class ArchivosOpcionalesTests(SimpleTestCase):
    """`LOG_TO_FILES` apagado = nada en disco; encendido = los cinco archivos."""

    def _config(self, log_to_files):
        return construir_logging(log_dir=Path("/tmp/logs"), debug=False, log_to_files=log_to_files)

    def test_sin_la_variable_no_hay_handlers_de_archivo(self):
        config = self._config(False)

        self.assertEqual(list(config["handlers"]), ["console"])
        self.assertEqual(config["root"]["handlers"], ["console"])

    def test_con_la_variable_vuelven_los_cinco_archivos(self):
        config = self._config(True)

        self.assertEqual(len(config["handlers"]), 6, "console + los cinco de archivo")
        self.assertIn("error_file", config["root"]["handlers"])

    def test_stdout_esta_siempre(self):
        for log_to_files in (True, False):
            with self.subTest(log_to_files=log_to_files):
                self.assertIn("console", self._config(log_to_files)["root"]["handlers"])


class RetencionTests(SimpleTestCase):
    """En icore `./logs` está montado desde el host y crecía sin techo."""

    def test_borra_las_carpetas_mas_viejas_que_la_retencion(self):
        with TemporaryDirectory() as temporal:
            raiz = Path(temporal)
            vieja = raiz / (date.today() - timedelta(days=30)).isoformat()
            nueva = raiz / date.today().isoformat()
            ajena = raiz / "no-es-una-fecha"
            for carpeta in (vieja, nueva, ajena):
                carpeta.mkdir()
                (carpeta / "info.log").write_text("x", encoding="utf-8")

            borradas = purgar_logs_viejos(raiz, 14)

            self.assertEqual(borradas, [vieja])
            self.assertTrue(nueva.is_dir())
            self.assertTrue(ajena.is_dir(), "lo que no escribió el handler no se toca")

    def test_retencion_cero_no_borra_nada(self):
        with TemporaryDirectory() as temporal:
            raiz = Path(temporal)
            (raiz / (date.today() - timedelta(days=99)).isoformat()).mkdir()

            self.assertEqual(purgar_logs_viejos(raiz, 0), [])

    def test_un_directorio_que_no_existe_no_rompe(self):
        self.assertEqual(purgar_logs_viejos(Path("/no/existe/este/directorio"), 14), [])
