import logging
import os
import re
import time
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth import logout, user_logged_in
from django.contrib.auth.views import redirect_to_login
from django.dispatch import receiver
from django.http import HttpResponse
from django.shortcuts import redirect

from core import rbac
from core.services.throttle import ip_cliente

logger = logging.getLogger("core.requests")


def _split_env_list(value):
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _is_dev_origin(origin):
    if not getattr(settings, "DEBUG", False):
        return False

    parsed = urlparse(origin)
    hostname = parsed.hostname or ""
    if hostname in ("localhost", "127.0.0.1", "0.0.0.0"):
        return True
    if hostname.startswith("192.168.") or hostname.startswith("10."):
        return True
    if hostname.startswith("172."):
        try:
            second = int(hostname.split(".")[1])
        except (IndexError, ValueError):
            return False
        return 16 <= second <= 31
    return False


class ApiCorsMiddleware:
    """CORS acotado a la API para clientes mobile/web de desarrollo."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.allowed_origins = set(_split_env_list(os.getenv("DJANGO_CORS_ALLOWED_ORIGINS", "")))

    def __call__(self, request):
        if request.path.startswith("/api/") and request.method == "OPTIONS":
            response = HttpResponse(status=200)
        else:
            response = self.get_response(request)

        if request.path.startswith("/api/"):
            self._add_cors_headers(request, response)
        return response

    def _add_cors_headers(self, request, response):
        origin = request.META.get("HTTP_ORIGIN", "")
        if not origin:
            return
        if origin not in self.allowed_origins and not _is_dev_origin(origin):
            return

        response["Access-Control-Allow-Origin"] = origin
        response["Access-Control-Allow-Credentials"] = "true"
        response["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Authorization, Content-Type, Accept, X-CSRFToken, X-Requested-With"
        response["Access-Control-Max-Age"] = "86400"
        response["Vary"] = "Origin"
        if request.META.get("HTTP_ACCESS_CONTROL_REQUEST_PRIVATE_NETWORK") == "true":
            response["Access-Control-Allow-Private-Network"] = "true"


class PortalCiudadanoMiddleware:
    """
    Impide que usuarios del grupo Ciudadanos accedan al backoffice.
    Si un ciudadano autenticado accede a una URL fuera de /portal/, se lo redirige.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Los checks de path van primero: cortan sin pagar la query de grupos.
        # `/media/` NO está exento (SEC-09): ahí viven los adjuntos del backoffice
        # y la exención dejaba que cualquier sesión de ciudadano los bajara.
        if (
            not request.path.startswith("/portal/")
            and not request.path.startswith("/static/")
            and rbac.es_ciudadano_portal(request.user)
        ):
            # SEC-29: «mi perfil» ya no existe (el portal ciudadano está apagado).
            # La barrera sigue siendo la misma; cambia solo a dónde se lo manda.
            return redirect("portal:home")
        return self.get_response(request)


#: Clave de la sesión donde vive el instante del último pedido (SEC-35).
CLAVE_ULTIMA_ACTIVIDAD = "last_activity"

#: Cada cuánto, como máximo, se reescribe esa clave. Sin este techo la sesión se
#: guardaría en **cada** request: un `UPDATE django_session` por clic en QA y en
#: dev (motor `db`), y un `SET` de Redis por clic en prd.
VENTANA_REFRESCO_SEGUNDOS = 60

#: Margen sobre ``SESSION_IDLE_TIMEOUT_MINUTES``. El contador del navegador mide
#: actividad del usuario (mouse, teclado) y el del servidor mide pedidos HTTP:
#: con el latido de ``idle-logout.js`` llegando una vez por minuto, el servidor
#: puede ir hasta ``VENTANA_REFRESCO_SEGUNDOS`` atrás del navegador. El margen
#: existe para que el servidor **nunca** corte antes que el aviso de la pantalla:
#: quien está trabajando no pierde lo que estaba cargando, y quien dejó la
#: pantalla abierta igual queda afuera al minuto siguiente.
MARGEN_INACTIVIDAD_SEGUNDOS = VENTANA_REFRESCO_SEGUNDOS


def minutos_de_inactividad():
    """Se lee en cada request, no al importar: así el setting se puede pisar."""
    try:
        return int(getattr(settings, "SESSION_IDLE_TIMEOUT_MINUTES", 0) or 0)
    except (TypeError, ValueError):
        return 0


def marcar_actividad(session, *, ahora=None):
    """Anota el instante del pedido, salteando las escrituras seguidas.

    La usa el middleware y también el `user_logged_in` de ``core.apps``: dejar la
    marca puesta en el login hace que el primer request de la sesión no tenga que
    escribirla, que es lo que mantiene los presupuestos de consultas donde estaban.
    """
    ahora = time.time() if ahora is None else ahora
    ultima = session.get(CLAVE_ULTIMA_ACTIVIDAD)
    if ultima is not None and ahora - float(ultima) < VENTANA_REFRESCO_SEGUNDOS:
        return
    session[CLAVE_ULTIMA_ACTIVIDAD] = ahora


@receiver(user_logged_in)
def _marcar_actividad_al_entrar(sender, request, user, **kwargs):
    """La sesión nace con su marca puesta.

    `login()` ya está escribiendo la sesión en ese momento, así que la marca sale
    gratis; sin esto, la escribiría el primer request de cada sesión —una consulta
    más justo en la pantalla que el usuario abre después de entrar—.
    """
    if request is not None and hasattr(request, "session"):
        marcar_actividad(request.session)


class ExpiracionPorInactividadMiddleware:
    """Cierra del lado del **servidor** la sesión que dejó de pedir (SEC-35).

    Hasta el Cambio 185 el cierre por inactividad era solo
    ``static/custom/js/idle-logout.js``: una cookie de sesión robada —o una
    pantalla abierta en una máquina compartida con el JS deshabilitado— seguía
    sirviendo las 24 h de ``SESSION_COOKIE_AGE``. El navegador sigue haciendo lo
    suyo (el aviso con cuenta regresiva y el POST al logout); esto es lo que hace
    que el límite **exista** aunque nadie ejecute ese JS.

    Dónde va en la cadena: después de ``AuthenticationMiddleware`` —necesita
    ``request.user``— y **antes** de ``PortalCiudadanoMiddleware``,
    ``BackofficeSingleSessionMiddleware`` y ``CambioContrasenaObligatorioMiddleware``:
    una sesión vencida no tiene por qué pagar el `get_or_create` del Profile ni
    terminar en la pantalla de cambio de clave; termina en el login.

    ``/api/`` queda exento igual que en ``CambioContrasenaObligatorioMiddleware``:
    la app de campo autentica por Token **dentro** de la vista, no tiene sesión que
    expirar, y acá su ``request.user`` todavía es anónimo.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        minutos = minutos_de_inactividad()
        usuario = getattr(request, "user", None)
        if minutos <= 0 or request.path.startswith("/api/") or not (usuario and usuario.is_authenticated):
            return self.get_response(request)

        ahora = time.time()
        ultima = request.session.get(CLAVE_ULTIMA_ACTIVIDAD)
        if ultima is not None and ahora - float(ultima) > minutos * 60 + MARGEN_INACTIVIDAD_SEGUNDOS:
            logger.info(
                "sesión cerrada por inactividad user=%s ip=%s",
                usuario.get_username(),
                ip_cliente(request),
            )
            logout(request)
            return redirect_to_login(request.get_full_path())

        marcar_actividad(request.session, ahora=ahora)
        return self.get_response(request)


# El link de inscripción pública lleva su token en la ruta: quien lea los logs
# podría inscribir gente en esa convocatoria. Se registra la forma, no el valor.
_RUTA_CON_TOKEN = re.compile(r"^(/portal/inscripcion/)[0-9a-fA-F-]{8,}(/.*)?$")


def _path_sin_secretos(path):
    coincide = _RUTA_CON_TOKEN.match(path or "")
    if not coincide:
        return path
    return f"{coincide.group(1)}<token>{coincide.group(2) or ''}"


class RequestLoggingMiddleware:
    """Loguea cada request HTTP con método, URL, usuario, IP, status y duración."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.monotonic()
        response = self.get_response(request)
        duration_ms = int((time.monotonic() - start) * 1000)

        user = getattr(request, "user", None)
        username = user.username if user and user.is_authenticated else "anon"
        ip = ip_cliente(request)

        log_request = logger.warning if duration_ms > settings.SLOW_REQUEST_MS else logger.info
        log_request(
            "%s %s user=%s ip=%s status=%s duration=%dms",
            request.method,
            _path_sin_secretos(request.path),
            username,
            ip,
            response.status_code,
            duration_ms,
        )

        return response
