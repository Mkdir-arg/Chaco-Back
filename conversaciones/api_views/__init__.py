from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from rest_framework.decorators import api_view

from ..models import Conversacion
from ..selectors.conversaciones import (
    get_alertas_conversaciones_count,
    get_alertas_preview_mensajes,
    get_alertas_preview_nuevas_conversaciones,
    get_conversacion_asignada_a_operador,
    usuario_tiene_permiso_conversaciones,
)
from ..services.chat import marcar_mensajes_ciudadano_leidos


@login_required
@api_view(["GET"])
def alertas_conversaciones_count(request):
    """Contador de conversaciones con mensajes no leídos"""
    if not usuario_tiene_permiso_conversaciones(request.user):
        return JsonResponse({"count": 0})

    return JsonResponse({"count": get_alertas_conversaciones_count(request.user), "tipo": "conversaciones"})


@login_required
@api_view(["GET"])
def alertas_conversaciones_preview(request):
    """Preview de mensajes no leídos para el dropdown"""
    if not usuario_tiene_permiso_conversaciones(request.user):
        return JsonResponse({"results": []})

    results = []
    for mensaje in get_alertas_preview_mensajes(request.user):
        results.append(
            {
                "id": f"conv_{mensaje.conversacion.id}_{mensaje.id}",
                "conversacion_id": mensaje.conversacion.id,
                "mensaje": f"Nuevo mensaje en conversación #{mensaje.conversacion.id}",
                "contenido": mensaje.contenido[:100] + "..." if len(mensaje.contenido) > 100 else mensaje.contenido,
                "fecha": mensaje.fecha_envio.strftime("%d/%m/%Y %H:%M"),
                "prioridad": "MEDIA",
                "ciudadano_nombre": f"Conversación #{mensaje.conversacion.id}",
            }
        )

    for nueva in get_alertas_preview_nuevas_conversaciones(request.user):
        results.append(
            {
                "id": f"nueva_conv_{nueva.conversacion.id}",
                "conversacion_id": nueva.conversacion.id,
                "mensaje": f"Nueva conversación #{nueva.conversacion.id} disponible",
                "contenido": "Conversación sin asignar esperando atención",
                "fecha": nueva.creado.strftime("%d/%m/%Y %H:%M"),
                "prioridad": "ALTA",
                "ciudadano_nombre": f"Nueva Conversación #{nueva.conversacion.id}",
            }
        )

    return JsonResponse({"results": results})


@login_required
@api_view(["POST"])
def marcar_mensajes_leidos(request, conversacion_id):
    """Marcar mensajes como leídos cuando se abre la conversación"""
    try:
        conversacion = get_conversacion_asignada_a_operador(conversacion_id, request.user)
        marcar_mensajes_ciudadano_leidos(conversacion)
        return JsonResponse({"success": True})
    except Conversacion.DoesNotExist:
        return JsonResponse({"error": "Conversación no encontrada"}, status=404)
