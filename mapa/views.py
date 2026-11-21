"""`/mapa/` y su API JSON de puntos (Cambio 493, fase 3).

La pantalla exige `mapa.ver`; cada capa además filtra por la regla de su módulo (`mapa.services`). La API
(`/mapa/api/puntos/`) solo toca el modelo `Punto`: lista con `mapa.ver`, y crea, mueve y borra con `mapa.editar`.
Responde siempre JSON, también el 403 (la llama el `fetch` de la pantalla), y usa la protección CSRF de Django.
"""

import json
from functools import wraps

from django.http import JsonResponse, QueryDict
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods

from core import rbac
from core.rbac import requiere
from mapa import services
from mapa.forms import PosicionForm, PuntoForm
from mapa.models import Punto

MENSAJE_SIN_PERMISO = "No tenés permiso para hacer esto en el mapa."


def _api(capacidad):
    """Como ``@requiere``, pero en JSON: 401 sin sesión y 403 sin la capacidad."""

    def decorador(vista):
        @wraps(vista)
        def envuelta(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return JsonResponse({"ok": False, "message": "Tu sesión terminó. Volvé a ingresar."}, status=401)
            if not rbac.puede(request.user, capacidad):
                return JsonResponse({"ok": False, "message": MENSAJE_SIN_PERMISO}, status=403)
            return vista(request, *args, **kwargs)

        return envuelta

    return decorador


def _datos(request):
    """El cuerpo de un PATCH: JSON o formulario."""

    if (request.content_type or "").startswith("application/json"):
        try:
            cuerpo = json.loads(request.body or b"{}")
        except ValueError:
            return None
        return cuerpo if isinstance(cuerpo, dict) else None
    return QueryDict(request.body)


def _errores(form):
    return JsonResponse({"ok": False, "errors": {campo: list(msgs) for campo, msgs in form.errors.items()}}, status=400)


@requiere(services.CAP_VER)
def mapa(request):
    datos = services.capas_del_mapa(request.user)
    return render(
        request,
        "mapa/mapa.html",
        {
            **datos,
            "categorias": services.categorias(),
            "form": PuntoForm() if datos["editable"] else None,
        },
    )


@_api(services.CAP_VER)
@require_http_methods(["GET", "POST"])
def puntos(request):
    editable = services.puede_editar(request.user)
    if request.method == "GET":
        lista = services.puntos_sueltos()
        return JsonResponse({"ok": True, "puntos": [services.punto_de_punto(p, editable=editable) for p in lista]})
    if not editable:
        return JsonResponse({"ok": False, "message": MENSAJE_SIN_PERMISO}, status=403)
    form = PuntoForm(request.POST)
    if not form.is_valid():
        return _errores(form)
    punto = form.save(commit=False)
    punto.cargado_por = request.user
    punto.save()
    datos = services.punto_de_punto(punto, editable=True)
    item = render_to_string(
        "components/_item_lista.html", {"nombre": datos["titulo"], "meta": datos["subtitulo"], "clave": datos["id"]}
    )
    return JsonResponse(
        {
            "ok": True,
            "punto": datos,
            "item": item,
            "message": f"Agregamos «{punto.nombre}» al mapa.",
        },
        status=201,
    )


@_api(services.CAP_EDITAR)
@require_http_methods(["PATCH", "DELETE"])
def punto(request, pk):
    obj = get_object_or_404(Punto.objects.select_related("cargado_por"), pk=pk)
    if request.method == "DELETE":
        nombre = obj.nombre
        obj.delete()
        return JsonResponse({"ok": True, "message": f"Eliminamos «{nombre}» del mapa."})
    datos = _datos(request)
    if datos is None:
        return JsonResponse({"ok": False, "message": "El pedido no se pudo leer."}, status=400)
    form = PosicionForm(datos, instance=obj)
    if not form.is_valid():
        return _errores(form)
    form.save()
    return JsonResponse(
        {
            "ok": True,
            "punto": services.punto_de_punto(obj, editable=True),
            "message": f"Guardamos la nueva ubicación de «{obj.nombre}».",
        }
    )
