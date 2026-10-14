"""Lecturas compartidas del vencimiento de relevamientos edilicios.

Módulo aparte de `selectors/inspecciones.py`: aquel importa del servicio de inspecciones,
y el servicio lee estas funciones, así que juntos formarían un ciclo.
"""

from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from programas.models import InspeccionEdificio


def condicion_relevamiento_vencido(hoy=None):
    return Q(estado=InspeccionEdificio.Estado.ASIGNADA, fecha_vencimiento__lt=hoy or timezone.localdate())


def relevamientos_vencidos(hoy=None):
    """En curso con fecha pasada; el día del vencimiento todavía está vigente."""
    return InspeccionEdificio.objects.filter(condicion_relevamiento_vencido(hoy))


def tiene_relevamiento_vencido(campo_edificio="pk", hoy=None):
    """Expresión para anotar edificios o sus vínculos sin consultas por fila."""
    return Exists(relevamientos_vencidos(hoy).filter(edificio_id=OuterRef(campo_edificio)))
