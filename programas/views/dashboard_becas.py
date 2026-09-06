"""Solapa «Dashboard» del programa Becas (análisis #366, Cambio 64).

Dos vistas de solo lectura: los datos en JSON para la solapa y la exportación.
Ninguna calcula nada por su cuenta: todo sale de ``programas.services.dashboard_becas``.

Permisos (RN-1, RN-2): ``becas.reportes.ver`` para ver y ``becas.reportes.exportar`` para
descargar, evaluados sobre el programa Becas igual que en el módulo de reportes, más el
programa SIIS visible para el usuario (mismo criterio que la pantalla del programa).
"""

import logging

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseBadRequest, HttpResponseServerError, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_GET

from core.rbac import puede
from programas.forms_reportes import DashboardBecasFiltroForm
from programas.models import ProgramaSiis
from programas.services import dashboard_becas
from programas.services.autorizacion import convocatorias_visibles, programa_becas
from programas.services.exportacion_reportes import respuesta_libro, respuesta_reporte

logger = logging.getLogger(__name__)

CAP_VER = "becas.reportes.ver"
CAP_EXPORTAR = "becas.reportes.exportar"
FORMATOS = ("xlsx", "csv")


def puede_ver_dashboard(user):
    return puede(user, CAP_VER, programa=programa_becas(user))


def puede_exportar_dashboard(user):
    return puede(user, CAP_EXPORTAR, programa=programa_becas(user))


def _programa_o_403(request, pk, capacidad):
    """El programa pedido, si el usuario tiene la capacidad y además lo ve."""
    # Import diferido: ``configuracion`` importa este módulo para el contexto de la pantalla.
    from programas.views.configuracion import _programas_qs

    if not puede(request.user, capacidad, programa=programa_becas(request.user)):
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


def _mensaje_error(etapa, exc):
    """Texto para la pantalla: qué etapa falló y el tipo de error, sin detalles internos.
    El traceback completo va al log del servidor con ``logger.exception``."""
    return f"No se pudieron calcular {etapa} ({type(exc).__name__}). El error quedó registrado en el servidor."


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
    # Por etapas: si fallan las métricas no hay tablero (500 con la etapa); si falla
    # solo la pregunta elegida, el tablero se muestra igual y la tarjeta avisa. En los
    # dos casos el traceback queda en el log del servidor.
    recalcular = request.GET.get("recalcular") == "1"
    try:
        # El alcance (ids de segmentos, convocatorias y relevamientos) se resuelve una
        # sola vez y lo comparten la clave de caché, las métricas y las respuestas.
        alcance = dashboard_becas.resolver_alcance(request.user, programa, filtros)
        datos, desde_cache = dashboard_becas.metricas_cacheadas(
            request.user, programa, filtros, recalcular=recalcular, alcance=alcance
        )
    except Exception as exc:  # noqa: BLE001 — se registra y se informa la etapa
        logger.exception("dashboard becas: fallo al calcular las métricas (programa=%s, filtros=%s)", pk, filtros)
        return JsonResponse({"errores": [_mensaje_error("las métricas", exc)]}, status=500)
    clave = form.clave_pregunta()
    respuestas, avisos = None, []
    if clave:
        try:
            distribucion, _ = dashboard_becas.distribucion_cacheada(
                request.user, programa, filtros, clave, recalcular=recalcular, alcance=alcance, catalogo=form.preguntas
            )
            respuestas = distribucion.to_dict()
        except Exception as exc:  # noqa: BLE001
            logger.exception("dashboard becas: fallo al calcular las respuestas (programa=%s, pregunta=%s)", pk, clave)
            avisos.append(_mensaje_error("las respuestas de la pregunta elegida", exc))
    convocatoria = form.cleaned_data.get("convocatoria")
    return JsonResponse(
        {
            "datos": datos.to_dict(),
            "desde_cache": desde_cache,
            "respuestas": respuestas,
            "avisos": avisos,
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
    codigo = request.GET.get("bloque", "resumen")
    try:
        alcance = dashboard_becas.resolver_alcance(request.user, programa, filtros)
        datos, _ = dashboard_becas.metricas_cacheadas(request.user, programa, filtros, alcance=alcance)
        distribuciones = dashboard_becas.distribuciones_respuestas(
            request.user, programa, filtros, alcance=alcance, catalogo=form.preguntas
        )
        bloques = dashboard_becas.bloques_exportacion(datos, distribuciones)
        nombre = f"becas_dashboard_{slugify(programa.nombre) or programa.pk}_{timezone.localdate():%Y-%m-%d}"
        if formato == "xlsx":
            return respuesta_libro(list(bloques.values()), nombre, alcance=datos.alcance)
        if codigo not in bloques:
            return HttpResponseBadRequest("Bloque de exportación no válido.")
        _, reporte = bloques[codigo]
        return respuesta_reporte(reporte, "csv", f"{nombre}_{codigo}", alcance=datos.alcance)
    except Exception as exc:  # noqa: BLE001 — incluye armar el archivo: un texto raro no puede dar un 500 mudo
        logger.exception("dashboard becas: fallo al exportar (programa=%s, formato=%s, bloque=%s)", pk, formato, codigo)
        return HttpResponseServerError(_mensaje_error("los datos para exportar", exc))


@login_required
@require_GET
def programa_dashboard_respuestas_xlsx(request, pk, convocatoria_pk):
    """Excel con **un registro por caso** de la convocatoria y una columna por pregunta
    (Cambio 65). Exige la capacidad de exportar y que la convocatoria sea del programa
    y esté dentro del alcance del usuario; si no, 404 como el resto del backoffice."""
    programa = _programa_o_403(request, pk, CAP_EXPORTAR)
    convocatoria = get_object_or_404(
        convocatorias_visibles(request.user).filter(segmento__programa=programa).select_related("segmento"),
        pk=convocatoria_pk,
    )
    try:
        reporte, alcance = dashboard_becas.respuestas_por_persona(convocatoria)
        nombre = f"becas_respuestas_{slugify(convocatoria.nombre) or convocatoria.pk}_{timezone.localdate():%Y-%m-%d}"
        return respuesta_libro([("Respuestas", reporte)], nombre, alcance=alcance)
    except Exception as exc:  # noqa: BLE001
        logger.exception("dashboard becas: fallo al exportar respuestas por persona (convocatoria=%s)", convocatoria_pk)
        return HttpResponseServerError(_mensaje_error("las respuestas por persona", exc))
