"""Backoffice — eliminación (baja lógica en cascada) de la estructura de Becas.

Una vista por nivel. Todas son POST, piden su capacidad ``becas.<nivel>.eliminar``
con el alcance del Programa Becas y el alcance del objeto que ya usa el resto de la
pantalla. La regla de la cascada vive en ``programas.services.eliminacion``.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from programas.models import ProgramaSiis, Relevamiento, Segmento
from programas.services.autorizacion import (
    assert_alcance_relevamiento,
    convocatorias_visibles,
    programas_siis_visibles,
    puede_configurar_segmento,
)
from programas.services.eliminacion import (
    CAP_CONVOCATORIA_ELIMINAR,
    CAP_PROGRAMA_ELIMINAR,
    CAP_RELEVAMIENTO_ELIMINAR,
    CAP_SEGMENTO_ELIMINAR,
    EliminacionBloqueada,
    assert_alcance_programa_completo,
    assert_puede_eliminar,
    eliminar,
    mensaje_bloqueo,
    resumen_cascada,
)


def _eliminar_y_avisar(request, objeto, que, destino):
    try:
        marcados = eliminar(objeto, request.user)
    except EliminacionBloqueada as error:
        messages.error(request, mensaje_bloqueo(error, que))
    else:
        messages.success(request, f"Se eliminó {que} «{objeto}».{resumen_cascada(marcados)}")
    return redirect(destino)


@login_required
@require_POST
def programa_eliminar(request, pk):
    assert_puede_eliminar(request.user, CAP_PROGRAMA_ELIMINAR)
    programa = get_object_or_404(ProgramaSiis, pk=pk)
    if not programas_siis_visibles(request.user).filter(pk=programa.pk).exists():
        raise PermissionDenied("No tiene acceso a este programa.")
    assert_alcance_programa_completo(request.user, programa)
    return _eliminar_y_avisar(request, programa, "el programa", "becas:programas")


@login_required
@require_POST
def segmento_eliminar(request, pk):
    assert_puede_eliminar(request.user, CAP_SEGMENTO_ELIMINAR)
    segmento = get_object_or_404(Segmento, pk=pk)
    if not puede_configurar_segmento(request.user, segmento):
        raise PermissionDenied("No tiene acceso a este segmento.")
    return _eliminar_y_avisar(request, segmento, "el segmento", "becas:segmentos")


@login_required
@require_POST
def convocatoria_eliminar(request, pk):
    assert_puede_eliminar(request.user, CAP_CONVOCATORIA_ELIMINAR)
    convocatoria = get_object_or_404(convocatorias_visibles(request.user), pk=pk)
    return _eliminar_y_avisar(request, convocatoria, "la convocatoria", "becas:convocatorias")


@login_required
@require_POST
def relevamiento_eliminar(request, pk):
    assert_puede_eliminar(request.user, CAP_RELEVAMIENTO_ELIMINAR)
    relevamiento = get_object_or_404(Relevamiento.objects.select_related("convocatoria__segmento"), pk=pk)
    assert_alcance_relevamiento(request.user, relevamiento)
    return _eliminar_y_avisar(request, relevamiento, "el relevamiento", "becas:relevamientos")
