"""Lecturas de `LegajoAtencion` — una sola definición de «legajo activo».

Antes la regla estaba escrita en `reportes_view` (`exclude(estado="CERRADO")`) y el
inicio ni siquiera miraba este modelo: su tarjeta «Legajos activos» salía de
`dashboard.utils.contar_legajos()`, que agrega `InscripcionPrograma`. Las dos
pantallas se contradecían en la misma sesión (G2-04, ronda 2 del PR 7 de la Ola 5).

Acá vive la regla y de acá la toman las dos.
"""

from django.db.models import Count, Q

from ..models import LegajoAtencion

#: Único estado que saca a un legajo de la operación. `LegajoBase.Estado` tiene
#: cuatro: ABIERTO, EN_SEGUIMIENTO, DERIVADO y CERRADO. Un legajo derivado sigue
#: siendo trabajo de alguien, así que cuenta como activo.
ESTADO_CERRADO = LegajoAtencion.Estado.CERRADO


def legajos_abiertos(queryset=None):
    """Los legajos que siguen en curso: todo lo que no esté cerrado."""
    base = LegajoAtencion.objects.all() if queryset is None else queryset
    return base.exclude(estado=ESTADO_CERRADO)


def resumen_legajos_atencion(queryset=None):
    """``{"total": n, "activos": n}`` en **una** consulta.

    Dos `count()` serían dos consultas sobre la misma tabla; el `aggregate` con
    `filter=` las resuelve juntas y usa el índice de `estado`.
    """
    base = LegajoAtencion.objects.all() if queryset is None else queryset
    return base.aggregate(
        total=Count("id"),
        activos=Count("id", filter=~Q(estado=ESTADO_CERRADO)),
    )
