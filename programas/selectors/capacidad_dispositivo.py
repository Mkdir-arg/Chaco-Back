"""Lecturas de configuración de la capacidad instalada y del predio compartido."""

from programas.models import Dispositivo, Edificio, Estadia, Plaza, ReservaPlaza
from programas.services.dispositivos import dispositivos_visibles
from programas.services.inspecciones import edificios_en_alcance


def instituciones_del_predio(usuario, edificios_ids):
    """Identidad de instituciones visibles; no revela siquiera nombres fuera del alcance.

    Sector no tiene vínculo con Edificio: no se atribuyen sectores a un inmueble.
    Una consulta para todos los edificios, con el tipo en el mismo JOIN.
    """

    if usuario is None:
        return {}
    filas = (
        Edificio.dispositivos.through.objects.filter(
            edificio_id__in=edificios_ids,
            dispositivo_id__in=dispositivos_visibles(usuario).values("pk"),
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
                "get_estado_display": dict(Dispositivo.Estado.choices)[fila["dispositivo__estado"]],
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


def codigos_del_dispositivo(dispositivo):
    return set(Plaza.objects.filter(sector__dispositivo=dispositivo).values_list("codigo", flat=True))
