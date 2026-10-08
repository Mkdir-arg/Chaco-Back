import logging
from datetime import timedelta

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.exceptions import ValidationError
from django.utils import timezone

from core.utils_fechas import fecha_local

from ..models import (
    AlertaCiudadano,
    Ciudadano,
    LegajoAtencion,
)
from ..models.contactos import HistorialContacto
from .linking import get_legajos_queryset_for_ciudadano, get_programa_ids_for_legajo_ids

logger = logging.getLogger(__name__)


class AlertasService:
    """Servicio para generar y gestionar alertas automáticas."""

    @staticmethod
    def generar_alertas_ciudadano(ciudadano_id):
        """Genera todas las alertas para un ciudadano específico.

        Pensado para la señal de guardado y el comando periódico ``generar_alertas``,
        NO para el request path de vistas de lectura.
        """
        try:
            ciudadano = Ciudadano.objects.get(id=ciudadano_id)
            legajos = get_legajos_queryset_for_ciudadano(
                ciudadano,
                LegajoAtencion.objects.select_related("responsable"),
            )

            AlertaCiudadano.objects.filter(
                ciudadano=ciudadano,
                activa=True,
                prioridad__in=["MEDIA", "BAJA"],
            ).update(activa=False)

            alertas_generadas = []

            for legajo in legajos:
                alertas_generadas.extend(AlertasService._generar_alertas_legajo(legajo))

            return alertas_generadas

        except Exception as exc:
            logger.exception("Error generando alertas: %s", exc)
            return []

    @staticmethod
    def generar_alertas_legajo(legajo):
        """Regenera solo las alertas del legajo dado (para la señal post_save)."""
        try:
            return AlertasService._generar_alertas_legajo(legajo)
        except Exception as exc:
            logger.exception("Error generando alertas del legajo: %s", exc)
            return []

    @staticmethod
    def _generar_alertas_legajo(legajo):
        """Genera alertas específicas de un legajo."""
        alertas = []
        ciudadano = legajo.ciudadano

        if not ciudadano:
            return alertas

        if legajo.nivel_riesgo == "ALTO":
            alertas.append(
                AlertasService._crear_alerta(
                    ciudadano,
                    legajo,
                    "RIESGO_ALTO",
                    "ALTA",
                    "Legajo con nivel de riesgo alto",
                )
            )

        evaluacion = getattr(legajo, "evaluacion", None)
        if not evaluacion:
            dias_sin_eval = (timezone.localdate() - legajo.fecha_apertura).days
            if dias_sin_eval > 15:
                alertas.append(
                    AlertasService._crear_alerta(
                        ciudadano,
                        legajo,
                        "SIN_EVALUACION",
                        "MEDIA",
                        f"Sin evaluación inicial hace {dias_sin_eval} días",
                    )
                )

        if legajo.estado in ["ABIERTO", "EN_SEGUIMIENTO"] and not legajo.plan_vigente:
            alertas.append(
                AlertasService._crear_alerta(
                    ciudadano,
                    legajo,
                    "SIN_PLAN",
                    "MEDIA",
                    "Legajo activo sin plan de intervención",
                )
            )

        ultimo_contacto = HistorialContacto.objects.filter(legajo=legajo).order_by("-fecha_contacto").first()

        if ultimo_contacto:
            dias_sin_contacto = (timezone.localdate() - fecha_local(ultimo_contacto.fecha_contacto)).days
            if dias_sin_contacto > 30:
                alertas.append(
                    AlertasService._crear_alerta(
                        ciudadano,
                        legajo,
                        "SIN_CONTACTO",
                        "ALTA",
                        f"Sin contacto hace {dias_sin_contacto} días",
                    )
                )

        contactos_fallidos = HistorialContacto.objects.filter(
            legajo=legajo,
            estado="NO_CONTESTA",
            fecha_contacto__gte=timezone.now() - timedelta(days=30),
        ).count()

        if contactos_fallidos >= 3:
            alertas.append(
                AlertasService._crear_alerta(
                    ciudadano,
                    legajo,
                    "CONTACTOS_FALLIDOS",
                    "MEDIA",
                    f"{contactos_fallidos} contactos fallidos en el último mes",
                )
            )

        return alertas

    @staticmethod
    def _crear_alerta(ciudadano, legajo, tipo, prioridad, mensaje):
        """Crea una alerta si no existe una similar activa."""
        alerta_existente = AlertaCiudadano.objects.filter(
            ciudadano=ciudadano,
            legajo=legajo,
            tipo=tipo,
            activa=True,
        ).first()

        if not alerta_existente:
            alerta = AlertaCiudadano.objects.create(
                ciudadano=ciudadano,
                legajo=legajo,
                tipo=tipo,
                prioridad=prioridad,
                mensaje=mensaje,
            )
            AlertasService._enviar_notificacion_alerta(alerta)
            return alerta

        return alerta_existente

    @staticmethod
    def _ruteo_de(legajo_id, responsable_id):
        """Datos **de servidor** para que el consumer decida el alcance sin consultar.

        El grupo `alertas_sistema` es uno solo y el filtro por alcance va en la
        entrega. Resolverlo ahí costaba cinco consultas por alerta **y por
        socket** —tres ``IN`` anidados sobre las 40k inscripciones—, y la pasada
        horaria de ``generar_alertas`` redifunde todo de una: con el
        ``read_timeout`` de 10 s de ECOM eso es una cola. Acá se resuelve **una
        vez por alerta**, del lado del emisor, y el consumer compara contra el
        alcance que tiene cacheado (`AlertasConsumer`).

        Viaja en el evento aparte de ``alerta``: nunca se le manda al cliente.
        """
        if legajo_id is None:
            return {"responsable_id": None, "programa_ids": []}
        return {
            "responsable_id": responsable_id,
            "programa_ids": sorted(set(get_programa_ids_for_legajo_ids([legajo_id]))),
        }

    @staticmethod
    def _enviar_notificacion_alerta(alerta):
        """Envía notificación WebSocket para nueva alerta."""
        try:
            channel_layer = get_channel_layer()

            alerta_data = {
                "id": alerta.id,
                "ciudadano": alerta.ciudadano.nombre_completo,
                "ciudadano_id": alerta.ciudadano.id,
                "tipo": alerta.tipo,
                "prioridad": alerta.prioridad,
                "mensaje": alerta.mensaje,
                "fecha": alerta.creado.strftime("%d/%m/%Y %H:%M"),
                # `LegajoAtencion.id` es un UUID y el consumer serializa el
                # evento con `json.dumps`: sin `str()` reventaba con
                # «Object of type UUID is not JSON serializable» —y reventaba
                # justo en las alertas que **sí** cuelgan de un legajo, que son
                # las únicas que caen dentro del alcance de alguien (G1c-04)—.
                # El error moría en el log del consumer, así que la difusión
                # parecía andar.
                "legajo_id": str(alerta.legajo.id) if alerta.legajo else None,
            }

            # **Un** `group_send` por alerta, también para las CRÍTICAS. G1c-17
            # había arreglado la rama crítica —mandaba al grupo `alertas_criticas`
            # con el tipo `nueva_alerta_critica`, que no existen en ningún
            # consumer, y por eso el modal nunca se disparaba— pero la dejó como un
            # **segundo** mensaje sobre el mismo grupo: la crítica llegaba dos
            # veces, el cliente mostraba toast *y* modal, el sonido sonaba dos
            # veces y el contador se refrescaba dos veces. La prioridad ya viaja en
            # el payload: la forma del aviso la decide el cliente.
            async_to_sync(channel_layer.group_send)(
                "alertas_sistema",
                {
                    "type": "nueva_alerta",
                    "alerta": alerta_data,
                    "ruteo": AlertasService._ruteo_de(alerta.legajo_id, getattr(alerta.legajo, "responsable_id", None)),
                },
            )
        except Exception as exc:
            logger.exception("Error enviando notificación WebSocket: %s", exc)

    @staticmethod
    def _enviar_cierre_alerta(alerta):
        """Avisa por WS que una alerta se cerró, para sacarla del dashboard abierto.

        El handler `alerta_cerrada` del consumer existía desde el principio **sin
        un solo productor**, así que nunca podía llegar: la tarjeta de la alerta
        que otro acababa de cerrar se quedaba en pantalla hasta recargar. Y
        resolver su alcance con ``obtener_alertas_usuario`` —que filtra
        ``activa=True``— era imposible por construcción, porque para cuando se
        emite el cierre la alerta ya está en ``activa=False``. El ruteo del
        emisor no mira ``activa``, así que el cierre se entrega al mismo conjunto
        de sockets que recibió el alta.
        """
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                "alertas_sistema",
                {
                    "type": "alerta_cerrada",
                    "alerta_id": alerta.id,
                    "ruteo": AlertasService._ruteo_de(alerta.legajo_id, getattr(alerta.legajo, "responsable_id", None)),
                },
            )
        except Exception as exc:
            logger.exception("Error enviando el cierre de alerta por WebSocket: %s", exc)

    @staticmethod
    def obtener_alertas_ciudadano(ciudadano_id):
        """Obtiene alertas activas de un ciudadano."""
        return (
            AlertaCiudadano.objects.filter(
                ciudadano_id=ciudadano_id,
                activa=True,
            )
            .select_related("legajo")
            .order_by("-prioridad", "-creado")
        )

    @staticmethod
    def cerrar_alerta(alerta_id, usuario=None):
        """Cierra una alerta **del alcance del usuario**.

        Antes resolvía ``AlertaCiudadano.objects.get(id=alerta_id)`` sobre toda
        la tabla: con `n = 1..N` cualquier cuenta de backoffice silenciaba las
        alertas de todo el sistema (SEC-18, auditoría oct-2026). Ahora la busca
        dentro de ``FiltrosUsuarioService.obtener_alertas_usuario``, el mismo
        alcance con el que el usuario las ve; fuera de ahí devuelve ``False``.

        Un ``alerta_id`` que no es un entero (el `pk` crudo de una ruta de DRF)
        levantaba ``ValueError`` y la vista contestaba **500**: acá también es
        ``False``.
        """
        from .filtros_usuario import FiltrosUsuarioService

        if usuario is None:
            return False
        try:
            # `select_related("legajo")`: el aviso de cierre por WS necesita el
            # `responsable_id` del legajo y así no cuesta una consulta extra.
            alerta = FiltrosUsuarioService.obtener_alertas_usuario(usuario).select_related("legajo").get(id=alerta_id)
        except (AlertaCiudadano.DoesNotExist, ValueError, TypeError, ValidationError):
            return False

        alerta.activa = False
        alerta.fecha_cierre = timezone.now()
        alerta.cerrada_por = usuario
        alerta.save()
        AlertasService._enviar_cierre_alerta(alerta)
        return True

    @staticmethod
    def generar_alerta_mensaje_ciudadano(conversacion):
        """Genera alerta cuando un ciudadano envía un mensaje."""
        if not conversacion or not hasattr(conversacion, "ciudadano"):
            return None

        return AlertasService._crear_alerta(
            conversacion.ciudadano,
            None,
            "MENSAJE_CIUDADANO",
            "MEDIA",
            "Nuevo mensaje del ciudadano en conversación",
        )

    @staticmethod
    def generar_alerta_seguimiento_vencido(seguimiento):
        """Genera alerta por seguimiento vencido."""
        if not seguimiento or not seguimiento.legajo:
            return None

        ciudadano = seguimiento.legajo.ciudadano
        if not ciudadano:
            return None

        return AlertasService._crear_alerta(
            ciudadano,
            seguimiento.legajo,
            "SEGUIMIENTO_VENCIDO",
            "ALTA",
            "Seguimiento con fecha vencida",
        )

    @staticmethod
    def generar_alerta_evento_critico(legajo, tipo_evento, descripcion):
        """Genera alerta por evento crítico."""
        if not legajo:
            return None

        ciudadano = legajo.ciudadano
        if not ciudadano:
            return None

        return AlertasService._crear_alerta(
            ciudadano,
            legajo,
            tipo_evento,
            "CRITICA",
            descripcion,
        )
