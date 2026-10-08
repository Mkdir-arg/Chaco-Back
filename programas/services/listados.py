"""Paginación «pk primero, hidratar después» de las bandejas de Becas.

El patrón, medido en los Cambios 66, 92 y 93 y de nuevo en PERF-02 (auditoría
oct-2026) contra MariaDB 10.11: una página que proyecta las columnas de presentación
—cuatro JSON de unos 7 KB por caso— y además ordena por una columna sin índice obliga
al motor a materializar **todas** las filas del conjunto antes de recortar. En la
pantalla de cupo del banco de 20.000 casos eso eran 4,5 s por tabla; con la consulta
liviana (solo el pk) y una segunda consulta por los 50 de la página, 20 ms.

Las dos piezas viven acá y no en una vista porque las usan tres —``relevamientos``,
``revision`` y ``cupo``—, y el ratchet de RED-79 cuenta las aristas vista→vista.
"""

from django.core.paginator import Paginator


class PaginadorConConteo(Paginator):
    """Paginador que recibe el total ya contado.

    Para las bandejas que de todos modos hacen un ``aggregate`` sobre el mismo conjunto
    (total + aprobados, total + pendientes): el ``COUNT`` propio del paginador era un
    segundo recorrido de las mismas filas.
    """

    def __init__(self, object_list, per_page, total, **kwargs):
        super().__init__(object_list, per_page, **kwargs)
        self._total = total

    @property
    def count(self):
        return self._total


def hidratar_en_orden(pks, queryset):
    """Los objetos de ``queryset`` con esos ``pks``, en **el mismo orden** de la lista.

    ``filter(pk__in=…)`` no garantiza orden: el que manda es el de la consulta liviana
    que eligió la página, y es el que ve el usuario.
    """
    pks = list(pks)
    if not pks:
        return []
    por_pk = {obj.pk: obj for obj in queryset.filter(pk__in=pks)}
    return [por_pk[pk] for pk in pks if pk in por_pk]


def hidratar_pagina(pagina, queryset):
    """``hidratar_en_orden`` sobre una página de pks, devolviendo la misma página."""
    pagina.object_list = hidratar_en_orden(list(pagina.object_list), queryset)
    return pagina
