"""Datos de la pantalla «Sectores y plazas» de un dispositivo (MVP v2, etapa 1 · P5).

La vista no cuenta ni decide estados: delega acá, y acá tampoco se deciden. El estado de
cada plaza (disponible, ocupada, reservada, prestada, fuera de servicio) y su tono los
deriva `programas.services.ocupacion.estado_de_plazas`, **el mismo** que usa el mapa del
asistente de ingreso: la misma plaza no puede verse distinta en las dos pantallas.

Queda una costura: `resumen_de_plazas` (los contadores por sector) todavía cuenta por su
cuenta y no suma ocupadas, reservadas ni disponibles; el servicio de ocupación ya las da.
"""

from django.db.models import Count, Q

from programas.models import Plaza, Sector
from programas.services.ocupacion import LEYENDA_PLAZAS, estado_de_plazas

# Tope por sector: el componente dibuja hasta 200 y avisa «Mostrando 200 de N»; la vista
# acota cada sector para no mandar un dispositivo entero en una sola grilla.
TOPE_PLAZAS_POR_SECTOR = 200

# La ocupación sale de `ocupacion.estado_de_plazas`: ya se conoce.
OCUPACION_CONOCIDA = True


def resumen_de_plazas(sector_ids):
    """Contadores por sector: `{sector_id: {"total", "operativas", "fuera_servicio"}}`.

    PROVISIONAL (costura task 22): una sola agregación. Con el servicio de cálculo, esta
    función le pide los números a él y suma ocupadas, reservadas, prestadas y disponibles.
    """

    filas = (
        Plaza.objects.filter(sector_id__in=sector_ids)
        .values("sector_id")
        .annotate(
            total=Count("pk"),
            fuera_servicio=Count("pk", filter=Q(estado=Plaza.Estado.FUERA_SERVICIO)),
        )
    )
    resumen = {sector_id: {"total": 0, "operativas": 0, "fuera_servicio": 0} for sector_id in sector_ids}
    for fila in filas:
        resumen[fila["sector_id"]] = {
            "total": fila["total"],
            "operativas": fila["total"] - fila["fuera_servicio"],
            "fuera_servicio": fila["fuera_servicio"],
        }
    return resumen


def _plaza_para_el_mapa(plaza, estado):
    """Un dict del mapa: estado y tono vienen del servicio, nunca del template ni de acá."""

    return {"codigo": plaza.codigo, "estado": estado.estado, "tono": estado.tono, "detalle": estado.detalle}


def sectores_con_plazas(dispositivo):
    """Todo lo que la pantalla dibuja: sectores activos con su mapa acotado y los totales."""

    sectores = list(Sector.objects.filter(dispositivo=dispositivo, activo=True).order_by("nombre"))
    resumen = resumen_de_plazas([sector.pk for sector in sectores])
    totales = {"total": 0, "operativas": 0, "fuera_servicio": 0}
    for contadores in resumen.values():
        for clave in totales:
            totales[clave] += contadores[clave]

    armados = []
    for sector in sectores:
        plazas = list(
            Plaza.objects.filter(sector=sector)
            .only("id", "codigo", "estado", "motivo_fuera_servicio")
            .order_by("codigo")[:TOPE_PLAZAS_POR_SECTOR]
        )
        estados = estado_de_plazas(plazas)
        armados.append(
            {
                "sector": sector,
                "resumen": resumen[sector.pk],
                "difiere_de_lo_declarado": sector.capacidad != resumen[sector.pk]["total"],
                "plazas": [_plaza_para_el_mapa(plaza, estados[plaza.pk]) for plaza in plazas],
            }
        )
    return {
        "sectores": armados,
        "totales": totales,
        "leyenda": LEYENDA_PLAZAS,
        "ocupacion_conocida": OCUPACION_CONOCIDA,
    }
