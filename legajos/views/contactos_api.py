"""APIs JSON del detalle de ciudadano y del legajo.

Hasta la auditoría oct-2026 todas estas vistas llevaban **solo**
``@login_required``: cualquier cuenta de backoffice —un rol de Becas, uno de
Dispositivos, el usuario recién creado sin un solo rol— listaba los documentos
de cualquier ciudadano, los borraba con un ``DELETE`` (hard delete, sin papelera)
y leía su timeline, sus alertas y su score de riesgo. El barrido de RED-89 lo
midió ruta por ruta. Acá se cierra con capacidades:

- ``ciudadano.ver`` para leer (SEC-10 en los archivos, SEC-11 en el resto).
- ``ciudadano.editar`` para subir y borrar archivos (SEC-10).
- el dueño en la URL para borrar, así el borrado queda acotado al ciudadano o al
  legajo del que cuelga el adjunto (SEC-10).

``timeline_ciudadano_api``, ``alertas_ciudadano_api`` y ``prediccion_riesgo_api``
llevaban ``ciudadano.ver`` como **piso** mientras se decidía D-11. Resuelta la
decisión (**D-11 = Sí**), las tres piden ``ciudadano.sensible``: el timeline, el
texto de la alerta y el score de riesgo son datos sensibles del ciudadano, no
una ficha de consulta. Es la segunda mitad de SEC-11, coordinada con el
WebSocket de alertas (G1c-04), que pide la misma capacidad.
"""

import logging

from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404

from core.rbac import requiere

from ..models import Ciudadano, LegajoAtencion
from ..selectors import (
    build_ciudadano_actividades_payload,
    build_ciudadano_archivos_payload,
    build_ciudadano_timeline_payload,
    build_legajo_archivos_payload,
    build_legajo_evolucion_payload,
)
from ..services import AlertasService, ContactosFilesError, eliminar_archivo_de_objeto, subir_archivos_para_objeto
from ..services.ml_predictor import RiskPredictor
from .mensajes import ERROR_GENERICO

logger = logging.getLogger(__name__)


@login_required
@requiere("ciudadano.ver")
def actividades_ciudadano_api(request, ciudadano_id):
    """API para obtener todas las actividades de un ciudadano"""
    try:
        return JsonResponse(build_ciudadano_actividades_payload(ciudadano_id))
    except Http404:
        raise
    except Exception:
        logger.exception("Error armando las actividades del ciudadano %s", ciudadano_id)
        return JsonResponse({"results": [], "count": 0, "error": ERROR_GENERICO}, status=500)


@login_required
@requiere("ciudadano.editar")
def subir_archivos_ciudadano(request, ciudadano_id):
    """Vista para subir archivos a un ciudadano"""
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Método no permitido"}, status=405)

    ciudadano = get_object_or_404(Ciudadano, id=ciudadano_id)
    return _subir_archivos(request, ciudadano)


@login_required
@requiere("ciudadano.editar")
def subir_archivos_legajo(request, legajo_id):
    """Vista para subir archivos a un legajo"""
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Método no permitido"}, status=405)

    legajo = get_object_or_404(LegajoAtencion, id=legajo_id)
    return _subir_archivos(request, legajo)


def _subir_archivos(request, instance):
    """Cuerpo común de las dos subidas: el dueño ya viene resuelto."""
    try:
        archivos_subidos = subir_archivos_para_objeto(
            instance,
            request.FILES.getlist("archivo"),
            request.POST.get("etiqueta", ""),
        )
    except ContactosFilesError as exc:
        # Mensajes de negocio ("Formato no permitido", "es muy grande"): los
        # escribe el servicio para que el usuario sepa qué corregir.
        return JsonResponse({"success": False, "error": str(exc)}, status=400)
    except Exception:
        logger.exception("Error subiendo archivos a %s %s", type(instance).__name__, instance.pk)
        return JsonResponse({"success": False, "error": ERROR_GENERICO}, status=500)

    return JsonResponse(
        {
            "success": True,
            "archivos": archivos_subidos,
            "mensaje": f"{len(archivos_subidos)} archivo(s) subido(s) exitosamente",
        }
    )


@login_required
@requiere("ciudadano.ver")
def archivos_ciudadano_api(request, ciudadano_id):
    """API para obtener todos los archivos de un ciudadano"""
    try:
        return JsonResponse(build_ciudadano_archivos_payload(ciudadano_id))
    except Http404:
        raise
    except Exception:
        logger.exception("Error listando los archivos del ciudadano %s", ciudadano_id)
        return JsonResponse({"results": [], "count": 0, "error": ERROR_GENERICO}, status=500)


@login_required
@requiere("ciudadano.editar")
def eliminar_archivo_ciudadano(request, ciudadano_id, archivo_id):
    """Borra un adjunto **de ese ciudadano** (SEC-10)."""
    if request.method != "DELETE":
        return JsonResponse({"success": False, "error": "Método no permitido"}, status=405)

    ciudadano = get_object_or_404(Ciudadano, id=ciudadano_id)
    return _eliminar_archivo(ciudadano, archivo_id)


@login_required
@requiere("ciudadano.editar")
def eliminar_archivo_legajo(request, legajo_id, archivo_id):
    """Borra un adjunto **de ese legajo** (SEC-10)."""
    if request.method != "DELETE":
        return JsonResponse({"success": False, "error": "Método no permitido"}, status=405)

    legajo = get_object_or_404(LegajoAtencion, id=legajo_id)
    return _eliminar_archivo(legajo, archivo_id)


def _eliminar_archivo(instance, archivo_id):
    try:
        eliminar_archivo_de_objeto(instance, archivo_id)
    except Http404:
        raise
    except Exception:
        logger.exception("Error eliminando el adjunto %s de %s", archivo_id, instance.pk)
        return JsonResponse({"success": False, "error": ERROR_GENERICO}, status=500)
    return JsonResponse({"success": True})


@login_required
@requiere("ciudadano.sensible")  # D-11 = Sí: el contenido es sensible (SEC-11, Ola 2)
def alertas_ciudadano_api(request, ciudadano_id):
    """API para obtener alertas de un ciudadano"""
    try:
        alertas = AlertasService.obtener_alertas_ciudadano(ciudadano_id)
        return JsonResponse(
            {
                "results": [
                    {
                        "id": alerta.id,
                        "tipo": alerta.tipo,
                        "tipo_display": alerta.get_tipo_display(),
                        "prioridad": alerta.prioridad,
                        "mensaje": alerta.mensaje,
                        "color_css": alerta.color_css,
                        "fecha_creacion": alerta.creado.isoformat(),
                        "legajo_id": str(alerta.legajo.id) if alerta.legajo else None,
                    }
                    for alerta in alertas
                ],
                "count": len(alertas),
            }
        )
    except Http404:
        raise
    except Exception:
        logger.exception("Error listando las alertas del ciudadano %s", ciudadano_id)
        return JsonResponse({"results": [], "count": 0, "error": ERROR_GENERICO}, status=500)


@login_required
@requiere("ciudadano.sensible")  # igual que las otras dos entradas de cierre (D-11, Cambio 179)
def cerrar_alerta_api(request, alerta_id):
    """API para cerrar una alerta.

    El alcance lo pone ``AlertasService.cerrar_alerta``, que busca la alerta
    dentro de las del usuario: una alerta fuera de su alcance no se cierra
    aunque adivine el id (SEC-18).

    La capacidad sube con el resto de las superficies de alertas: las tres
    entradas de cierre —esta, ``cerrar-ajax/`` y ``AlertasViewSet.cerrar``—
    piden lo mismo que la pantalla que las dispara.
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Método no permitido"}, status=405)

    try:
        success = AlertasService.cerrar_alerta(alerta_id, request.user)
    except Exception:
        logger.exception("Error cerrando la alerta %s", alerta_id)
        return JsonResponse({"success": False, "error": ERROR_GENERICO}, status=500)

    if not success:
        return JsonResponse({"success": False, "error": "Alerta no encontrada"}, status=404)
    return JsonResponse({"success": True})


@login_required
@requiere("ciudadano.sensible")  # D-11 = Sí: el contenido es sensible (SEC-11, Ola 2)
def prediccion_riesgo_api(request, ciudadano_id):
    """API para obtener predicción de riesgo con IA"""
    ciudadano = get_object_or_404(Ciudadano, id=ciudadano_id)
    try:
        return JsonResponse(RiskPredictor.obtener_prediccion_completa(ciudadano))
    except Exception:
        logger.exception("Error calculando la predicción de riesgo del ciudadano %s", ciudadano_id)
        return JsonResponse(
            {
                "error": ERROR_GENERICO,
                "abandono": {"score": 0, "nivel": "BAJO", "factores": []},
                "evento_critico": {"score": 0, "nivel": "BAJO", "factores": []},
                "recomendaciones": [],
            },
            status=500,
        )


@login_required
@requiere("ciudadano.ver")
def evolucion_legajo_api(request, legajo_id):
    """API para obtener datos de evolución de un legajo"""
    try:
        return JsonResponse(build_legajo_evolucion_payload(legajo_id))
    except Http404:
        raise
    except Exception:
        logger.exception("Error armando la evolución del legajo %s", legajo_id)
        return JsonResponse(
            {
                "error": ERROR_GENERICO,
                "total_seguimientos": 0,
                "adherencia_promedio": None,
                "objetivos_totales": 0,
                "objetivos_cumplidos": 0,
                "hitos": [],
            },
            status=500,
        )


@login_required
@requiere("ciudadano.sensible")  # D-11 = Sí: el contenido es sensible (SEC-11, Ola 2)
def timeline_ciudadano_api(request, ciudadano_id):
    """API para obtener línea temporal de eventos del ciudadano"""
    try:
        return JsonResponse(build_ciudadano_timeline_payload(ciudadano_id))
    except Http404:
        raise
    except Exception:
        logger.exception("Error armando el timeline del ciudadano %s", ciudadano_id)
        return JsonResponse({"eventos": [], "count": 0, "error": ERROR_GENERICO}, status=500)


@login_required
@requiere("ciudadano.ver")
def archivos_legajo_api(request, legajo_id):
    """API para obtener archivos de un legajo"""
    try:
        return JsonResponse(build_legajo_archivos_payload(legajo_id))
    except Http404:
        raise
    except Exception:
        logger.exception("Error listando los archivos del legajo %s", legajo_id)
        return JsonResponse({"success": False, "error": ERROR_GENERICO}, status=500)
