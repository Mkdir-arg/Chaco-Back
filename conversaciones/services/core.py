import logging

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from ..models import ColaAsignacion, Conversacion, MetricasOperador

logger = logging.getLogger(__name__)


class AsignadorAutomatico:
    """Servicio para asignación automática de conversaciones"""

    @staticmethod
    def obtener_operador_disponible():
        """Obtiene el operador más adecuado para asignar una conversación (solo operadores logueados)"""
        try:
            from ..presencia import usuarios_logueados as get_usuarios_logueados

            usuarios_logueados = get_usuarios_logueados()

            # Buscar operadores disponibles que estén logueados
            cola_disponible = (
                ColaAsignacion.objects.filter(
                    activo=True,
                    operador_id__in=usuarios_logueados,
                    conversaciones_actuales__lt=models.F("max_conversaciones"),
                )
                .select_related("operador")
                .order_by("conversaciones_actuales", "ultima_asignacion")
                .first()
            )

            if cola_disponible:
                return cola_disponible.operador

            # Si no hay operadores disponibles con capacidad, buscar el menos cargado que esté logueado
            cola_menos_cargada = (
                ColaAsignacion.objects.filter(activo=True, operador_id__in=usuarios_logueados)
                .select_related("operador")
                .order_by("conversaciones_actuales")
                .first()
            )

            return cola_menos_cargada.operador if cola_menos_cargada else None

        except Exception as e:
            logger.error(f"Error al obtener operador disponible: {e}")
            return None

    @staticmethod
    def asignar_conversacion_automatica(conversacion):
        """Asigna automáticamente una conversación al operador más adecuado"""
        try:
            operador = AsignadorAutomatico.obtener_operador_disponible()

            if operador:
                conversacion.asignar_operador(operador)

                # Incremento atómico: mantiene el orden de reparto entre
                # asignaciones consecutivas sin un COUNT + save por ítem.
                cola, created = ColaAsignacion.objects.get_or_create(
                    operador=operador, defaults={"max_conversaciones": 5}
                )
                ColaAsignacion.objects.filter(pk=cola.pk).update(
                    conversaciones_actuales=models.F("conversaciones_actuales") + 1,
                    ultima_asignacion=timezone.now(),
                )

                logger.info(f"Conversación {conversacion.id} asignada automáticamente a {operador.username}")
                return True
            else:
                logger.warning(f"No hay operadores disponibles para conversación {conversacion.id}")
                return False

        except Exception as e:
            logger.error(f"Error al asignar conversación automáticamente: {e}")
            return False

    @staticmethod
    def configurar_operador(operador, max_conversaciones=5, activo=True):
        """Configura un operador en el sistema de cola"""
        cola, created = ColaAsignacion.objects.get_or_create(
            operador=operador, defaults={"max_conversaciones": max_conversaciones, "activo": activo}
        )

        if not created:
            cola.max_conversaciones = max_conversaciones
            cola.activo = activo
            cola.save()

        cola.actualizar_contador()
        return cola

    @staticmethod
    def actualizar_todas_las_colas():
        """Actualiza los contadores de todas las colas (1 agregado + 1 bulk_update)."""
        from django.db.models import Count

        conteos = dict(
            Conversacion.objects.filter(estado="activa", operador_asignado__isnull=False)
            .values("operador_asignado")
            .annotate(n=Count("id"))
            .values_list("operador_asignado", "n")
        )
        colas = list(ColaAsignacion.objects.all())
        for cola in colas:
            cola.conversaciones_actuales = conteos.get(cola.operador_id, 0)
        ColaAsignacion.objects.bulk_update(colas, ["conversaciones_actuales"])


class MetricasService:
    """Servicio para cálculo y actualización de métricas"""

    @staticmethod
    def calcular_metricas_globales():
        """Métricas globales, cacheadas: la página de métricas se refresca sola
        y varios usuarios pueden mirarla a la vez; los agregados corren 1 vez/min."""
        from django.core.cache import cache

        return cache.get_or_set(
            "conversaciones:metricas_globales",
            MetricasService._calcular_metricas_globales,
            60,
        )

    @staticmethod
    def _calcular_metricas_globales():
        from datetime import timedelta

        from django.db.models import Avg, Count, Q

        ahora = timezone.now()
        hoy = ahora.date()
        semana_pasada = hoy - timedelta(days=7)
        mes_pasado = hoy - timedelta(days=30)

        # Optimizar con una sola consulta aggregate
        stats = Conversacion.objects.aggregate(
            total_conversaciones=Count("id"),
            conversaciones_hoy=Count("id", filter=Q(fecha_inicio__date=hoy)),
            conversaciones_semana=Count("id", filter=Q(fecha_inicio__date__gte=semana_pasada)),
            conversaciones_mes=Count("id", filter=Q(fecha_inicio__date__gte=mes_pasado)),
            pendientes=Count("id", filter=Q(estado="pendiente")),
            activas=Count("id", filter=Q(estado="activa")),
            cerradas_hoy=Count("id", filter=Q(estado="cerrada", fecha_cierre__date=hoy)),
            tiempo_respuesta_promedio=Avg("tiempo_respuesta_segundos"),
            tiempo_espera_promedio=Avg("tiempo_espera_segundos"),
            satisfaccion_promedio=Avg("satisfaccion"),
        )

        metricas = stats

        # Normalizar valores None a 0
        metricas["tiempo_respuesta_promedio"] = stats["tiempo_respuesta_promedio"] or 0
        metricas["tiempo_espera_promedio"] = stats["tiempo_espera_promedio"] or 0
        metricas["satisfaccion_promedio"] = stats["satisfaccion_promedio"] or 0

        # Operadores (consulta separada optimizada)
        operadores_stats = ColaAsignacion.objects.aggregate(
            operadores_activos=Count("id", filter=Q(activo=True)),
            operadores_disponibles=Count(
                "id", filter=Q(activo=True, conversaciones_actuales__lt=models.F("max_conversaciones"))
            ),
        )
        metricas.update(operadores_stats)

        # Convertir segundos a minutos
        metricas["tiempo_respuesta_promedio_min"] = round(metricas["tiempo_respuesta_promedio"] / 60, 1)
        metricas["tiempo_espera_promedio_min"] = round(metricas["tiempo_espera_promedio"] / 60, 1)

        return metricas

    @staticmethod
    def actualizar_metricas_operador(operador):
        """Actualiza las métricas de un operador específico"""
        metricas, created = MetricasOperador.objects.get_or_create(operador=operador)
        metricas.actualizar_metricas()
        return metricas

    @staticmethod
    def actualizar_todas_las_metricas():
        """Actualiza las métricas de todos los operadores"""
        operadores = User.objects.filter(groups__name__in=["Conversaciones", "OperadorCharla"]).prefetch_related(
            "groups"
        )

        for operador in operadores:
            MetricasService.actualizar_metricas_operador(operador)


class NotificacionService:
    """Servicio para notificaciones en tiempo real"""

    @staticmethod
    def notificar_nueva_conversacion(conversacion):
        """Notifica a los operadores sobre una nueva conversación"""
        # TODO: Implementar con WebSockets cuando esté configurado
        try:
            # from channels.layers import get_channel_layer
            # from asgiref.sync import async_to_sync
            #
            # channel_layer = get_channel_layer()
            # async_to_sync(channel_layer.group_send)(
            #     'conversaciones_operadores',
            #     {
            #         'type': 'nueva_conversacion',
            #         'conversacion': {
            #             'id': conversacion.id,
            #             'tipo': conversacion.get_tipo_display(),
            #             'prioridad': conversacion.get_prioridad_display(),
            #             'dni': conversacion.dni_ciudadano or 'Anónimo',
            #             'fecha': conversacion.fecha_inicio.strftime('%H:%M')
            #         }
            #     }
            # )
            logger.info(f"Notificación enviada para conversación {conversacion.id}")
        except Exception as e:
            logger.error(f"Error al enviar notificación: {e}")

    @staticmethod
    def notificar_mensaje(conversacion, mensaje):
        """Notifica sobre un nuevo mensaje en una conversación"""
        # TODO: Implementar con WebSockets
        try:
            # Notificar en el canal específico de la conversación
            # y en el canal general de operadores
            logger.info(f"Mensaje notificado en conversación {conversacion.id}")
        except Exception as e:
            logger.error(f"Error al notificar mensaje: {e}")
