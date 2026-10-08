"""Bandeja de derivaciones a programa: aceptar y rechazar.

Las dos rutas eran ``@login_required`` a secas y aceptaban **GET**, así que un
``<img src="/legajos/derivaciones-ciudadano/<id>/aceptar/">`` en cualquier página
—un correo, un chat, otro sistema— aceptaba la derivación con la sesión de quien
la mirara, sin capacidad y sin CSRF; aceptar crea además una
``InscripcionPrograma``. Ahora van con ``@require_POST`` (CSRF obligatorio) y
``@requiere("ciudadano.editar")`` (SEC-12).

**DECISIÓN CLIENTE D-12 = reusar ``ciudadano.editar``**, sin capacidad nueva:
mover una derivación es escribir sobre el legajo del ciudadano, que es
exactamente lo que esa capacidad habilita, y así el cambio no necesita migración
de datos ni re-tildar roles en PRD.
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from core.rbac import requiere
from programas.models import DerivacionPrograma

from ..services import DerivacionProgramaService


@requiere("ciudadano.editar")
@require_POST
def aceptar_derivacion_programa(request, derivacion_id):
    derivacion = get_object_or_404(DerivacionPrograma, id=derivacion_id)

    if derivacion.estado != "PENDIENTE":
        messages.warning(request, "Esta derivación ya fue procesada.")
        return redirect("legajos:programa_detalle", pk=derivacion.programa_destino.id)

    try:
        result = DerivacionProgramaService.accept_derivacion(
            derivacion_id=derivacion.id,
            usuario=request.user,
        )
        messages.success(request, result.message)
    except ValidationError as exc:
        messages.error(request, exc.messages[0])

    return redirect("legajos:programa_detalle", pk=derivacion.programa_destino.id)


@requiere("ciudadano.editar")
@require_POST
def rechazar_derivacion_programa(request, derivacion_id):
    derivacion = get_object_or_404(DerivacionPrograma, id=derivacion_id)

    if derivacion.estado != "PENDIENTE":
        messages.warning(request, "Esta derivación ya fue procesada.")
        return redirect("legajos:programa_detalle", pk=derivacion.programa_destino.id)

    try:
        result = DerivacionProgramaService.reject_derivacion(
            derivacion_id=derivacion.id,
            usuario=request.user,
            motivo_rechazo="Rechazado desde bandeja de derivaciones",
        )
        messages.success(request, result.message)
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    except Exception as exc:
        messages.error(request, f"Error al rechazar derivación: {exc}")

    return redirect("legajos:programa_detalle", pk=derivacion.programa_destino.id)
