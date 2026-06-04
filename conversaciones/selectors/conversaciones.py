from datetime import datetime

from django.contrib.auth.models import User
from django.db import models
from django.db.models import Avg, Count, Q
from django.utils import timezone

from ..models import ColaAsignacion, Conversacion, MetricasOperador
from ..permisos import es_operador_restringido, puede_operar


def usuario_tiene_permiso_conversaciones(user):
    return puede_operar(user)


def get_conversaciones_queryset_para_lista(user, filtros):
    if es_operador_restringido(user):
        queryset = Conversacion.objects.select_related('operador_asignado').annotate(
            mensajes_no_leidos=Count(
                'mensajes',
                filter=Q(mensajes__remitente='ciudadano', mensajes__leido=False),
            )
        ).filter(
            models.Q(operador_asignado=None) | models.Q(operador_asignado=user)
        )
    else:
        queryset = Conversacion.objects.select_related('operador_asignado').annotate(
            mensajes_no_leidos=Count(
                'mensajes',
                filter=Q(mensajes__remitente='ciudadano', mensajes__leido=False),
            )
        )

    if filtros.get('estado'):
        queryset = queryset.filter(estado=filtros['estado'])

    if filtros.get('operador'):
        if filtros['operador'] == 'sin_asignar':
            queryset = queryset.filter(operador_asignado=None)
        elif filtros['operador'] == 'mis_conversaciones':
            queryset = queryset.filter(operador_asignado=user)
        else:
            queryset = queryset.filter(operador_asignado_id=filtros['operador'])

    if filtros.get('fecha_desde'):
        queryset = queryset.filter(fecha_inicio__date__gte=filtros['fecha_desde'])

    if filtros.get('fecha_hasta'):
        queryset = queryset.filter(fecha_inicio__date__lte=filtros['fecha_hasta'])

    if filtros.get('busqueda'):
        queryset = queryset.filter(
            Q(id__icontains=filtros['busqueda']) | Q(dni_ciudadano__icontains=filtros['busqueda'])
        )

    if filtros.get('tipo'):
        queryset = queryset.filter(tipo=filtros['tipo'])

    return queryset


def get_estadisticas_lista():
    ahora = datetime.now()
    tiempo_promedio = Conversacion.objects.filter(
        operador_asignado__isnull=False,
        tiempo_respuesta_segundos__isnull=False,
    ).aggregate(
        promedio=Avg('tiempo_respuesta_segundos')
    )['promedio'] or 0

    return {
        'chats_no_atendidos': Conversacion.objects.filter(
            operador_asignado=None,
            estado='activa',
        ).count(),
        'atendidos_mes': Conversacion.objects.filter(
            operador_asignado__isnull=False,
            fecha_inicio__month=ahora.month,
            fecha_inicio__year=ahora.year,
        ).count(),
        'tiempo_promedio': round(tiempo_promedio / 60, 1),
    }


def get_operadores_con_carga():
    return User.objects.filter(
        groups__name__in=['Conversaciones', 'OperadorCharla']
    ).annotate(
        conversaciones_activas=Count('conversacion', filter=Q(conversacion__estado='activa'))
    ).order_by('first_name', 'last_name')


def get_todos_los_operadores():
    return User.objects.filter(
        groups__name__in=['Conversaciones', 'OperadorCharla']
    ).order_by('first_name', 'last_name')


def get_conversacion_detalle_queryset():
    return Conversacion.objects.select_related('operador_asignado').prefetch_related('mensajes')


def get_conversacion_api_detalle(conversacion_id):
    return Conversacion.objects.select_related('operador_asignado').annotate(
        mensajes_no_leidos=Count('mensajes', filter=Q(mensajes__remitente='ciudadano', mensajes__leido=False))
    ).get(id=conversacion_id)


def get_metricas_contexto():
    from ..services import MetricasService

    return {
        'metricas_globales': MetricasService.calcular_metricas_globales(),
        'metricas_operadores': MetricasOperador.objects.select_related('operador').all(),
        'colas': ColaAsignacion.objects.select_related('operador').all(),
    }


def get_configuracion_cola_contexto():
    return {
        'operadores': get_todos_los_operadores(),
        'colas': ColaAsignacion.objects.select_related('operador').all(),
    }


def get_conversaciones_sin_asignar():
    return Conversacion.objects.filter(
        estado='activa',
        operador_asignado=None,
    ).only('id', 'estado')


def get_estadisticas_tiempo_real():
    ahora = timezone.now()
    tiempo_promedio = Conversacion.objects.filter(
        operador_asignado__isnull=False,
        tiempo_respuesta_segundos__isnull=False,
    ).aggregate(
        promedio=Avg('tiempo_respuesta_segundos')
    )['promedio'] or 0

    return {
        'chats_no_atendidos': Conversacion.objects.filter(
            operador_asignado=None,
            estado='activa',
        ).count(),
        'atendidos_mes': Conversacion.objects.filter(
            operador_asignado__isnull=False,
            fecha_inicio__month=ahora.month,
            fecha_inicio__year=ahora.year,
        ).count(),
        'tiempo_promedio': round(tiempo_promedio / 60, 1),
    }


def get_alertas_conversaciones_count(user):
    from ..models import HistorialAlertaConversacion

    return HistorialAlertaConversacion.objects.filter(
        operador=user,
        vista=False,
    ).count()


def get_alertas_preview_mensajes(user):
    from ..models import Mensaje

    return Mensaje.objects.filter(
        conversacion__operador_asignado=user,
        conversacion__estado='activa',
        remitente='ciudadano',
        leido=False,
    ).select_related('conversacion').order_by('-fecha_envio')[:5]


def get_alertas_preview_nuevas_conversaciones(user):
    from ..models import NuevaConversacionAlerta

    return NuevaConversacionAlerta.objects.filter(
        operador=user,
        vista=False,
        conversacion__estado='pendiente',
    ).select_related('conversacion').order_by('-creado')[:3]


def get_conversacion_asignada_a_operador(conversacion_id, operador):
    return Conversacion.objects.get(
        id=conversacion_id,
        operador_asignado=operador,
    )
