"""Las lecturas de la solapa «Abastecimiento» de E8 (análisis 009, §3.9 y §4.1, A1-A5).

Solo lectura: nada de acá calcula, decide una regla, mira permisos ni llama a ``now()``. Las reglas
de consumo (necesario, remanente, cobertura, faltan, urgencia, orden) están en
``programas.services.abastecimiento_emergencia``, que trabaja sobre lo que devuelve
:func:`lecturas_de_abastecimiento` y sobre la foto de situación, sin consultas.

Se lee **solo** con ``?tab=abastecimiento`` (RNF-009-11): la vista no llama a este módulo desde
otra solapa. No repite ninguna lectura de la foto: la red (con el estado de los elegibles), la
última recepción de cada dispositivo con gente («nunca recibió», «sin entrega en 48 h») y la salud
de las personas alojadas (``ficha__avisos_salud``, AE-9 = AE-7) salen de ``FotoSituacion``.

Todo lo acumulado cuenta **desde ``SLAEmergencia.inicio_evento``** (§3.9): lo recibido y lo egresado
antes no entra. Presupuesto (``programas.tests.test_emergencia_abastecimiento``, ``@tag("performance")``,
con 50 dispositivos, 30 ítems, 2.000 entregas y 3.000 alojados, más un evento anterior):

====  ==============================================================  ===========
A1    Ítems activos del catálogo con su regla de consumo               1
A2    Recibido por dispositivo × ítem desde el inicio, con la primera  1
      recepción del ítem en el dispositivo
A3    En camino y preparadas por dispositivo × ítem                    1
A4    Personas alojadas (y egresadas desde la primera recepción más     1
      vieja de A2) con su estadía, familia y lactantes declarados
A5    Dispositivos con gente que no están en la red de la foto (p. ej.  0 o 1
      suspendidos): su estado
**Solapa**                                                             **≤ 5**
====  ==============================================================  ===========

Ninguna consulta es por dispositivo ni por ítem: los cruces son diccionarios en Python.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import NamedTuple

from django.db.models import Min, Q, Sum

from programas.models import Dispositivo, EntregaKit, IntegranteGrupo, LineaEntrega
from programas.selectors.kits import q_demorada
from programas.services.configuracion_emergencia import catalogo_kits

#: La clave de «en camino hace más de 48 h»: va aparte de ``EN_CAMINO`` en ``LecturasAbastecimiento.abiertas``.
DEMORADA = "DEMORADA"


class ItemDelCatalogo(NamedTuple):
    """Un ítem activo con su regla (RN-009-15). ``modo`` vacío = sin regla."""

    id: int
    nombre: str
    unidad: str
    modo: str
    cantidad: Decimal | None
    por: str
    cada_dias: int | None


class Recibido(NamedTuple):
    """Lo recibido de un ítem en un dispositivo desde el inicio del evento (``cantidad_recibida``)."""

    cantidad: int
    primera: datetime


class PersonaDelAbastecimiento(NamedTuple):
    """Un integrante con estadía: alojado ahora (``egresado_en`` nulo) o egresado después del corte de A4."""

    dispositivo_id: int
    ingreso: datetime
    egresado_en: datetime | None
    orden: int
    grupo_id: int
    lactantes: int


class DispositivoFueraDeLaRed(NamedTuple):
    """Un dispositivo con gente que la red de la foto no trae (no es elegible: suspendido, sin camas…)."""

    id: int
    nombre: str
    localidad: str
    estado: str
    reservado: bool
    #: El tipo lleva stock (RN-010-01): E8 le muestra el «Stock registrado» (RN-010-20).
    lleva_stock: bool = False


@dataclass(frozen=True)
class LecturasAbastecimiento:
    inicio_evento: datetime
    items: tuple[ItemDelCatalogo, ...]
    #: ``{(dispositivo_id, item_id): Recibido}``
    recibido: dict
    #: ``{(dispositivo_id, item_id, estado): cantidad_enviada}`` de las ``PREPARADA`` y ``EN_CAMINO``.
    abiertas: dict
    personas: tuple[PersonaDelAbastecimiento, ...]
    #: ``{id: DispositivoFueraDeLaRed}``
    fuera_de_la_red: dict


def _items():
    """A1: los ítems activos en el orden del catálogo, con y sin regla."""

    filas = catalogo_kits(solo_activos=True).values_list(
        "id", "nombre", "unidad", "regla_modo", "regla_cantidad", "regla_por", "regla_cada_dias"
    )
    return tuple(ItemDelCatalogo(*fila) for fila in filas)


def _recibido(inicio_evento, dispositivo_id=None):
    """A2: ``Sum(cantidad_recibida)`` y ``Min(recibida_en)`` por dispositivo e ítem, desde el inicio."""

    lineas = LineaEntrega.objects.filter(
        entrega__estado__in=EntregaKit.ESTADOS_RECIBIDOS, entrega__recibida_en__gte=inicio_evento
    )
    if dispositivo_id is not None:
        lineas = lineas.filter(entrega__dispositivo_id=dispositivo_id)
    filas = (
        lineas.values("entrega__dispositivo_id", "item_id")
        .annotate(cantidad=Sum("cantidad_recibida"), primera=Min("entrega__recibida_en"))
        .order_by()
    )
    return {
        (fila["entrega__dispositivo_id"], fila["item_id"]): Recibido(fila["cantidad"] or 0, fila["primera"])
        for fila in filas
    }


def _primera_recepcion(inicio_evento):
    """La recepción más vieja desde el inicio, de todos los dispositivos: el corte de los egresados de A4."""

    return LineaEntrega.objects.filter(
        entrega__estado__in=EntregaKit.ESTADOS_RECIBIDOS, entrega__recibida_en__gte=inicio_evento
    ).aggregate(primera=Min("entrega__recibida_en"))["primera"]


def _abiertas(inicio_evento, ahora, dispositivo_id=None):
    """A3: lo enviado de las entregas ``PREPARADA`` y ``EN_CAMINO`` creadas desde el inicio, por estado.

    Lo que lleva más de :attr:`EntregaKit.HORAS_PARA_DEMORADA` horas en camino sin recibir **no cuenta** como
    ``EN_CAMINO``: va aparte, bajo la clave :data:`DEMORADA`, para que el faltante real se vea (Cambio 586). Sigue
    siendo **una** consulta. Con ``dispositivo_id`` solo ese dispositivo.
    """

    lineas = LineaEntrega.objects.filter(
        entrega__estado__in=EntregaKit.ESTADOS_ABIERTOS, entrega__creado__gte=inicio_evento
    )
    if dispositivo_id is not None:
        lineas = lineas.filter(entrega__dispositivo_id=dispositivo_id)
    filas = (
        lineas.values("entrega__dispositivo_id", "item_id", "entrega__estado")
        .annotate(
            cantidad=Sum("cantidad_enviada"),
            demorada=Sum("cantidad_enviada", filter=q_demorada(ahora, "entrega__")),
        )
        .order_by()
    )
    abiertas = {}
    for fila in filas:
        clave = (fila["entrega__dispositivo_id"], fila["item_id"])
        demorada = fila["demorada"] or 0
        abiertas[(*clave, fila["entrega__estado"])] = (fila["cantidad"] or 0) - demorada
        if demorada:
            abiertas[(*clave, DEMORADA)] = demorada
    return abiertas


def _personas(desde, dispositivo_id=None):
    """A4: los alojados ahora y, si ``desde`` no es ``None``, los egresados desde ahí.

    ``desde`` es ``max(inicio_evento, primera recepción más vieja de A2)``: antes de la primera
    recepción no hay consumo que imputar. Sin recepciones, solo los alojados ahora.
    """

    egreso = Q(egresado_en__isnull=True)
    if desde is not None:
        egreso |= Q(egresado_en__gte=desde)
    integrantes = IntegranteGrupo.objects.filter(estadia__isnull=False)
    if dispositivo_id is not None:
        # Las familias de este dispositivo **enteras**: su dispositivo principal es el del integrante de menor
        # `orden`, que puede estar en otro, y el cálculo tiene que decidirlo igual que la solapa.
        de_este = IntegranteGrupo.objects.filter(estadia__dispositivo_id=dispositivo_id).values("grupo_id")
        integrantes = integrantes.filter(grupo_id__in=de_este)
    filas = (
        integrantes.filter(egreso)
        .order_by()  # sin el orden del modelo: el cruce es en Python y el ORDER BY costaba un filesort
        .values_list(
            "estadia__dispositivo_id", "estadia__fecha_ingreso", "egresado_en", "orden", "grupo_id", "grupo__lactantes"
        )
    )
    return tuple(
        PersonaDelAbastecimiento(dispositivo, ingreso, egresado, orden, grupo, lactantes or 0)
        for dispositivo, ingreso, egresado, orden, grupo, lactantes in filas
    )


def _fuera_de_la_red(ids):
    """A5: solo si hay dispositivos con gente que la red de la foto no trae (casi siempre 0 consultas)."""

    if not ids:
        return {}
    filas = (
        Dispositivo.objects.filter(pk__in=ids)
        .order_by("nombre", "id")
        .values_list("id", "nombre", "localidad", "estado", "tipo__ubicacion_reservada", "tipo__maneja_stock")
    )
    return {
        pk: DispositivoFueraDeLaRed(pk, nombre, localidad or "", estado, bool(reservado), bool(lleva_stock))
        for pk, nombre, localidad, estado, reservado, lleva_stock in filas
    }


def lecturas_de_abastecimiento(foto, inicio_evento: datetime) -> LecturasAbastecimiento:
    """A1-A5 sobre la foto de E8. **≤ 5 consultas fijas.** ``inicio_evento`` no puede ser ``None``.

    A2 va antes que A4: A4 usa su primera recepción más vieja como corte de los egresados.
    """

    if inicio_evento is None:
        raise ValueError("Sin inicio del evento la solapa no calcula: la vista muestra el estado vacío.")
    items = _items()
    recibido = _recibido(inicio_evento)
    abiertas = _abiertas(inicio_evento, foto.ahora)
    primera = min((r.primera for r in recibido.values()), default=None)
    personas = _personas(max(inicio_evento, primera) if primera is not None else None)
    en_la_red = {dispositivo.id for dispositivo in foto.red.dispositivos}
    con_gente = {p.dispositivo_id for p in personas if p.egresado_en is None}
    return LecturasAbastecimiento(
        inicio_evento=inicio_evento,
        items=items,
        recibido=recibido,
        abiertas=abiertas,
        personas=personas,
        fuera_de_la_red=_fuera_de_la_red(sorted(con_gente - en_la_red)),
    )


def lecturas_de_un_dispositivo(dispositivo_id, inicio_evento: datetime, ahora: datetime) -> LecturasAbastecimiento:
    """A1-A4 acotadas a **un** dispositivo, sin la foto de situación: lo que necesita «Le falta (estimado)» de
    la entrega nueva (Cambio 586). **5 consultas fijas** (ítems, recibido, primera recepción de la red, en camino y
    preparadas, personas).

    Lo que se calcula con esto sale de las mismas reglas que la solapa Abastecimiento (``armar_abastecimiento``),
    así que el faltante de acá coincide con el de Situación. ``fuera_de_la_red`` va vacío: no hace falta el nombre.
    """

    if inicio_evento is None:
        raise ValueError("Sin inicio del evento no se estima: la pantalla lo dice.")
    recibido = _recibido(inicio_evento, dispositivo_id)
    # El corte de los egresados es el de la solapa: la primera recepción de **toda la red**, no la de este
    # dispositivo; si no, con un egreso entre las dos fechas la cobertura de las dos pantallas difiere.
    primera = _primera_recepcion(inicio_evento)
    return LecturasAbastecimiento(
        inicio_evento=inicio_evento,
        items=_items(),
        recibido=recibido,
        abiertas=_abiertas(inicio_evento, ahora, dispositivo_id),
        personas=_personas(max(inicio_evento, primera) if primera is not None else None, dispositivo_id),
        fuera_de_la_red={},
    )
