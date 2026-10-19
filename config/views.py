import functools
import logging

from django.db import close_old_connections
from django.http import HttpResponseServerError
from django.shortcuts import render
from django.views import defaults
from django.views.csrf import csrf_failure as csrf_failure_django

logger = logging.getLogger(__name__)

# Qué ve el usuario si ni siquiera se puede renderizar la plantilla de error
# (la base de datos está caída y `includes/base.html` consulta permisos).
HTML_500_MINIMO = (
    '<!doctype html><html lang="es"><head><meta charset="utf-8">'
    "<title>Error del servidor</title></head><body>"
    "<h1>Error del servidor</h1>"
    "<p>Ocurrió un error inesperado. Intentá de nuevo en unos minutos.</p>"
    "</body></html>"
)


def _con_conexiones_frescas(vista):
    """Corre una vista de error sin heredar una conexión muerta del hilo.

    Django 5.2 en modo async arma la respuesta de error con
    `sync_to_async(response_for_exception, thread_sensitive=False)`
    (`django/core/handlers/exception.py`): corre en un hilo del pool que NO es
    el de `close_old_connections` (señales `request_started/finished`). Ese hilo
    puede guardar una conexión de un error anterior que MariaDB ya cerró por
    inactividad, y el render de `404.html`/`500.html` (que consulta permisos en
    el context processor y en templatetags) muere con `OperationalError 2006`.

    Se usa `close_old_connections()` y no `connections.close_all()`: cierra solo
    la conexión inutilizable o vencida. Con `CONN_MAX_AGE=0` (daphne) eso es
    siempre; con `CONN_MAX_AGE=60` (gunicorn) una conexión viva de un request
    sync en curso se conserva.
    """

    @functools.wraps(vista)
    def envuelta(request, *args, **kwargs):
        close_old_connections()
        try:
            return vista(request, *args, **kwargs)
        finally:
            close_old_connections()

    return envuelta


@_con_conexiones_frescas
def bad_request(request, exception, template_name="400.html"):
    return defaults.bad_request(request, exception, template_name=template_name)


@_con_conexiones_frescas
def permission_denied(request, exception, template_name="403.html"):
    return defaults.permission_denied(request, exception, template_name=template_name)


@_con_conexiones_frescas
def page_not_found(request, exception, template_name="404.html"):
    return defaults.page_not_found(request, exception, template_name=template_name)


@_con_conexiones_frescas
def server_error(request, template_name="500.html"):
    """Render the 500 error page with the request in the context.

    Si el render completo falla (la base de verdad caída), devuelve un 500
    mínimo sin base de datos en vez de propagar otra excepción.
    """
    try:
        return render(request, template_name, status=500)
    except Exception:
        logger.exception("No se pudo renderizar %s; se devuelve el 500 mínimo", template_name)
        return HttpResponseServerError(HTML_500_MINIMO, content_type="text/html; charset=utf-8")


def _destino_seguro(request):
    """La ruta a la que se puede volver, sin abrir un redirect a otro dominio.

    `//otro-dominio` es una ruta válida para el navegador pero una URL absoluta
    dentro de un `href`, así que no alcanza con exigir que empiece con «/».
    """
    destino = request.get_full_path()
    if destino.startswith("/") and not destino.startswith("//"):
        return destino
    return "/portal/"


def csrf_failure(request, reason=""):
    """CSRF fallido: en el portal público la pantalla tiene que ser recuperable.

    El 403 crudo de Django no le dice nada a un ciudadano ni le deja continuar, y
    en un formulario público la causa habitual no es un ataque: el backoffice y el
    portal comparten dominio y `django.contrib.auth.login` rota la cookie CSRF de
    todo el navegador, así que un formulario abierto en otra pestaña se queda con
    un token que ya no vale.

    Fuera del portal se conserva la pantalla de Django tal como estaba: el
    backoffice es una superficie con login y su 403 no se toca en este cambio.
    """
    if request.path.startswith("/portal/"):
        return render(
            request,
            "portal/sesion_vencida.html",
            {"volver": _destino_seguro(request), "motivo": reason},
            status=403,
        )
    return csrf_failure_django(request, reason=reason)
