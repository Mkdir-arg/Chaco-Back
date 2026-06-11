from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import Conversacion
from .permisos import puede_operar


@login_required
@api_view(['GET'])
def conversacion_detalle(request, conversacion_id):
    """Devuelve datos mínimos de una conversación para actualizar la lista en vivo"""
    if not puede_operar(request.user):
        return JsonResponse({'error': 'No autorizado'}, status=403)

    try:
        conv = Conversacion.objects.select_related('operador_asignado').get(id=conversacion_id)
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
        'no_leidos': conv.mensajes.filter(remitente='ciudadano', leido=False).count(),
    }
    return Response({'conversacion': data})

