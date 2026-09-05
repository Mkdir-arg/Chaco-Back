"""Solapa «Dashboard» del programa Becas (análisis #366, Cambio 64).

Dos vistas de solo lectura: los datos en JSON para la solapa y la exportación.
Ninguna calcula nada por su cuenta: todo sale de ``programas.services.dashboard_becas``.

Permisos (RN-1, RN-2): ``becas.reportes.ver`` para ver y ``becas.reportes.exportar`` para
descargar, evaluados sobre el programa Becas igual que en el módulo de reportes, más el
programa SIIS visible para el usuario (mismo criterio que la pantalla del programa).
"""

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_GET

from core.rbac import puede
from programas.forms_reportes import DashboardBecasFiltroForm
from programas.models import ProgramaSiis
from programas.services import dashboard_becas
from programas.services.autorizacion import programa_becas
from programas.services.exportacion_reportes import respuesta_libro, respuesta_reporte

CAP_VER = "becas.reportes.ver"
CAP_EXPORTAR = "becas.reportes.exportar"
FORMATOS = ("xlsx", "csv")


def puede_ver_dashboard(user):
    return puede(user, CAP_VER, programa=programa_becas())


def puede_exportar_dashboard(user):
    return puede(user, CAP_EXPORTAR, programa=programa_becas())


def _programa_o_403(request, pk, capacidad):
    """El programa pedido, si el usuario tiene la capacidad y además lo ve."""
    # Import diferido: ``configuracion`` importa este módulo para el contexto de la pantalla.
    from programas.views.configuracion import _programas_qs

    if not puede(request.user, capacidad, programa=programa_becas()):
        raise PermissionDenied("No tiene acceso al dashboard de Becas.")
    programa = get_object_or_404(ProgramaSiis, pk=pk)
    if not _programas_qs(request.user).filter(pk=programa.pk).exists():
        raise PermissionDenied("No tiene acceso a este programa.")
    return programa


def _errores(form):
    errores = list(form.non_field_errors())
    for campo, lista in form.errors.items():
        if campo != "__all__":
            errores.extend(f"{form.fields[campo].label or campo}: {e}" for e in lista)
    return errores or ["Revisá los filtros ingresados."]


@login_required
@require_GET
def programa_dashboard_datos(request, pk):
    """JSON con todos los bloques para el recorte pedido (CA-2). ``?recalcular=1``
    saltea la caché (RN-17)."""
    programa = _programa_o_403(request, pk, CAP_VER)
    form = DashboardBecasFiltroForm(request.GET, user=request.user, programa=programa)
    if not form.is_valid():
        return JsonResponse({"errores": _errores(form)}, status=400)
    filtros = form.filtros()
    datos, desde_cache = dashboard_becas.metricas_cacheadas(
        request.user, programa, filtros, recalcular=request.GET.get("recalcular") == "1"
    )
    clave = form.clave_pregunta()
    respuestas = (
        dashboard_becas.distribucion_respuestas(request.user, programa, filtros, clave).to_dict() if clave else None
    )
    convocatoria = form.cleaned_data.get("convocatoria")
    return JsonResponse(
        {
            "datos": datos.to_dict(),
            "desde_cache": desde_cache,
            "respuestas": respuestas,
            "opciones": {"relevamientos": form.relevamientos_de(convocatoria)},
            # Lo que quedó aplicado después de limpiar selecciones inválidas (RN-5, RN-6).
            "filtros_aplicados": {
                "periodo": form.cleaned_data.get("periodo"),
                "segmento": getattr(form.cleaned_data.get("segmento"), "pk", None),
                "convocatoria": getattr(convocatoria, "pk", None),
                "relevamiento": getattr(form.cleaned_data.get("relevamiento"), "pk", None),
                "canal": form.cleaned_data.get("canal") or "",
                "pregunta": clave,
            },
        }
    )


@login_required
@require_GET
def programa_dashboard_exportar(request, pk, formato):
    """``xlsx`` → libro con una hoja por bloque · ``csv?bloque=<codigo>`` → un bloque.
    Siempre con los filtros aplicados y el alcance en el encabezado (RN-16)."""
    if formato not in FORMATOS:
        return HttpResponseBadRequest("Formato de exportación no válido.")
    programa = _programa_o_403(request, pk, CAP_EXPORTAR)
    form = DashboardBecasFiltroForm(request.GET, user=request.user, programa=programa)
    if not form.is_valid():
        return HttpResponseBadRequest(" ".join(_errores(form)))
    filtros = form.filtros()
    datos, _ = dashboard_becas.metricas_cacheadas(request.user, programa, filtros)
    distribuciones = dashboard_becas.distribuciones_respuestas(request.user, programa, filtros)
    bloques = dashboard_becas.bloques_exportacion(datos, distribuciones)
    nombre = f"becas_dashboard_{slugify(programa.nombre) or programa.pk}_{timezone.localdate():%Y-%m-%d}"
    if formato == "xlsx":
        return respuesta_libro(list(bloques.values()), nombre, alcance=datos.alcance)
    codigo = request.GET.get("bloque", "resumen")
    if codigo not in bloques:
        return HttpResponseBadRequest("Bloque de exportación no válido.")
    _, reporte = bloques[codigo]
    return respuesta_reporte(reporte, "csv", f"{nombre}_{codigo}", alcance=datos.alcance)
