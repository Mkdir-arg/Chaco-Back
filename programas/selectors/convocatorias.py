"""Lecturas de convocatorias de Becas para las pantallas de configuración.

Son selectores: leen, no deciden ni escriben. El alcance (qué convocatorias ve cada
rol) lo resuelve ``services.autorizacion.convocatorias_visibles``.
"""

from django.db.models import Count

from programas.models import Convocatoria
from programas.services.autorizacion import convocatorias_visibles


def convocatorias_listado_qs(user):
    """Convocatorias visibles para ``user``, listas para una tabla con su badge de estado.

    El badge de estado de cada fila mira ``pausa_efectiva``, que sube por
    segmento → programa y por subsegmento → segmento → programa: sin estas
    relaciones precargadas la tabla hace tres consultas por convocatoria.
    Es el queryset del listado de convocatorias y el de la solapa del segmento.
    """
    return (
        Convocatoria.objects.select_related(
            "segmento__programa",
            "subsegmento__segmento__programa",
        )
        .defer("descripcion", "segmento__descripcion", "subsegmento__descripcion")
        .annotate(n_relevamientos=Count("relevamientos", distinct=True))
        .filter(pk__in=convocatorias_visibles(user))
        .order_by("-fecha_inicio", "nombre")
    )


def convocatorias_de_segmento(user, segmento):
    """Las convocatorias del segmento: las del segmento entero y las de sus subsegmentos.

    Mismo orden que el listado de convocatorias. Se acota a lo que ``user`` puede ver:
    el Coordinador Regional recibe solo las de su subsegmento.
    """
    return convocatorias_listado_qs(user).filter(segmento=segmento)
