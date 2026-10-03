import logging

from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from django.utils import timezone

from ..models import Mensaje
from ..selectors import get_conversaciones_sin_asignar
from .core import AsignadorAutomatico, NotificacionService

logger = logging.getLogger(__name__)


def _notificar_grupo(nombre_grupo, payload):
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(nombre_grupo, payload)
    except Exception as exc:
        logger.warning("No se pudo enviar notificación realtime: %s", exc)


# Acá vivían `consultar_renaper_para_chat`, `iniciar_conversacion_publica` y
# `crear_mensaje_ciudadano`, que solo alimentaban las rutas públicas del chat.
# El alta anónima creaba el legajo de cualquier DNI con el nombre que mandara el
# cliente y la consulta devolvía los datos de RENAPER sin login (G1-01 y G1-02,
# auditoría oct-2026): se eliminan junto con sus rutas.


def asignar_conversacion_operador(conversacion, operador, usuario_asignador):
    conversacion.asignar_operador(operador, usuario_asignador)
    AsignadorAutomatico.actualizar_todas_las_colas()
    _notificar_grupo(
        "conversaciones_list",
        {
            "type": "actualizar_lista",
            "mensaje": f"Conversación #{conversacion.id} asignada",
        },
    )
    return conversacion


def crear_mensaje_operador(conversacion, operador, contenido):
    if conversacion.operador_asignado and conversacion.operador_asignado != operador:
        raise PermissionError("No tienes permisos para responder esta conversación")

    if not conversacion.operador_asignado:
        conversacion.operador_asignado = operador
        conversacion.save(update_fields=["operador_asignado"])

    mensaje = Mensaje.objects.create(
        conversacion=conversacion,
        remitente="operador",
        contenido=contenido,
    )
    conversacion.marcar_primera_respuesta()
    NotificacionService.notificar_mensaje(conversacion, mensaje)
    _notificar_grupo(
        "conversaciones_list",
        {
            "type": "nuevo_mensaje",
            "conversacion_id": conversacion.id,
            "mensaje": f"Respuesta del operador en conversación #{conversacion.id}",
        },
    )
    return mensaje


def cerrar_conversacion(conversacion):
    conversacion.estado = "cerrada"
    conversacion.fecha_cierre = timezone.now()
    conversacion.save(update_fields=["estado", "fecha_cierre"])
    return conversacion


def configurar_operador_cola(cleaned_data):
    operador = get_object_or_404(User, id=cleaned_data["operador_id"])
    return AsignadorAutomatico.configurar_operador(
        operador,
        cleaned_data["max_conversaciones"],
        cleaned_data.get("activo", False),
    )


def ejecutar_asignacion_automatica():
    asignadas = 0
    sin_operadores = 0

    for conversacion in get_conversaciones_sin_asignar():
        try:
            if AsignadorAutomatico.asignar_conversacion_automatica(conversacion):
                asignadas += 1
            else:
                sin_operadores += 1
        except Exception as exc:
            logger.warning("Error asignando conversación %s: %s", conversacion.id, exc)
            sin_operadores += 1

    AsignadorAutomatico.actualizar_todas_las_colas()
    return asignadas, sin_operadores


# `evaluar_conversacion` solo lo llamaban las dos vistas homónimas, que se fueron
# con la ruta `<id>/evaluar/` (R0-01, auditoría oct-2026). El campo
# `Conversacion.satisfaccion` y las métricas que lo promedian quedan como están.


def marcar_mensajes_ciudadano_leidos(conversacion):
    return Mensaje.objects.filter(
        conversacion=conversacion,
        remitente="ciudadano",
        leido=False,
    ).update(leido=True)
