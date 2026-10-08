import json
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from core import rbac

from .models import Conversacion, Mensaje
from .permisos import puede_operar

logger = logging.getLogger(__name__)


class ConversacionConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        try:
            self.conversacion_id = self.scope["url_route"]["kwargs"]["conversacion_id"]
            self.room_group_name = f"conversacion_{self.conversacion_id}"

            if not await self.tiene_permiso():
                await self.close(code=4403)
                return

            await self.channel_layer.group_add(self.room_group_name, self.channel_name)
            await self.accept()
        except Exception:
            logger.exception("Error conectando WebSocket de conversacion")
            await self.close(code=1011)

    async def disconnect(self, close_code):
        try:
            if hasattr(self, "room_group_name"):
                await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        except Exception:
            logger.exception("Error desconectando WebSocket de conversacion")

    async def receive(self, text_data):
        data = json.loads(text_data)
        mensaje = data["mensaje"]

        mensaje_obj = await self.crear_mensaje(mensaje)

        if mensaje_obj:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat_message",
                    "mensaje": {
                        "id": mensaje_obj.id,
                        "contenido": mensaje_obj.contenido,
                        "remitente": mensaje_obj.remitente,
                        "fecha": mensaje_obj.fecha_envio.strftime("%H:%M"),
                        "usuario": self.scope["user"].get_full_name() or self.scope["user"].username,
                    },
                },
            )

            await self.generar_alerta_respuesta_operador(mensaje_obj)

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({"type": "mensaje", "mensaje": event["mensaje"]}))

    @database_sync_to_async
    def tiene_permiso(self):
        try:
            user = self.scope["user"]
            if not user.is_authenticated:
                return False
            return puede_operar(user)
        except Exception:
            logger.exception("Error validando permisos de conversacion")
            return False

    @database_sync_to_async
    def crear_mensaje(self, contenido):
        try:
            conversacion = Conversacion.objects.get(id=self.conversacion_id)
            user = self.scope["user"]

            if conversacion.operador_asignado and conversacion.operador_asignado != user:
                return None

            if not conversacion.operador_asignado:
                conversacion.operador_asignado = user
                conversacion.save()
                self.generar_alerta_asignacion(conversacion, user)

            mensaje = Mensaje.objects.create(
                conversacion=conversacion,
                remitente="operador",
                contenido=contenido,
            )
            return mensaje
        except Exception:
            logger.exception("Error creando mensaje en WebSocket de conversacion")
            return None

    @database_sync_to_async
    def generar_alerta_asignacion(self, conversacion, operador):
        try:
            from legajos.models import AlertaCiudadano
            from legajos.services import AlertasService

            ciudadano = conversacion.ciudadano_relacionado if hasattr(conversacion, "ciudadano_relacionado") else None

            if ciudadano:
                alerta = AlertaCiudadano.objects.create(
                    ciudadano=ciudadano,
                    tipo="OPERADOR_ASIGNADO",
                    prioridad="BAJA",
                    mensaje=f"Operador {operador.get_full_name() or operador.username} asignado a conversacion",
                )
                AlertasService._enviar_notificacion_alerta(alerta)
        except Exception:
            logger.exception("Error generando alerta de asignacion")

    async def generar_alerta_respuesta_operador(self, mensaje):
        try:
            await self._crear_alerta_respuesta(mensaje)
        except Exception:
            logger.exception("Error generando alerta de respuesta de operador")

    @database_sync_to_async
    def _crear_alerta_respuesta(self, mensaje):
        try:
            from datetime import timedelta

            from legajos.models import AlertaCiudadano
            from legajos.services import AlertasService

            conversacion = mensaje.conversacion
            ciudadano = conversacion.ciudadano_relacionado if hasattr(conversacion, "ciudadano_relacionado") else None

            if ciudadano:
                ultimo_mensaje_ciudadano = (
                    conversacion.mensajes.filter(remitente="ciudadano").order_by("-fecha_envio").first()
                )

                if ultimo_mensaje_ciudadano:
                    tiempo_respuesta = mensaje.fecha_envio - ultimo_mensaje_ciudadano.fecha_envio
                    if tiempo_respuesta < timedelta(minutes=1):
                        alerta = AlertaCiudadano.objects.create(
                            ciudadano=ciudadano,
                            tipo="RESPUESTA_RAPIDA",
                            prioridad="BAJA",
                            mensaje=f"Respuesta muy rapida del operador ({tiempo_respuesta.seconds}s)",
                        )
                        AlertasService._enviar_notificacion_alerta(alerta)
        except Exception:
            logger.exception("Error creando alerta de respuesta")


class ConversacionesListConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        try:
            if not await self.tiene_permiso():
                await self.close(code=4403)
                return

            self.room_group_name = "conversaciones_list"
            await self.channel_layer.group_add(self.room_group_name, self.channel_name)
            await self.accept()
        except Exception:
            logger.exception("Error conectando WebSocket de lista de conversaciones")
            await self.close(code=1011)

    async def disconnect(self, close_code):
        try:
            if hasattr(self, "room_group_name"):
                await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        except Exception:
            logger.exception("Error desconectando WebSocket de lista de conversaciones")

    async def nueva_conversacion(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "nueva_conversacion",
                    "conversacion_id": event.get("conversacion_id"),
                    "mensaje": event.get("mensaje", "Nueva conversacion disponible"),
                }
            )
        )

    async def nuevo_mensaje(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "nuevo_mensaje",
                    "conversacion_id": event.get("conversacion_id"),
                    "mensaje": event.get("mensaje", ""),
                }
            )
        )

    async def actualizar_lista(self, event):
        await self.send(text_data=json.dumps({"type": "actualizar_lista", "mensaje": event["mensaje"]}))

    @database_sync_to_async
    def tiene_permiso(self):
        try:
            user = self.scope["user"]
            if not user.is_authenticated:
                return False
            return puede_operar(user)
        except Exception:
            logger.exception("Error validando permisos de lista de conversaciones")
            return False


class AlertasConsumer(AsyncWebsocketConsumer):
    """Difusión en vivo de las alertas del legajo (G1c-04).

    Tres reglas, todas medidas como agujeros por la auditoría oct-2026:

    1. **Capacidad.** Pide ``ciudadano.sensible``, la misma que las APIs JSON de
       alertas y timeline (SEC-11, D-11). Con ``ciudadano.ver`` el socket
       entregaba por WS —y como notificación del sistema operativo— alertas de
       tipo «Riesgo Suicida» que por HTTP ese usuario no veía.
    2. **Sesión.** El backoffice admite una sola sesión por usuario
       (``BackofficeSingleSessionMiddleware``) y bloquea la navegación con la
       clave provisoria sin cambiar. El WS no pasa por middlewares de HTTP, así
       que ambos chequeos se repiten acá a mano.
    3. **Alcance, en cada entrega.** El grupo ``alertas_sistema`` es uno solo:
       el filtro por alcance va en el envío, resuelto con
       ``FiltrosUsuarioService`` —la misma pieza que acota el listado HTTP— y
       revalidando la capacidad, así un socket ya abierto deja de recibir
       cuando le quitan el rol (se cierra con 4403) en vez de seguir
       escuchando hasta que el navegador se cierre.
    """

    async def connect(self):
        try:
            if not await self.puede_escuchar_alertas():
                await self.close(code=4403)
                return

            self.room_group_name = "alertas_sistema"
            await self.channel_layer.group_add(self.room_group_name, self.channel_name)
            await self.accept()
        except Exception:
            logger.exception("Error conectando WebSocket de alertas")
            await self.close(code=1011)

    async def disconnect(self, close_code):
        try:
            if hasattr(self, "room_group_name"):
                await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        except Exception:
            logger.exception("Error desconectando WebSocket de alertas")

    async def _entregar(self, tipo, event):
        """Revalida y manda solo si la alerta sigue siendo de este usuario."""
        alerta_id = (event.get("alerta") or {}).get("id")
        permitida = await self.alerta_entregable(alerta_id)
        if permitida is None:
            # Ya no tiene la capacidad (o la sesión dejó de ser válida): el
            # socket no se queda escuchando con un rol que no existe.
            await self.close(code=4403)
            return
        if not permitida:
            return
        await self.send(text_data=json.dumps({"type": tipo, "alerta": event["alerta"]}))

    async def nueva_alerta(self, event):
        await self._entregar("nueva_alerta", event)

    async def alerta_critica(self, event):
        await self._entregar("alerta_critica", event)

    async def alerta_cerrada(self, event):
        if await self.alerta_entregable(event.get("alerta_id")):
            await self.send(text_data=json.dumps({"type": "alerta_cerrada", "alerta_id": event["alerta_id"]}))

    @database_sync_to_async
    def puede_escuchar_alertas(self):
        try:
            user = self.scope["user"]
            if not user.is_authenticated:
                return False
            if not rbac.puede(user, "ciudadano.sensible"):
                return False
            return self._sesion_vigente(user)
        except Exception:
            logger.exception("Error validando permisos de alertas")
            return False

    @database_sync_to_async
    def alerta_entregable(self, alerta_id):
        """``None`` = el usuario perdió el permiso; ``bool`` = está en su alcance."""
        from django.contrib.auth import get_user_model

        from legajos.services.filtros_usuario import FiltrosUsuarioService

        try:
            user = self.scope["user"]
            if not user.is_authenticated:
                return None
            # Relee el usuario: `self.scope["user"]` quedó cacheado en el
            # handshake y ni sus grupos ni su alta se refrescan solos.
            user = get_user_model()._default_manager.filter(pk=user.pk, is_active=True).first()
            if user is None or not rbac.puede(user, "ciudadano.sensible") or not self._sesion_vigente(user):
                return None
            if alerta_id is None:
                return False
            return FiltrosUsuarioService.obtener_alertas_usuario(user).filter(pk=alerta_id).exists()
        except Exception:
            logger.exception("Error resolviendo el alcance de la alerta %s", alerta_id)
            return False

    def _sesion_vigente(self, user):
        """La misma sesión única y el mismo bloqueo por clave provisoria del HTTP."""
        from users.models import Profile

        sesion = self.scope.get("session")
        clave = getattr(sesion, "session_key", None)
        profile = Profile.objects.filter(user=user).only("backoffice_session_key", "debe_cambiar_contrasena").first()
        if profile is None:
            return True
        if profile.debe_cambiar_contrasena:
            return False
        if profile.backoffice_session_key and profile.backoffice_session_key != clave:
            return False
        return True


class AlertasConversacionesConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        try:
            if not await self.tiene_permiso_conversaciones():
                await self.close(code=4403)
                return

            user_id = self.scope["user"].id
            self.room_group_name = f"conversaciones_operador_{user_id}"
            await self.channel_layer.group_add(self.room_group_name, self.channel_name)
            await self.accept()
        except Exception:
            logger.exception("Error conectando WebSocket de alertas de conversaciones")
            await self.close(code=1011)

    async def disconnect(self, close_code):
        try:
            if hasattr(self, "room_group_name"):
                await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        except Exception:
            logger.exception("Error desconectando WebSocket de alertas de conversaciones")

    async def nueva_alerta_conversacion(self, event):
        await self.send(text_data=json.dumps({"type": "nueva_alerta_conversacion", "alerta": event["alerta"]}))

    @database_sync_to_async
    def tiene_permiso_conversaciones(self):
        try:
            user = self.scope["user"]
            if not user.is_authenticated:
                return False
            return puede_operar(user)
        except Exception:
            logger.exception("Error validando permisos de alertas de conversaciones")
            return False
