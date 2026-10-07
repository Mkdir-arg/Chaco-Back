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
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

CREDENCIALES = dict(
    SIIS_API_URL="https://siis.example",
    SIIS_API_CLIENT_ID="client",
    SIIS_API_CLIENT_SECRET="secret",
    SIIS_API_CONNECT_TIMEOUT=1,
    SIIS_API_TIMEOUT=2,
)

#: El SIIS de desarrollo de ECOM, el único ambiente donde el alta de prueba es gratis.
URL_DESARROLLO = "https://siisapi.ecomdev.ar"


def _respuesta(payload, status=200):
    respuesta = Mock(status_code=status)
    respuesta.json.return_value = payload
    respuesta.raise_for_status.return_value = None
    return respuesta


def _correr(*args):
    """Corre el comando y devuelve ``(salida, codigo_de_salida)``."""
    salida = StringIO()
    codigo = 0
    try:
        call_command("diagnosticar_siis", *args, stdout=salida)
    except SystemExit as exc:
        codigo = exc.code
    return salida.getvalue(), codigo


@override_settings(**CREDENCIALES)
class DiagnosticarSiisTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @patch("programas.services.siis.sesion.get")
    @patch("programas.services.siis.sesion.post")
    def test_catalogo_con_programas_cierra_sin_fallas(self, post, get):
        post.return_value = _respuesta({"access_token": "abc", "expires_in": 3600})
        get.return_value = _respuesta({"programas": [{"id": 34, "nombre": "Chaco Joven", "estado": "ACTIVO"}]})

        salida, codigo = _correr()

        self.assertEqual(codigo, 0)
        self.assertIn("#34 Chaco Joven", salida)
        self.assertIn("Diagnóstico sin fallas", salida)

    @patch("programas.services.siis.sesion.get")
    @patch("programas.services.siis.sesion.post")
    def test_catalogo_vacio_avisa_pero_no_es_falla_de_integracion(self, post, get):
        """El entorno de test de ECOM puede no publicar programas: eso no es un error nuestro."""
        post.return_value = _respuesta({"access_token": "abc", "expires_in": 3600})
        get.return_value = _respuesta({"total": 0, "programas": []})

        salida, codigo = _correr()

        self.assertEqual(codigo, 0)
        self.assertIn("respondió sin programas", salida)
        self.assertNotIn("FALLA", salida)
        # Con la lista vacía hay que poder ver el cuerpo, porque "vacío" y "clave
        # que no reconocemos" se ven iguales en el conteo.
        self.assertIn('"programas": []', salida)
        self.assertIn("claves de primer nivel: ['programas', 'total']", salida)

    @patch("programas.services.siis.sesion.get")
    @patch("programas.services.siis.sesion.post")
    def test_lista_bajo_una_clave_desconocida_queda_visible_en_el_cuerpo(self, post, get):
        """Si ECOM renombra el contenedor, el conteo da 0 igual que un catálogo vacío."""
        post.return_value = _respuesta({"access_token": "abc", "expires_in": 3600})
        get.return_value = _respuesta({"items": [{"id": 34, "nombre": "Chaco Joven", "estado": "ACTIVO"}]})

        salida, codigo = _correr()

        self.assertEqual(codigo, 0)
        self.assertIn("items en la respuesta   : 0", salida)
        # El cuerpo delata que el programa vino, pero bajo otra clave.
        self.assertIn("Chaco Joven", salida)
        self.assertIn("claves de primer nivel: ['items']", salida)
        self.assertIn("claves que la app busca", salida)

    @patch("programas.services.siis.sesion.get")
    @patch("programas.services.siis.sesion.post")
    def test_cuerpo_largo_se_recorta(self, post, get):
        post.return_value = _respuesta({"access_token": "abc", "expires_in": 3600})
        get.return_value = _respuesta({"items": [{"relleno": "x" * 900}]})

        salida, _ = _correr()

        self.assertIn("caracteres)", salida)
        self.assertNotIn("x" * 500, salida)

    @patch("programas.services.siis.sesion.get")
    @patch("programas.services.siis.sesion.post")
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

    @patch("programas.services.siis.sesion.get")
    @patch("programas.services.siis.sesion.post")
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

    @patch("programas.services.siis.sesion.post")
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
        with patch("programas.services.siis.sesion.post") as post:
            salida, codigo = _correr()

        self.assertEqual(codigo, 1)
        self.assertIn("SIIS_API_CLIENT_ID: vacía", salida)
        self.assertIn("SIIS_API_CLIENT_SECRET: vacía", salida)
        self.assertNotIn("2. Autenticación", salida)
        post.assert_not_called()


class AltaDePruebaTests(SimpleTestCase):
    """SIIS-19: el paso 6 escribe en SIIS y SIIS no tiene baja.

    Un alta de prueba mandada al ambiente equivocado deja ahí, para siempre, un
    beneficiario «PRUEBA INTEGRACION DATANACH» con un DNI que ni siquiera eligió
    quien corrió el comando —venía por defecto—. Las dos guardas: fuera del SIIS
    de desarrollo el alta pide ``--si-entiendo-prd --motivo``, y el DNI deja de
    tener default.
    """

    def setUp(self):
        cache.clear()

    def correr(self, *args):
        """Corre ``--alta`` con la red mockeada.

        Devuelve ``(salida, mock_del_alta, error)``. El mock vuelve también
        cuando el comando cortó, porque lo que hay que afirmar en ese caso es
        justamente que **no** llegó a llamarse.
        """
        salida = StringIO()
        error = None
        with (
            patch("programas.services.siis.SiisAPIClient.cargar_beneficiario") as alta,
            patch("programas.services.siis.sesion.get") as get,
            patch("programas.services.siis.sesion.post") as post,
        ):
            post.return_value = _respuesta({"access_token": "abc", "expires_in": 3600})
            get.return_value = _respuesta({"programas": [{"id": 34, "nombre": "Chaco Joven", "estado": "ACTIVO"}]})
            alta.return_value = {"success": True, "siis_id": 7, "data": {}}
            try:
                call_command("diagnosticar_siis", "--alta", *args, stdout=salida)
            except SystemExit:
                pass
            except CommandError as exc:
                error = exc
        return salida.getvalue(), alta, error

    @override_settings(**{**CREDENCIALES, "SIIS_API_URL": "https://siis.chaco.gob.ar"})
    def test_contra_una_url_que_no_es_la_de_desarrollo_corta_sin_escribir(self):
        _, alta, error = self.correr("--alta-dni", "35111222")

        self.assertIn("--si-entiendo-prd", str(error))
        alta.assert_not_called()

    @override_settings(**{**CREDENCIALES, "SIIS_API_URL": "https://siis.chaco.gob.ar"})
    def test_la_bandera_sin_motivo_tampoco_alcanza(self):
        _, alta, error = self.correr("--alta-dni", "35111222", "--si-entiendo-prd")

        self.assertIn("--motivo", str(error))
        alta.assert_not_called()

    @override_settings(**{**CREDENCIALES, "SIIS_API_URL": "https://siis.chaco.gob.ar"})
    def test_con_bandera_y_motivo_escribe_y_deja_rastro(self):
        with self.assertLogs("programas.management.commands._base_siis", level="WARNING") as registro:
            salida, alta, error = self.correr(
                "--alta-dni", "35111222", "--si-entiendo-prd", "--motivo", "verificación pedida por ECOM"
            )

        self.assertIsNone(error)
        alta.assert_called_once()
        self.assertIn("verificación pedida por ECOM", "\n".join(registro.output))
        self.assertIn("si-entiendo-prd", salida)

    @override_settings(**{**CREDENCIALES, "SIIS_API_URL": URL_DESARROLLO})
    def test_contra_el_siis_de_desarrollo_no_pide_nada(self):
        _, alta, error = self.correr("--alta-dni", "35111222")

        self.assertIsNone(error)
        alta.assert_called_once()
        self.assertEqual(alta.call_args.args[0]["dni"], 35111222)

    @override_settings(**{**CREDENCIALES, "SIIS_API_URL": URL_DESARROLLO})
    def test_sin_alta_dni_no_se_inventa_uno(self):
        """El default `35111222` hacía que correr `--alta` sin pensar diera de
        alta siempre a la misma persona del manual."""
        _, alta, error = self.correr()

        self.assertIn("--alta-dni", str(error))
        alta.assert_not_called()

    @override_settings(**{**CREDENCIALES, "SIIS_API_URL": ""})
    def test_sin_url_no_se_puede_saber_a_donde_iria(self):
        _, alta, error = self.correr("--alta-dni", "35111222")

        self.assertIn("SIIS_API_URL", str(error))
        alta.assert_not_called()

    @override_settings(**{**CREDENCIALES, "SIIS_API_URL": "https://siis.chaco.gob.ar"})
    def test_los_pasos_de_solo_lectura_siguen_corriendo_contra_produccion(self):
        """La guarda es del paso 6, no del comando: diagnosticar sigue siendo lo
        primero que se corre en un ambiente recién configurado."""
        with (
            patch("programas.services.siis.sesion.get") as get,
            patch("programas.services.siis.sesion.post") as post,
        ):
            post.return_value = _respuesta({"access_token": "abc", "expires_in": 3600})
            get.return_value = _respuesta({"programas": [{"id": 34, "nombre": "Chaco Joven", "estado": "ACTIVO"}]})
            salida, codigo = _correr()

        self.assertEqual(codigo, 0)
        self.assertIn("Diagnóstico sin fallas", salida)
