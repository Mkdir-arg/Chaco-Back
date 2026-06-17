from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from ..services.ml_predictor import RiskPredictor
from ..models import Ciudadano, LegajoAtencion
from ..selectors import (
    build_ciudadano_actividades_payload,
    build_ciudadano_archivos_payload,
    build_ciudadano_timeline_payload,
    build_legajo_archivos_payload,
    build_legajo_evolucion_payload,
)
from ..services import AlertasService
from ..services import ContactosFilesError, eliminar_archivo_por_id, subir_archivos_para_objeto


@login_required
def actividades_ciudadano_api(request, ciudadano_id):
    """API para obtener todas las actividades de un ciudadano"""
    try:
        return JsonResponse(build_ciudadano_actividades_payload(ciudadano_id))
    except Exception as exc:
        return JsonResponse({'results': [], 'count': 0, 'error': str(exc)})


@login_required
def subir_archivos_ciudadano(request, ciudadano_id):
    """Vista para subir archivos a un ciudadano"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'})

    try:
        ciudadano = get_object_or_404(Ciudadano, id=ciudadano_id)
        archivos = request.FILES.getlist('archivo')
        etiqueta = request.POST.get('etiqueta', '')
        archivos_subidos = subir_archivos_para_objeto(ciudadano, archivos, etiqueta)
        return JsonResponse(
            {
                'success': True,
                'archivos': archivos_subidos,
                'mensaje': f'{len(archivos_subidos)} archivo(s) subido(s) exitosamente',
            }
        )
    except ContactosFilesError as exc:
        return JsonResponse({'success': False, 'error': str(exc)})
    except Exception as exc:
        return JsonResponse({'success': False, 'error': str(exc)})


@login_required
def subir_archivos_legajo(request, legajo_id):
    """Vista para subir archivos a un legajo"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'})

    try:
        legajo = get_object_or_404(LegajoAtencion, id=legajo_id)
        archivos = request.FILES.getlist('archivo')
        etiqueta = request.POST.get('etiqueta', '')
        archivos_subidos = subir_archivos_para_objeto(legajo, archivos, etiqueta)
        return JsonResponse(
            {
                'success': True,
                'archivos': archivos_subidos,
                'mensaje': f'{len(archivos_subidos)} archivo(s) subido(s) exitosamente',
            }
        )
    except ContactosFilesError as exc:
        return JsonResponse({'success': False, 'error': str(exc)})
    except Exception as exc:
        return JsonResponse({'success': False, 'error': str(exc)})


@login_required
def archivos_ciudadano_api(request, ciudadano_id):
    """API para obtener todos los archivos de un ciudadano"""
    try:
        return JsonResponse(build_ciudadano_archivos_payload(ciudadano_id))
    except Exception as exc:
        return JsonResponse({'results': [], 'count': 0, 'error': str(exc)})


@login_required
def eliminar_archivo(request, archivo_id):
    """Vista para eliminar un archivo"""
    if request.method != 'DELETE':
        return JsonResponse({'success': False, 'error': 'Método no permitido'})

    try:
        eliminar_archivo_por_id(archivo_id)
        return JsonResponse({'success': True})
    except Exception as exc:
        return JsonResponse({'success': False, 'error': str(exc)})


@login_required
def alertas_ciudadano_api(request, ciudadano_id):
    """API para obtener alertas de un ciudadano"""
    try:
        AlertasService.generar_alertas_ciudadano(ciudadano_id)
        alertas = AlertasService.obtener_alertas_ciudadano(ciudadano_id)
        return JsonResponse(
            {
                'results': [
                    {
                        'id': alerta.id,
                        'tipo': alerta.tipo,
                        'tipo_display': alerta.get_tipo_display(),
                        'prioridad': alerta.prioridad,
                        'mensaje': alerta.mensaje,
                        'color_css': alerta.color_css,
                        'fecha_creacion': alerta.creado.isoformat(),
                        'legajo_id': str(alerta.legajo.id) if alerta.legajo else None,
                    }
                    for alerta in alertas
                ],
                'count': len(alertas),
            }
        )
    except Exception as exc:
        return JsonResponse({'results': [], 'count': 0, 'error': str(exc)})


@login_required
def cerrar_alerta_api(request, alerta_id):
    """API para cerrar una alerta"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'})

    try:
        success = AlertasService.cerrar_alerta(alerta_id, request.user)
        if not success:
            return JsonResponse({'success': False, 'error': 'Alerta no encontrada'})
        return JsonResponse({'success': True})
    except Exception as exc:
        return JsonResponse({'success': False, 'error': str(exc)})


@login_required
def prediccion_riesgo_api(request, ciudadano_id):
    """API para obtener predicción de riesgo con IA"""
    try:
        ciudadano = get_object_or_404(Ciudadano, id=ciudadano_id)
        return JsonResponse(RiskPredictor.obtener_prediccion_completa(ciudadano))
    except Exception as exc:
        return JsonResponse(
            {
                'error': str(exc),
                'abandono': {'score': 0, 'nivel': 'BAJO', 'factores': []},
                'evento_critico': {'score': 0, 'nivel': 'BAJO', 'factores': []},
                'recomendaciones': [],
            }
        )


@login_required
def evolucion_legajo_api(request, legajo_id):
    """API para obtener datos de evolución de un legajo"""
    try:
        return JsonResponse(build_legajo_evolucion_payload(legajo_id))
    except Exception as exc:
        return JsonResponse(
            {
                'error': str(exc),
                'total_seguimientos': 0,
                'adherencia_promedio': None,
                'objetivos_totales': 0,
                'objetivos_cumplidos': 0,
                'hitos': [],
            }
        )


@login_required
def timeline_ciudadano_api(request, ciudadano_id):
    """API para obtener línea temporal de eventos del ciudadano"""
    try:
        return JsonResponse(build_ciudadano_timeline_payload(ciudadano_id))
    except Exception as exc:
        return JsonResponse({'eventos': [], 'count': 0, 'error': str(exc)})


@login_required
def archivos_legajo_api(request, legajo_id):
    """API para obtener archivos de un legajo"""
    try:
        return JsonResponse(build_legajo_archivos_payload(legajo_id))
    except Exception as exc:
        return JsonResponse({'success': False, 'error': str(exc)})
