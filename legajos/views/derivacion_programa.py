from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError

from programas.models import DerivacionPrograma
from ..services import DerivacionProgramaService

@login_required
def aceptar_derivacion_programa(request, derivacion_id):
    derivacion = get_object_or_404(DerivacionPrograma, id=derivacion_id)

    if derivacion.estado != 'PENDIENTE':
        messages.warning(request, 'Esta derivación ya fue procesada.')
        return redirect('legajos:programa_detalle', pk=derivacion.programa_destino.id)

    # Si es Ñachec, mostrar modal de validación
    if derivacion.programa_destino.tipo in ['NACHEC', 'ÑACHEC']:
        if request.method == 'GET':
            return render(
                request,
                'legajos/nachec/modal_aceptar_derivacion.html',
                DerivacionProgramaService.build_nachec_acceptance_context(derivacion),
            )

        if request.method == 'POST':
            try:
                result = DerivacionProgramaService.accept_nachec_derivacion(
                    derivacion_id=derivacion.id,
                    usuario=request.user,
                    payload=request.POST,
                )
                getattr(messages, result.status)(request, result.message)
            except ValidationError as exc:
                messages.error(request, exc.messages[0])
                return redirect('legajos:derivacion_aceptar', derivacion_id=derivacion_id)
            except Exception as exc:
                messages.error(request, f'Error al aceptar derivación: {exc}')

            return redirect('legajos:programa_detalle', pk=derivacion.programa_destino.id)

    # Flujo normal legacy
    try:
        result = DerivacionProgramaService.accept_derivacion(
            derivacion_id=derivacion.id,
            usuario=request.user,
        )
        messages.success(request, result.message)
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    except Exception as exc:
        messages.error(request, f'Error al aceptar derivación: {exc}')

    return redirect('legajos:programa_detalle', pk=derivacion.programa_destino.id)


@login_required
def rechazar_derivacion_programa(request, derivacion_id):
    derivacion = get_object_or_404(DerivacionPrograma, id=derivacion_id)

    if derivacion.estado != 'PENDIENTE':
        messages.warning(request, 'Esta derivación ya fue procesada.')
        return redirect('legajos:programa_detalle', pk=derivacion.programa_destino.id)

    try:
        result = DerivacionProgramaService.reject_derivacion(
            derivacion_id=derivacion.id,
            usuario=request.user,
            motivo_rechazo='Rechazado desde bandeja de derivaciones',
        )
        messages.success(request, result.message)
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    except Exception as exc:
        messages.error(request, f'Error al rechazar derivación: {exc}')

    return redirect('legajos:programa_detalle', pk=derivacion.programa_destino.id)
