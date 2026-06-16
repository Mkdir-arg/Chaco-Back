from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from ..models import Conversacion
from ..selectors.conversaciones import get_conversacion_api_detalle, usuario_tiene_permiso_conversaciones


@login_required
@api_view(['GET'])
def conversacion_detalle(request, conversacion_id):
    """Devuelve datos minimos de una conversacion para actualizar la lista en vivo"""
    if not usuario_tiene_permiso_conversaciones(request.user):
        return JsonResponse({'error': 'No autorizado'}, status=403)

    try:
        conv = get_conversacion_api_detalle(conversacion_id)
    except Conversacion.DoesNotExist:
        return JsonResponse({'error': 'No encontrada'}, status=404)

    data = {
        'id': conv.id,
        'tipo': conv.get_tipo_display(),
        'estado': conv.estado,
        'estado_display': conv.get_estado_display(),
        'operador': (conv.operador_asignado.get_full_name() if conv.operador_asignado else 'Sin asignar'),
        'dni': conv.dni_ciudadano or '',
        'sexo': conv.sexo_ciudadano or '',
        'fecha': conv.fecha_inicio.strftime('%d/%m/%Y %H:%M'),
        'mensajes': conv.mensajes.count(),
        'no_leidos': conv.mensajes_no_leidos,
    }
    return Response({'conversacion': data})
