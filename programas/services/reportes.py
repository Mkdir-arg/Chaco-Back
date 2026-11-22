"""Datasets de solo lectura para los reportes exportables de Programas."""

from collections.abc import Iterable
from dataclasses import dataclass

from django.db.models import Q


@dataclass(frozen=True)
class Reporte:
    encabezados: tuple[str, ...]
    filas: tuple[tuple, ...]


@dataclass(frozen=True)
class ReportePerezoso:
    """Mismo contrato que :class:`Reporte` —``encabezados`` y ``filas``— pero las filas
    llegan en un iterador que se arma **por lotes** mientras se escribe el archivo, y que
    se consume **una sola vez** (PERF-03 punto 3).

    Quien lo escribe no nota la diferencia: ``respuesta_libro`` y el CSV por streaming
    recorren ``filas`` igual. Lo que cambia es que ni el servicio ni la respuesta tienen
    las 40.000 filas en memoria a la vez, y que el archivo empieza a salir sin esperar a
    la última.
    """

    encabezados: tuple[str, ...]
    filas: Iterable[tuple]

    def materializado(self) -> Reporte:
        """El :class:`Reporte` de siempre, con todas las filas en memoria."""
        return Reporte(self.encabezados, tuple(self.filas))


def filtrar_dispositivos(dispositivos, *, tipo=None, estado=None, localidad=None, q=None, localidades_ofrecidas=()):
    """Filtros del padrón institucional.

    **Localidad.** Si el valor es una de las que el select ofrece (`localidades_ofrecidas`, las de
    `dispositivos.localidades_visibles`), filtra exacto (sin distinguir mayúsculas): «Corzuela» no trae
    «Corzuela Norte». Si es otra cosa —un enlace viejo con texto libre— sigue como siempre, con
    `icontains`. La regla es esta y la usan el listado y la exportación.

    El filtro por **período** —dispositivos con un ingreso o un egreso dentro del
    rango— se fue con la estadía de la versión 1. Vuelve en el MVP v2 contra `Estadia`,
    y con él los reportes de ocupación y movimientos.
    """
    if tipo:
        dispositivos = dispositivos.filter(tipo_id=tipo)
    if estado:
        dispositivos = dispositivos.filter(estado=estado)
    if localidad:
        coincidencia = "iexact" if localidad in localidades_ofrecidas else "icontains"
        dispositivos = dispositivos.filter(**{f"localidad__{coincidencia}": localidad})
    if q:
        # Solo lo que la fila del listado muestra: nombre, código y localidad.
        dispositivos = dispositivos.filter(Q(nombre__icontains=q) | Q(codigo__icontains=q) | Q(localidad__icontains=q))
    return dispositivos


def padron_dispositivos(dispositivos):
    dispositivos = dispositivos.select_related("tipo").order_by("nombre", "codigo")
    return Reporte(
        encabezados=("Código", "Nombre", "Tipo", "Localidad", "Estado"),
        filas=tuple(
            (
                dispositivo.codigo,
                dispositivo.nombre,
                dispositivo.tipo.nombre,
                dispositivo.localidad,
                dispositivo.get_estado_display(),
            )
            for dispositivo in dispositivos
        ),
    )
