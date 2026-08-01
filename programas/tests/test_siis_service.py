from unittest.mock import Mock, patch

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from programas.services.siis import TOKEN_CACHE_KEY, SiisAPIClient


@override_settings(
    SIIS_API_URL="https://siis.example",
    SIIS_API_CLIENT_ID="client",
    SIIS_API_CLIENT_SECRET="secret",
    SIIS_API_CONNECT_TIMEOUT=1,
    SIIS_API_TIMEOUT=2,
)
class SiisClientTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @patch("programas.services.siis.requests.post")
    def test_compatible_obtiene_token_y_envia_sexo(self, post):
        token = Mock(status_code=200)
        token.json.return_value = {"access_token": "abc", "expires_in": 3600}
        token.raise_for_status.return_value = None
        respuesta = Mock(status_code=200)
        respuesta.json.return_value = {"resultado": "OK", "id_consulta": "9b04df54-bde0-4aaa-85e7-99234e9e21aa"}
        post.side_effect = [token, respuesta]

        resultado = SiisAPIClient().validar_compatibilidad("21884116", "m", 59)

        self.assertTrue(resultado["success"])
        self.assertTrue(resultado["compatible"])
        self.assertEqual(
            post.call_args_list[1].kwargs["json"], {"documento": "21884116", "sexo": "M", "id_segmento": 59}
        )

    @patch("programas.services.siis.requests.post")
    def test_rechazo_funcional_no_se_trata_como_error_tecnico(self, post):
        cache.set(TOKEN_CACHE_KEY, "abc", 60)
        respuesta = Mock(status_code=400)
        respuesta.json.return_value = {
            "resultado": "RECHAZADO",
            "codigo_motivo": "BENEFICIO_EXISTENTE",
            "motivo": "Ya posee beneficio",
        }
        post.return_value = respuesta

        resultado = SiisAPIClient().validar_compatibilidad("21884116", "M", 59)

        self.assertTrue(resultado["success"])
        self.assertFalse(resultado["compatible"])

    @patch("programas.services.siis.requests.post")
    def test_error_de_contrato_se_informa_como_tecnico(self, post):
        cache.set(TOKEN_CACHE_KEY, "abc", 60)
        respuesta = Mock(status_code=400)
        respuesta.json.return_value = {"error": "id_segmento invalido"}
        post.return_value = respuesta

        resultado = SiisAPIClient().validar_compatibilidad("21884116", "M", 999)

        self.assertFalse(resultado["success"])
        self.assertEqual(resultado["error"], "id_segmento invalido")

    @patch("programas.services.siis.requests.get")
    def test_lista_programas_normaliza_id_del_contrato_real(self, get):
        cache.set(TOKEN_CACHE_KEY, "abc", 60)
        respuesta = Mock(status_code=200)
        respuesta.json.return_value = {"programas": [{"id": 38, "nombre": "Programa A"}]}
        respuesta.raise_for_status.return_value = None
        get.return_value = respuesta

        self.assertEqual(SiisAPIClient().listar_programas(), [{"id": 38, "nombre": "Programa A"}])

    @patch("programas.services.siis.requests.get")
    def test_lista_segmentos_del_programa(self, get):
        cache.set(TOKEN_CACHE_KEY, "abc", 60)
        respuesta = Mock(status_code=200)
        respuesta.json.return_value = {"data": [{"id_segmento": 7, "nombre": "Segmento A"}]}
        respuesta.raise_for_status.return_value = None
        get.return_value = respuesta

        self.assertEqual(SiisAPIClient().listar_segmentos(38), [{"id": 7, "nombre": "Segmento A"}])
        self.assertIn("/api/v1/programas/38/segmentos", get.call_args.args[0])
