from dataclasses import dataclass
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from ..models.nachec import CasoNachec, HistorialEstadoCaso, TareaNachec
from ..models_programas import DerivacionPrograma


@dataclass(frozen=True)
class DerivacionProgramaResult:
    status: str
    message: str


class DerivacionProgramaService:
    @staticmethod
    def build_nachec_acceptance_context(derivacion):
        ciudadano = derivacion.ciudadano
        validaciones = {
            'tiene_nombre': bool(ciudadano.nombre and ciudadano.apellido),
            'tiene_dni': bool(ciudadano.dni),
            'tiene_contacto': bool(ciudadano.telefono or ciudadano.domicilio),
            'tiene_municipio': bool(ciudadano.municipio),
        }
        duplicados = CasoNachec.objects.none()
        if ciudadano.dni and ciudadano.dni.strip():
            duplicados = CasoNachec.objects.filter(
                ciudadano_titular__dni=ciudadano.dni
            ).exclude(
                estado__in=['DERIVADO', 'CERRADO', 'RECHAZADO', 'SUSPENDIDO']
            ).select_related('ciudadano_titular')

        return {
            'derivacion': derivacion,
            'validaciones': validaciones,
            'duplicados': duplicados,
            'datos_completos': all(validaciones.values()),
        }

    @classmethod
    @transaction.atomic
    def accept_derivacion(cls, derivacion_id, usuario):
        derivacion = cls._get_pending_derivacion(derivacion_id)
        derivacion.aceptar(usuario=usuario)
        return DerivacionProgramaResult(
            status='success',
            message=(
                f'Derivación aceptada. {derivacion.ciudadano.nombre_completo} '
                f'inscrito en {derivacion.programa_destino.nombre}.'
            ),
        )

    @classmethod
    @transaction.atomic
    def accept_nachec_derivacion(cls, derivacion_id, usuario, payload):
        derivacion = cls._get_pending_derivacion(derivacion_id)
        duplicate_resolution = cls._normalize_duplicate_resolution(payload)
        if duplicate_resolution == 'vincular':
            return DerivacionProgramaResult(
                status='info',
                message='Funcionalidad de vincular a caso existente en desarrollo',
            )

        derivacion.aceptar(usuario=usuario)
        cls._sync_nachec_case_after_acceptance(
            derivacion=derivacion,
            usuario=usuario,
            urgencia=payload.get('urgencia', 'MEDIA'),
            tipo_atencion=payload.get('tipo_atencion', 'No especificado'),
            comentario=payload.get('comentario', 'Sin comentarios'),
        )
        return DerivacionProgramaResult(
            status='success',
            message='Derivación aceptada. Caso en revisión con tarea asignada.',
        )

    @classmethod
    @transaction.atomic
    def reject_derivacion(cls, derivacion_id, usuario, motivo_rechazo):
        derivacion = cls._get_pending_derivacion(derivacion_id)
        derivacion.rechazar(
            usuario=usuario,
            motivo_rechazo=motivo_rechazo,
        )
        return DerivacionProgramaResult(
            status='success',
            message=f'Derivación de {derivacion.ciudadano.nombre_completo} rechazada.',
        )

    @staticmethod
    def _get_pending_derivacion(derivacion_id):
        derivacion = DerivacionPrograma.objects.select_for_update().select_related(
            'ciudadano',
            'programa_destino',
            'programa_origen',
        ).get(id=derivacion_id)
        if derivacion.estado != DerivacionPrograma.Estado.PENDIENTE:
            raise ValidationError('Esta derivación ya fue procesada.')
        return derivacion

    @staticmethod
    def _normalize_duplicate_resolution(payload):
        if payload.get('tiene_duplicado') != 'true':
            return None

        resolution = payload.get('resolucion_duplicado')
        if resolution == 'justificar':
            justificacion = (payload.get('justificacion_duplicado') or '').strip()
            if not justificacion:
                raise ValidationError('Debe justificar la creación de nuevo caso')
            return resolution
        if resolution != 'vincular':
            raise ValidationError('Debe seleccionar una opción para resolver el duplicado')
        return resolution

    @staticmethod
    def _sync_nachec_case_after_acceptance(derivacion, usuario, urgencia, tipo_atencion, comentario):
        caso = CasoNachec.objects.filter(
            ciudadano_titular=derivacion.ciudadano
        ).first()
        if not caso:
            return

        sla_dias = {'ALTA': 1, 'MEDIA': 2, 'BAJA': 3}.get(urgencia, 2)
        caso.prioridad = urgencia
        caso.save(update_fields=['prioridad'])

        TareaNachec.objects.create(
            caso=caso,
            tipo='VALIDACION',
            titulo='Revisión inicial - Validación de datos',
            descripcion=(
                "Checklist de revisión inicial:\n"
                "- Validar identidad (DNI o documento alternativo)\n"
                "- Validar jurisdicción (municipio/localidad)\n"
                "- Verificar datos de contacto\n"
                "- Determinar si corresponde relevamiento territorial\n"
                "- Definir si requiere asistencia inmediata\n"
                "- Confirmar o ajustar prioridad\n"
                "- Determinar próximos pasos\n\n"
                f"Tipo de atención: {tipo_atencion}\n"
                f"Comentario: {comentario}"
            ),
            asignado_a=usuario,
            creado_por=usuario,
            estado='PENDIENTE',
            prioridad=urgencia,
            fecha_vencimiento=timezone.now().date() + timedelta(days=sla_dias),
        )

        HistorialEstadoCaso.objects.create(
            caso=caso,
            estado_anterior='DERIVADO',
            estado_nuevo=caso.estado,
            usuario=usuario,
            observacion=f'Derivación aceptada. SLA: {sla_dias} días. Urgencia: {urgencia}',
        )
