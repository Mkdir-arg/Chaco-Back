from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from legajos.services.consulta_renaper import APIClient, reparar_mojibake, reparar_texto_mojibake


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
