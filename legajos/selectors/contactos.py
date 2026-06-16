from datetime import datetime

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.shortcuts import get_object_or_404

from ..services.linking import get_legajos_queryset_for_ciudadano
from ..models import (
    Adjunto,
    Ciudadano,
    Derivacion,
    LegajoAtencion,
)

try:
    from ..models.contactos import HistorialContacto, VinculoFamiliar
except ImportError:  # pragma: no cover - compatibilidad legacy
    HistorialContacto = None
    VinculoFamiliar = None


def get_legajo_contactos_context(legajo_id):
    legajo = get_object_or_404(LegajoAtencion, id=legajo_id)
    return {
        'legajo': legajo,
        'ciudadano': legajo.ciudadano,
    }


def _format_legajo_codigo(legajo):
    return f"{str(legajo.codigo)[:12]}..." if legajo.codigo else str(legajo.id)


def _serialize_adjunto(archivo, *, legajo=None, origen='ciudadano'):
    payload = {
        'id': archivo.id,
        'nombre': archivo.archivo.name.split('/')[-1],
        'etiqueta': archivo.etiqueta,
        'url': archivo.archivo.url,
        'tamano': archivo.archivo.size,
        'fecha_subida': archivo.creado.isoformat(),
        'tipo_origen': origen,
    }
    if legajo is None:
        payload.update({'legajo_id': '-', 'legajo_codigo': 'Ciudadano'})
    else:
        payload.update(
            {
                'legajo_id': str(legajo.id),
                'legajo_codigo': _format_legajo_codigo(legajo),
            }
        )
    return payload


def build_ciudadano_actividades_payload(ciudadano_id):
    ciudadano = get_object_or_404(Ciudadano, id=ciudadano_id)
    legajos = get_legajos_queryset_for_ciudadano(
        ciudadano,
        LegajoAtencion.objects.select_related('responsable'),
    )
    actividades = []

    for legajo in legajos:
        if legajo.fecha_apertura:
            actividades.append(
                {
                    'fecha_hora': legajo.fecha_apertura.isoformat(),
                    'tipo': 'APERTURA',
                    'descripcion': (
                        f'Acompañamiento abierto en '
                        'programa vigente'
                    ),
                    'usuario_nombre': legajo.responsable.get_full_name() if legajo.responsable else 'Sistema',
                    'legajo_id': str(legajo.id),
                    'legajo_codigo': _format_legajo_codigo(legajo),
                }
            )

        if legajo.fecha_cierre:
            actividades.append(
                {
                    'fecha_hora': legajo.fecha_cierre.isoformat(),
                    'tipo': 'CIERRE',
                    'descripcion': 'Acompañamiento cerrado',
                    'usuario_nombre': 'Sistema',
                    'legajo_id': str(legajo.id),
                    'legajo_codigo': _format_legajo_codigo(legajo),
                }
            )

        derivaciones = Derivacion.objects.filter(legajo=legajo).select_related('actividad_destino')
        for derivacion in derivaciones:
            actividades.append(
                {
                    'fecha_hora': derivacion.creado.isoformat(),
                    'tipo': 'DERIVACION',
                    'descripcion': (
                        f'Derivación a '
                        f'{derivacion.actividad_destino.nombre if derivacion.actividad_destino else "destino no especificado"}'
                        f' - Estado: {derivacion.get_estado_display()}'
                    ),
                    'usuario_nombre': 'Sistema',
                    'legajo_id': str(legajo.id),
                    'legajo_codigo': _format_legajo_codigo(legajo),
                }
            )

    if VinculoFamiliar:
        for vinculo in VinculoFamiliar.objects.filter(ciudadano_principal=ciudadano):
            actividades.append(
                {
                    'fecha_hora': (
                        vinculo.creado.isoformat()
                        if hasattr(vinculo, 'creado')
                        else datetime.now().isoformat()
                    ),
                    'tipo': 'VINCULO',
                    'descripcion': (
                        'Vínculo agregado: '
                        f'{vinculo.get_tipo_vinculo_display() if hasattr(vinculo, "get_tipo_vinculo_display") else vinculo.tipo_vinculo}'
                    ),
                    'usuario_nombre': 'Sistema',
                    'legajo_id': '-',
                    'legajo_codigo': 'General',
                }
            )

    actividades.sort(key=lambda item: item['fecha_hora'] or '', reverse=True)
    return {
        'results': actividades[:50],
        'count': len(actividades),
    }


def build_ciudadano_archivos_payload(ciudadano_id):
    ciudadano = get_object_or_404(Ciudadano, id=ciudadano_id)
    legajos = list(get_legajos_queryset_for_ciudadano(ciudadano))
    ciudadano_content_type = ContentType.objects.get_for_model(Ciudadano)
    legajo_content_type = ContentType.objects.get_for_model(LegajoAtencion)

    archivos = Adjunto.objects.filter(
        Q(content_type=ciudadano_content_type, object_id=ciudadano.id)
        | Q(content_type=legajo_content_type, object_id__in=[legajo.id for legajo in legajos])
    ).order_by('-creado')

    legajos_por_id = {str(legajo.id): legajo for legajo in legajos}
    archivos_data = []
    for archivo in archivos:
        if archivo.content_type.model == 'ciudadano':
            archivos_data.append(_serialize_adjunto(archivo))
            continue
        legajo = legajos_por_id.get(str(archivo.object_id))
        if legajo:
            archivos_data.append(_serialize_adjunto(archivo, legajo=legajo, origen='legajo'))

    return {
        'results': archivos_data,
        'count': len(archivos_data),
    }


def build_legajo_archivos_payload(legajo_id):
    legajo = get_object_or_404(LegajoAtencion, id=legajo_id)
    content_type = ContentType.objects.get_for_model(LegajoAtencion)
    archivos = Adjunto.objects.filter(content_type=content_type, object_id=legajo.id).order_by('-creado')
    return {
        'success': True,
        'archivos': [
            {
                'id': archivo.id,
                'nombre': archivo.archivo.name.split('/')[-1],
                'etiqueta': archivo.etiqueta,
                'url': archivo.archivo.url,
                'fecha': archivo.creado.strftime('%d/%m/%Y %H:%M'),
            }
            for archivo in archivos
        ],
    }


def build_legajo_evolucion_payload(legajo_id):
    legajo = get_object_or_404(LegajoAtencion, id=legajo_id)
    total_seguimientos = HistorialContacto.objects.filter(legajo=legajo).count()
    adherencia_promedio = None
    objetivos_totales = 0
    objetivos_cumplidos = 0

    hitos = [
        {
            'tipo': 'APERTURA',
            'titulo': 'Apertura de Acompañamiento',
            'fecha': legajo.fecha_apertura.isoformat(),
        }
    ]
    evaluacion = getattr(legajo, 'evaluacion', None)
    if evaluacion:
        hitos.append(
            {
                'tipo': 'EVALUACION',
                'titulo': 'Evaluación Inicial',
                'fecha': evaluacion.creado.isoformat(),
            }
        )
    ultimo_seguimiento = HistorialContacto.objects.filter(legajo=legajo).order_by('-fecha_contacto').first()
    if ultimo_seguimiento:
        hitos.append(
            {
                'tipo': 'SEGUIMIENTO',
                'titulo': 'Último contacto registrado',
                'fecha': ultimo_seguimiento.fecha_contacto.isoformat(),
            }
        )
    derivacion_reciente = Derivacion.objects.filter(legajo=legajo).order_by('-creado').first()
    if derivacion_reciente:
        hitos.append(
            {
                'tipo': 'DERIVACION',
                'titulo': (
                    f'Derivación a '
                    f'{derivacion_reciente.actividad_destino.nombre if derivacion_reciente.actividad_destino else "destino no especificado"}'
                ),
                'fecha': derivacion_reciente.creado.isoformat(),
            }
        )
    if legajo.fecha_cierre:
        hitos.append(
            {
                'tipo': 'CIERRE',
                'titulo': 'Cierre de Acompañamiento',
                'fecha': legajo.fecha_cierre.isoformat(),
            }
        )

    hitos.sort(key=lambda item: item['fecha'])
    return {
        'total_seguimientos': total_seguimientos,
        'adherencia_promedio': adherencia_promedio,
        'objetivos_totales': objetivos_totales,
        'objetivos_cumplidos': objetivos_cumplidos,
        'hitos': hitos,
    }


def build_ciudadano_timeline_payload(ciudadano_id):
    ciudadano = get_object_or_404(Ciudadano, id=ciudadano_id)
    legajos = get_legajos_queryset_for_ciudadano(
        ciudadano,
        LegajoAtencion.objects.select_related('responsable'),
    )
    eventos = []

    for legajo in legajos:
        eventos.append(
            {
                'fecha': legajo.fecha_apertura.isoformat(),
                'tipo': 'APERTURA',
                'titulo': 'Apertura de Acompañamiento',
                'descripcion': (
                    'Acompañamiento iniciado'
                ),
                'legajo_id': str(legajo.id),
            }
        )

        evaluacion = getattr(legajo, 'evaluacion', None)
        if evaluacion:
            eventos.append(
                {
                    'fecha': evaluacion.creado.isoformat(),
                    'tipo': 'EVALUACION',
                    'titulo': 'Evaluación Inicial',
                    'descripcion': (
                        f'Evaluación realizada - Nivel de riesgo: {legajo.nivel_riesgo}'
                    ),
                    'legajo_id': str(legajo.id),
                }
            )

        for seguimiento in HistorialContacto.objects.filter(legajo=legajo).order_by('-fecha_contacto')[:3]:
            eventos.append(
                {
                    'fecha': seguimiento.fecha_contacto.isoformat(),
                    'tipo': 'SEGUIMIENTO',
                    'titulo': 'Seguimiento',
                    'descripcion': seguimiento.resumen[:150] if seguimiento.resumen else 'Sin descripción',
                    'legajo_id': str(legajo.id),
                }
            )

        for derivacion in Derivacion.objects.filter(legajo=legajo).select_related('actividad_destino'):
            eventos.append(
                {
                    'fecha': derivacion.creado.isoformat(),
                    'tipo': 'DERIVACION',
                    'titulo': 'Derivación',
                    'descripcion': (
                        f'Derivado a '
                        f'{derivacion.actividad_destino.nombre if derivacion.actividad_destino else "destino no especificado"}'
                        f' - {derivacion.get_estado_display()}'
                    ),
                    'legajo_id': str(legajo.id),
                }
            )

        if legajo.fecha_cierre:
            eventos.append(
                {
                    'fecha': legajo.fecha_cierre.isoformat(),
                    'tipo': 'CIERRE',
                    'titulo': 'Cierre de Acompañamiento',
                    'descripcion': f'Acompañamiento cerrado - Estado: {legajo.get_estado_display()}',
                    'legajo_id': str(legajo.id),
                }
            )

    if VinculoFamiliar:
        for vinculo in VinculoFamiliar.objects.filter(ciudadano_principal=ciudadano):
            eventos.append(
                {
                    'fecha': (
                        vinculo.creado.isoformat()
                        if hasattr(vinculo, 'creado')
                        else datetime.now().isoformat()
                    ),
                    'tipo': 'VINCULO',
                    'titulo': 'Vínculo Familiar',
                    'descripcion': (
                        'Vínculo agregado: '
                        f'{vinculo.get_tipo_vinculo_display() if hasattr(vinculo, "get_tipo_vinculo_display") else vinculo.tipo_vinculo}'
                    ),
                    'legajo_id': None,
                }
            )

    try:
        from ..models import AlertaCiudadano

        for alerta in AlertaCiudadano.objects.filter(
            ciudadano=ciudadano,
            prioridad__in=['CRITICA', 'ALTA'],
        ).order_by('-creado')[:5]:
            eventos.append(
                {
                    'fecha': alerta.creado.isoformat(),
                    'tipo': 'ALERTA',
                    'titulo': f'Alerta - {alerta.get_tipo_display()}',
                    'descripcion': alerta.mensaje,
                    'legajo_id': str(alerta.legajo.id) if alerta.legajo else None,
                }
            )
    except Exception:
        pass

    eventos.sort(key=lambda item: item['fecha'], reverse=True)
    return {
        'eventos': eventos[:30],
        'count': len(eventos),
    }
