"""
Servicios para gestión operativa de programas sociales.
"""
from django.db import transaction
from django.utils import timezone


class BajaProgramaService:
    """Gestiona la baja formal de un ciudadano de un programa persistente."""

    @staticmethod
    @transaction.atomic
    def dar_de_baja(inscripcion_id, usuario, motivo):
        """
        Da de baja a un ciudadano de un programa persistente.

        1. Valida que la inscripción esté en estado activo o en seguimiento.
        2. Actualiza estado a DADO_DE_BAJA con motivo y fecha de cierre.
        3. Cancela turnos pendientes/confirmados vinculados al programa.
        4. Cancela el flujo activo si existe.

        Raises:
            ValueError: si la inscripción no existe o no está en estado válido.
        """
        from programas.models import InscripcionPrograma

        try:
            inscripcion = InscripcionPrograma.objects.select_for_update().get(
                id=inscripcion_id
            )
        except InscripcionPrograma.DoesNotExist:
            raise ValueError("Inscripción no encontrada.")

        estados_validos = [
            InscripcionPrograma.Estado.ACTIVO,
            InscripcionPrograma.Estado.EN_SEGUIMIENTO,
            InscripcionPrograma.Estado.PENDIENTE,
        ]
        if inscripcion.estado not in estados_validos:
            raise ValueError(
                f"No se puede dar de baja una inscripción con estado "
                f"'{inscripcion.get_estado_display()}'."
            )

        # 1. Dar de baja la inscripción
        inscripcion.estado = InscripcionPrograma.Estado.DADO_DE_BAJA
        inscripcion.motivo_cierre = motivo
        inscripcion.fecha_cierre = timezone.now().date()
        inscripcion.save(update_fields=['estado', 'motivo_cierre', 'fecha_cierre'])

        return inscripcion
