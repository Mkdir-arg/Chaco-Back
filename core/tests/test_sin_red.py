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

import requests
from django.test import SimpleTestCase
from django.test.runner import DiscoverRunner

from core.tests.runner import RedProhibidaEnTests, RunnerSinRed


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
