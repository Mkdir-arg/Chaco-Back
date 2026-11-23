"""Lecturas de configuración de la capacidad instalada y del predio compartido."""

from typing import NamedTuple

from django.db.models import Case, Count, Exists, F, OuterRef, Q, Value, When

from programas.models import Dispositivo, Edificio, Estadia, Plaza, ReservaPlaza, Sector
from programas.services.dispositivos import dispositivos_visibles
from programas.services.inspecciones import edificios_en_alcance
from programas.services.nombre_plaza import clave_natural


def instituciones_del_predio(usuario, edificios_ids, tambien=None):
    """Identidad de instituciones visibles; no revela siquiera nombres fuera del alcance.

    Los sectores se ubican en un edificio (`Sector.edificio`, Cambio 429) pero acá solo van
    las instituciones: los sectores por edificio los lee `sectores_por_edificio`.
    Una consulta para todos los edificios, con el tipo en el mismo JOIN.
    `tambien` (queryset de `Dispositivo`) suma otro alcance del usuario al de lectura: el
    coordinador de un relevamiento ve las instituciones que coordina aunque no las lea.
    """

    if usuario is None:
        return {}
    alcance = Q(dispositivo_id__in=dispositivos_visibles(usuario).values("pk"))
    if tambien is not None:
        alcance |= Q(dispositivo_id__in=tambien.values("pk"))
    filas = (
        Edificio.dispositivos.through.objects.filter(
            alcance,
            edificio_id__in=edificios_ids,
        )
        .values(
            "edificio_id", "dispositivo_id", "dispositivo__nombre", "dispositivo__tipo__nombre", "dispositivo__estado"
        )
        .order_by("dispositivo__nombre", "dispositivo_id")
    )
    resultado = {}
    for fila in filas:
        resultado.setdefault(fila["edificio_id"], []).append(
            {
                "pk": fila["dispositivo_id"],
                "nombre": fila["dispositivo__nombre"],
                "tipo": fila["dispositivo__tipo__nombre"],
                "estado": fila["dispositivo__estado"],
                "get_estado_display": dict(Dispositivo.Estado.choices).get(
                    fila["dispositivo__estado"], fila["dispositivo__estado"]
                ),
            }
        )
    return resultado


def edificios_vinculables(usuario, dispositivo):
    """Los edificios activos del alcance de ``usuario`` que ``dispositivo`` todavía no ocupa (el inactivo no se vincula)."""

    return (
        edificios_en_alcance(usuario, "dispositivo.editar")
        .filter(activo=True)
        .exclude(dispositivos=dispositivo)
        .order_by("nombre", "pk")
    )


def edificios_del_dispositivo(dispositivo):
    return Edificio.objects.filter(dispositivos=dispositivo).order_by("nombre", "pk")


def plazas_tomadas_del_sector(sector):
    """Dos consultas fijas: incluye reservas y préstamos abiertos aunque hayan vencido."""

    con_estadia = set(Estadia.objects.activas().filter(plaza__sector=sector).values_list("plaza_id", flat=True))
    con_reserva = set(
        ReservaPlaza.objects.filter(plaza__sector=sector, estado=ReservaPlaza.Estado.VIGENTE).values_list(
            "plaza_id", flat=True
        )
    )
    return len(con_estadia | con_reserva)


class CompromisosDelSector(NamedTuple):
    alojadas: int
    reservas: int


def compromisos_del_sector(sector):
    """Personas alojadas y reservas abiertas en las plazas del sector, por separado (dos consultas)."""

    return CompromisosDelSector(
        alojadas=Estadia.objects.activas().filter(plaza__sector=sector).count(),
        reservas=ReservaPlaza.objects.abiertas().filter(plaza__sector=sector).count(),
    )


def codigos_del_sector(sector):
    """Los códigos de TODAS las plazas del sector, también las fuera de servicio y las dadas de baja."""

    return set(Plaza.todas.filter(sector=sector).values_list("codigo", flat=True))


def sectores_por_edificio(dispositivo):
    """Los sectores ACTIVOS del dispositivo con su cantidad de plazas, agrupados por edificio (una consulta).

    Devuelve ``(por_edificio, sin_edificio)``: un dict ``edificio_id -> [fila]`` y la lista de los
    que todavía no tienen edificio (los anteriores al campo en un dispositivo con 2+ edificios,
    hasta que un administrador los asigne). Cada fila: ``pk``, ``nombre``, ``tipo``, ``plazas``.
    """

    sectores = (
        Sector.objects.filter(dispositivo=dispositivo, activo=True)
        .annotate(cantidad_plazas=Count("plazas", filter=Q(plazas__activa=True)))
        .order_by("nombre", "pk")
        .values("pk", "nombre", "tipo", "edificio_id", "cantidad_plazas")
    )
    por_edificio = {}
    sin_edificio = []
    for fila in sectores:
        item = {
            "pk": fila["pk"],
            "nombre": fila["nombre"],
            "tipo": Sector.Tipo(fila["tipo"]).label if fila["tipo"] in Sector.Tipo.values else fila["tipo"],
            "plazas": fila["cantidad_plazas"],
        }
        if fila["edificio_id"] is None:
            sin_edificio.append(item)
        else:
            por_edificio.setdefault(fila["edificio_id"], []).append(item)
    return por_edificio, sin_edificio


#: Cómo se nombra el edificio de un sector que no tiene (o que ya no está vinculado al dispositivo).
SIN_EDIFICIO = "Sin edificio"


def nombre_de_edificio(sector):
    """El rótulo del edificio de un sector **activo** (lado Python de «Sin edificio»).

    Los sectores inactivos lo resuelven en SQL, en `sectores_inactivos` (que además mira el vínculo
    del edificio con el dispositivo). El criterio de los dos lados no es el mismo a propósito.
    """

    return sector.edificio.nombre if sector.edificio else SIN_EDIFICIO


def sectores_inactivos(dispositivo, *, q_alcance=None):
    """Los sectores dados de baja del dispositivo, con su cantidad de plazas, por nombre.

    Cada uno trae su edificio (`select_related`) y `edificio_vinculado`: un edificio que el
    dispositivo ya no tiene vinculado cuenta como «sin edificio», igual que en la reactivación.
    `edificio_nombre` ya trae el rótulo que se dibuja (`SIN_EDIFICIO` incluido): el template no decide.
    """

    vinculado = Edificio.dispositivos.through.objects.filter(
        edificio_id=OuterRef("edificio_id"), dispositivo_id=dispositivo.pk
    )
    return (
        Sector.objects.filter(dispositivo=dispositivo, activo=False)
        .filter(q_alcance if q_alcance is not None else Q())
        .select_related("edificio")
        .annotate(cantidad_plazas=Count("plazas", filter=Q(plazas__activa=True)), edificio_vinculado=Exists(vinculado))
        .annotate(
            edificio_nombre=Case(
                When(edificio_vinculado=True, edificio__isnull=False, then=F("edificio__nombre")),
                default=Value(SIN_EDIFICIO),
            )
        )
        .order_by("nombre")
    )


#: Cuántas bajas de un sector se ven de entrada; el resto va plegado en el mismo grupo («Ver las N restantes»).
TOPE_BAJAS_POR_GRUPO = 20


class GrupoDeBajas(NamedTuple):
    """Las plazas dadas de baja de un sector: las primeras `TOPE_BAJAS_POR_GRUPO` y las que quedan plegadas."""

    sector: Sector
    cantidad: int
    visibles: list
    restantes: list
    abierto: bool


class PlazasDadasDeBaja(NamedTuple):
    """Lo que dibuja la sección «Plazas dadas de baja»: ya agrupado, contado y con el filtro validado.

    `opciones` son todos los sectores que tienen bajas (`[(pk, nombre)]`), también con el filtro puesto: es lo que
    ofrece el select. `filtro` es el sector elegido, o ``None`` si no se pidió o no vale.
    """

    total: int
    cantidad_sectores: int
    opciones: list
    filtro: int | None
    grupos: list


def plazas_dadas_de_baja(dispositivo, *, q_alcance=None, sector_id=None, abierto_id=None, tope=TOPE_BAJAS_POR_GRUPO):
    """Las plazas dadas de baja de los sectores activos del dispositivo, agrupadas por sector (una consulta).

    Las de un sector inactivo no se listan: vuelven con su sector, y reactivar una sola no tendría
    dónde dibujarse. Una consulta fija: el agrupado, la cuenta y el recorte de cada grupo se hacen en Python sobre
    ese resultado, así que no crece con los sectores ni con las plazas.

    ``sector_id`` es el filtro pedido: solo vale si ese sector tiene bajas (uno ajeno, inexistente o sin bajas se
    ignora y quedan todos) y deja solo su grupo, abierto. ``abierto_id`` abre el grupo de ese sector sin filtrar
    (la vuelta de «Reactivar»). Por grupo se ven ``tope`` plazas y el resto va en `restantes`.
    """

    filas = (
        Plaza.todas.filter(sector__dispositivo=dispositivo, sector__activo=True, activa=False)
        .filter(q_alcance if q_alcance is not None else Q())
        .select_related("sector")
        .order_by("sector__nombre", "sector_id", "codigo")
    )
    por_sector = {}
    for plaza in filas:
        por_sector.setdefault(plaza.sector_id, []).append(plaza)
    opciones = [(pk, plazas[0].sector.nombre) for pk, plazas in por_sector.items()]
    filtro = sector_id if sector_id in por_sector else None
    grupos = []
    for pk, plazas in por_sector.items():
        if filtro is not None and pk != filtro:
            continue
        # El orden natural dentro del grupo («99» antes que «100»), como el mapa.
        plazas = sorted(plazas, key=lambda plaza: clave_natural(plaza.codigo))
        grupos.append(
            GrupoDeBajas(
                sector=plazas[0].sector,
                cantidad=len(plazas),
                visibles=plazas[:tope],
                restantes=plazas[tope:],
                abierto=filtro is not None or pk == abierto_id,
            )
        )
    return PlazasDadasDeBaja(
        total=sum(len(plazas) for plazas in por_sector.values()),
        cantidad_sectores=len(por_sector),
        opciones=opciones,
        filtro=filtro,
        grupos=grupos,
    )
