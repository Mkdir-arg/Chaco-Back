from django.core.exceptions import ValidationError
from django.db import transaction

from programas.models import (
    AsignacionCoordinadorRegional,
    AsignacionTerritorial,
    Convocatoria,
    TransferenciaRegional,
)
from programas.services.autorizacion import es_coordinador_regional_becas


@transaction.atomic
def transferir_responsabilidad_regional(*, origen, destino, ejecutado_por):
    """Transfiere el alcance vigente sin alterar creador ni datos históricos."""
    if origen == destino:
        raise ValidationError("El reemplazante debe ser otro usuario.")
    if not es_coordinador_regional_becas(origen) or not es_coordinador_regional_becas(destino):
        raise ValidationError("Ambos usuarios deben tener el rol Coordinador regional.")
    try:
        asignacion_origen = origen.asignacion_coordinador_regional
    except AsignacionCoordinadorRegional.DoesNotExist as exc:
        raise ValidationError("El Coordinador de origen no tiene una región asignada.") from exc

    region = asignacion_origen.region
    AsignacionCoordinadorRegional.objects.update_or_create(coordinador=destino, defaults={"region": region})
    convocatorias = Convocatoria.objects.filter(responsable_regional=origen).update(responsable_regional=destino)
    territoriales = AsignacionTerritorial.objects.filter(coordinador_regional=origen).update(
        coordinador_regional=destino
    )
    asignacion_origen.delete()
    transferencia = TransferenciaRegional.objects.create(
        region=region,
        coordinador_origen=origen,
        coordinador_destino=destino,
        ejecutado_por=ejecutado_por,
        convocatorias_transferidas=convocatorias,
        territoriales_transferidos=territoriales,
    )
    return {
        "region": region,
        "convocatorias": convocatorias,
        "territoriales": territoriales,
        "ejecutado_por": ejecutado_por,
        "transferencia": transferencia,
    }
