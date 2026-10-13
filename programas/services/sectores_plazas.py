"""Datos de la pantalla «Sectores y plazas» de un dispositivo (MVP v2, etapa 1 · P5).

La vista no cuenta ni decide estados: delega acá, y acá tampoco se deciden. El estado de
cada plaza (disponible, ocupada, reservada, prestada, fuera de servicio) y su tono los
deriva `programas.services.ocupacion.estado_de_plazas`, **el mismo** que usa el mapa del
asistente de ingreso: la misma plaza no puede verse distinta en las dos pantallas.

Los contadores del encabezado y de cada sector salen de `ocupacion.ocupacion_de_plazas`
(el `Conteo` del servicio), no de una cuenta propia de la pantalla.
"""

from programas.models import Plaza, Sector
from programas.services.ocupacion import LEYENDA_PLAZAS, estado_de_plazas, ocupacion_de_plazas

# Tope por sector: el componente dibuja hasta 200 y avisa «Mostrando 200 de N»; la vista
# acota cada sector para no mandar un dispositivo entero en una sola grilla.
TOPE_PLAZAS_POR_SECTOR = 200


def _resumen(conteo):
    """Las cifras de un `Conteo` del servicio de ocupación, con las claves que lee la pantalla.

    `reservadas` es la cifra del servicio: reservas **y** préstamos vigentes.
    """

    return {
        "total": conteo.totales,
        "operativas": conteo.operativas,
        "fuera_servicio": conteo.fuera_de_servicio,
        "ocupadas": conteo.ocupadas,
        "reservadas": conteo.reservadas,
        "disponibles": conteo.disponibles,
    }


def _plaza_para_el_mapa(plaza, estado):
    """Un dict del mapa: estado y tono vienen del servicio, nunca del template ni de acá."""

    return {"codigo": plaza.codigo, "estado": estado.estado, "tono": estado.tono, "detalle": estado.detalle}


def sectores_con_plazas(dispositivo):
    """Todo lo que la pantalla dibuja: sectores activos con su mapa acotado y los totales.

    Las cifras del encabezado y de cada sector salen de `ocupacion.ocupacion_de_plazas` y
    los estados de las celdas de `ocupacion.estado_de_plazas`: las dos son el mismo
    servicio, así que el encabezado y el mapa no pueden decir cosas distintas.
    """

    ocupacion = ocupacion_de_plazas(dispositivo).de(dispositivo)
    sectores = {sector.pk: sector for sector in Sector.objects.filter(dispositivo=dispositivo, activo=True)}

    armados = []
    for item in ocupacion.sectores:
        sector = sectores[item.sector_id]
        plazas = list(
            Plaza.objects.filter(sector=sector)
            .only("id", "codigo", "estado", "motivo_fuera_servicio")
            .order_by("codigo")[:TOPE_PLAZAS_POR_SECTOR]
        )
        estados = estado_de_plazas(plazas)
        armados.append(
            {
                "sector": sector,
                "resumen": _resumen(item.conteo),
                "difiere_de_lo_declarado": sector.capacidad != item.conteo.totales,
                "plazas": [_plaza_para_el_mapa(plaza, estados[plaza.pk]) for plaza in plazas],
            }
        )
    return {
        "sectores": armados,
        "totales": _resumen(ocupacion.conteo),
        "leyenda": LEYENDA_PLAZAS,
    }
