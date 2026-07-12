from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect

from programas.models import DerivacionPrograma

from ..services import DerivacionProgramaService


@login_required
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
    except Exception as exc:
        messages.error(request, f"Error al aceptar derivación: {exc}")

    return redirect("legajos:programa_detalle", pk=derivacion.programa_destino.id)


@login_required
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
