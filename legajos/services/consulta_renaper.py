import datetime
import logging
import random
import threading
import time
import unicodedata

import urllib3
from django.conf import settings
from django.core.cache import cache
from requests.exceptions import ConnectionError, RequestException
from urllib3.util.retry import Retry

from core.integraciones import MARGEN_ESPERA_LOGIN, Cortacircuito, sesion_http
from core.models import Provincia
from core.performance.query_observability import instrument_external_call

# Suprimir warnings de SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

# Clave interna de cache; no contiene una credencial.
TOKEN_CACHE_KEY = "renaper:token"  # nosec B105
CONSULTA_CACHE_TTL = 600  # 10 min por (dni, sexo)

#: SIIS-09 / ronda 2 del PR 7a. Con RENAPER caído, cada alta de ciudadano
#: retenía un hilo de daphne hasta agotar el timeout, una por una. Tres fallas
#: de red seguidas lo dejan sin consultar por un minuto, y en ese minuto el alta
#: falla en el acto con «no se pudo consultar» en vez de colgarse.
cortacircuito = Cortacircuito("renaper")

#: Margen sobre el peor caso del login para la espera del token ajeno. El que
#: espera **no** hace su propia llamada: su techo es lo que tarda el login del
#: otro, y eso ya lo acota ``requests`` con ``connect + read``. El margen es para
#: que el ganador alcance a publicar el token. Un número fijo más chico que el
#: timeout —la ronda 2 usaba 2 s— hacía fallar a los que esperaban un login
#: **sano** que tardaba un poco más que eso.
#:
#: Vive en ``core.integraciones`` y se reexporta acá: el presupuesto de
#: ``CADENAS`` lo tiene que sumar y no puede importar una app de dominio.

#: Vueltas de :meth:`APIClient.get_token` antes de darse por vencido. Una vuelta
#: es «¿hay token? si no, logueate vos o esperá al que está». Dos alcanzan para
#: el camino normal y la tercera cubre que entre medio un 401 haya descartado el
#: token recién traído (SIIS-14).
VUELTAS_TOKEN = 3

#: Los dos motivos por los que no se consigue el token, que no son el mismo
#: problema: uno dice «el login de otro no termina» y el otro «terminó y no
#: dejó token» (lo descartó un 401, o el proveedor contestó 200 sin token).
ESPERA_AGOTADA = "No se pudo obtener el token de RENAPER: se agotó la espera de un login en curso."
LOGIN_SIN_TOKEN = "No se pudo obtener el token de RENAPER: el login terminó sin dejar token."  # nosec B105 - mensaje de error, no una credencial


class _IntentoDeLogin:
    """Lo que un login en curso le cuenta a los que esperan su resultado.

    No alcanza con «terminó»: el que espera necesita saber **si salió bien**.
    Si salió mal, hacer su propio login es pegarle al mismo muro y en fila, que
    es justo la cola que la ronda 2 sacó de acá.
    """

    __slots__ = ("listo", "fallo")

    def __init__(self):
        self.listo = threading.Event()
        self.fallo = None


MOJIBAKE_MARKERS = ("Ã", "Â", "â€", "â€“", "â€”", "â€œ", "â€", "â€™")


def _clean_api_base(raw_url):
    if not raw_url:
        return ""
    # No quitar el slash final si la URL ya incluye el endpoint completo
    return str(raw_url).strip().strip('"').strip("'")


def _join_url(base_url, path):
    if not base_url:
        return ""
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _parse_positive_int(raw_value, default):
    try:
        value = int(raw_value)
        return value if value > 0 else default
    except (TypeError, ValueError):
        return default


def _normalizar_sexo(sexo):
    raw = (sexo or "").strip()
    norm = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("utf-8").lower()
    mapping = {
        "m": "M",
        "masculino": "M",
        "hombre": "M",
        "f": "F",
        "femenino": "F",
        "mujer": "F",
        "x": "X",
        "no binario": "X",
        "nobinario": "X",
        "otro": "X",
    }
    return mapping.get(norm, raw.upper() if raw else "")


def _encode_mojibake_bytes(value):
    raw = bytearray()
    for char in value:
        for encoding in ("cp1252", "latin1"):
            try:
                raw.extend(char.encode(encoding))
                break
            except UnicodeError:
                continue
        else:
            return None
    return bytes(raw)


def reparar_texto_mojibake(value):
    if not isinstance(value, str) or not any(marker in value for marker in MOJIBAKE_MARKERS):
        return value

    raw_bytes = _encode_mojibake_bytes(value)
    if raw_bytes:
        try:
            repaired = raw_bytes.decode("utf-8")
        except UnicodeError:
            repaired = None
        if repaired and repaired != value:
            return repaired

    for encoding in ("latin1", "cp1252"):
        try:
            repaired = value.encode(encoding).decode("utf-8")
        except UnicodeError:
            continue
        if repaired and repaired != value:
            return repaired

    return value


def reparar_mojibake(value):
    if isinstance(value, dict):
        return {key: reparar_mojibake(item) for key, item in value.items()}
    if isinstance(value, list):
        return [reparar_mojibake(item) for item in value]
    if isinstance(value, tuple):
        return tuple(reparar_mojibake(item) for item in value)
    return reparar_texto_mojibake(value)


class APIClient:
    def __init__(self):
        self.username = settings.RENAPER_API_USERNAME
        self.password = settings.RENAPER_API_PASSWORD
        self.api_key = (getattr(settings, "RENAPER_API_KEY", "") or "").strip()
        self.api_key_header = (getattr(settings, "RENAPER_API_KEY_HEADER", "X-API-Key") or "X-API-Key").strip()
        self.api_key_prefix = (getattr(settings, "RENAPER_API_KEY_PREFIX", "") or "").strip()
        self.auth_mode = (getattr(settings, "RENAPER_AUTH_MODE", "auto") or "auto").strip().lower()
        self.http_method = (getattr(settings, "RENAPER_HTTP_METHOD", "auto") or "auto").strip().lower()

        self.api_base = _clean_api_base(settings.RENAPER_API_URL)
        self.login_url = self._build_login_url(self.api_base)
        self.consulta_url = self._build_consulta_url(self.api_base)

        # SIIS-09: los defaults siguen a los de ``settings`` —consulta (5, 10)—
        # para que el presupuesto de red por request no dependa de cuál de los
        # dos valores gane.
        connect_timeout = _parse_positive_int(getattr(settings, "RENAPER_CONNECT_TIMEOUT", 5), 5)
        read_timeout = _parse_positive_int(getattr(settings, "RENAPER_TIMEOUT", 10), 10)
        self.timeout = (connect_timeout, read_timeout)

        self.token = None
        self.token_expiration = None
        # El cliente es de módulo (``_get_client``) y daphne corre las vistas
        # sync en un pool de hilos: ``login`` escribe ``self.token`` y
        # ``get_token`` lo lee. Sin coordinación, N requests simultáneos con el
        # token vencido disparan N logins contra RENAPER (G1c-15).
        #
        # El candado protege **solo el estado**, nunca el HTTP: envolver el
        # login con un candado hacía que N requests hicieran cola detrás de un
        # login colgado y que el enésimo esperara N × timeout —con (5, 10) la
        # cuarta alta concurrente se comía los 60 s de nginx—. Quién se loguea se
        # decide acá; los demás esperan el **resultado**, acotado (ver
        # :meth:`get_token`).
        self._candado_estado = threading.Lock()
        self._login_en_curso = None
        # Derivada del timeout y no un número suelto: ningún login **sano**
        # puede durar más que `connect + read`, así que el que espera siempre
        # llega a ver su resultado. Lo que la espera corta es el caso en que el
        # login no termina nunca, que es el que haría cola.
        self.espera_login = sum(self.timeout) + MARGEN_ESPERA_LOGIN
        retry_count = _parse_positive_int(getattr(settings, "RENAPER_RETRIES", 0), 0)
        retries = Retry(
            total=retry_count,
            connect=retry_count,
            read=retry_count,
            backoff_factor=0.8,
            # G1c-15: `status_forcelist` sin presupuesto de reintentos es una
            # trampa. urllib3 marca la respuesta como «a reintentar», ve que no
            # hay intentos y levanta `MaxRetryError`, que `requests` convierte en
            # `RetryError`: un 503 del proveedor salía como «error interno de
            # conexión» con `status_code: None` y la rama que informa el código
            # HTTP no corría nunca. Con `raise_on_status=False` la respuesta
            # llega igual aunque el presupuesto se agote.
            status_forcelist=(429, 500, 502, 503, 504) if retry_count else (),
            allowed_methods=frozenset(["GET", "POST"]),
            raise_on_status=False,
            # Un `Retry-After` generoso del proveedor retenía el hilo más que el
            # timeout configurado, que es lo único que el presupuesto de
            # `core.integraciones` sabe contar.
            respect_retry_after_header=False,
        )
        # Sesión compartida del repo (SIIS-09): pool acotado y **sin cookie
        # jar**. Con una `requests.Session()` cruda, una cookie que devolviera
        # el proveedor quedaba guardada en el cliente de módulo y se reenviaba
        # en las consultas que ese proceso hace por otras personas.
        self.session = sesion_http(max_retries=retries)

    def _build_consulta_url(self, api_base):
        explicit_url = _clean_api_base(getattr(settings, "RENAPER_CONSULTA_URL", ""))
        if explicit_url:
            return explicit_url
        if not api_base:
            return ""
        base = api_base.rstrip("/")
        lower_base = base.lower()
        if lower_base.endswith("/api") and not self._use_api_key_mode():
            return _join_url(base, "consultarenaper")
        return base

    def _build_login_url(self, api_base):
        explicit_url = _clean_api_base(getattr(settings, "RENAPER_LOGIN_URL", ""))
        if explicit_url:
            return explicit_url
        if not api_base:
            return ""
        return _join_url(api_base, "auth/login")

    def _use_api_key_mode(self):
        if self.auth_mode == "api_key":
            return True
        if self.auth_mode == "credentials":
            return False
        return bool(self.api_key)

    def _resolve_http_method(self):
        if self.http_method in ("get", "post"):
            return self.http_method
        # En modo API key para SISOC priorizamos POST.
        return "post" if self._use_api_key_mode() else "get"

    def login(self):
        """Pide un token nuevo y lo devuelve. **Sin candado**: ver :meth:`get_token`."""
        if self._use_api_key_mode():
            return None

        try:
            response = instrument_external_call(
                "renaper",
                self.session.post,
                self.login_url,
                json={"username": self.username, "password": self.password},
                timeout=self.timeout,
            )
        except ConnectionError:
            cortacircuito.registrar_falla()
            raise Exception("Error de conexion con el servicio.")
        except RequestException as e:
            # SIIS-14: nunca `str(e)`. El texto de una excepción de
            # `requests` arrastra la URL completa, y en modo GET ahí viaja el
            # documento consultado. El tipo es lo que sirve para diagnosticar.
            cortacircuito.registrar_falla()
            raise Exception(f"No se pudo conectar al servicio de login: {type(e).__name__}")

        # Contestó: el servicio está en pie. Un 500 del login es una respuesta,
        # no una falla de red, y no abre el cortacircuito (mismo criterio que
        # ``programas.services.personas``).
        cortacircuito.registrar_exito()
        if response.status_code != 200:
            # SIIS-14: sin `response.text`. El cuerpo de un login fallido es
            # del proveedor y puede traer cualquier cosa (incluido el eco de
            # lo que se le mandó); esto termina en el log por `exception`.
            raise Exception(f"Login fallido: {response.status_code}")

        data = response.json()
        token = data.get("token")
        expiration = datetime.datetime.fromisoformat(data["expiration"].replace("Z", "+00:00"))
        # Los dos juntos y bajo el candado: son un solo dato. Escribirlos sueltos
        # deja una ventana en la que otro hilo lee el token nuevo con el
        # vencimiento viejo (o al revés).
        with self._candado_estado:
            self.token = token
            self.token_expiration = expiration
        # Compartir el token entre workers/procesos: sin esto cada request
        # pagaba un round-trip extra de login contra RENAPER.
        ttl = (expiration - datetime.datetime.now(datetime.timezone.utc)).total_seconds() - 60
        if ttl > 0:
            cache.set(
                TOKEN_CACHE_KEY,
                {"token": token, "expiration": expiration.isoformat()},
                ttl,
            )
        # Lo que trajo **esta** llamada, no ``self.token``: entre que se publica y
        # que el ganador lo lee, un 401 de otro hilo puede haberlo descartado, y
        # ahí «no hay token» significa cosas distintas (ver ``get_token``).
        return token

    def _token_vigente(self):
        """El token que ya se tiene —propio o de la caché compartida—, o ``None``."""
        ahora = datetime.datetime.now(datetime.timezone.utc)
        with self._candado_estado:
            if self.token and self.token_expiration and ahora < self.token_expiration:
                return self.token

        cached = cache.get(TOKEN_CACHE_KEY)
        if cached:
            try:
                expiration = datetime.datetime.fromisoformat(cached["expiration"])
                if ahora < expiration:
                    with self._candado_estado:
                        self.token = cached["token"]
                        self.token_expiration = expiration
                        return self.token
            except (KeyError, TypeError, ValueError):
                pass
        return None

    def get_token(self, limite=None):
        """El token, pidiéndolo si hace falta. Un solo login a la vez, sin cola.

        **Lo que no se puede hacer es envolver el login en un candado.** Medido
        con 4 hilos y un login de 0,4 s que falla: con candado, 1,61 s
        (0,41/0,80/1,20/1,59), porque cada uno espera su turno para fallar
        igual; con los timeouts reales (5 + 10 s) la cuarta alta concurrente se
        come los 60 s de nginx. El candado solo sirve para no pedir dos tokens a
        la vez **cuando el login funciona**.

        Así que el candado protege nada más que la decisión —quién se loguea— y
        se suelta antes del HTTP. El que la gana publica el **resultado** en un
        :class:`_IntentoDeLogin`; los demás lo esperan y, según cómo haya ido,
        siguen o cortan. El tiempo total deja de crecer con la cantidad de
        requests.

        **Ronda 3:** el que espera vuelve a la decisión en vez de darse por
        vencido en el primer intento. Con una sola vuelta, un token rotado
        —el ganador consulta, se come un 401 y llama ``descartar_token`` antes de
        que los demás lean— dejaba a N−1 altas con «error al obtener token» sin
        haber consultado nada (medido: 1 de 4 y 1 de 8 éxitos). Las tres salidas
        del que espera, en orden:

        * el login ajeno **salió bien** → vuelta nueva: o toma ese token, o
          —si alguien lo descartó en el medio— esta vez el ganador es él;
        * el login ajeno **falló** → corta. Hacer el propio es pegarle al mismo
          muro, y en fila: esa es la cola que la ronda 2 sacó de acá;
        * **no terminó** dentro de ``espera_login`` → corta. Un login sano no
          puede tardar más que su propio ``connect + read``, así que llegar acá
          es un login que no termina nunca.

        **El ganador vuelve a la decisión igual que los que esperan** (seguimiento
        del PR 7a). Leía ``self.token`` fuera del candado apenas volvía de
        ``login()``: si un 401 de otro hilo lo descartaba en esa ventana, el
        ganador —que acababa de traer un token bueno— levantaba «el login terminó
        sin dejar token» sin usar sus vueltas restantes, mientras los que
        esperaban sí reintentaban. Hoy ``login()`` devuelve **lo que trajo**: con
        token vuelve a la decisión, y solo un 200 sin token en el cuerpo corta,
        porque ahí no hay nada que reintentar.

        **El límite** (``limite``, un ``time.monotonic()``) es de quien llama y
        cubre **todo** el request: las vueltas, la espera y el reintento por 401
        de ``consultar_ciudadano``. Pasado el límite no se empieza nada nuevo, que
        es lo que hace que la cadena declarada en ``core.integraciones.CADENAS``
        —espera + login + consulta— sea un techo de verdad y no la suma de dos de
        los tres tiempos.
        """
        if self._use_api_key_mode():
            return None

        if limite is None:
            limite = time.monotonic() + self.espera_login

        for _ in range(VUELTAS_TOKEN):
            token = self._token_vigente()
            if token:
                return token

            restante = limite - time.monotonic()
            if restante <= 0:
                raise Exception(ESPERA_AGOTADA)

            with self._candado_estado:
                intento = self._login_en_curso
                me_toca = intento is None
                if me_toca:
                    intento = self._login_en_curso = _IntentoDeLogin()

            if me_toca:
                try:
                    obtenido = self.login()
                except Exception as exc:
                    intento.fallo = exc
                    raise
                finally:
                    with self._candado_estado:
                        self._login_en_curso = None
                    # Pase lo que pase, los que esperan se enteran ahora: un
                    # login que falla no puede dejarlos esperando su turno.
                    intento.listo.set()
                if obtenido is None:
                    # 200 sin `token` en el cuerpo: seguir con «bearer None» es
                    # mandar una consulta que no puede salir bien y leerla como un
                    # 401 del proveedor. Reintentar tampoco sirve: el proveedor
                    # contesta lo mismo y cada vuelta cuesta un login entero.
                    raise Exception(LOGIN_SIN_TOKEN)
                continue

            if not intento.listo.wait(restante):
                raise Exception(ESPERA_AGOTADA)
            if intento.fallo is not None:
                raise Exception(f"No se pudo obtener el token de RENAPER: {intento.fallo}")

        raise Exception(LOGIN_SIN_TOKEN)

    def descartar_token(self, usado=None):
        """Olvida el token, acá y en la caché que comparten los workers.

        SIIS-14: ``get_token`` confía en el ``expiration`` que informó RENAPER.
        Si el proveedor lo rota antes, el token guardado está muerto y **todos**
        los procesos siguen usándolo hasta que caduque de viejo: horas de «Error
        HTTP 401» en cada alta de ciudadano del backoffice.

        Con ``usado`` solo descarta **ese** token. Un 401 que llega de un request
        que todavía tenía el token viejo no puede tirar el que otro acaba de
        traer: eso convertía una rotación en una ronda de logins en cadena.

        **La guarda vale también entre procesos** (seguimiento del PR 7a). Antes
        comparaba contra ``self.token``, que es del worker: si el que rotó fue
        **otro** worker —en producción hay varios— el 401 viejo pasaba la guarda
        (su ``self.token`` *era* el usado) y borraba de la caché compartida el
        token nuevo que ese otro acababa de publicar, con lo que la rotación
        volvía a ser una ronda de logins, ahora en todos los procesos. Hoy se
        compara contra lo que hay **en la caché** y solo se borra si sigue siendo
        el token que se usó.

        **El límite**: la caché de Django no tiene un «borrar si vale esto»
        atómico (ni LocMem ni Redis lo exponen por esta API), así que entre el
        ``get`` y el ``delete`` queda una ventana de microsegundos en la que otro
        worker puede publicar un token nuevo y este ``delete`` llevárselo. Es el
        mismo desenlace que había **siempre** antes del arreglo y lo único que
        cuesta es un login de más; cerrarla del todo pide un script Lua o un
        ``WATCH``, que ataría el código al backend de caché.
        """
        with self._candado_estado:
            if usado is not None and self.token is not None and self.token != usado:
                return
            self.token = None
            self.token_expiration = None
        if usado is None:
            cache.delete(TOKEN_CACHE_KEY)
            return
        compartido = cache.get(TOKEN_CACHE_KEY)
        if compartido is None:
            return
        if not isinstance(compartido, dict) or compartido.get("token") == usado:
            cache.delete(TOKEN_CACHE_KEY)

    def _headers(self, limite=None):
        """``(headers, token, error)``: lo que autentica la consulta, o por qué no.

        El ``token`` sale acá y no se vuelve a leer del header: es el que hay que
        descartar si la consulta se come un 401, y descartar «el token actual»
        en vez de «el que usé» tira el que otro hilo acaba de traer.
        """
        headers = {"Content-Type": "application/json"}
        if self._use_api_key_mode():
            if not self.api_key:
                return None, None, {"success": False, "error": "Falta RENAPER_API_KEY para autenticar con API Key."}
            headers[self.api_key_header] = f"{self.api_key_prefix} {self.api_key}".strip()
            return headers, None, None
        try:
            token = self.get_token(limite)
        except Exception:
            # El mensaje de la excepción ya viene saneado por `login`.
            logger.exception("Error al obtener token RENAPER")
            return None, None, {"success": False, "error": "Error interno al obtener token"}
        headers["Authorization"] = f"bearer {token}"
        return headers, token, None

    def _pedir(self, headers, payload, method):
        """``(response, error)`` de una sola llamada a la consulta."""
        try:
            if method == "post":
                respuesta = instrument_external_call(
                    "renaper",
                    self.session.post,
                    self.consulta_url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                    verify=False,
                )
            else:
                respuesta = instrument_external_call(
                    "renaper",
                    self.session.get,
                    self.consulta_url,
                    headers=headers,
                    params=payload,
                    timeout=self.timeout,
                    verify=False,
                )
            # Contestó: el servicio está en pie. Lo que abre el cortacircuito es
            # **no poder hablarle**; un 401 o un 500 son respuestas.
            cortacircuito.registrar_exito()
            return respuesta, None
        except ConnectionError:
            cortacircuito.registrar_falla()
            return None, {"success": False, "error": "Error de conexion al servicio."}
        except RequestException as exc:
            cortacircuito.registrar_falla()
            # SIIS-14: sin `logger.exception`. El traceback de `requests`
            # arrastra la URL completa y con `RENAPER_HTTP_METHOD=get` ahí va
            # `?dni=…&sexo=…`. Queda el tipo del error, que es lo que diagnostica.
            logger.error("RequestException RENAPER (%s)", type(exc).__name__)
            return None, {
                "success": False,
                "error": "Error interno de conexion al servicio.",
            }

    def consultar_ciudadano(self, dni, sexo):
        if cortacircuito.abierto():
            # SIIS-09: tres fallas de red seguidas. Con RENAPER caído, cada alta
            # de ciudadano retenía un hilo hasta agotar el timeout; durante el
            # minuto que dura el corte el alta falla en el acto y el operador
            # decide qué hacer, que es lo mismo que haría al minuto siguiente.
            return {"success": False, "error": "No se pudo consultar RENAPER.", "cortado": True}

        payload = {"dni": dni, "sexo": _normalizar_sexo(sexo)}
        method = self._resolve_http_method()

        # Un solo límite para todo lo que este request puede repetir: las vueltas
        # de `get_token`, su espera y el reintento por 401. Es lo que hace que la
        # cadena declarada en `core.integraciones.CADENAS` —espera + login +
        # consulta, 46 s con los valores de hoy— sea un techo y no la suma de dos
        # de los tres tiempos. Sin él, tres vueltas de espera más el reintento se
        # pasaban de los 60 s de nginx.
        limite = time.monotonic() + self.espera_login

        # SIIS-14: un 401/403 puede ser el token rotado antes de tiempo. Se
        # descarta y se reintenta **una** vez; un segundo rechazo con un token
        # recién pedido no es el token. En modo API key no hay nada que renovar.
        response = None
        for intento in (1, 2):
            headers, usado, error = self._headers(limite)
            if error:
                if response is not None:
                    # Ya hubo una respuesta del servicio —el 401 que disparó el
                    # reintento— y el token nuevo no se pudo traer. Lo que informa
                    # es el 401: «no se pudo renovar el token» taparía lo único
                    # que de verdad se sabe de RENAPER en este request.
                    break
                return error
            response, error = self._pedir(headers, payload, method)
            if error:
                return error
            if (
                intento == 1
                and response.status_code in (401, 403)
                and not self._use_api_key_mode()
                # Pasado el límite ya no se empieza nada: renovar el token y
                # repetir la consulta son otros 30 s, y el 401 es lo único que de
                # verdad se sabe de RENAPER en este request. Se informa ese.
                and time.monotonic() < limite
            ):
                self.descartar_token(usado=usado)
                continue
            break

        if response.status_code != 200:
            try:
                error_data = response.json()
            except Exception:
                error_data = response.text[:500] if hasattr(response, "text") else "Sin contenido"
            return {
                "success": False,
                "error": f"Error HTTP {response.status_code}: Error en la respuesta del servicio.",
                "status_code": response.status_code,
                "raw_response": error_data,
            }

        try:
            data = response.json()
        except Exception:
            logger.exception("Respuesta RENAPER no es JSON valido")
            raw_text = response.text[:500] if hasattr(response, "text") else "No response text"
            return {
                "success": False,
                "error": "Error interno: respuesta no es JSON valido.",
                "raw_response": raw_text,
            }

        data = reparar_mojibake(data)

        if data.get("success", False):
            return {"success": True, "data": data["data"]}

        if data.get("isSuccess", False):
            return {"success": True, "data": data.get("result") or {}}

        if "isSuccess" in data:
            return {
                "success": False,
                "error": data.get("message") or "Respuesta de Renaper no indica exito.",
                "raw_response": data,
            }

        if not data.get("success", False):
            return {
                "success": False,
                "error": "Respuesta de Renaper no indica exito.",
                "raw_response": data,
            }

        return {"success": True, "data": data["data"]}


def normalizar(texto):
    if not texto:
        return ""
    texto = texto.lower().replace("_", " ")
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("utf-8")
    return texto.strip()


_client = None
_client_lock = threading.Lock()


def _get_client():
    """Cliente compartido a nivel módulo: reutiliza la Session (keep-alive) y el
    token entre requests, en vez de instanciar y loguearse por cada consulta."""
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = APIClient()
    return _client


def consultar_datos_renaper(dni, sexo):
    """Consulta RENAPER con cache de resultados por (dni, sexo)."""
    cache_key = f"renaper:consulta:{dni}:{_normalizar_sexo(sexo)}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    resultado = _consultar_datos_renaper(dni, sexo)

    # Solo se cachean respuestas deterministas (éxito o fallecido), nunca errores.
    if resultado.get("success") or resultado.get("fallecido"):
        cache.set(cache_key, resultado, CONSULTA_CACHE_TTL)
    return resultado


def _consultar_datos_renaper(dni, sexo):
    if getattr(settings, "RENAPER_TEST_MODE", False):
        latency_seconds = getattr(settings, "RENAPER_TEST_LATENCY_SECONDS", 0)
        if latency_seconds > 0:
            time.sleep(latency_seconds)

        nombres = [
            "Juan Carlos",
            "Maria Elena",
            "Roberto",
            "Ana Sofia",
            "Carlos Alberto",
            "Lucia",
            "Fernando",
            "Valentina",
        ]
        apellidos = ["Perez", "Gonzalez", "Rodriguez", "Lopez", "Martinez", "Garcia", "Fernandez", "Morales"]
        calles = ["Av. Corrientes", "Av. Santa Fe", "Rivadavia", "San Martin", "Belgrano", "Mitre", "9 de Julio"]
        provincias = ["Buenos Aires", "Cordoba", "Santa Fe", "Mendoza", "Tucuman"]

        nombre_random = random.choice(nombres)
        apellido_random = random.choice(apellidos)
        calle_random = random.choice(calles)
        numero_random = random.randint(100, 9999)
        provincia_random = random.choice(provincias)
        anio_random = random.randint(1970, 2000)
        mes_random = random.randint(1, 12)
        dia_random = random.randint(1, 28)

        return {
            "success": True,
            "data": {
                "dni": dni,
                "nombre": nombre_random,
                "apellido": apellido_random,
                "fecha_nacimiento": f"{anio_random}-{mes_random:02d}-{dia_random:02d}",
                "genero": _normalizar_sexo(sexo),
                "domicilio": f"{calle_random} {numero_random}",
                "provincia": random.randint(1, 24),
            },
            "datos_api": {
                "nombres": nombre_random,
                "apellido": apellido_random,
                "fechaNacimiento": f"{anio_random}-{mes_random:02d}-{dia_random:02d}",
                "provincia": provincia_random,
                "calle": calle_random,
                "numero": str(numero_random),
            },
        }

    api_url = _clean_api_base(getattr(settings, "RENAPER_API_URL", None))
    api_key = (getattr(settings, "RENAPER_API_KEY", None) or "").strip()
    username = getattr(settings, "RENAPER_API_USERNAME", None)
    password = getattr(settings, "RENAPER_API_PASSWORD", None)

    if not api_url:
        return {
            "success": False,
            "error": "Configuracion RENAPER incompleta (URL).",
        }

    if not api_key and not (username and password):
        return {
            "success": False,
            "error": "Configuracion RENAPER incompleta (API key o usuario/password).",
        }

    try:
        client = _get_client()
        response = client.consultar_ciudadano(dni, sexo)

        if not response["success"]:
            return {
                "success": False,
                "error": response.get("error", "Error al consultar RENAPER"),
                "status_code": response.get("status_code"),
                "datos_api": response.get("raw_response"),
            }

        datos = response["data"] if isinstance(response.get("data"), dict) else {}

        if datos.get("mensaf") == "FALLECIDO":
            return {"success": False, "fallecido": True}

        # Que el proveedor anide `result` un nivel más deja `data` vacío y el
        # ciudadano se daba de alta **marcado como validado** con el nombre en
        # blanco (lo medía `test_contratos_externos
        # ::test_renaper_con_el_result_anidado_un_nivel_mas_no_se_marca_validado`,
        # que nombraba a la Ola 3 junto con SIIS-10). Sin nombre y apellido no
        # hay identidad que acreditar: es una respuesta que no se puede usar.
        if not str(datos.get("nombres") or "").strip() or not str(datos.get("apellido") or "").strip():
            logger.warning("RENAPER contestó éxito sin nombre ni apellido: la identidad no se da por validada")
            return {
                "success": False,
                "error": "La respuesta de RENAPER no trae la identidad de la persona.",
            }

        equivalencias_provincias = {
            "ciudad de buenos aires": "ciudad autonoma de buenos aires",
            "caba": "ciudad autonoma de buenos aires",
            "ciudad autonoma de buenos aires": "ciudad autonoma de buenos aires",
            "tierra del fuego": "tierra del fuego, antartida e islas del atlantico sur",
            "tierra del fuego antartida e islas del atlantico sur": "tierra del fuego, antartida e islas del atlantico sur",
        }

        provincia_api = datos.get("provincia", "")
        provincia_api_norm = normalizar(provincia_api)
        provincia_api_norm = equivalencias_provincias.get(provincia_api_norm, provincia_api_norm)

        provincia = None
        for prov in Provincia.objects.all():
            nombre_norm = normalizar(prov.nombre)
            if provincia_api_norm == nombre_norm:
                provincia = prov
                break

        genero = _normalizar_sexo(sexo)
        datos_mapeados = {
            "dni": dni,
            "nombre": datos.get("nombres"),
            "apellido": datos.get("apellido"),
            "fecha_nacimiento": datos.get("fechaNacimiento"),
            "genero": genero if genero in ("M", "F", "X") else "X",
            "domicilio": f"{datos.get('calle', '')} {datos.get('numero', '')} {datos.get('piso', '')} {datos.get('departamento', '')}".strip(),
            "provincia": provincia.pk if provincia else None,
        }

        return {"success": True, "data": datos_mapeados, "datos_api": datos}

    except Exception:
        logger.exception("Error inesperado en consultar_datos_renaper")
        return {
            "success": False,
            "error": "Error interno inesperado al consultar Renaper",
        }
