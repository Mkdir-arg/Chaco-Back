"""Helpers para guardar formularios de modales vía AJAX (sin recarga de página).

Patrón: la vista detecta la petición AJAX (header ``X-Requested-With``) y, si el
form es válido, devuelve ``{ok: true, target, html}`` donde ``html`` es el cuerpo
re-renderizado de la tabla/sección afectada (un partial). El JS reemplaza el
contenido de ``target`` con ese HTML. Si el form es inválido, devuelve
``{ok: false, errors}`` con status 400 para que el JS pinte los errores inline.

Las vistas siguen funcionando sin AJAX (fallback a redirect tradicional).
"""

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect
from django.template.loader import render_to_string


def is_ajax(request):
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


def ajax_ok(request, *, target, partial, context, message="Guardado."):
    """Respuesta de éxito: re-renderiza ``partial`` y lo manda para reemplazar
    el contenido de ``target`` (un selector CSS)."""
    html = render_to_string(partial, context, request=request)
    return JsonResponse({"ok": True, "target": target, "html": html, "message": message})


def ajax_redirect(request, url, message="Guardado.", level=messages.SUCCESS):
    """Respuesta de éxito que ordena al front navegar a ``url`` (ej. "guardar y
    configurar": crear la entidad y abrir su detalle).

    El front navega sin mostrar ``message``, así que el aviso se encola en el
    framework de messages de Django y lo muestra la página destino (``base.html``
    → ``nodo-toast``). ``message`` sigue en el JSON por compatibilidad."""
    messages.add_message(request, level, message)
    return JsonResponse({"ok": True, "redirect": url, "message": message})


def ajax_errors(form):
    """Respuesta de error de validación (status 400) con los errores del form."""
    return JsonResponse({"ok": False, "errors": form.errors}, status=400)


def errores_del_servicio(error, form=None):
    """Lo que un servicio rechaza (`ValidationError`), en la forma ``{campo: [mensajes]}`` del modal.

    Una clave que el formulario no tiene —`estado` cuando la reserva ya se liberó, `plaza`
    cuando quedó tomada— va al error general, el único lugar donde el modal la puede
    mostrar. Un `ValidationError` sin diccionario (lista o mensaje suelto) va entero ahí.

    Vive en `ajax_utils` y no en una vista porque lo necesitan los modales de varias
    pantallas de Dispositivos, y una vista que le pide un helper a otra vista es la arista
    que mide `programas.tests.test_arquitectura` (este módulo es su único exento).
    """

    if not hasattr(error, "error_dict"):
        return {"__all__": list(error.messages)}
    campos = form.fields if form is not None else {}
    errores = {}
    for campo, mensajes in error.message_dict.items():
        destino = campo if campo in campos else "__all__"
        errores.setdefault(destino, []).extend(mensajes)
    return errores


def rechazar(request, errores, volver):
    """Devuelve los errores al modal (AJAX, 400) o los encola como mensajes y vuelve."""

    if is_ajax(request):
        return JsonResponse({"ok": False, "errors": {k: list(v) for k, v in errores.items()}}, status=400)
    for mensajes in errores.values():
        for mensaje in mensajes:
            messages.error(request, mensaje)
    return redirect(volver)
