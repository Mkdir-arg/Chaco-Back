import json
import logging
import time

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

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
       alertas y timeline (SEC-11, D-11) y la misma que la campana del navbar.
       Con ``ciudadano.ver`` el socket entregaba por WS —y como notificación del
       sistema operativo— alertas de tipo «Riesgo Suicida» que por HTTP ese
       usuario no veía.
    2. **Sesión.** El backoffice admite una sola sesión por usuario
       (``BackofficeSingleSessionMiddleware``) y bloquea la navegación con la
       clave provisoria sin cambiar. El WS no pasa por middlewares de HTTP, así
       que ambos chequeos se repiten acá a mano.
    3. **Alcance, por ventana.** El grupo ``alertas_sistema`` es uno solo, así
       que el filtro por alcance va en el envío. Resolverlo *por entrega* con
       ``FiltrosUsuarioService.obtener_alertas_usuario(user).filter(pk=…)``
       costaba **cinco consultas por alerta y por socket** —tres ``IN`` anidados
       sobre las 40k inscripciones—, y la pasada horaria de ``generar_alertas``
       redifunde de golpe: con el ``read_timeout`` de 10 s de ECOM eso es una
       cola. Ahora el alcance se resuelve **una vez por ventana**
       (``VENTANA_REVALIDACION``, 60 s por defecto) y se guarda en el socket;
       cada entrega lo compara contra los datos de ruteo que el emisor ya
       calculó (``AlertasService._ruteo_de``), **sin tocar la base**. Al vencer
       la ventana se revalida todo —usuario, capacidad y sesión— y, si lo
       perdió, el socket se cierra con 4403. Esa ventana es la latencia máxima
       declarada entre quitarle el rol a alguien y que deje de recibir.

    El criterio del alcance es el mismo que el de ``FiltrosUsuarioService``, pero
    evaluado en memoria: superusuario o ``config.administrar`` ven todo; el resto,
    solo si tienen legajos propios y la alerta cuelga de un legajo del que son
    responsables o de un legajo inscripto en alguno de sus programas.
    """

    #: Segundos que vale el alcance cacheado antes de volver a la base.
    VENTANA_REVALIDACION = 60

    def _ventana(self):
        return getattr(settings, "ALERTAS_WS_VENTANA_REVALIDACION", self.VENTANA_REVALIDACION)

    async def connect(self):
        try:
            self._alcance = None
            self._alcance_vence = 0.0
            if not await self.refrescar_alcance():
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

    async def _alcance_vigente(self):
        """El alcance cacheado, revalidado contra la base si venció la ventana.

        ``None`` cuando el usuario perdió la capacidad, el alta o la sesión;
        quien llama cierra con 4403.
        """
        if self._alcance is not None and time.monotonic() < self._alcance_vence:
            return self._alcance
        if not await self.refrescar_alcance():
            return None
        return self._alcance

    async def _entregar(self, mensaje, event):
        """Manda solo si la alerta cae en el alcance vigente de este socket."""
        alcance = await self._alcance_vigente()
        if alcance is None:
            # Ya no tiene la capacidad (o la sesión dejó de ser válida): el
            # socket no se queda escuchando con un rol que no existe.
            await self.close(code=4403)
            return
        if not self._en_alcance(alcance, event.get("ruteo")):
            return
        await self.send(text_data=json.dumps(mensaje))

    @staticmethod
    def _en_alcance(alcance, ruteo):
        """Misma regla que ``FiltrosUsuarioService``, sin consultar (G1c-04 (a))."""
        if alcance["global"]:
            return True
        if not ruteo or not alcance["tiene_legajos_propios"]:
            return False
        if ruteo.get("responsable_id") is not None and ruteo["responsable_id"] == alcance["user_pk"]:
            return True
        return bool(alcance["programas"].intersection(ruteo.get("programa_ids") or []))

    async def nueva_alerta(self, event):
        await self._entregar({"type": "nueva_alerta", "alerta": event["alerta"]}, event)

    async def alerta_cerrada(self, event):
        """Saca del dashboard abierto la alerta que otro acaba de cerrar.

        Este handler vivió sin productor desde el principio y además era
        **inalcanzable por construcción**: su alcance se resolvía con
        ``obtener_alertas_usuario``, que filtra ``activa=True``, y para cuando
        se emite el cierre la alerta ya está en ``activa=False``. Se resolvió
        para cerradas —el ruteo que manda el emisor no mira ``activa``, así que
        el cierre llega a los mismos sockets que recibieron el alta— y
        ``AlertasService.cerrar_alerta`` lo emite.
        """
        await self._entregar({"type": "alerta_cerrada", "alerta_id": event["alerta_id"]}, event)

    @database_sync_to_async
    def refrescar_alcance(self):
        """Revalida contra la base y recalcula el alcance. ``False`` = ya no puede.

        Las consultas que acá se pagan **una vez por ventana** son las que antes
        iban en **cada** entrega: releer el usuario (``scope["user"]`` se
        resolvió en el handshake y ni sus grupos ni su alta se refrescan solos),
        el ``Profile`` de la sesión y los programas de sus legajos propios.
        """
        from django.contrib.auth import get_user_model

        from legajos.models import LegajoAtencion
        from legajos.services.filtros_usuario import FiltrosUsuarioService

        self._alcance = None
        try:
            user = self.scope["user"]
            if not user.is_authenticated:
                return False
            user = get_user_model()._default_manager.filter(pk=user.pk, is_active=True).first()
            if user is None or not rbac.puede(user, "ciudadano.sensible") or not self._sesion_vigente(user):
                return False

            if FiltrosUsuarioService.tiene_alcance_global(user):
                alcance = {"global": True, "user_pk": user.pk, "programas": frozenset(), "tiene_legajos_propios": True}
            else:
                # Mismo corte que `obtener_alertas_usuario`: sin legajos propios no
                # hay alcance, y los programas salen de esos mismos legajos.
                propios = LegajoAtencion.objects.filter(responsable=user).values_list("id", flat=True)
                tiene_propios = propios.exists()
                programas = FiltrosUsuarioService._obtener_programas_usuario(user) if tiene_propios else ()
                alcance = {
                    "global": False,
                    "user_pk": user.pk,
                    "programas": frozenset(programas),
                    "tiene_legajos_propios": tiene_propios,
                }

            self._alcance = alcance
            self._alcance_vence = time.monotonic() + self._ventana()
            return True
        except Exception:
            logger.exception("Error resolviendo el alcance de alertas del socket")
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
