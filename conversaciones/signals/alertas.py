import logging
from datetime import timedelta

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from ..models import Conversacion, Mensaje
from legajos.services import AlertasService

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Conversacion)
def alerta_nueva_conversacion(sender, instance, created, **kwargs):
    """Genera alerta cuando se crea nueva conversación"""
    if created and instance.estado == 'pendiente':
        try:
            from django.contrib.auth.models import User
            from ..models import NuevaConversacionAlerta, HistorialAlertaConversacion

            operador_ids = list(
                User.objects.filter(
                    groups__name__in=['Conversaciones', 'OperadorCharla'],
                    is_active=True,
                ).distinct().values_list('id', flat=True)
            )

            if not operador_ids:
                return

            NuevaConversacionAlerta.objects.bulk_create(
                [
                    NuevaConversacionAlerta(
                        conversacion=instance,
                        operador_id=operador_id,
                        vista=False,
                    )
                    for operador_id in operador_ids
                ],
                ignore_conflicts=True,
            )

            HistorialAlertaConversacion.objects.bulk_create(
                [
                    HistorialAlertaConversacion(
                        conversacion=instance,
                        operador_id=operador_id,
                        tipo='NUEVA_CONVERSACION',
                        mensaje=f'Nueva conversación #{instance.id} disponible',
                    )
                    for operador_id in operador_ids
                ]
            )

            logger.info(
                "Nueva conversación #%s notificada a %s operadores",
                instance.id,
                len(operador_ids),
            )

        except Exception:
            logger.exception("Error generando alerta de nueva conversación")


@receiver(pre_save, sender=Conversacion)
def alerta_conversacion_cerrada(sender, instance, **kwargs):
    """Genera alerta cuando se cierra conversación"""
    if instance.pk:
        try:
            conversacion_anterior = Conversacion.objects.get(pk=instance.pk)
            if conversacion_anterior.estado != 'CERRADA' and instance.estado == 'CERRADA':
                if hasattr(instance, 'ciudadano_relacionado') and instance.ciudadano_relacionado:
                    from legajos.models import AlertaCiudadano
                    
                    # Calcular duración de la conversación
                    duracion = timezone.now() - instance.creado
                    
                    alerta = AlertaCiudadano.objects.create(
                        ciudadano=instance.ciudadano_relacionado,
                        tipo='CONVERSACION_CERRADA',
                        prioridad='BAJA',
                        mensaje=f'Conversación cerrada. Duración: {duracion.seconds//60} minutos'
                    )
                    AlertasService._enviar_notificacion_alerta(alerta)
        except Conversacion.DoesNotExist:
            pass
        except Exception:
            logger.exception("Error generando alerta de conversación cerrada")


@receiver(post_save, sender=Mensaje)
def verificar_tiempo_respuesta(sender, instance, created, **kwargs):
    """Verifica tiempo de respuesta en conversaciones"""
    if created and instance.remitente == 'ciudadano':
        try:
            conversacion = instance.conversacion
            
            # Verificar palabras clave de riesgo PRIMERO
            if conversacion.operador_asignado:
                _verificar_palabras_riesgo(conversacion, instance)
                _generar_alerta_mensaje_ciudadano(conversacion, instance)
                _crear_historial_mensaje(conversacion, instance)
            
            # Verificar si hay operador asignado
            if not conversacion.operador_asignado:
                return
            
            # Buscar último mensaje del operador
            ultimo_msg_operador = conversacion.mensajes.filter(
                remitente='operador',
                fecha_envio__lt=instance.fecha_envio
            ).order_by('-fecha_envio').first()
            
            if ultimo_msg_operador:
                # Verificar si el ciudadano respondió muy rápido (posible crisis)
                tiempo_respuesta = instance.fecha_envio - ultimo_msg_operador.fecha_envio
                
                if tiempo_respuesta < timedelta(minutes=2):
                    if hasattr(conversacion, 'ciudadano_relacionado') and conversacion.ciudadano_relacionado:
                        from legajos.models import AlertaCiudadano
                        
                        alerta = AlertaCiudadano.objects.create(
                            ciudadano=conversacion.ciudadano_relacionado,
                            tipo='RESPUESTA_RAPIDA_CIUDADANO',
                            prioridad='MEDIA',
                            mensaje=f'Ciudadano respondió muy rápido ({tiempo_respuesta.seconds}s) - posible urgencia'
                        )
                        AlertasService._enviar_notificacion_alerta(alerta)
        except Exception:
            logger.exception("Error verificando tiempo de respuesta")


def _verificar_palabras_riesgo(conversacion, mensaje):
    """Verifica palabras clave de riesgo en el mensaje"""
    try:
        palabras_riesgo = ['suicidio', 'lastimar', 'drogas', 'violencia', 'matar', 'morir', 'suicidar']
        contenido_lower = mensaje.contenido.lower()
        
        palabras_encontradas = [palabra for palabra in palabras_riesgo if palabra in contenido_lower]
        
        if palabras_encontradas:
            # Crear alerta crítica en el sistema principal
            if hasattr(conversacion, 'ciudadano_relacionado') and conversacion.ciudadano_relacionado:
                from legajos.models import AlertaCiudadano
                
                alerta = AlertaCiudadano.objects.create(
                    ciudadano=conversacion.ciudadano_relacionado,
                    tipo='RIESGO_CRITICO_CONVERSACION',
                    prioridad='CRITICA',
                    mensaje=f'RIESGO CRÍTICO: Palabras de riesgo detectadas en conversación #{conversacion.id}'
                )
                AlertasService._enviar_notificacion_alerta(alerta)
    except Exception:
        logger.exception("Error verificando palabras de riesgo")


def _generar_alerta_mensaje_ciudadano(conversacion, mensaje):
    """Genera alerta específica para operadores de conversaciones"""
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        
        # Datos de la alerta
        alerta_data = {
            'id': f'conv_{conversacion.id}_{mensaje.id}',
            'conversacion_id': conversacion.id,
            'tipo': 'NUEVO_MENSAJE_CIUDADANO',
            'prioridad': 'MEDIA',
            'mensaje': f'Nuevo mensaje en conversación #{conversacion.id}',
            'fecha': mensaje.fecha_envio.strftime('%d/%m/%Y %H:%M'),
            'operador_id': conversacion.operador_asignado.id,
            'contenido_mensaje': mensaje.contenido[:100] + '...' if len(mensaje.contenido) > 100 else mensaje.contenido
        }
        
        # Enviar notificación WebSocket específica para conversaciones
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'conversaciones_operador_{conversacion.operador_asignado.id}',
            {
                'type': 'nueva_alerta_conversacion',
                'alerta': alerta_data
            }
        )
        
    except Exception:
        logger.exception("Error generando alerta de mensaje ciudadano")


def _crear_historial_mensaje(conversacion, mensaje):
    """Crea historial de alerta por nuevo mensaje"""
    try:
        from ..models import HistorialAlertaConversacion
        
        HistorialAlertaConversacion.objects.create(
            conversacion=conversacion,
            operador=conversacion.operador_asignado,
            tipo='NUEVO_MENSAJE',
            mensaje=f'Nuevo mensaje en conversación #{conversacion.id}'
        )
    except Exception:
        logger.exception("Error creando historial de mensaje")
