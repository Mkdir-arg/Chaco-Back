from unittest.mock import Mock, patch

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from legajos.services.consulta_renaper import (
    APIClient,
    consultar_datos_renaper,
    reparar_mojibake,
    reparar_texto_mojibake,
)


class RenaperEncodingTests(SimpleTestCase):
    def test_reparar_texto_mojibake_con_enie(self):
        self.assertEqual(reparar_texto_mojibake("FARIÃA"), "FARIÑA")

    def test_reparar_texto_mojibake_con_acentos(self):
        self.assertEqual(reparar_texto_mojibake("JOSÃ‰ GARCÃA"), "JOSÉ GARCÍA")

    def test_reparar_mojibake_recursivo(self):
        data = {
            "success": True,
            "data": {
                "apellido": "FARIÃA",
                "domicilio": {"calle": "SAN MARTÃN"},
                "observaciones": ["NiÃ±ez", "sin cambios"],
            },
        }

        self.assertEqual(
            reparar_mojibake(data),
            {
                "success": True,
                "data": {
                    "apellido": "FARIÑA",
                    "domicilio": {"calle": "SAN MARTÍN"},
                    "observaciones": ["Niñez", "sin cambios"],
                },
            },
        )


class RenaperTestModeTests(SimpleTestCase):
    """TST-02: estos dos dependían del orden en que corrieran.

    `consultar_datos_renaper` cachea por `renaper:consulta:<dni>:<sexo>`, y esa caché
    es de **proceso** (LocMem): nadie la limpia entre tests y un `SimpleTestCase` no
    revierte nada. Con los dos consultando el mismo DNI, el segundo en correr pegaba
    en la caché y **no llamaba al servicio**. En el orden alfabético de siempre eso
    dejaba a `test_el_modo_test_no_agrega_latencia_por_defecto` pasando por el motivo
    equivocado —no dormía porque no se ejecutaba—, y con `--shuffle` (semilla
    2529168576 del CI) el que quedaba segundo era el de la latencia, que sí falla:
    `Expected 'sleep' to be called once. Called 0 times.`

    El arreglo es doble a propósito: `cache.clear()` para que cada test arranque frío
    pase lo que pase antes, y **un DNI distinto por caso**, para que ni siquiera
    puedan pisarse entre sí.
    """

    def setUp(self):
        cache.clear()

    @override_settings(RENAPER_TEST_MODE=True)
    @patch("legajos.services.consulta_renaper.time.sleep")
    def test_el_modo_test_no_agrega_latencia_por_defecto(self, sleep):
        result = consultar_datos_renaper("30111222", "M")

        self.assertTrue(result["success"])
        sleep.assert_not_called()

    @override_settings(RENAPER_TEST_MODE=True, RENAPER_TEST_LATENCY_SECONDS=0.25)
    @patch("legajos.services.consulta_renaper.time.sleep")
    def test_el_modo_test_aplica_la_latencia_configurada(self, sleep):
        result = consultar_datos_renaper("30111333", "M")

        self.assertTrue(result["success"])
        sleep.assert_called_once_with(0.25)

    @override_settings(RENAPER_TEST_MODE=True, RENAPER_TEST_LATENCY_SECONDS=0.25)
    @patch("legajos.services.consulta_renaper.time.sleep")
    def test_la_segunda_consulta_del_mismo_dni_sale_de_la_cache(self, sleep):
        """La caché que causaba el problema, afirmada: es comportamiento buscado.

        Sin este test, alguien podría «arreglar» el acoplamiento sacando la caché, que
        es justamente lo que evita una llamada a RENAPER por cada visita a la pantalla.
        """
        primera = consultar_datos_renaper("30111444", "M")
        segunda = consultar_datos_renaper("30111444", "M")

        self.assertEqual(primera, segunda)
        sleep.assert_called_once_with(0.25)


class RenaperApiClientTests(SimpleTestCase):
    @override_settings(
        RENAPER_API_URL="https://wsv2.secretarianaf.gob.ar/api",
        RENAPER_CONSULTA_URL="",
        RENAPER_LOGIN_URL="",
        RENAPER_AUTH_MODE="credentials",
        RENAPER_HTTP_METHOD="get",
        RENAPER_API_KEY="",
        RENAPER_API_KEY_HEADER="X-API-Key",
        RENAPER_API_KEY_PREFIX="",
        RENAPER_CONNECT_TIMEOUT=10,
        RENAPER_TIMEOUT=20,
        RENAPER_RETRIES=0,
    )
    @patch.object(APIClient, "get_token", return_value="token-test")
    def test_consulta_renaper_cid_usa_endpoint_y_formato_documentado(self, _token):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "isSuccess": True,
            "message": "",
            "result": {"apellido": "Perez", "nombres": "Juan"},
        }

        client = APIClient()
        client.session.get = Mock(return_value=response)

        result = client.consultar_ciudadano("30111222", "M")

        self.assertEqual(client.consulta_url, "https://wsv2.secretarianaf.gob.ar/api/consultarenaper")
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["apellido"], "Perez")
        _, kwargs = client.session.get.call_args
        self.assertEqual(kwargs["params"], {"dni": "30111222", "sexo": "M"})
        self.assertEqual(kwargs["headers"]["Authorization"], "bearer token-test")
