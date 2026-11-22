"""Lo que una institución o un sector tiene con gente adentro o por llegar (Cambio 536).

Lee y cuenta, no decide: quien decide qué se rechaza es `services/dispositivos.py` (cerrar e
inactivar) y `services/plazas.py` (mover un sector de edificio). Cada función hace un número
fijo de consultas, sin importar cuántas plazas haya.

«Reservas» son las `ReservaPlaza` **abiertas** —vencidas o no, mientras nadie las libere—:
una reserva vencida sin liberar sigue colgada de la plaza, y por eso cuenta.
"""

from typing import NamedTuple

from django.db.models import Count, Q

from programas.models import Derivacion, Estadia, ReservaPlaza


class CompromisosDeLaInstitucion(NamedTuple):
    alojadas: int
    reservas_comunes: int
    reservas_de_derivacion: int
    derivaciones: int

    @property
    def reservas(self):
        return self.reservas_comunes + self.reservas_de_derivacion


class CompromisosDelSector(NamedTuple):
    alojadas: int
    reservas: int


def compromisos_de_la_institucion(dispositivo):
    """Estadías abiertas, reservas abiertas (comunes y de derivación) y derivaciones de Emergencia vigentes.

    Tres consultas. Las derivaciones vigentes son las pendientes y las aceptadas: una aceptada
    es la que está esperando a la familia o la que tiene el ingreso a medias.
    """

    alojadas = Estadia.objects.activas().filter(dispositivo=dispositivo).count()
    reservas = (
        ReservaPlaza.objects.abiertas()
        .filter(plaza__sector__dispositivo=dispositivo)
        .aggregate(
            comunes=Count("pk", filter=Q(derivacion__isnull=True)),
            de_derivacion=Count("pk", filter=Q(derivacion__isnull=False)),
        )
    )
    derivaciones = Derivacion.objects.filter(dispositivo=dispositivo, estado__in=Derivacion.ESTADOS_VIGENTES).count()
    return CompromisosDeLaInstitucion(
        alojadas=alojadas,
        reservas_comunes=reservas["comunes"],
        reservas_de_derivacion=reservas["de_derivacion"],
        derivaciones=derivaciones,
    )


def reservas_comunes_abiertas(dispositivo):
    """Las reservas y préstamos comunes sin liberar de la institución, con su plaza (una consulta)."""

    return list(
        ReservaPlaza.objects.abiertas()
        .filter(plaza__sector__dispositivo=dispositivo, derivacion__isnull=True)
        .select_related("plaza__sector")
        .order_by("plaza_id", "pk")
    )


def compromisos_del_sector(sector):
    """Personas alojadas y reservas abiertas en las plazas del sector (dos consultas)."""

    return CompromisosDelSector(
        alojadas=Estadia.objects.activas().filter(plaza__sector=sector).count(),
        reservas=ReservaPlaza.objects.abiertas().filter(plaza__sector=sector).count(),
    )
