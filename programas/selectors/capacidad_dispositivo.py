"""Lecturas de configuración de la capacidad instalada y del predio compartido."""

from django.db.models import Case, Count, Exists, F, OuterRef, Q, Value, When

from programas.models import Dispositivo, Edificio, Estadia, Plaza, ReservaPlaza, Sector
from programas.services.dispositivos import dispositivos_visibles
from programas.services.inspecciones import edificios_en_alcance


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
    return (
        edificios_en_alcance(usuario, "dispositivo.editar").exclude(dispositivos=dispositivo).order_by("nombre", "pk")
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


def codigos_del_sector(sector):
    """Los códigos de TODAS las plazas del sector, también las fuera de servicio."""

    return set(Plaza.objects.filter(sector=sector).values_list("codigo", flat=True))


def sectores_por_edificio(dispositivo):
    """Los sectores ACTIVOS del dispositivo con su cantidad de plazas, agrupados por edificio (una consulta).

    Devuelve ``(por_edificio, sin_edificio)``: un dict ``edificio_id -> [fila]`` y la lista de los
    que todavía no tienen edificio (los anteriores al campo en un dispositivo con 2+ edificios,
    hasta que un administrador los asigne). Cada fila: ``pk``, ``nombre``, ``tipo``, ``plazas``.
    """

    sectores = (
        Sector.objects.filter(dispositivo=dispositivo, activo=True)
        .annotate(cantidad_plazas=Count("plazas"))
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


def sectores_inactivos(dispositivo):
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
        .select_related("edificio")
        .annotate(cantidad_plazas=Count("plazas"), edificio_vinculado=Exists(vinculado))
        .annotate(
            edificio_nombre=Case(
                When(edificio_vinculado=True, edificio__isnull=False, then=F("edificio__nombre")),
                default=Value(SIN_EDIFICIO),
            )
        )
        .order_by("nombre")
    )
