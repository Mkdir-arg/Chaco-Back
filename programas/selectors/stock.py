"""Lectura del stock de insumos (anÃ¡lisis 010, PR 2a). Sin reglas de negocio ni permisos: quiÃ©n puede ver quÃ© lo
decide quien llama (``services.stock.puede_ver_stock``). Cada funciÃ³n es una consulta, o dos como mucho."""

from django.db.models import Count, Exists, F, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce

from core.utils_fechas import rango_dia_local
from programas.models import MovimientoStock, SaldoStock


def saldos_de(dispositivo, edificio):
    """Las filas de saldo de (instituciÃ³n, edificio) con su insumo, por nombre.

    Un insumo desactivado con saldo 0 no se muestra (RN-010-17); uno activo con saldo 0 sÃ­, porque se puede cargar.
    """

    return (
        SaldoStock.objects.filter(dispositivo=dispositivo, edificio=edificio)
        .exclude(item__activo=False, cantidad=0)
        .select_related("item")
        .order_by("item__nombre", "item_id")
    )


#: Filtros que entiende :func:`movimientos_de`.
FILTROS_DE_MOVIMIENTOS = ("item", "tipo", "desde", "hasta")


def movimientos_de(dispositivo, edificio, filtros=None):
    """Los movimientos de (instituciÃ³n, edificio), del mÃ¡s nuevo al mÃ¡s viejo.

    ``filtros`` (todos opcionales): ``item`` (id), ``tipo`` (un ``MovimientoStock.Tipo``), ``desde`` y ``hasta``
    (``date`` locales, inclusivos). No trae a la persona: el nombre de quien recibiÃ³ una entrega es un dato personal
    que decide la pantalla segÃºn ``ciudadano.ver`` (PR 6b).
    """

    filtros = filtros or {}
    consulta = MovimientoStock.objects.filter(dispositivo=dispositivo, edificio=edificio)
    if filtros.get("item"):
        consulta = consulta.filter(item_id=filtros["item"])
    if filtros.get("tipo"):
        consulta = consulta.filter(tipo=filtros["tipo"])
    if filtros.get("desde"):
        consulta = consulta.filter(creado_en__gte=rango_dia_local(filtros["desde"])[0])
    if filtros.get("hasta"):
        consulta = consulta.filter(creado_en__lt=rango_dia_local(filtros["hasta"])[1])
    return consulta.select_related("item", "operacion", "operacion__usuario").order_by("-creado_en", "-id")


def resumen_por_edificio(dispositivo, edificio_ids):
    """Para la tarjeta del edificio, en **una** consulta agrupada: ``{edificio_id: {"insumos": n, "unidades": total}}``.

    Cuenta los insumos con saldo mayor que 0. Un edificio sin saldo no aparece en el resultado.
    """

    filas = (
        SaldoStock.objects.filter(dispositivo=dispositivo, edificio_id__in=list(edificio_ids), cantidad__gt=0)
        .values("edificio_id")
        .annotate(insumos=Count("item_id"), unidades=Sum("cantidad"))
    )
    return {fila["edificio_id"]: {"insumos": fila["insumos"], "unidades": fila["unidades"]} for fila in filas}


def stock_por_dispositivo_e_item(dispositivo_ids):
    """Î£ de los saldos de **todos** los edificios de cada instituciÃ³n, en una consulta (E8, RN-010-20).

    ``{dispositivo_id: {item_id: cantidad}}``, solo con cantidades mayores que 0.
    """

    resultado = {}
    filas = (
        SaldoStock.objects.filter(dispositivo_id__in=list(dispositivo_ids), cantidad__gt=0)
        .values("dispositivo_id", "item_id")
        .annotate(total=Sum("cantidad"))
    )
    for fila in filas:
        resultado.setdefault(fila["dispositivo_id"], {})[fila["item_id"]] = fila["total"]
    return resultado


def diferencias_de_saldo():
    """Las claves donde se rompe el invariante ``saldo == Î£ movimientos == saldo_posterior del Ãºltimo`` (Â§6.5).

    Devuelve ``[{"dispositivo_id", "edificio_id", "item_id", "saldo", "suma", "ultimo"}]``; vacÃ­o si todo cierra. Una
    consulta agrupada con subconsultas correlacionadas, mÃ¡s una por si hubiera movimientos de una clave sin fila de
    saldo (que los servicios no producen: crean el saldo antes de moverlo).
    """

    del_par = {
        "dispositivo_id": OuterRef("dispositivo_id"),
        "edificio_id": OuterRef("edificio_id"),
        "item_id": OuterRef("item_id"),
    }
    suma = (
        MovimientoStock.objects.filter(**del_par)
        .order_by()
        .values("dispositivo_id", "edificio_id", "item_id")
        .annotate(total=Sum("cantidad"))
        .values("total")
    )
    ultimo = MovimientoStock.objects.filter(**del_par).order_by("-id").values("saldo_posterior")[:1]
    filas = (
        SaldoStock.objects.annotate(suma=Coalesce(Subquery(suma), 0), ultimo=Coalesce(Subquery(ultimo), 0))
        .filter(~Q(cantidad=F("suma")) | ~Q(cantidad=F("ultimo")))
        .order_by("dispositivo_id", "edificio_id", "item_id")
        .values("dispositivo_id", "edificio_id", "item_id", "cantidad", "suma", "ultimo")
    )
    diferencias = [
        {
            "dispositivo_id": fila["dispositivo_id"],
            "edificio_id": fila["edificio_id"],
            "item_id": fila["item_id"],
            "saldo": fila["cantidad"],
            "suma": fila["suma"],
            "ultimo": fila["ultimo"],
        }
        for fila in filas
    ]
    huerfanos = (
        MovimientoStock.objects.filter(~Exists(SaldoStock.objects.filter(**del_par)))
        .order_by()
        .values("dispositivo_id", "edificio_id", "item_id")
        .annotate(total=Sum("cantidad"))
    )
    for fila in huerfanos:
        diferencias.append(
            {
                "dispositivo_id": fila["dispositivo_id"],
                "edificio_id": fila["edificio_id"],
                "item_id": fila["item_id"],
                "saldo": None,
                "suma": fila["total"],
                "ultimo": None,
            }
        )
    return diferencias
