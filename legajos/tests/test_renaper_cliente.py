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

import datetime
import threading
import time
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


# ── Ronda 2: el login no puede hacer cola (MAJOR de la revisión) ─────────────

#: Cuánto tarda el login simulado en fallar. Suficiente para que una cola de 4
#: se note (4 × 0,3 = 1,2 s) sin que el test tarde.
LOGIN_LENTO = 0.3
HILOS = 4


class LoginConcurrenteTests(_BaseRenaperTest):
    """El candado del token no puede serializar los logins que fallan.

    Medido antes del arreglo con 4 hilos y un login de 0,4 s que falla: 1,61 s
    (0,41 / 0,80 / 1,20 / 1,59), porque cada request esperaba su turno para
    fallar igual. Con los timeouts reales (5 + 10 s) la cuarta alta concurrente
    se come los 60 s de nginx. El candado solo sirve para no pedir dos tokens a
    la vez **cuando el login funciona**.
    """

    def _correr(self, post, cliente=None, hilos=HILOS):
        """``(resultados, segundos)`` de ``hilos`` consultas simultáneas."""
        cliente = cliente or consulta_renaper.APIClient()
        resultados = []
        barrera = threading.Barrier(hilos)

        def trabajo():
            barrera.wait()
            resultados.append(cliente.consultar_ciudadano("30111222", "F"))

        with patch.object(cliente.session, "post", side_effect=post):
            equipo = [threading.Thread(target=trabajo) for _ in range(hilos)]
            arranque = time.monotonic()
            for hilo in equipo:
                hilo.start()
            for hilo in equipo:
                hilo.join()
            tardo = time.monotonic() - arranque
        return resultados, tardo

    def test_un_login_lento_que_falla_no_hace_cola(self):
        intentos = []

        def post(url, **kwargs):
            if url.endswith("/auth/login"):
                intentos.append(url)
                time.sleep(LOGIN_LENTO)
                return _respuesta(500, {"message": "no"})
            return _respuesta(200, PERSONA)

        resultados, tardo = self._correr(post)

        # Lo determinista: un solo login para las cuatro consultas.
        self.assertEqual(len(intentos), 1, "cada request pidió su propio token")
        self.assertEqual(len(resultados), HILOS)
        for resultado in resultados:
            self.assertFalse(resultado["success"])
        # Y el tiempo total no crece con la cantidad de requests: en cola serían
        # 4 × 0,3 = 1,2 s, y el margen de abajo deja lugar al ruido del runner.
        self.assertLess(tardo, LOGIN_LENTO * 2.5, f"los logins hicieron cola: {tardo:.2f} s")

    def test_un_login_lento_que_funciona_se_comparte(self):
        """La razón de ser del candado: un solo round-trip para los cuatro."""
        intentos = []

        def post(url, **kwargs):
            if url.endswith("/auth/login"):
                intentos.append(url)
                time.sleep(LOGIN_LENTO)
                return _respuesta(200, {"token": "tok1", "expiration": "2099-01-01T00:00:00Z"})
            return _respuesta(200, PERSONA)

        resultados, tardo = self._correr(post)

        self.assertEqual(len(intentos), 1)
        for resultado in resultados:
            self.assertTrue(resultado["success"], resultado.get("error"))
        self.assertLess(tardo, LOGIN_LENTO * 2.5)

    def test_el_que_espera_el_token_de_otro_no_espera_para_siempre(self):
        """Si el login se cuelga, el que espera falla rápido en vez de encolarse."""
        cliente = consulta_renaper.APIClient()
        cliente.espera_login = 0.1
        arrancó = threading.Event()
        soltar = threading.Event()

        def post(url, **kwargs):
            if url.endswith("/auth/login"):
                arrancó.set()
                soltar.wait(5)
                return _respuesta(500, {"message": "no"})
            return _respuesta(200, PERSONA)

        with patch.object(cliente.session, "post", side_effect=post):
            colgado = threading.Thread(target=lambda: cliente.consultar_ciudadano("30111222", "F"))
            colgado.start()
            self.assertTrue(arrancó.wait(2), "el login simulado no arrancó")
            arranque = time.monotonic()
            resultado = cliente.consultar_ciudadano("30111223", "F")
            tardo = time.monotonic() - arranque
            soltar.set()
            colgado.join(5)

        self.assertFalse(resultado["success"])
        self.assertLess(tardo, 1.0, f"hizo cola detrás del login colgado: {tardo:.2f} s")


class TokenRotadoConcurrenteTests(LoginConcurrenteTests):
    """Ronda 3 (MAJOR): el que espera el token tiene más de un intento.

    Con una sola vuelta, el que esperaba hacía `wait()` → `_token_vigente()` y,
    si no había token, **levantaba**. Con rotación —el ganador consulta, recibe
    el 401 de SIIS-14 y llama `descartar_token()` antes de que los demás lean—
    N−1 altas terminaban en «Error interno al obtener token» **sin consultar**:
    medido 1 de 4 y 1 de 8 éxitos, en 5 de 5 corridas. Hoy el que espera vuelve
    a la decisión: o toma el token nuevo, o se vuelve él el que se loguea.
    """

    def _servicio_con_rotacion(self, logins, consultas):
        """El primer token que se emita da 401; del segundo en adelante, 200."""
        candado = threading.Lock()
        muertos = set()

        def post(url, **kwargs):
            if url.endswith("/auth/login"):
                with candado:
                    logins.append(url)
                    numero = len(logins)
                    if numero == 1:
                        muertos.add(f"tok{numero}")
                return _respuesta(200, {"token": f"tok{numero}", "expiration": "2099-01-01T00:00:00Z"})
            token = (kwargs.get("headers") or {}).get("Authorization", "").split(" ", 1)[-1]
            with candado:
                consultas.append(token)
                vencido = token in muertos
            if vencido:
                return _respuesta(401, {"message": "token vencido"})
            return _respuesta(200, PERSONA)

        return post

    def _rotacion(self, hilos):
        logins, consultas = [], []
        resultados, _ = self._correr(self._servicio_con_rotacion(logins, consultas), hilos=hilos)
        return resultados, logins, consultas

    def test_la_rotacion_del_token_no_voltea_a_los_que_esperan(self):
        for hilos in (4, 8):
            with self.subTest(hilos=hilos):
                self.setUp()  # cliente y caché limpios por subtest
                resultados, logins, _ = self._rotacion(hilos)

                exitos = [r for r in resultados if r["success"]]
                self.assertEqual(len(resultados), hilos)
                self.assertEqual(len(exitos), hilos, [r.get("error") for r in resultados if not r["success"]])
                # Una oleada por token: el que muere y el que lo reemplaza. Un
                # login por request sería volver a no coordinar nada.
                self.assertLessEqual(len(logins), 2, f"{len(logins)} logins para {hilos} requests")

    def test_ninguno_se_queda_sin_consultar(self):
        """El síntoma exacto del hallazgo: fallar sin haber hablado con RENAPER.

        El piso es una consulta por request: el que llega después de la rotación
        ya toma el token nuevo de la caché compartida y no necesita reintentar.
        """
        resultados, _, consultas = self._rotacion(HILOS)

        self.assertGreaterEqual(len(consultas), HILOS, "alguno falló sin consultar")
        self.assertIn("tok2", consultas, "nadie llegó a usar el token nuevo")
        for resultado in resultados:
            self.assertTrue(resultado["success"], resultado.get("error"))

    def test_el_que_espera_vuelve_a_intentar_cuando_el_token_ya_no_esta(self):
        """El hallazgo, sin depender de cómo caiga el scheduler.

        Las dos pruebas de arriba reproducen la rotación de punta a punta, pero
        si gana la carrera dependen del planificador: en esta máquina los que
        esperan alcanzan a leer el token antes de que el 401 lo descarte, y
        pasan también con el código anterior. Acá la ventana se abre a mano: el
        login del ganador termina **sin** dejar token, que es exactamente el
        estado en que quedaba el que esperaba. Antes levantaba «hay un login en
        curso»; ahora vuelve a la decisión y se loguea él.
        """
        cliente = consulta_renaper.APIClient()
        entro, seguir, logins = threading.Event(), threading.Event(), []

        def login_falso():
            logins.append(1)
            if len(logins) == 1:
                entro.set()
                seguir.wait(5)
                # El proveedor contestó 200 sin token: `login` devuelve None y el
                # ganador corta ahí (no hay nada que reintentar).
                return None
            cliente.token = "tok2"
            cliente.token_expiration = datetime.datetime(2099, 1, 1, tzinfo=datetime.timezone.utc)
            return "tok2"

        with patch.object(cliente, "login", side_effect=login_falso):
            ganador = threading.Thread(target=lambda: self.assertRaises(Exception, cliente.get_token))
            ganador.start()
            self.assertTrue(entro.wait(2), "el login del ganador no arrancó")
            soltar = threading.Timer(0.05, seguir.set)
            soltar.start()
            token = cliente.get_token()
            soltar.cancel()
            ganador.join(5)

        self.assertEqual(token, "tok2")
        self.assertEqual(len(logins), 2, "el que esperaba no se volvió el que se loguea")

    def test_un_401_con_el_token_viejo_no_tira_el_token_nuevo(self):
        """Sin esto, una rotación se convierte en una ronda de logins en cadena."""
        cliente = consulta_renaper.APIClient()
        cliente.token = "tok2"
        cliente.token_expiration = datetime.datetime(2099, 1, 1, tzinfo=datetime.timezone.utc)

        cliente.descartar_token(usado="tok1")

        self.assertEqual(cliente.token, "tok2")

        cliente.descartar_token(usado="tok2")

        self.assertIsNone(cliente.token)


class LoginSanoLentoTests(LoginConcurrenteTests):
    """Ronda 3: un login **sano** que tarda no puede voltear a los que esperan.

    La ronda 2 esperaba 2 s fijos, un número más chico que el timeout del propio
    login: un login sano de 2,5 s hacía fallar a todos los que esperaban. La
    espera pasa a derivarse del timeout, que es lo que de verdad acota cuánto
    puede durar un login.
    """

    def test_la_espera_cubre_el_peor_caso_del_login(self):
        cliente = consulta_renaper.APIClient()

        self.assertGreaterEqual(cliente.espera_login, sum(cliente.timeout))

    def test_un_login_sano_y_lento_termina_bien_para_todos(self):
        intentos = []

        def post(url, **kwargs):
            if url.endswith("/auth/login"):
                intentos.append(url)
                time.sleep(LOGIN_LENTO * 2)
                return _respuesta(200, {"token": "tok1", "expiration": "2099-01-01T00:00:00Z"})
            return _respuesta(200, PERSONA)

        resultados, _ = self._correr(post)

        self.assertEqual(len(intentos), 1)
        for resultado in resultados:
            self.assertTrue(resultado["success"], resultado.get("error"))

    def test_el_mensaje_distingue_la_espera_agotada_de_un_login_sin_token(self):
        """MINOR: no es lo mismo «sigue colgado» que «terminó y no dejó nada»."""
        cliente = consulta_renaper.APIClient()
        cliente.espera_login = 0.05
        colgado = threading.Event()

        with patch.object(cliente, "login", side_effect=lambda: colgado.wait(5)):
            hilo = threading.Thread(target=cliente.get_token)
            hilo.start()
            time.sleep(0.05)
            with self.assertRaises(Exception) as capturado:  # noqa: B017
                cliente.get_token()
            colgado.set()
            hilo.join(5)

        self.assertIn("se agotó la espera", str(capturado.exception))

        # El otro mensaje: el login termina bien pero no deja token (lo descartó
        # un 401 en el medio), y las vueltas se agotan.
        sin_token = consulta_renaper.APIClient()
        with patch.object(sin_token, "login", return_value=None):
            with self.assertRaises(Exception) as capturado:  # noqa: B017
                sin_token.get_token()

        self.assertIn("sin dejar token", str(capturado.exception))


class CortacircuitoRenaperTests(_BaseRenaperTest):
    """SIIS-09 para RENAPER: con el servicio caído se falla rápido."""

    def setUp(self):
        super().setUp()
        self.addCleanup(cache.clear)

    def test_tres_fallas_de_red_seguidas_dejan_de_consultar(self):
        cliente = consulta_renaper.APIClient()
        llamadas = []

        def post(url, **kwargs):
            llamadas.append(url)
            raise RequestException("sin ruta al host")

        with patch.object(cliente.session, "post", side_effect=post):
            for _ in range(consulta_renaper.cortacircuito.fallas):
                cliente.consultar_ciudadano("30111222", "F")
            antes = len(llamadas)
            resultado = cliente.consultar_ciudadano("30111223", "F")

        self.assertEqual(len(llamadas), antes, "siguió saliendo a la red con el cortacircuito abierto")
        self.assertTrue(resultado["cortado"])
        self.assertFalse(resultado["success"])

    def test_una_respuesta_de_error_no_abre_el_cortacircuito(self):
        """Un 500 del proveedor es una respuesta: el servicio está en pie."""
        cliente = consulta_renaper.APIClient()

        for _ in range(consulta_renaper.cortacircuito.fallas + 2):
            resultado, servicio = self._consultar([500], cliente=cliente)

        self.assertFalse(consulta_renaper.cortacircuito.abierto())
        self.assertEqual(resultado["status_code"], 500)

    def test_una_consulta_que_anda_borra_lo_acumulado(self):
        cliente = consulta_renaper.APIClient()

        with patch.object(cliente.session, "post", side_effect=RequestException("boom")):
            cliente.consultar_ciudadano("30111222", "F")
            cliente.consultar_ciudadano("30111223", "F")
        self._consultar([200], cliente=cliente)

        with patch.object(cliente.session, "post", side_effect=RequestException("boom")) as post:
            cliente.consultar_ciudadano("30111224", "F")

        self.assertFalse(consulta_renaper.cortacircuito.abierto())
        self.assertTrue(post.called)


class SesionCompartidaTests(_BaseRenaperTest):
    """El cliente usa la sesión del repo: pool acotado y sin cookie jar."""

    def test_la_sesion_no_guarda_cookies(self):
        cliente = consulta_renaper.APIClient()

        politica = cliente.session.cookies.get_policy()

        self.assertFalse(politica.set_ok(Mock(), Mock()))
        self.assertFalse(politica.return_ok(Mock(), Mock()))

    def test_la_sesion_conserva_la_configuracion_de_reintentos(self):
        """`sesion_http` no puede pisar el `Retry` de G1c-15."""
        reintentos = consulta_renaper.APIClient().session.get_adapter(BASE).max_retries

        self.assertFalse(reintentos.raise_on_status)
        self.assertEqual(reintentos.total, 0)
