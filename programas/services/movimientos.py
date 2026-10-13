"""Movimientos de la estadía: cómo se registran y cómo se leen (MVP v2, etapa 3 · #694).

Este módulo **no decide nada**: no mira permisos, no bloquea filas y no valida plazas.
Esas reglas viven en `programas.services.estadias`, que es el único que escribe —en la
misma transacción que el cambio— a través de :func:`registrar_movimiento`. Lo que hay
acá es la forma única de un movimiento y las lecturas que salen de ellos.

La permanencia
--------------

Se **calcula**, no se carga: `Estadia.permanencia()` la deriva del ingreso y del egreso
(o de ahora), y los movimientos de ingreso y de egreso llevan esas mismas dos fechas
como `momento`. :func:`tramos_por_plaza` reparte esa misma permanencia entre las plazas
por las que pasó la persona, leyendo solo los movimientos: la suma de los tramos es la
permanencia, y si no lo fuera, la línea de tiempo y la ficha se estarían contradiciendo.

Todo en Python y sin ningún `Trunc*`: la base de ECOM no tiene tablas de zona horaria.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db.models import Q
from django.utils import timezone

from programas.models import Estadia, MovimientoEstadia


def _pk(objeto):
    """Acepta la instancia o su id: el egreso tiene a mano el id y no la plaza."""

    return getattr(objeto, "pk", objeto)


def registrar_movimiento(
    *,
    estadia,
    tipo,
    momento,
    responsable,
    motivo="",
    plaza_origen=None,
    plaza_destino=None,
    estado_anterior="",
    estado_nuevo="",
):
    """Agrega un movimiento a la estadía. Lo llaman solo los servicios de `estadias`.

    El dispositivo se copia de la estadía: es el mismo siempre, y viaja en el movimiento
    para que el censo por turno lo filtre sin pasar por ella.
    """

    movimiento = MovimientoEstadia(
        estadia=estadia,
        dispositivo_id=estadia.dispositivo_id,
        tipo=tipo,
        momento=momento,
        responsable=responsable,
        motivo=(motivo or "").strip(),
        plaza_origen_id=_pk(plaza_origen),
        plaza_destino_id=_pk(plaza_destino),
        estado_anterior=estado_anterior,
        estado_nuevo=estado_nuevo,
    )
    movimiento.save()
    return movimiento


def ultimo_momento(estadia):
    """Desde cuándo se puede registrar el próximo movimiento de la estadía.

    Es el del último movimiento, o el ingreso si la estadía no tiene ninguno (una
    cargada por fuera de los servicios). Un movimiento anterior a este reescribiría la
    historia: un cambio de plaza fechado antes del anterior dejaría a la persona saliendo
    de una plaza en la que todavía no estaba.
    """

    ultimo = (
        MovimientoEstadia.objects.filter(estadia_id=estadia.pk)
        .order_by("-momento", "-id")
        .values_list("momento", flat=True)
        .first()
    )
    if ultimo is None or ultimo < estadia.fecha_ingreso:
        return estadia.fecha_ingreso
    return ultimo


def plaza_ocupada_despues_de(plaza, momento):
    """Si alguien estuvo en la plaza en algún instante desde ``momento`` hasta hoy, según los movimientos.

    Es la pregunta de una carga **retroactiva** (revisión de #826, MINOR 3): que la plaza
    esté libre ahora no dice que lo estuvo desde ``momento``. Alguien la ocupó en ese
    lapso si **entró** a ella en ``momento`` o después, o si **salió** de ella después de
    ``momento`` —entrara cuando entrara—. Quien salió justo en ``momento`` ya no estaba:
    la ventana de su tramo es ``[desde, hasta)``. Quien sigue adentro lo dice la estadía
    activa, que el ingreso y el cambio ya controlan aparte.
    """

    return (
        MovimientoEstadia.objects.filter(
            Q(plaza_destino_id=_pk(plaza), momento__gte=momento) | Q(plaza_origen_id=_pk(plaza), momento__gt=momento)
        )
        .order_by()
        .exists()
    )


def linea_de_tiempo(estadia):
    """Los movimientos de la estadía en el orden en que pasaron, con lo que P7 dibuja."""

    return (
        MovimientoEstadia.objects.filter(estadia_id=estadia.pk)
        .select_related("responsable", "plaza_origen", "plaza_destino")
        .linea_de_tiempo()
    )


@dataclass(frozen=True)
class Tramo:
    """Un período de la estadía en una misma plaza. `plaza` es `None` si no tenía asignada."""

    plaza_id: int | None
    desde: datetime
    hasta: datetime

    @property
    def duracion(self) -> timedelta:
        return self.hasta - self.desde


def tramos_por_plaza(estadia, movimientos=None, momento=None):
    """La permanencia repartida entre las plazas por las que pasó la persona.

    Se arma **solo** con los movimientos (o con los que se pasen, ya leídos): el ingreso
    abre el primer tramo, cada cambio de sector o de plaza cierra uno y abre otro, y el
    egreso cierra el último. Una estadía abierta tiene su último tramo hasta `momento`
    (por omisión, ahora). La suma de las duraciones es `estadia.permanencia(momento)`.

    Una estadía sin movimiento de ingreso —cargada por fuera de los servicios y sin
    reconstruir— devuelve una lista vacía: no se inventa una historia que no se registró.
    """

    if movimientos is None:
        movimientos = MovimientoEstadia.objects.filter(estadia_id=estadia.pk).linea_de_tiempo()
    corte = momento or timezone.now()

    tramos = []
    abierto = None  # (plaza_id, desde)
    for movimiento in movimientos:
        if movimiento.tipo == MovimientoEstadia.Tipo.INGRESO:
            abierto = (movimiento.plaza_destino_id, movimiento.momento)
        elif movimiento.tipo in MovimientoEstadia.TIPOS_DE_CAMBIO_DE_PLAZA and abierto is not None:
            tramos.append(Tramo(plaza_id=abierto[0], desde=abierto[1], hasta=movimiento.momento))
            abierto = (movimiento.plaza_destino_id, movimiento.momento)
        elif movimiento.tipo == MovimientoEstadia.Tipo.EGRESO and abierto is not None:
            tramos.append(Tramo(plaza_id=abierto[0], desde=abierto[1], hasta=movimiento.momento))
            abierto = None
    if abierto is not None:
        hasta = estadia.fecha_egreso if estadia.estado == Estadia.Estado.EGRESADA else corte
        tramos.append(Tramo(plaza_id=abierto[0], desde=abierto[1], hasta=hasta))
    return tramos
