import datetime

from django.db.models import Q
from django.shortcuts import get_object_or_404

from conversaciones.models import Conversacion
from programas.models import DerivacionPrograma, InscripcionPrograma


def get_ciudadano_perfil_context(*, user, ciudadano):
    inscripciones_activas = []
    if hasattr(ciudadano, 'inscripciones_programas'):
        inscripciones_activas = list(
            ciudadano.inscripciones_programas.filter(
                estado__in=['ACTIVO', 'EN_SEGUIMIENTO']
            ).select_related('programa')[:5]
        )

    conversaciones_recientes = Conversacion.objects.filter(
        Q(dni_ciudadano=ciudadano.dni) | Q(ciudadano_usuario=user)
    ).order_by('-fecha_inicio')[:3]

    eventos = []
    inscripciones_timeline = []
    if hasattr(ciudadano, 'inscripciones_programas'):
        inscripciones_timeline = ciudadano.inscripciones_programas.select_related('programa').order_by('-fecha_inscripcion')[:3]

    for inscripcion in inscripciones_timeline:
        eventos.append(
            {
                'tipo': 'programa',
                'icono': 'fa-clipboard-list',
                'color': 'blue',
                'descripcion': f'Inscripción al programa {inscripcion.programa.nombre}',
                'fecha': datetime.datetime.combine(inscripcion.fecha_inscripcion, datetime.time.min),
                'fecha_display': inscripcion.fecha_inscripcion,
                'estado': inscripcion.estado,
            }
        )

    for conversacion in conversaciones_recientes:
        fecha = conversacion.fecha_inicio
        fecha_naive = fecha.replace(tzinfo=None) if fecha.tzinfo else fecha
        eventos.append(
            {
                'tipo': 'consulta',
                'icono': 'fa-comments',
                'color': 'green',
                'descripcion': 'Consulta iniciada',
                'fecha': fecha_naive,
                'fecha_display': fecha,
                'estado': conversacion.estado,
            }
        )

    eventos.sort(key=lambda item: item['fecha'], reverse=True)
    return {
        'inscripciones_activas': inscripciones_activas,
        'conversaciones_recientes': conversaciones_recientes,
        'eventos': eventos[:5],
    }


def get_ciudadano_programas_context(ciudadano):
    return {
        'inscripciones_activas': ciudadano.inscripciones_programas.filter(
            estado__in=['ACTIVO', 'EN_SEGUIMIENTO', 'PENDIENTE']
        ).select_related('programa').order_by('-fecha_inscripcion'),
        'inscripciones_historial': ciudadano.inscripciones_programas.filter(
            estado__in=['CERRADO', 'SUSPENDIDO']
        ).select_related('programa').order_by('-fecha_inscripcion'),
    }


def get_ciudadano_programa_detalle_or_404(ciudadano, pk):
    return get_object_or_404(InscripcionPrograma, pk=pk, ciudadano=ciudadano)


def get_ciudadano_programa_derivaciones(ciudadano, programa):
    return DerivacionPrograma.objects.filter(
        ciudadano=ciudadano,
        programa_destino=programa,
    ).select_related('programa_origen', 'programa_destino').order_by('-creado')
