"""Lecturas para la revisión de relevamientos edilicios."""

from programas.models import InspeccionEdificio
from programas.services.inspecciones import CAP_ASIGNAR, edificios_en_alcance


def relevamiento_para_revision(usuario, pk):
    """Ajeno e inexistente producen el mismo resultado, antes de leer su estado."""

    return (
        InspeccionEdificio.objects.filter(pk=pk, edificio__in=edificios_en_alcance(usuario, CAP_ASIGNAR))
        .select_related("edificio")
        .first()
    )
