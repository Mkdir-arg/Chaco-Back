import logging

from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.html import escape

from core.services.cache import invalidate_cache_pattern

from ..models import Conversacion, Mensaje
from ..selectors import get_conversaciones_sin_asignar
from .core import AsignadorAutomatico, MetricasService, NotificacionService

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


def consultar_renaper_para_chat(dni, sexo):
    from legajos.services.consulta_renaper import consultar_datos_renaper

    return consultar_datos_renaper(dni, sexo)


def iniciar_conversacion_publica(cleaned_data):
    conversacion = Conversacion.objects.create(
        tipo=cleaned_data["tipo"],
        dni_ciudadano=cleaned_data["dni"] if cleaned_data["tipo"] == "personal" and cleaned_data["dni"] else None,
        sexo_ciudadano=cleaned_data["sexo"] if cleaned_data["tipo"] == "personal" and cleaned_data["sexo"] else None,
        prioridad=cleaned_data["prioridad"],
        estado="activa",
    )

    if conversacion.tipo == "personal" and conversacion.dni_ciudadano and conversacion.sexo_ciudadano:
        try:
            from legajos.models import Ciudadano

            datos_renaper = cleaned_data.get("datos_renaper") or {}
            Ciudadano.objects.get_or_create(
                dni=conversacion.dni_ciudadano,
                defaults={
                    "nombre": datos_renaper.get("nombre", "Usuario"),
                    "apellido": datos_renaper.get("apellido", "Chat"),
                    "genero": conversacion.sexo_ciudadano,
                    "domicilio": datos_renaper.get("domicilio", ""),
                },
            )
        except Exception as exc:
            logger.warning("No se pudo vincular/crear ciudadano para conversación %s: %s", conversacion.id, exc)

    if AsignadorAutomatico.asignar_conversacion_automatica(conversacion):
        conversacion.refresh_from_db()

    NotificacionService.notificar_nueva_conversacion(conversacion)
    _notificar_grupo(
        "conversaciones_list",
        {
            "type": "nueva_conversacion",
            "conversacion_id": conversacion.id,
            "mensaje": f"Nueva conversación #{conversacion.id} creada",
        },
    )
    return conversacion


def crear_mensaje_ciudadano(conversacion_id, contenido):
    conversacion = get_object_or_404(Conversacion, id=conversacion_id)
    mensaje = Mensaje.objects.create(
        conversacion=conversacion,
        remitente="ciudadano",
        contenido=escape(contenido),
    )

    _notificar_grupo(
        f"conversacion_{conversacion_id}",
        {
            "type": "chat_message",
            "mensaje": {
                "id": mensaje.id,
                "contenido": mensaje.contenido,
                "remitente": "ciudadano",
                "fecha": mensaje.fecha_envio.strftime("%H:%M"),
                "usuario": "Ciudadano",
            },
        },
    )
    _notificar_grupo(
        "conversaciones_list",
        {
            "type": "nuevo_mensaje",
            "conversacion_id": conversacion_id,
            "mensaje": f"Nuevo mensaje en conversación #{conversacion_id}",
        },
    )
    return mensaje


def asignar_conversacion_operador(conversacion, operador, usuario_asignador):
    conversacion.asignar_operador(operador, usuario_asignador)
    AsignadorAutomatico.actualizar_todas_las_colas()
    invalidate_cache_pattern("conversaciones:lista_conversaciones")
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
    invalidate_cache_pattern("conversaciones:lista_conversaciones")
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


def evaluar_conversacion(conversacion, satisfaccion):
    conversacion.satisfaccion = satisfaccion
    conversacion.save(update_fields=["satisfaccion"])
    if conversacion.operador_asignado:
        MetricasService.actualizar_metricas_operador(conversacion.operador_asignado)
    return conversacion


def marcar_mensajes_ciudadano_leidos(conversacion):
    return Mensaje.objects.filter(
        conversacion=conversacion,
        remitente="ciudadano",
        leido=False,
    ).update(leido=True)
