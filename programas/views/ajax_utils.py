"""Helpers para guardar formularios de modales vía AJAX (sin recarga de página).

Patrón: la vista detecta la petición AJAX (header ``X-Requested-With``) y, si el
form es válido, devuelve ``{ok: true, target, html}`` donde ``html`` es el cuerpo
re-renderizado de la tabla/sección afectada (un partial). El JS reemplaza el
contenido de ``target`` con ese HTML. Si el form es inválido, devuelve
``{ok: false, errors}`` con status 400 para que el JS pinte los errores inline.

Las vistas siguen funcionando sin AJAX (fallback a redirect tradicional).
"""

from django.http import JsonResponse
from django.template.loader import render_to_string


def is_ajax(request):
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


def ajax_ok(request, *, target, partial, context, message="Guardado."):
    """Respuesta de éxito: re-renderiza ``partial`` y lo manda para reemplazar
    el contenido de ``target`` (un selector CSS)."""
    html = render_to_string(partial, context, request=request)
    return JsonResponse({"ok": True, "target": target, "html": html, "message": message})


def ajax_redirect(url, message="Guardado."):
    """Respuesta de éxito que ordena al front navegar a ``url`` (ej. "guardar y
    configurar": crear la entidad y abrir su detalle)."""
    return JsonResponse({"ok": True, "redirect": url, "message": message})


def ajax_errors(form):
    """Respuesta de error de validación (status 400) con los errores del form."""
    return JsonResponse({"ok": False, "errors": form.errors}, status=400)
