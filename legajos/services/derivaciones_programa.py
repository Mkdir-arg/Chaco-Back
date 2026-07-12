from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction

from programas.models import DerivacionPrograma


@dataclass(frozen=True)
class DerivacionProgramaResult:
    status: str
    message: str


class DerivacionProgramaService:
    @classmethod
    @transaction.atomic
    def accept_derivacion(cls, derivacion_id, usuario):
        derivacion = cls._get_pending_derivacion(derivacion_id)
        derivacion.aceptar(usuario=usuario)
        return DerivacionProgramaResult(
            status="success",
            message=(
                f"Derivación aceptada. {derivacion.ciudadano.nombre_completo} "
                f"inscrito en {derivacion.programa_destino.nombre}."
            ),
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
            status="success",
            message=f"Derivación de {derivacion.ciudadano.nombre_completo} rechazada.",
        )

    @staticmethod
    def _get_pending_derivacion(derivacion_id):
        derivacion = (
            DerivacionPrograma.objects.select_for_update()
            .select_related(
                "ciudadano",
                "programa_destino",
                "programa_origen",
            )
            .get(id=derivacion_id)
        )
        if derivacion.estado != DerivacionPrograma.Estado.PENDIENTE:
            raise ValidationError("Esta derivación ya fue procesada.")
        return derivacion
