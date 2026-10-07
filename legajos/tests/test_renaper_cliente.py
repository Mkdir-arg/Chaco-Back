"""SIIS-14 (= G3-02) y G1c-15 · El cliente RENAPER ante un 401 y ante un 5xx.

Es la PoC `poc/test_repro_admin_cron_renaper.py::RenaperClienteTests` invertida.
La PoC levantaba un `HTTPServer` local; acá **no se abre ningún socket** —el
runner de la suite los corta a propósito (`core/tests/runner.py`)—, así que cada
ficha se ejercita en la capa donde de verdad vive:

* **G1c-15** vive en el `Retry` del `HTTPAdapter`, que es lógica pura de
  `urllib3`: `Retry(total=0, status_forcelist=(429, 500, 502, 503, 504))` con el
  `raise_on_status` por default hacía que urllib3 levantara `MaxRetryError`
  **sin reintentar nada**, y `requests` lo convertía en `RetryError`. Un 503 real
  salía como «Error interno de conexión al servicio» con `status_code: None`: la
  rama que informa el código HTTP no corría nunca. Acá se corre la misma decisión
  que toma `HTTPConnectionPool.urlopen`, con el objeto `Retry` que el cliente
  monta de verdad.
* **SIIS-14** vive arriba, en `consultar_ciudadano`: un 401 no descartaba el
  token. Si RENAPER lo rota antes del vencimiento que informó, todas las altas de
  ciudadano del backoffice fallan con «Error HTTP 401» hasta que el token caduca
  de viejo (horas). Se ejercita parcheando la `Session`, que es por donde salen
  el login y la consulta.
* **SIIS-14, segunda mitad:** el documento consultado viajaba al log. Con
  `RENAPER_HTTP_METHOD=get` la URL lleva `?dni=…&sexo=…` y `logger.exception`
  arrastra la URL completa en el traceback de `requests`.
"""

from unittest.mock import Mock, patch

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings
from requests.exceptions import RequestException
from urllib3.exceptions import MaxRetryError
from urllib3.response import HTTPResponse

import legajos.services.consulta_renaper as consulta_renaper

BASE = "https://renaper.example/api"

AJUSTES = dict(
    RENAPER_TEST_MODE=False,
    RENAPER_API_URL=BASE,
    RENAPER_API_USERNAME="u",
    RENAPER_API_PASSWORD="p",
    RENAPER_API_KEY="",
    RENAPER_AUTH_MODE="credentials",
    RENAPER_HTTP_METHOD="post",
    RENAPER_LOGIN_URL="",
    RENAPER_CONSULTA_URL="",
)

PERSONA = {"success": True, "data": {"nombres": "Sintetica", "apellido": "Prueba", "fechaNacimiento": "1990-01-02"}}


def _respuesta(status, cuerpo):
    respuesta = Mock(status_code=status)
    respuesta.json.return_value = cuerpo
    respuesta.text = str(cuerpo)
    return respuesta


class _ServicioSimulado:
    """Sustituto de ``Session.post``: cuenta logins y sirve estados en orden."""

    def __init__(self, estados):
        self.estados = list(estados)
        self.logins = 0
        self.consultas = 0
        self.tokens_usados = []

    def __call__(self, url, **kwargs):
        if url.endswith("/auth/login"):
            self.logins += 1
            return _respuesta(200, {"token": f"tok{self.logins}", "expiration": "2099-01-01T00:00:00Z"})
        self.consultas += 1
        self.tokens_usados.append((kwargs.get("headers") or {}).get("Authorization"))
        estado = self.estados[min(self.consultas - 1, len(self.estados) - 1)]
        return _respuesta(estado, PERSONA if estado == 200 else {"message": "no"})


@override_settings(**AJUSTES)
class _BaseRenaperTest(SimpleTestCase):
    def setUp(self):
        cache.clear()
        consulta_renaper._client = None
        self.addCleanup(self._limpiar)

    def _limpiar(self):
        consulta_renaper._client = None
        cache.clear()

    def _consultar(self, estados, dni="30111222", sexo="F", cliente=None):
        """``(resultado, servicio)`` de una consulta completa, sin tocar la red."""
        cliente = cliente or consulta_renaper.APIClient()
        servicio = _ServicioSimulado(estados)
        with patch.object(cliente.session, "post", side_effect=servicio):
            resultado = cliente.consultar_ciudadano(dni, sexo)
        return resultado, servicio


# ── G1c-15 ───────────────────────────────────────────────────────────────────


def _decision_de_urllib3(reintentos, metodo, status):
    """Lo que hace ``HTTPConnectionPool.urlopen`` con una respuesta de ``status``.

    Mismo orden que urllib3: pregunta si corresponde reintentar, si corresponde
    incrementa, y si el presupuesto está agotado propaga o devuelve la respuesta
    según ``raise_on_status``. Sin esto habría que abrir un socket para ver la
    diferencia entre «devuelve el 503» y «levanta MaxRetryError».
    """
    if not reintentos.is_retry(metodo, status, has_retry_after=False):
        return "devuelve la respuesta"
    try:
        reintentos.increment(metodo, BASE, response=HTTPResponse(status=status))
    except MaxRetryError:
        return "levanta MaxRetryError" if reintentos.raise_on_status else "devuelve la respuesta"
    return "reintenta"


class RespuestaDeErrorDelServicioTests(_BaseRenaperTest):
    """G1c-15: un 5xx del proveedor es una respuesta, no un error de conexión."""

    def _reintentos(self):
        return consulta_renaper.APIClient().session.get_adapter(BASE).max_retries

    def test_un_503_no_se_convierte_en_un_error_de_conexion(self):
        for status in (429, 500, 502, 503, 504):
            with self.subTest(status=status):
                self.assertEqual(_decision_de_urllib3(self._reintentos(), "POST", status), "devuelve la respuesta")

    def test_sin_presupuesto_de_reintentos_la_lista_de_estados_esta_vacia(self):
        """`status_forcelist` sin `total` es una trampa: marca para reintentar
        algo que no se puede reintentar, y el único efecto es la excepción."""
        self.assertEqual(set(self._reintentos().status_forcelist), set())

    def test_no_se_espera_lo_que_diga_retry_after(self):
        """Un `Retry-After` del proveedor podía retener el hilo más que el timeout."""
        self.assertFalse(self._reintentos().respect_retry_after_header)

    @override_settings(RENAPER_RETRIES=2)
    def test_con_reintentos_configurados_si_se_reintenta(self):
        reintentos = self._reintentos()

        self.assertEqual(set(reintentos.status_forcelist), {429, 500, 502, 503, 504})
        self.assertEqual(_decision_de_urllib3(reintentos, "POST", 503), "reintenta")

    def test_el_codigo_del_servicio_llega_a_quien_pregunta(self):
        """La rama `status_code != 200`, que con el bug no corría nunca."""
        resultado, _ = self._consultar([503])

        self.assertFalse(resultado["success"])
        self.assertEqual(resultado["status_code"], 503)
        self.assertIn("503", resultado["error"])

    def test_un_error_de_red_de_verdad_sigue_siendo_un_error_de_conexion(self):
        cliente = consulta_renaper.APIClient()
        with patch.object(cliente.session, "post", side_effect=RequestException("boom")):
            resultado = cliente.consultar_ciudadano("30111222", "F")

        self.assertFalse(resultado["success"])
        self.assertIsNone(resultado.get("status_code"))


# ── SIIS-14 / G3-02 ──────────────────────────────────────────────────────────


class TokenQueCaducaAntesDeTiempoTests(_BaseRenaperTest):
    """SIIS-14: un 401 descarta el token y se reintenta una sola vez."""

    def test_un_401_descarta_el_token_y_reintenta(self):
        resultado, servicio = self._consultar([401, 200])

        self.assertTrue(resultado["success"], resultado.get("error"))
        self.assertEqual(servicio.logins, 2, "el token viejo tenía que descartarse")
        self.assertEqual(servicio.consultas, 2)
        self.assertEqual(servicio.tokens_usados, ["bearer tok1", "bearer tok2"])

    def test_el_reintento_por_401_es_uno_solo(self):
        resultado, servicio = self._consultar([401])

        self.assertFalse(resultado["success"])
        self.assertIn("401", resultado["error"])
        self.assertEqual(servicio.logins, 2)
        self.assertEqual(servicio.consultas, 2)

    def test_un_403_se_trata_igual_que_el_401(self):
        resultado, servicio = self._consultar([403, 200])

        self.assertTrue(resultado["success"], resultado.get("error"))
        self.assertEqual(servicio.logins, 2)

    def test_el_token_compartido_tambien_se_borra_de_la_cache(self):
        """Sin esto, el worker de al lado sigue usando el token muerto."""
        self._consultar([401, 200])

        self.assertEqual(cache.get(consulta_renaper.TOKEN_CACHE_KEY)["token"], "tok2")

    def test_un_500_no_descarta_el_token(self):
        """Solo el 401/403 habla del token; un 500 es del otro lado."""
        _, servicio = self._consultar([500])

        self.assertEqual(servicio.logins, 1)
        self.assertEqual(servicio.consultas, 1)

    @override_settings(RENAPER_API_KEY="una-clave", RENAPER_AUTH_MODE="api_key")
    def test_en_modo_api_key_un_401_no_intenta_loguearse(self):
        """Con API key no hay token que renovar: reintentar es pegarle al mismo muro."""
        resultado, servicio = self._consultar([401])

        self.assertFalse(resultado["success"])
        self.assertEqual(servicio.logins, 0)
        self.assertEqual(servicio.consultas, 1)


class LogSinDatosPersonalesTests(_BaseRenaperTest):
    """SIIS-14: ni el documento consultado ni el cuerpo del login llegan al log."""

    def test_un_error_de_red_no_escribe_el_documento(self):
        url_con_dni = f"{BASE}/consultarenaper?dni=30111222&sexo=F"
        cliente = consulta_renaper.APIClient()
        cliente.token = "tok"
        servicio = _ServicioSimulado([200])

        def post(url, **kwargs):
            if url.endswith("/auth/login"):
                return servicio(url, **kwargs)
            raise RequestException(f"HTTPConnectionPool: Max retries exceeded with url: {url_con_dni}")

        with patch.object(cliente.session, "post", side_effect=post):
            with self.assertLogs("legajos.services.consulta_renaper", level="ERROR") as registro:
                resultado = cliente.consultar_ciudadano("30111222", "F")

        escrito = "\n".join(registro.output)
        self.assertFalse(resultado["success"])
        self.assertNotIn("30111222", escrito)
        self.assertIn("RequestException", escrito)

    def test_un_login_fallido_no_vuelca_el_cuerpo_de_la_respuesta(self):
        cliente = consulta_renaper.APIClient()
        cuerpo = {"detalle": "usuario u con clave p rechazado"}

        with patch.object(cliente.session, "post", return_value=_respuesta(500, cuerpo)):
            with self.assertRaises(Exception) as capturado:  # noqa: B017 - el cliente levanta Exception pelado
                cliente.login()

        self.assertIn("500", str(capturado.exception))
        self.assertNotIn("clave p", str(capturado.exception))

    def test_un_login_que_no_conecta_no_escribe_la_url(self):
        cliente = consulta_renaper.APIClient()

        with patch.object(cliente.session, "post", side_effect=RequestException(f"url: {BASE}?dni=30111222")):
            with self.assertRaises(Exception) as capturado:  # noqa: B017
                cliente.login()

        self.assertNotIn("30111222", str(capturado.exception))
        self.assertIn("RequestException", str(capturado.exception))
