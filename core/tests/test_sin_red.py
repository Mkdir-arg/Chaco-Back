"""La suite no sale a internet (SIIS-09, ronda 2).

Un test que parchea el lugar equivocado no falla solo: sale a la red de verdad,
tarda lo que tarde el DNS y después afirma algo que nunca se ejercitó. Pasó
cuando los clientes de SIIS y de Base de Personas cambiaron de ``requests.post``
a una ``Session`` de módulo y un test de seguridad del portal siguió parcheando
``programas.services.personas.requests.get``: el mock quedaba en cero llamadas y
la regresión que cuidaba pasaba por accidente.

La guarda vive en ``core.tests.runner.RunnerSinRed`` (``TEST_RUNNER``). Estos
tests comprueban que está armada: si alguien saca el runner de los settings,
estos dos se ponen en rojo y dicen por qué.
"""

import http.client
import urllib.error
import urllib.request

import requests
from django.test import SimpleTestCase
from django.test.runner import DiscoverRunner, ParallelTestSuite

from core.tests.runner import RedProhibidaEnTests, RunnerSinRed, SuiteParalelaSinRed


class SinRedEnLosTestsTests(SimpleTestCase):
    def test_una_llamada_sin_mock_falla_en_vez_de_salir_a_internet(self):
        with self.assertRaises(RedProhibidaEnTests) as capturado:
            requests.get("https://personas.example/personas/consulta/?dni=30111222", timeout=1)

        mensaje = str(capturado.exception)
        self.assertIn("https://personas.example", mensaje)
        # El mensaje termina en la salida del CI: el documento consultado no va.
        self.assertNotIn("30111222", mensaje)

    def test_una_sesion_propia_tampoco_sale(self):
        """El corte es en ``HTTPAdapter.send``: cubre las sesiones de módulo."""
        from core.integraciones import sesion_http

        with self.assertRaises(RedProhibidaEnTests):
            sesion_http().post("https://siis.example/api/v1/auth/token", json={}, timeout=1)

    def test_el_runner_configurado_es_el_que_corta(self):
        from django.conf import settings

        self.assertEqual(settings.TEST_RUNNER, "core.tests.runner.RunnerSinRed")
        self.assertTrue(issubclass(RunnerSinRed, DiscoverRunner))

    def test_la_guarda_sobrevive_a_un_patch_stopall(self):
        """Trece tests de la suite usan ``addCleanup(patch.stopall)``.

        Si la guarda se instalara con ``patch(...).start()``, el primero de ellos
        la apagaría y de ahí en adelante la suite volvería a salir a la red en
        silencio. Por eso el runner asigna el método en vez de parchearlo.
        """
        from unittest.mock import patch

        patch("programas.services.siis.TOKEN_CACHE_KEY", "x").start()
        patch.stopall()

        with self.assertRaises(RedProhibidaEnTests):
            requests.get("https://personas.example/", timeout=1)


class ClientesQueNoSonRequestsTests(SimpleTestCase):
    """La docstring del runner promete «ningún test abre HTTP»; era cierto solo
    para ``requests``. ``urllib.request`` y ``http.client`` llegaban a la red sin
    pasar por ``HTTPAdapter.send`` y salían de verdad."""

    def test_urllib_request_tampoco_sale(self):
        with self.assertRaises((RedProhibidaEnTests, urllib.error.URLError)) as capturado:
            urllib.request.urlopen("http://personas.example/consulta?dni=30111222", timeout=1)

        # ``urlopen`` envuelve lo que levante el transporte en ``URLError``.
        error = capturado.exception
        original = getattr(error, "reason", error)
        self.assertIsInstance(original, RedProhibidaEnTests)
        self.assertNotIn("30111222", str(original))

    def test_http_client_tampoco_sale(self):
        conexion = http.client.HTTPSConnection("siis.example", timeout=1)
        with self.assertRaises(RedProhibidaEnTests) as capturado:
            conexion.request("GET", "/api/v1/auth/catalogos/provincias")

        self.assertIn("siis.example", str(capturado.exception))


class GuardaEnLosWorkersParalelosTests(SimpleTestCase):
    """Con ``--parallel`` y *spawn* (el default en Windows), el worker no hereda
    el parche del proceso padre: Django llama al ``setup_test_environment`` del
    módulo, no al método del runner. Sin esto, ``manage.py test --parallel``
    corría con la red abierta y la guarda valía solo para el padre."""

    def test_el_runner_usa_una_suite_paralela_propia(self):
        self.assertIs(RunnerSinRed.parallel_test_suite, SuiteParalelaSinRed)
        self.assertTrue(issubclass(SuiteParalelaSinRed, ParallelTestSuite))
        self.assertIsNot(SuiteParalelaSinRed.init_worker, ParallelTestSuite.init_worker)

    def test_el_init_worker_instala_la_guarda_despues_del_de_django(self):
        """Se ejercita el wrapper con el ``_init_worker`` de Django anulado: lo
        que se mira es que la guarda quede puesta, no lo que hace Django."""
        from unittest.mock import patch

        from core.tests import runner as runner_mod

        original = http.client.HTTPConnection.connect
        try:
            http.client.HTTPConnection.connect = original  # estado conocido
            with patch.object(runner_mod, "_init_worker") as init_django:
                runner_mod._init_worker_sin_red("contador")

            init_django.assert_called_once_with("contador")
            self.assertIs(http.client.HTTPConnection.connect, runner_mod._bloquear_conexion)
            self.assertIs(requests.adapters.HTTPAdapter.send, runner_mod._bloquear)
        finally:
            http.client.HTTPConnection.connect = runner_mod._bloquear_conexion

    def test_el_init_worker_se_puede_picklear(self):
        """``multiprocessing`` lo manda al pool por nombre: si no es un objeto de
        módulo, ``--parallel`` muere con un ``PicklingError`` al arrancar."""
        import pickle

        from core.tests import runner as runner_mod

        self.assertIs(pickle.loads(pickle.dumps(runner_mod._init_worker_sin_red)), runner_mod._init_worker_sin_red)
