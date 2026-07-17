import logging
import os
import time
from urllib.parse import urlparse

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect

from core import rbac

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
        if (
            not request.path.startswith("/portal/")
            and not request.path.startswith("/static/")
            and not request.path.startswith("/media/")
            and rbac.es_ciudadano_portal(request.user)
        ):
            return redirect("portal:ciudadano_mi_perfil")
        return self.get_response(request)


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
        ip = request.META.get("HTTP_X_REAL_IP") or request.META.get("REMOTE_ADDR", "-")

        log_request = logger.warning if duration_ms > settings.SLOW_REQUEST_MS else logger.info
        log_request(
            "%s %s user=%s ip=%s status=%s duration=%dms",
            request.method,
            request.path,
            username,
            ip,
            response.status_code,
            duration_ms,
        )

        return response
