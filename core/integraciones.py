"""Lo que comparten las llamadas a servicios externos (SIIS-09 / PERF-09).

Tres piezas, las tres por el mismo motivo: **nginx corta el request a los 60 s**
(``nginx.conf:97`` y ``:172``, ``proxy_read_timeout 60s``) y el backoffice
encadena varias llamadas externas dentro de un mismo clic. «Aprobar» hace token
→ compatibilidad → alta en SIIS → correo de resolución; con los timeouts que
había —``(10, 30)`` para las tres llamadas a SIIS y 10 s por operación de
socket del SMTP— la cadena podía pasar los 120 s. El operador se llevaba un 504
**con el alta posiblemente hecha del otro lado**, y el 504 empuja al reintento
manual, que es justo lo que SIIS-01/SIIS-02 no quieren.

1. :data:`CADENAS` — qué llamadas externas encadena cada request, y cuánto puede
   tardar cada una en el peor caso. Es una **declaración**, no una medición: la
   verifica ``core.checks.presupuesto_de_llamadas_externas`` (``check --deploy``,
   o sea el CI y la etapa de verificación del deploy). Subir un timeout o
   encadenar una llamada más deja el check en rojo, que es la única forma de que
   «la suma entra en los 60 s» siga siendo cierta dentro de seis meses.
2. :class:`Cortacircuito` — un servicio que ya falló tres veces seguidas no se
   vuelve a consultar por un minuto. Con la Gran Base caída, cada paso 1 del link
   público retenía un hilo hasta agotar el timeout; el cortacircuito lo baja a
   cero y la identidad cae a ``manual``, que es el camino que el Cambio 57 ya
   tiene previsto.
3. :func:`sesion_http` — un ``requests.Session`` por módulo, con su pool. Sin
   sesión, cada llamada abre una conexión TLS nueva contra el mismo host.

Los valores de los timeouts son el default de **D-S09**: consultas ``(5, 10)``,
alta ``(5, 20)``, ``EMAIL_TIMEOUT`` 5.
"""

import logging
from http.cookiejar import CookiePolicy

import requests
from django.conf import settings
from django.core.cache import cache
from requests.adapters import HTTPAdapter

logger = logging.getLogger(__name__)

#: Techo de red por request. nginx corta a los 60 s: los 5 que faltan son para
#: todo lo que no es red (consultas a la base, render de la plantilla).
PRESUPUESTO_SEGUNDOS = 55

#: Cuánto puede tardar, como mucho, cada tipo de llamada externa. Son
#: ``connect + read``: el peor caso de ``requests`` es agotar los dos.
COSTOS = {
    "siis.token": lambda: settings.SIIS_API_CONNECT_TIMEOUT + settings.SIIS_API_TIMEOUT_TOKEN,
    "siis.consulta": lambda: settings.SIIS_API_CONNECT_TIMEOUT + settings.SIIS_API_TIMEOUT_CONSULTA,
    "siis.alta": lambda: settings.SIIS_API_CONNECT_TIMEOUT + settings.SIIS_API_TIMEOUT,
    "personas.token": lambda: settings.PERSONAS_API_CONNECT_TIMEOUT + settings.PERSONAS_API_TIMEOUT,
    "personas.consulta": lambda: settings.PERSONAS_API_CONNECT_TIMEOUT + settings.PERSONAS_API_TIMEOUT,
    "renaper.login": lambda: settings.RENAPER_CONNECT_TIMEOUT + settings.RENAPER_TIMEOUT,
    "renaper.consulta": lambda: settings.RENAPER_CONNECT_TIMEOUT + settings.RENAPER_TIMEOUT,
    # El paso 1 del link público verifica el token contra Google **antes** de
    # consultar identidad: es parte de la cadena, no algo aparte.
    "recaptcha": lambda: settings.RECAPTCHA_CONNECT_TIMEOUT + settings.RECAPTCHA_TIMEOUT,
    # ``EMAIL_TIMEOUT`` es por operación de socket, no por envío. Se cuenta una
    # vez: el envío de un correo son varias operaciones, pero la que puede
    # colgarse contra un SMTP que no responde es la que abre la conexión.
    "smtp": lambda: settings.EMAIL_TIMEOUT,
}

#: Las cadenas de llamadas externas que vive un request. El token de SIIS se
#: cuenta **una sola vez** por cadena aunque lo pidan dos llamadas: está en
#: caché compartida con el TTL que informa SIIS (``expires_in - 60``), así que
#: dentro de un mismo request no se pide dos veces salvo que haya un 401 de por
#: medio —y un 401 llega rápido, no agota ningún timeout—.
CADENAS = {
    "becas · aprobar un caso": ("siis.token", "siis.consulta", "siis.alta", "smtp"),
    "becas · rechazar un caso": ("siis.token", "siis.consulta", "smtp"),
    "becas · promover desde la lista de espera": ("siis.token", "siis.alta", "smtp"),
    "becas · agregar a la lista de espera": ("smtp",),
    "becas · revalidar la identidad": ("personas.token", "personas.consulta"),
    # El captcha va primero y después la identidad: las tres llamadas son del
    # mismo POST. El captcha no estaba declarado y es la más lenta de las tres.
    "link público · paso 1 (identificar)": ("recaptcha", "personas.token", "personas.consulta"),
    "link público · paso 2 (enviar la inscripción)": ("smtp",),
    "app de campo · identificar": ("personas.token", "personas.consulta"),
    "legajos · consultar RENAPER": ("renaper.login", "renaper.consulta"),
    "usuarios · alta con clave provisoria": ("smtp",),
}


def costo(llamada):
    """Segundos que puede tardar ``llamada`` en el peor caso."""
    return COSTOS[llamada]()


def costo_de_cadena(nombre):
    """Segundos que puede tardar, en el peor caso, el request ``nombre``."""
    return sum(costo(llamada) for llamada in CADENAS[nombre])


def cadenas_fuera_de_presupuesto():
    """``[(nombre, segundos)]`` de las cadenas que no entran en el presupuesto."""
    excedidas = []
    for nombre in CADENAS:
        segundos = costo_de_cadena(nombre)
        if segundos > PRESUPUESTO_SEGUNDOS:
            excedidas.append((nombre, segundos))
    return excedidas


# ── Cortacircuito ───────────────────────────────────────────────────────────

#: Fallas de red seguidas que abren el cortacircuito.
FALLAS_PARA_ABRIR = 3
#: Cuánto se deja de consultar al servicio una vez abierto.
PAUSA_SEGUNDOS = 60
#: Cuánto dura el contador de fallas sin que pase nada más. Más largo que la
#: pausa: si no, con tráfico ralo las fallas nunca se acumulan.
VENTANA_SEGUNDOS = 300


class Cortacircuito:
    """Deja de consultar un servicio externo que falla sistemáticamente.

    Cuenta **solo fallas de red** (timeout, conexión rechazada, respuesta
    ilegible): un 4xx o un «no encontrado» son respuestas, el servicio está
    sano. Tres seguidas lo abren por un minuto; durante ese minuto quien
    pregunta recibe el «no se pudo consultar» sin tocar la red.

    El estado vive en la caché, así que lo comparten los procesos del pod (en
    producción es Redis; en dev, LocMem por proceso, que alcanza). El conteo es
    *best effort* y no toma candado a propósito: dos pedidos a la vez pueden
    pisarse un incremento, y el costo de eso es abrir un pedido más tarde. Un
    candado por cada llamada externa costaría más que lo que ahorra.
    """

    def __init__(self, nombre, fallas=FALLAS_PARA_ABRIR, pausa=PAUSA_SEGUNDOS, ventana=VENTANA_SEGUNDOS):
        self.nombre = nombre
        self.fallas = fallas
        self.pausa = pausa
        self.ventana = ventana

    @property
    def _clave_fallas(self):
        return f"cortacircuito:{self.nombre}:fallas"

    @property
    def _clave_abierto(self):
        return f"cortacircuito:{self.nombre}:abierto"

    def abierto(self):
        return bool(cache.get(self._clave_abierto))

    def registrar_falla(self):
        """Suma una falla y abre el cortacircuito si ya van ``fallas`` seguidas."""
        seguidas = (cache.get(self._clave_fallas) or 0) + 1
        cache.set(self._clave_fallas, seguidas, self.ventana)
        if seguidas >= self.fallas:
            cache.set(self._clave_abierto, True, self.pausa)
            cache.delete(self._clave_fallas)
            logger.warning(
                "cortacircuito abierto: %s falló %s veces seguidas; no se consulta por %s s.",
                self.nombre,
                seguidas,
                self.pausa,
            )

    def registrar_exito(self):
        """El servicio contestó: se borra lo acumulado."""
        cache.delete(self._clave_fallas)
        cache.delete(self._clave_abierto)


# ── Sesión HTTP ─────────────────────────────────────────────────────────────


class SinCookies(CookiePolicy):
    """Rechaza toda cookie, en las dos direcciones.

    Una ``Session`` de módulo vive lo que vive el proceso y la comparten todos
    los requests que pasen por él. Su *cookie jar* es estado global: una cookie
    de sesión que devuelva el servicio externo se guardaría una vez y se
    reenviaría en las llamadas que ese proceso haga **por otras personas**. Las
    tres integraciones autentican con token en el header y ninguna necesita
    cookies, así que lo barato y seguro es no tener jar.
    """

    netscape = True
    rfc2965 = False
    hide_cookie2 = True

    def set_ok(self, cookie, request):
        return False

    def return_ok(self, cookie, request):
        return False

    def domain_return_ok(self, domain, request):
        return False

    def path_return_ok(self, path, request):
        return False


def sesion_http(pool_maxsize=10):
    """``requests.Session`` con pool acotado y sin cookies, una por módulo.

    Sin sesión, cada llamada abre una conexión TLS nueva contra el mismo host.
    El tope del pool es lo que impide que un servicio lento acumule sockets.

    Se comparte entre hilos (daphne corre las vistas sync en un pool de hilos):
    ``urllib3`` es seguro para eso. El *cookie jar* no lo es —es estado
    compartido entre usuarios—, así que se le pone una política que rechaza
    todo (:class:`SinCookies`).
    """
    sesion = requests.Session()
    sesion.cookies.set_policy(SinCookies())
    adaptador = HTTPAdapter(pool_maxsize=pool_maxsize, pool_connections=pool_maxsize)
    sesion.mount("https://", adaptador)
    sesion.mount("http://", adaptador)
    return sesion
