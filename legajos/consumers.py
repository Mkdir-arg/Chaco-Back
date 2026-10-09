"""Consumers de WebSocket de `legajos`.

`AlertasConsumer` vivía en `conversaciones/consumers.py` y se mudó acá con RED-13:
`/ws/alertas/` es el canal de las alertas del legajo —la campana del navbar,
`ciudadano.sensible`, el ruteo precalculado y la ventana de revalidación—, no tiene
nada que ver con el chat y es lo único que sobrevive al apagado de `conversaciones`
(G1-01 fase 2). El código es el mismo; cambian los imports y el módulo.
"""

import json
import logging
import time

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

from core import rbac

logger = logging.getLogger(__name__)


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
        """La misma sesión única y el mismo bloqueo por clave provisoria del HTTP.

        El logout **no** limpia ``Profile.backoffice_session_key``: borra la sesión y
        deja la clave vieja escrita, así que comparar solo contra el perfil daba
        ``True`` para siempre y el socket seguía entregando alertas después de cerrar
        sesión. Se confirma además que la sesión del handshake siga existiendo, por el
        backend configurado (``db`` en dev y QA, ``cache`` en prd).
        """
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
        if clave and not sesion.exists(clave):
            return False
        return True
