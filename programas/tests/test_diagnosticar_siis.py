"""Tests del comando ``diagnosticar_siis``.

Cubren sobre todo los caminos que no se pueden ejercitar contra el servicio real
sin credenciales válidas: catálogo con datos, catálogo vacío y catálogo que llega
pero que el normalizador descarta (cambio de contrato de ECOM). Lo que se verifica
es que el comando **distinga** los tres casos, porque desde el backoffice los tres
se ven igual: el select de Programa SIIS vacío.
"""

from io import StringIO
from unittest.mock import Mock, patch

from django.core.cache import cache
from django.core.management import call_command
from django.test import SimpleTestCase, override_settings

CREDENCIALES = dict(
    SIIS_API_URL="https://siis.example",
    SIIS_API_CLIENT_ID="client",
    SIIS_API_CLIENT_SECRET="secret",
    SIIS_API_CONNECT_TIMEOUT=1,
    SIIS_API_TIMEOUT=2,
)


def _respuesta(payload, status=200):
    respuesta = Mock(status_code=status)
    respuesta.json.return_value = payload
    respuesta.raise_for_status.return_value = None
    return respuesta


def _correr():
    """Corre el comando y devuelve ``(salida, codigo_de_salida)``."""
    salida = StringIO()
    codigo = 0
    try:
        call_command("diagnosticar_siis", stdout=salida)
    except SystemExit as exc:
        codigo = exc.code
    return salida.getvalue(), codigo


@override_settings(**CREDENCIALES)
class DiagnosticarSiisTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @patch("programas.services.siis.requests.get")
    @patch("programas.services.siis.requests.post")
    def test_catalogo_con_programas_cierra_sin_fallas(self, post, get):
        post.return_value = _respuesta({"access_token": "abc", "expires_in": 3600})
        get.return_value = _respuesta({"programas": [{"id": 34, "nombre": "Chaco Joven", "estado": "ACTIVO"}]})

        salida, codigo = _correr()

        self.assertEqual(codigo, 0)
        self.assertIn("#34 Chaco Joven", salida)
        self.assertIn("Diagnóstico sin fallas", salida)

    @patch("programas.services.siis.requests.get")
    @patch("programas.services.siis.requests.post")
    def test_catalogo_vacio_avisa_pero_no_es_falla_de_integracion(self, post, get):
        """El entorno de test de ECOM puede no publicar programas: eso no es un error nuestro."""
        post.return_value = _respuesta({"access_token": "abc", "expires_in": 3600})
        get.return_value = _respuesta({"programas": []})

        salida, codigo = _correr()

        self.assertEqual(codigo, 0)
        self.assertIn("respondió sin programas", salida)
        self.assertNotIn("FALLA", salida)

    @patch("programas.services.siis.requests.get")
    @patch("programas.services.siis.requests.post")
    def test_cambio_de_contrato_se_denuncia_como_falla_con_las_claves_recibidas(self, post, get):
        """Si ECOM renombra los campos, el select queda vacío sin ningún error visible."""
        post.return_value = _respuesta({"access_token": "abc", "expires_in": 3600})
        get.return_value = _respuesta(
            {"programas": [{"codigo": 34, "denominacion_programa": "Chaco Joven", "estado": "ACTIVO"}]}
        )

        salida, codigo = _correr()

        self.assertEqual(codigo, 1)
        self.assertIn("ninguno sobrevive al parseo", salida)
        self.assertIn("codigo", salida)
        self.assertIn("denominacion_programa", salida)

    @patch("programas.services.siis.requests.get")
    @patch("programas.services.siis.requests.post")
    def test_programa_inactivo_no_llega_al_select(self, post, get):
        post.return_value = _respuesta({"access_token": "abc", "expires_in": 3600})
        get.return_value = _respuesta({"programas": [{"id": 15, "nombre": "Chaco Olímpico", "estado": "INACTIVO"}]})

        salida, codigo = _correr()

        self.assertEqual(codigo, 0)
        self.assertIn("que llegan al select    : 0", salida)
        # Parsear bien y filtrar por vigencia no es una falla de integración.
        self.assertIn("ninguno está ACTIVO", salida)
        self.assertNotIn("FALLA", salida)
        self.assertIn("#15 Chaco Olímpico [INACTIVO]", salida)

    @patch("programas.services.siis.requests.post")
    def test_token_rechazado_corta_antes_del_catalogo(self, post):
        import requests

        respuesta = Mock(status_code=401, text='{"error":"CREDENCIALES_INVALIDAS"}')
        respuesta.raise_for_status.side_effect = requests.HTTPError(response=respuesta)
        post.return_value = respuesta

        salida, codigo = _correr()

        self.assertEqual(codigo, 1)
        self.assertIn("No se pudo obtener el token", salida)
        self.assertIn("CREDENCIALES_INVALIDAS", salida)
        self.assertNotIn("3. Catálogo", salida)


@override_settings(SIIS_API_URL="https://siis.example", SIIS_API_CLIENT_ID="", SIIS_API_CLIENT_SECRET="")
class DiagnosticarSiisSinConfiguracionTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_sin_credenciales_falla_en_el_primer_paso_y_no_sale_a_la_red(self):
        with patch("programas.services.siis.requests.post") as post:
            salida, codigo = _correr()

        self.assertEqual(codigo, 1)
        self.assertIn("SIIS_API_CLIENT_ID: vacía", salida)
        self.assertIn("SIIS_API_CLIENT_SECRET: vacía", salida)
        self.assertNotIn("2. Autenticación", salida)
        post.assert_not_called()
