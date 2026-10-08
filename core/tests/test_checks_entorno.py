"""System checks del entorno de integraciones (RED-61).

De los ~90 ``os.getenv`` de ``settings.py`` el único validado era
``DJANGO_SECRET_KEY``. ``SIIS_API_URL`` caía a un default que apunta al SIIS de
**desarrollo**, que responde 200: si en producción la variable falta o cambia de
nombre, el sistema arranca igual y las altas se dan por informadas sin que el
organismo reciba nada, en una integración **sin baja**.

El check corre con ``manage.py check --deploy`` (el CI, y la etapa ``verify`` de
ECOM cuando exista): no frena el arranque del contenedor.
"""

import os
from unittest.mock import patch

from django.core.checks import Error
from django.core.checks import Warning as CheckWarning
from django.core.checks.registry import registry
from django.test import SimpleTestCase, override_settings

from core.checks import entorno_de_integraciones

SIIS_PRD = "https://siisapi.chaco.gob.ar"
SIIS_DEV = "https://siisapi.ecomdev.ar"


def _en_produccion(valor="1"):
    return patch.dict(os.environ, {"DATANACH_ES_PRODUCCION": valor})


def _sin_la_variable():
    entorno = {k: v for k, v in os.environ.items() if k != "DATANACH_ES_PRODUCCION"}
    return patch.dict(os.environ, entorno, clear=True)


# Las claves de reCAPTCHA se declaran a nivel de clase porque, vacías, disparan
# el aviso de SIIS-21 (`core.W003`) y ensuciarían la lista de todos los demás
# casos. Cada test que mira ese aviso las pisa.
@override_settings(
    DEBUG=False,
    RENAPER_TEST_MODE=False,
    RECAPTCHA_SITE_KEY="sitio-de-prueba",
    RECAPTCHA_SECRET_KEY="secreto-de-prueba",
)
class ChecksDeEntornoTests(SimpleTestCase):
    def _correr(self):
        return entorno_de_integraciones(app_configs=None)

    # ── SIIS_API_URL ────────────────────────────────────────────────────────
    @override_settings(SIIS_API_URL="")
    def test_siis_vacio_es_error(self):
        with _sin_la_variable():
            mensajes = self._correr()
        self.assertEqual([m.id for m in mensajes], ["core.E001"])
        self.assertIsInstance(mensajes[0], Error)

    @override_settings(SIIS_API_URL=SIIS_DEV)
    def test_siis_de_desarrollo_en_produccion_es_error(self):
        with _en_produccion():
            mensajes = self._correr()
        self.assertEqual([m.id for m in mensajes], ["core.E002"])
        self.assertIsInstance(mensajes[0], Error)

    @override_settings(SIIS_API_URL=SIIS_DEV)
    def test_siis_de_desarrollo_fuera_de_produccion_no_es_error(self):
        """QA (el testing de ECOM) usa el SIIS de desarrollo legítimamente.

        Por eso el disparador es ``DATANACH_ES_PRODUCCION``, una variable
        explícita que ECOM setea solo en PRD, y no ``settings.ENVIRONMENT``: QA
        e icore valen ``prd``.
        """
        with _sin_la_variable():
            self.assertEqual(self._correr(), [])
        for valor in ("", "0", "False", "no"):
            with self.subTest(DATANACH_ES_PRODUCCION=valor), _en_produccion(valor):
                self.assertEqual(self._correr(), [])

    @override_settings(SIIS_API_URL=SIIS_PRD)
    def test_siis_de_produccion_en_produccion_no_dice_nada(self):
        with _en_produccion():
            self.assertEqual(self._correr(), [])

    @override_settings(SIIS_API_URL="https://siisapi.ecomdev.ar.atacante.com")
    def test_el_host_se_compara_por_dominio_y_no_por_substring(self):
        """``...ecomdev.ar.atacante.com`` no es el SIIS de desarrollo."""
        with _en_produccion():
            self.assertEqual([m.id for m in self._correr()], [])

    @override_settings(SIIS_API_URL="https://OTRO.EcomDev.AR/api")
    def test_el_subdominio_de_desarrollo_se_detecta_sin_importar_mayusculas(self):
        with _en_produccion():
            self.assertEqual([m.id for m in self._correr()], ["core.E002"])

    @override_settings(DEBUG=True, SIIS_API_URL="")
    def test_con_debug_el_check_no_dice_nada(self):
        """En desarrollo la variable puede faltar: nadie manda altas de verdad."""
        with _en_produccion():
            self.assertEqual(self._correr(), [])

    # ── RENAPER ─────────────────────────────────────────────────────────────
    @override_settings(SIIS_API_URL=SIIS_PRD, RENAPER_TEST_MODE=True)
    def test_renaper_en_modo_prueba_sin_debug_es_warning(self):
        with _sin_la_variable():
            mensajes = self._correr()
        self.assertEqual([m.id for m in mensajes], ["core.W001"])
        self.assertIsInstance(mensajes[0], CheckWarning)

    @override_settings(SIIS_API_URL="", RENAPER_TEST_MODE=True)
    def test_los_dos_problemas_se_informan_juntos(self):
        with _sin_la_variable():
            self.assertEqual(sorted(m.id for m in self._correr()), ["core.E001", "core.W001"])

    # ── SIIS-20: RENAPER_TEST_MODE en producción ────────────────────────────
    @override_settings(SIIS_API_URL=SIIS_PRD, RENAPER_TEST_MODE=True)
    def test_renaper_en_modo_prueba_en_produccion_es_error(self):
        """El modo de prueba inventa identidades al azar y las devuelve con
        ``success=True``, cacheadas 10 min. En PRD eso es dar de alta ciudadanos
        con datos inventados y marcarlos validados."""
        with _en_produccion():
            mensajes = self._correr()

        self.assertEqual([m.id for m in mensajes], ["core.E004"])
        self.assertIsInstance(mensajes[0], Error)

    @override_settings(SIIS_API_URL=SIIS_PRD, RENAPER_TEST_MODE=True)
    def test_fuera_de_produccion_el_modo_de_prueba_sigue_siendo_solo_un_aviso(self):
        """QA declara ``RENAPER_TEST_MODE=True`` a propósito (`.env.qa.example`):
        es como levanta sin credenciales del organismo."""
        with _sin_la_variable():
            self.assertEqual([m.id for m in self._correr()], ["core.W001"])

    @override_settings(SIIS_API_URL=SIIS_PRD, RENAPER_TEST_MODE=False)
    def test_en_produccion_sin_modo_de_prueba_no_dice_nada(self):
        with _en_produccion():
            self.assertEqual(self._correr(), [])

    # ── SIIS-21 / SEC-37: captcha aritmético en producción ──────────────────
    @override_settings(SIIS_API_URL=SIIS_PRD, RECAPTCHA_SITE_KEY="", RECAPTCHA_SECRET_KEY="")
    def test_el_captcha_aritmetico_en_produccion_es_error(self):
        """Sin claves de Google el desafío se resuelve leyendo la pregunta del
        HTML: no frena a un script contra el link público.

        Era `core.W003` (un aviso) hasta el Cambio 185. **D-37 = No**: el Cambio 71
        no se reabre —el paso 2 sigue mostrando nombre y fecha de nacimiento a
        partir de DNI + sexo— y lo que se exige a cambio es el captcha real en
        producción. Un aviso no exige nada: `check --deploy` termina en verde.
        """
        with _en_produccion():
            mensajes = self._correr()

        self.assertEqual([m.id for m in mensajes], ["core.E005"])
        self.assertIsInstance(mensajes[0], Error)

    @override_settings(SIIS_API_URL=SIIS_PRD, RECAPTCHA_SITE_KEY="sitio", RECAPTCHA_SECRET_KEY="secreto")
    def test_con_claves_de_recaptcha_no_dice_nada(self):
        with _en_produccion():
            self.assertEqual(self._correr(), [])

    @override_settings(SIIS_API_URL=SIIS_PRD, RECAPTCHA_SITE_KEY="", RECAPTCHA_SECRET_KEY="")
    def test_fuera_de_produccion_el_captcha_aritmetico_no_molesta(self):
        with _sin_la_variable():
            self.assertEqual(self._correr(), [])

    # ── Registro ────────────────────────────────────────────────────────────
    def test_el_check_esta_registrado_solo_para_deploy(self):
        """Sin esto el check existe pero no lo corre nadie."""
        self.assertIn(entorno_de_integraciones, registry.get_checks(include_deployment_checks=True))
        self.assertNotIn(entorno_de_integraciones, registry.get_checks(include_deployment_checks=False))
