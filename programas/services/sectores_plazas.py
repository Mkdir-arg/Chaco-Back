"""Datos de la pantalla «Sectores y plazas» de un dispositivo (MVP v2, etapa 1 · P5).

La vista no cuenta ni decide estados: delega acá. Y acá hay **dos costuras** que el
servicio único de cálculo de la task 22 tiene que reemplazar cuando exista:

* `resumen_de_plazas`: los contadores por sector (total, operativas, fuera de servicio y,
  con estadías, ocupadas, reservadas, prestadas y disponibles).
* `ocupacion_de_plazas`: el estado derivado de cada plaza que se dibuja.

**Mientras `Estadia` no exista, la ocupación no se puede saber.** `Plaza.estado` solo
guarda OPERATIVA o FUERA_SERVICIO, y pintar «Disponible» una plaza operativa sería
afirmar algo que nadie sabe. Por eso, con `OCUPACION_CONOCIDA = False`, una plaza
operativa se dibuja «Operativa» con el tono neutro del mapa, la leyenda trae solo los
dos estados que existen y la pantalla avisa por qué. El cuerpo provisional de las dos
costuras se borra cuando entre el servicio de la task 22; el resto del módulo no cambia.
"""

from django.db.models import Count, Q

from programas.models import Plaza, Sector

# Tope por sector: el componente dibuja hasta 200 y avisa «Mostrando 200 de N»; la vista
# acota cada sector para no mandar un dispositivo entero en una sola grilla.
TOPE_PLAZAS_POR_SECTOR = 200

# Costura de la task 22: pasa a True cuando las estadías permitan derivar la ocupación.
OCUPACION_CONOCIDA = False

ESTADO_OPERATIVA = "Operativa"
ESTADO_FUERA_SERVICIO = "Fuera de servicio"
TONO_OPERATIVA = "neutro"  # un tono desconocido dibuja la celda neutra: no es «disponible»
TONO_FUERA_SERVICIO = "danger"


def leyenda_plazas():
    """Los estados que la pantalla puede mostrar hoy, con el mismo tono que las plazas."""

    return [
        {"estado": ESTADO_OPERATIVA, "tono": TONO_OPERATIVA},
        {"estado": ESTADO_FUERA_SERVICIO, "tono": TONO_FUERA_SERVICIO},
    ]


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


def ocupacion_de_plazas(plaza_ids):
    """Estado derivado de las plazas que la ocupación vuelve a colorear.

    `{plaza_id: {"estado": "Ocupada", "tono": "info", "detalle": "Benítez, R."}}`.
    PROVISIONAL (costura task 22): sin estadías no hay nada que derivar.
    """

    return {}


def _plaza_para_el_mapa(plaza, ocupacion):
    """Un dict del mapa: estado y tono los decide esta función, nunca el template."""

    if plaza.estado == Plaza.Estado.FUERA_SERVICIO:
        return {
            "codigo": plaza.codigo,
            "estado": ESTADO_FUERA_SERVICIO,
            "tono": TONO_FUERA_SERVICIO,
            "detalle": plaza.motivo_fuera_servicio,
        }
    derivado = ocupacion.get(plaza.pk)
    if derivado:
        return {"codigo": plaza.codigo, **derivado}
    return {"codigo": plaza.codigo, "estado": ESTADO_OPERATIVA, "tono": TONO_OPERATIVA}


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
        ocupacion = ocupacion_de_plazas([plaza.pk for plaza in plazas])
        armados.append(
            {
                "sector": sector,
                "resumen": resumen[sector.pk],
                "difiere_de_lo_declarado": sector.capacidad != resumen[sector.pk]["total"],
                "plazas": [_plaza_para_el_mapa(plaza, ocupacion) for plaza in plazas],
            }
        )
    return {
        "sectores": armados,
        "totales": totales,
        "leyenda": leyenda_plazas(),
        "ocupacion_conocida": OCUPACION_CONOCIDA,
    }
