from unittest.mock import Mock, patch

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from programas.services.personas import TOKEN_CACHE_KEY, PersonasAPIClient, normalizar_persona


class PersonasNormalizationTests(SimpleTestCase):
    def test_normaliza_respuesta_anidada(self):
        payload = {
            "codigo_http": 200,
            "data": {
                "persona": {
                    "numero_documento": "30111222",
                    "apellido": "Perez",
                    "nombres": "Ana Maria",
                    "fechaNacimiento": "1990-01-02",
                    "genero": "F",
                }
            },
        }
        self.assertEqual(
            normalizar_persona(payload, "30111222"),
            {
                "dni": "30111222",
                "apellido": "Perez",
                "nombre": "Ana Maria",
                "fecha_nacimiento": "1990-01-02",
                "sexo": "F",
            },
        )


@override_settings(
    PERSONAS_API_URL="https://personas.example/api/v1",
    PERSONAS_API_CLIENT_ID="client",
    PERSONAS_API_CLIENT_SECRET="secret",
    PERSONAS_API_ENTIDAD_UUID="entity",
    PERSONAS_API_FUENTE_ID=13,
    PERSONAS_API_CONNECT_TIMEOUT=10,
    PERSONAS_API_TIMEOUT=20,
)
class PersonasClientTests(SimpleTestCase):
    def setUp(self):
        cache.delete(TOKEN_CACHE_KEY)

    @patch("programas.services.personas.requests.get")
    @patch("programas.services.personas.requests.post")
    def test_token_y_consulta_usan_contrato_documentado(self, post, get):
        auth = Mock()
        auth.json.return_value = {"data": {"token": "token-prueba"}}
        auth.raise_for_status.return_value = None
        post.return_value = auth
        response = Mock(status_code=200)
        response.json.return_value = {"data": {"dni": "30111222", "apellido": "Perez"}}
        response.raise_for_status.return_value = None
        get.return_value = response

        result = PersonasAPIClient().consultar("30111222", "F")

        self.assertTrue(result["success"])
        self.assertEqual(post.call_args.kwargs["json"]["entidad"], "entity")
        self.assertEqual(get.call_args.kwargs["params"], {"dni": "30111222", "sexo": "F", "fuente_id": 13})
        self.assertEqual(get.call_args.kwargs["headers"], {"Authorization": "Bearer token-prueba"})

    @patch("programas.services.personas.requests.get")
    def test_http_200_con_codigo_12_es_persona_no_encontrada(self, get):
        cache.set(TOKEN_CACHE_KEY, "token-prueba", 60)
        response = Mock(status_code=200)
        response.json.return_value = {
            "codigo_http": 200,
            "mensaje_http": "OK",
            "data": {"codigo": 12, "mensaje": "NO SE ENCONTRO INFORMACION"},
        }
        response.raise_for_status.return_value = None
        get.return_value = response

        result = PersonasAPIClient().consultar("48433496", "M")

        self.assertFalse(result["success"])
        self.assertTrue(result["not_found"])
        self.assertEqual(result["error"], "El DNI no fue encontrado en Base de Personas.")
