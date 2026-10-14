"""Lecturas de relevamientos edilicios: su revisión y su vencimiento."""

from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from programas.models import InspeccionEdificio
from programas.services.inspecciones import CAP_ASIGNAR, edificios_en_alcance


def relevamiento_para_revision(usuario, pk):
    """Ajeno e inexistente producen el mismo resultado, antes de leer su estado."""

    return (
        InspeccionEdificio.objects.filter(pk=pk, edificio__in=edificios_en_alcance(usuario, CAP_ASIGNAR))
        .select_related("edificio")
        .first()
    )


def condicion_relevamiento_vencido(hoy=None):
    return Q(estado=InspeccionEdificio.Estado.ASIGNADA, fecha_vencimiento__lt=hoy or timezone.localdate())


def relevamientos_vencidos(hoy=None):
    """En curso con fecha pasada; el día del vencimiento todavía está vigente."""
    return InspeccionEdificio.objects.filter(condicion_relevamiento_vencido(hoy))


def tiene_relevamiento_vencido(campo_edificio="pk", hoy=None):
    """Expresión para anotar edificios o sus vínculos sin consultas por fila."""
    return Exists(relevamientos_vencidos(hoy).filter(edificio_id=OuterRef(campo_edificio)))
