from unittest.mock import Mock, patch

import requests
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from programas.services.siis import TOKEN_CACHE_KEY, SiisAPIClient, SiisCatalogError, motivos_de_rechazo


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
    def test_compatible_obtiene_token_y_envia_el_contrato_vigente(self, post):
        token = Mock(status_code=200)
        token.json.return_value = {"access_token": "abc", "expires_in": 3600}
        token.raise_for_status.return_value = None
        respuesta = Mock(status_code=200)
        respuesta.json.return_value = {
            "resultado": "OK",
            "apto": True,
            "id_consulta": "9b04df54-bde0-4aaa-85e7-99234e9e21aa",
        }
        post.side_effect = [token, respuesta]

        resultado = SiisAPIClient().validar_compatibilidad("21884116", 59, "2005-08-15")

        self.assertTrue(resultado["success"])
        self.assertTrue(resultado["compatible"])
        self.assertEqual(
            post.call_args_list[1].kwargs["json"],
            {"dni": "21884116", "id_programa": 59, "fecha_nacimiento": "2005-08-15"},
        )

    @patch("programas.services.siis.requests.post")
    def test_sin_fecha_de_nacimiento_no_manda_el_campo(self, post):
        cache.set(TOKEN_CACHE_KEY, "abc", 60)
        respuesta = Mock(status_code=200)
        respuesta.json.return_value = {"resultado": "OK", "apto": True}
        post.return_value = respuesta

        SiisAPIClient().validar_compatibilidad("21884116", 59)

        self.assertEqual(post.call_args.kwargs["json"], {"dni": "21884116", "id_programa": 59})

    @patch("programas.services.siis.requests.post")
    def test_rechazo_llega_en_http_200_y_no_es_error_tecnico(self, post):
        """SIIS resuelve el veredicto siempre con 200: el rechazo viaja en ``apto``."""
        cache.set(TOKEN_CACHE_KEY, "abc", 60)
        respuesta = Mock(status_code=200)
        respuesta.json.return_value = {
            "resultado": "RECHAZADO",
            "apto": False,
            "validaciones": {
                "padron_siis": "REGISTRADO",
                "empleo_publico": "INCOMPATIBLE_PLANTA",
                "duplicidad_becas": "SIN_INCOMPATIBILIDAD",
            },
        }
        post.return_value = respuesta

        resultado = SiisAPIClient().validar_compatibilidad("21884116", 59)

        self.assertTrue(resultado["success"])
        self.assertFalse(resultado["compatible"])

    @patch("programas.services.siis.requests.post")
    def test_error_de_contrato_se_informa_como_tecnico(self, post):
        cache.set(TOKEN_CACHE_KEY, "abc", 60)
        respuesta = Mock(status_code=400)
        respuesta.json.return_value = {"error": "VALIDACION_ENTRADA"}
        post.return_value = respuesta

        resultado = SiisAPIClient().validar_compatibilidad("21884116", 999)

        self.assertFalse(resultado["success"])
        self.assertEqual(resultado["error"], "VALIDACION_ENTRADA")

    @patch("programas.services.siis.requests.get")
    def test_lista_programas_normaliza_id_del_contrato_real(self, get):
        cache.set(TOKEN_CACHE_KEY, "abc", 60)
        respuesta = Mock(status_code=200)
        respuesta.json.return_value = {"programas": [{"id": 38, "nombre": "Programa A"}]}
        respuesta.raise_for_status.return_value = None
        get.return_value = respuesta

        self.assertEqual(SiisAPIClient().listar_programas(), [{"id": 38, "nombre": "Programa A"}])

    def test_motivos_de_rechazo_solo_traduce_las_banderas_incumplidas(self):
        motivos = motivos_de_rechazo(
            {
                "padron_siis": "REGISTRADO",
                "vigencia_programa": "VIGENTE",
                "edad_minima": "EDAD_INSUFICIENTE",
                "empleo_publico": "INCOMPATIBLE_PLANTA",
                "horas_docentes": "SIN_INCOMPATIBILIDAD",
            }
        )

        self.assertEqual([bandera for bandera, _ in motivos], ["edad_minima", "empleo_publico"])
        self.assertIn("edad mínima", motivos[0][1])

    def test_motivos_de_rechazo_tolera_una_respuesta_sin_validaciones(self):
        self.assertEqual(motivos_de_rechazo(None), [])

    @patch("programas.services.siis.requests.get", side_effect=requests.Timeout)
    def test_timeout_del_catalogo_muestra_un_mensaje_util(self, _get):
        cache.set(TOKEN_CACHE_KEY, "abc", 60)

        with self.assertRaisesMessage(SiisCatalogError, "tardó demasiado en responder"):
            SiisAPIClient().listar_programas()
