"""Datasets de solo lectura para los reportes exportables de Programas."""

from dataclasses import dataclass
from datetime import date

from django.db.models import Prefetch, Q
from django.utils.dateparse import parse_date

from programas.models import EntregaMercaderia


@dataclass(frozen=True)
class Reporte:
    encabezados: tuple[str, ...]
    filas: tuple[tuple, ...]


def parsear_periodo(desde_valor, hasta_valor):
    desde = _fecha(desde_valor, "desde")
    hasta = _fecha(hasta_valor, "hasta")
    if desde and hasta and desde > hasta:
        raise ValueError("La fecha desde no puede ser posterior a la fecha hasta.")
    return desde, hasta


def _fecha(valor, nombre):
    if not valor:
        return None
    fecha = parse_date(valor)
    if fecha is None:
        raise ValueError(f"La fecha {nombre} no es válida.")
    return fecha


def filtrar_dispositivos(dispositivos, *, tipo=None, estado=None, localidad=None):
    """Filtros del padrón institucional.

    El filtro por **período** —dispositivos con un ingreso o un egreso dentro del
    rango— se fue con `Admision`. Vuelve en el MVP v2 contra `Estadia`, y con él
    los reportes de ocupación y movimientos.
    """
    if tipo:
        dispositivos = dispositivos.filter(tipo_id=tipo)
    if estado:
        dispositivos = dispositivos.filter(estado=estado)
    if localidad:
        dispositivos = dispositivos.filter(localidad__icontains=localidad)
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


def filtrar_merenderos(merenderos, *, estado=None, termino=None, desde=None, hasta=None):
    if estado:
        merenderos = merenderos.filter(estado=estado)
    if termino:
        merenderos = merenderos.filter(nombre__icontains=termino)
    if desde or hasta:
        entregas = Q(entregas_mercaderia__anulada=False)
        if desde:
            entregas &= Q(entregas_mercaderia__fecha__gte=desde)
        if hasta:
            entregas &= Q(entregas_mercaderia__fecha__lte=hasta)
        merenderos = merenderos.filter(entregas).distinct()
    return merenderos


def padron_merenderos_con_entregas(merenderos, *, desde: date | None = None, hasta: date | None = None):
    entregas = EntregaMercaderia.objects.filter(anulada=False).order_by("fecha", "pk")
    if desde:
        entregas = entregas.filter(fecha__gte=desde)
    if hasta:
        entregas = entregas.filter(fecha__lte=hasta)
    merenderos = merenderos.prefetch_related(
        Prefetch("entregas_mercaderia", queryset=entregas, to_attr="entregas_reporte")
    ).order_by("nombre", "codigo")
    filas = []
    for merendero in merenderos:
        base = (
            merendero.codigo,
            merendero.nombre,
            merendero.barrio,
            merendero.domicilio,
            merendero.responsable_nombre,
            merendero.get_estado_display(),
        )
        if merendero.entregas_reporte:
            filas.extend(
                base + (entrega.fecha.strftime("%d/%m/%Y"), entrega.cantidad_kits, entrega.servicio)
                for entrega in merendero.entregas_reporte
            )
        else:
            filas.append(base + ("", "", ""))
    return Reporte(
        encabezados=(
            "Código",
            "Merendero",
            "Barrio",
            "Domicilio",
            "Responsable",
            "Estado",
            "Fecha de entrega",
            "Kits entregados",
            "Servicio",
        ),
        filas=tuple(filas),
    )
