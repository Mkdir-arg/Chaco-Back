"""Lecturas de configuración de la capacidad instalada y del predio compartido."""

from programas.models import Edificio, Estadia, Plaza, ReservaPlaza
from programas.services.inspecciones import edificios_en_alcance


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
