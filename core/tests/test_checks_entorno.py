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

from core.checks import (
    ambiente_no_productivo,
    entorno_de_integraciones,
    escritura_siis_bloqueada,
    media_x_accel_necesita_el_location_interno,
)

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


class MediaXAccelCheckTests(SimpleTestCase):
    """`core.W004` — `MEDIA_X_ACCEL=True` sin el `location internal` baja 0 bytes.

    Seguimiento de #643. Django no puede verificar el ingress (es de otro equipo), así
    que el check **no afirma** que falte: avisa cuando la variable está prendida, que es
    justo cuando hay que leer el runbook. Apagada —el default— no dice nada.
    """

    def _correr(self):
        return media_x_accel_necesita_el_location_interno(None)

    @override_settings(MEDIA_X_ACCEL=False)
    def test_apagado_no_dice_nada(self):
        self.assertEqual(self._correr(), [])

    @override_settings(MEDIA_X_ACCEL=True)
    def test_prendido_avisa_y_nombra_el_location(self):
        mensajes = self._correr()

        self.assertEqual([m.id for m in mensajes], ["core.W004"])
        self.assertIsInstance(mensajes[0], CheckWarning)
        self.assertIn("/protected-media/", mensajes[0].msg)
        self.assertIn("0 bytes", mensajes[0].msg)
        self.assertIn("MEDIA_ROOT", mensajes[0].hint)

    def test_el_default_del_repo_lo_deja_callado(self):
        """Hoy nadie lo tiene prendido: el check no agrega ruido al CI."""
        self.assertEqual(self._correr(), [])

    def test_el_check_esta_registrado_solo_para_deploy(self):
        self.assertIn(
            media_x_accel_necesita_el_location_interno,
            registry.get_checks(include_deployment_checks=True),
        )
        self.assertNotIn(
            media_x_accel_necesita_el_location_interno,
            registry.get_checks(include_deployment_checks=False),
        )

    def test_el_runbook_tiene_el_paso_operativo(self):
        """La otra mitad de la ficha: si Django no puede verificarlo, va escrito."""
        from pathlib import Path

        runbook = Path(__file__).resolve().parents[2] / "docker" / "k8s" / "README.md"
        texto = runbook.read_text(encoding="utf-8")

        self.assertIn("core.W004", texto)
        self.assertIn("location /protected-media/", texto)


# ── #569: el testing de ECOM no escribe en el SIIS de producción ────────────
TESTING = "datanach.ecomdev.ar"
ICORE = "relevamiento-deshum.ecomdev.ar"
PRD = "datanach.chaco.gob.ar"


@override_settings(DEBUG=False)
class AmbienteNoProductivoTests(SimpleTestCase):
    """El ambiente se reconoce por los hosts que sirve, no por una variable.

    ``DATANACH_ES_PRODUCCION`` dice «esto es PRD» y su ausencia no prueba nada
    (Cambio 162): no hay evidencia de que PRD la tenga, y una guarda que la
    exigiera bloquearía producción. ``ALLOWED_HOSTS`` sí es una afirmación del
    ambiente: testing e icore se sirven bajo ``ecomdev.ar`` y PRD nunca.
    """

    def test_testing_e_icore_no_son_produccion(self):
        for host in (TESTING, ICORE, ".ecomdev.ar", "ecomdev.ar", "DataNach.EcomDev.AR"):
            with self.subTest(host=host), override_settings(ALLOWED_HOSTS=[host, "app", "web"]):
                self.assertTrue(ambiente_no_productivo())

    def test_produccion_nunca_cumple(self):
        with override_settings(ALLOWED_HOSTS=[PRD, "app", "web", "websocket"]):
            self.assertFalse(ambiente_no_productivo())

    def test_un_host_de_chaco_gob_ar_gana_aunque_haya_uno_de_ecomdev(self):
        """Falla hacia PRD: no sabemos qué hosts tiene PRD (puede compartir la
        plantilla de env con testing, o tener un ingress interno bajo ecomdev).
        Con un solo host de ``chaco.gob.ar`` el ambiente se trata como productivo."""
        for hosts in ([PRD, TESTING], [TESTING, ".chaco.gob.ar"], [ICORE, "chaco.gob.ar"]):
            with self.subTest(hosts=hosts), override_settings(ALLOWED_HOSTS=hosts):
                self.assertFalse(ambiente_no_productivo())

    def test_un_host_que_solo_contiene_chaco_gob_ar_no_es_produccion(self):
        for host in ("chaco.gob.ar.atacante.com", "nochaco.gob.ar"):
            with self.subTest(host=host), override_settings(ALLOWED_HOSTS=[TESTING, host]):
                self.assertTrue(ambiente_no_productivo())

    def test_debug_con_un_host_de_chaco_gob_ar_tampoco_bloquea(self):
        with override_settings(DEBUG=True, ALLOWED_HOSTS=["localhost", PRD]):
            self.assertFalse(ambiente_no_productivo())

    def test_el_dominio_se_compara_entero_y_no_por_substring(self):
        for host in ("ecomdev.ar.atacante.com", "noecomdev.ar", "datanach.ecomdev.ar.chaco.gob.ar"):
            with self.subTest(host=host), override_settings(ALLOWED_HOSTS=[host]):
                self.assertFalse(ambiente_no_productivo())

    def test_desarrollo_local_con_debug_no_es_produccion(self):
        with override_settings(DEBUG=True, ALLOWED_HOSTS=["localhost", "127.0.0.1", "*"]):
            self.assertTrue(ambiente_no_productivo())

    def test_localhost_sin_debug_no_alcanza(self):
        """El CI y el release-gate corren con ``DEBUG=False`` y ``localhost``: eso no dice nada."""
        with override_settings(ALLOWED_HOSTS=["localhost", "testserver"]):
            self.assertFalse(ambiente_no_productivo())


@override_settings(DEBUG=False)
class EscrituraSiisBloqueadaTests(SimpleTestCase):
    @override_settings(ALLOWED_HOSTS=[TESTING], SIIS_API_URL=SIIS_PRD)
    def test_testing_contra_el_siis_de_produccion_se_bloquea(self):
        self.assertTrue(escritura_siis_bloqueada())

    @override_settings(ALLOWED_HOSTS=[TESTING], SIIS_API_URL=SIIS_DEV)
    def test_testing_contra_el_siis_de_desarrollo_escribe(self):
        self.assertFalse(escritura_siis_bloqueada())

    @override_settings(ALLOWED_HOSTS=[PRD], SIIS_API_URL=SIIS_PRD)
    def test_produccion_contra_el_siis_de_produccion_escribe(self):
        self.assertFalse(escritura_siis_bloqueada())

    @override_settings(ALLOWED_HOSTS=[PRD, TESTING], SIIS_API_URL=SIIS_PRD)
    def test_produccion_con_un_host_de_ecomdev_escribe(self):
        self.assertFalse(escritura_siis_bloqueada())

    @override_settings(ALLOWED_HOSTS=[TESTING], SIIS_API_URL="")
    def test_sin_url_no_hay_nada_que_bloquear(self):
        """Sin host el alta ya falla sola (``_SiisConfigurationError``): no es esta guarda."""
        self.assertFalse(escritura_siis_bloqueada())

    @override_settings(ALLOWED_HOSTS=[TESTING], SIIS_API_URL="https://siisapi.ecomdev.ar.atacante.com")
    def test_un_host_que_solo_contiene_ecomdev_se_bloquea(self):
        self.assertTrue(escritura_siis_bloqueada())
