"""Datasets de solo lectura para los reportes exportables de Programas."""

from dataclasses import dataclass
from datetime import date

from django.db.models import Count, Prefetch, Q

from programas.models import Admision, Cama, EntregaMercaderia


@dataclass(frozen=True)
class Reporte:
    encabezados: tuple[str, ...]
    filas: tuple[tuple, ...]


def filtrar_dispositivos(dispositivos, *, tipo=None, estado=None, localidad=None):
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


def ocupacion_dispositivos(dispositivos):
    dispositivos = (
        dispositivos.select_related("tipo")
        .annotate(
            camas_totales_reporte=Count("camas", distinct=True),
            camas_fuera_servicio_reporte=Count(
                "camas",
                filter=Q(camas__estado=Cama.Estado.FUERA_SERVICIO),
                distinct=True,
            ),
            camas_ocupadas_reporte=Count(
                "admisiones__cama",
                filter=Q(admisiones__estado=Admision.Estado.ALOJADO, admisiones__cama__isnull=False),
                distinct=True,
            ),
        )
        .order_by("nombre", "codigo")
    )
    filas = []
    for dispositivo in dispositivos:
        operativas = max(dispositivo.camas_totales_reporte - dispositivo.camas_fuera_servicio_reporte, 0)
        libres = max(operativas - dispositivo.camas_ocupadas_reporte, 0)
        porcentaje = round((dispositivo.camas_ocupadas_reporte * 100) / operativas) if operativas else 0
        filas.append(
            (
                dispositivo.codigo,
                dispositivo.nombre,
                dispositivo.tipo.nombre,
                dispositivo.camas_totales_reporte,
                dispositivo.camas_ocupadas_reporte,
                libres,
                porcentaje,
            )
        )
    return Reporte(
        encabezados=("Código", "Dispositivo", "Tipo", "Camas totales", "Ocupadas", "Libres", "Ocupación (%)"),
        filas=tuple(filas),
    )


def movimientos_dispositivos(dispositivos, *, desde: date | None = None, hasta: date | None = None):
    admisiones = Admision.objects.filter(dispositivo__in=dispositivos).select_related(
        "ciudadano", "dispositivo", "dispositivo__tipo"
    )
    if desde:
        admisiones = admisiones.filter(Q(fecha_ingreso__date__gte=desde) | Q(fecha_egreso__date__gte=desde))
    if hasta:
        admisiones = admisiones.filter(Q(fecha_ingreso__date__lte=hasta) | Q(fecha_egreso__date__lte=hasta))

    movimientos = []
    for admision in admisiones:
        if (desde is None or admision.fecha_ingreso.date() >= desde) and (
            hasta is None or admision.fecha_ingreso.date() <= hasta
        ):
            movimientos.append(
                (
                    admision.fecha_ingreso,
                    "Ingreso",
                    admision.fecha_ingreso.strftime("%d/%m/%Y"),
                    admision.dispositivo.codigo,
                    admision.dispositivo.nombre,
                    admision.dispositivo.tipo.nombre,
                    admision.ciudadano.nombre_completo,
                    admision.get_estado_display(),
                )
            )
        if (
            admision.fecha_egreso
            and (desde is None or admision.fecha_egreso.date() >= desde)
            and (hasta is None or admision.fecha_egreso.date() <= hasta)
        ):
            movimientos.append(
                (
                    admision.fecha_egreso,
                    "Egreso",
                    admision.fecha_egreso.strftime("%d/%m/%Y"),
                    admision.dispositivo.codigo,
                    admision.dispositivo.nombre,
                    admision.dispositivo.tipo.nombre,
                    admision.ciudadano.nombre_completo,
                    admision.get_estado_display(),
                )
            )
    filas = tuple(fila[1:] for fila in sorted(movimientos, key=lambda fila: (fila[0], fila[1], fila[3])))
    return Reporte(
        encabezados=("Movimiento", "Fecha", "Código", "Dispositivo", "Tipo", "Ciudadano", "Estado de la estadía"),
        filas=filas,
    )


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
