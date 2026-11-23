"""Lo que se **lee** del catálogo de insumos de Emergencia (Cambio 578). Nada de acá escribe.

Presupuesto de consultas (lo fija ``programas.tests.test_emergencia_insumos``):

=============================  ==========================================================
``conteos_de_insumos``         1: un ``COUNT`` con filtro por estado sobre ``TipoKit``.
``insumos_del_catalogo``       1 por página: los insumos con su ``COUNT`` de entregas en el
                               mismo ``SELECT`` (sin una consulta por fila).
=============================  ==========================================================

«Usado en N entregas» cuenta líneas de entrega del insumo; hay una sola por entrega y por insumo
(``linea_entrega_item_unico_por_entrega``), así que líneas y entregas son lo mismo.
"""

from django.db.models import Count, Q

from programas.models import TipoKit

ESTADO_ACTIVOS = "activos"
ESTADO_INACTIVOS = "inactivos"
ESTADO_TODOS = "todos"

#: Los chips de la lista, en el orden en que se dibujan: clave y rótulo.
ESTADOS = (
    (ESTADO_ACTIVOS, "Activos"),
    (ESTADO_INACTIVOS, "Inactivos"),
    (ESTADO_TODOS, "Todos"),
)

_POR = {
    TipoKit.PorRegla.PERSONA: "persona",
    TipoKit.PorRegla.FAMILIA: "familia",
    TipoKit.PorRegla.LACTANTE: "lactante",
}

TEXTO_SIN_ESTIMAR = "Sin estimar · no se calcula en Situación"


def estado_valido(valor):
    """La clave del chip, o ``activos`` si el parámetro vino vacío o armado a mano."""
    return valor if valor in dict(ESTADOS) else ESTADO_ACTIVOS


def conteos_de_insumos():
    """``{clave de chip: cuántos}``. **Una consulta.**"""
    cuentas = TipoKit.objects.aggregate(
        activos=Count("pk", filter=Q(activo=True)),
        inactivos=Count("pk", filter=Q(activo=False)),
        todos=Count("pk"),
    )
    return {
        ESTADO_ACTIVOS: cuentas["activos"],
        ESTADO_INACTIVOS: cuentas["inactivos"],
        ESTADO_TODOS: cuentas["todos"],
    }


def insumos_del_catalogo(estado):
    """Los insumos del chip elegido, en el orden en que se ofrecen al armar una entrega.

    Cada uno trae ``entregas``: en cuántas entregas salió.
    """
    insumos = TipoKit.objects.annotate(entregas=Count("lineas_de_entrega")).order_by("orden", "nombre")
    if estado == ESTADO_ACTIVOS:
        return insumos.filter(activo=True)
    if estado == ESTADO_INACTIVOS:
        return insumos.filter(activo=False)
    return insumos


def _cantidad(valor):
    """«0,5», «1», «2,25»: sin ceros de más y con coma."""
    texto = format(valor.normalize(), "f") if hasattr(valor, "normalize") else str(valor)
    return texto.replace(".", ",")


def texto_de_consumo(tipo):
    """Cuánto se estima que hace falta, dicho para la mesa: «1 por familia cada 7 días»."""
    if tipo.regla_modo == TipoKit.ModoRegla.SIN_REGLA or tipo.regla_cantidad is None:
        return TEXTO_SIN_ESTIMAR
    por = _POR.get(tipo.regla_por, tipo.regla_por.lower())
    base = f"{_cantidad(tipo.regla_cantidad)} por {por}"
    if tipo.regla_modo == TipoKit.ModoRegla.DOTACION:
        return f"{base}, una sola vez"
    if tipo.regla_cada_dias == 1:
        return f"{base} por día"
    return f"{base} cada {tipo.regla_cada_dias} días"
