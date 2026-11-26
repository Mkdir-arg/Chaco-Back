"""Lo que muestra la solapa «Abastecimiento» de E8 (análisis 009, §3.9 y §12): lo armado, escrito.

Nada de acá consulta la base ni decide una regla: los números salen de
``services.abastecimiento_emergencia`` y las alertas AE-8 a AE-10 de
``services.alertas_situacion_emergencia``. Acá se escriben (miles con punto, «≈», la regla de cada
ítem, la cobertura en horas o en fecha) y se decide qué enlace viaja según quién mira:

* **Todo rotulado «estimado»; nunca «stock»** (RNF-009-13): la nota de arriba dice que no es un
  inventario. **Única excepción** (análisis 010, RN-010-20): en las instituciones cuyo tipo lleva stock, la
  columna «Stock registrado» muestra lo que hay en sus edificios, rotulado así y nunca «estimado». Si ninguna fila
  lleva stock, ni la columna ni la palabra aparecen; en las filas sin stock, la celda es «—». El faltante no cambia.
* **«Preparar entrega»** (paso 2 de E4) solo con ``operar`` o ``supervisar`` y el dispositivo
  ``ACTIVO``: sin eso, la URL ni se calcula.
* **Enlaces a «Insumos» y «Plazos de atención»** (la configuración de la mesa) solo con ``supervisar``.
* **Ubicación reservada** (RN-009-13): «Dispositivo de ubicación reservada», sin nombre ni localidad.
"""

from datetime import timedelta

from django.urls import reverse
from django.utils.formats import number_format

from programas.models import Dispositivo, EntregaKit, TipoKit
from programas.services.abastecimiento_emergencia import CUBRE, SIN_CONSUMO, nombre_visible, presentar_salud
from programas.services.alertas_situacion_emergencia import alertas_de_abastecimiento
from programas.services.ocupacion import etiqueta_y_tono
from programas.services.pantalla_situacion_emergencia import DIAS, RED_PROVINCIAL, SIN_DATO, badge, local, numero

TEXTO_SIN_ESTIMAR = "Sin estimar · no se calcula en Situación"
IR_A_PLAZOS = "Ir a Plazos de atención"
IR_A_INSUMOS = "Ir a Insumos"
SIN_STOCK = "—"

#: Los estados vacíos de la solapa (§3.9 y §12), listos para ``components/_estado_vacio.html``. La acción
#: de los que piden ir a Plazos o a Insumos solo viaja con ``supervisar``.
VACIO_SIN_PEDIR = {
    "icono": "fa-boxes-stacked",
    "titulo": "El abastecimiento se calcula cuando lo pedís",
    "texto": "Es una estimación de toda la red provincial; los filtros no la acotan.",
    "accion_texto": "Calcular el abastecimiento",
    "accion_icono": "fa-calculator",
}
VACIO_SIN_INICIO = {
    "icono": "fa-calendar-xmark",
    "titulo": "Para estimar el abastecimiento falta la fecha de inicio del evento",
    "texto": "Todo lo recibido y lo consumido se cuenta desde esa fecha. Se carga en Plazos de atención.",
    "accion_texto": IR_A_PLAZOS,
}
VACIO_SIN_REGLAS = {
    "icono": "fa-sliders",
    "titulo": "Ningún ítem tiene regla de consumo: se configuran en Insumos",
    "texto": "Sin una regla por ítem no se puede estimar qué falta.",
    "accion_texto": IR_A_INSUMOS,
}
VACIO_SIN_ALOJADOS = {
    "icono": "fa-house-chimney-user",
    "titulo": "Todavía no hay personas alojadas por la emergencia",
    "texto": "Cuando un dispositivo confirme a la primera, acá vas a ver qué le falta.",
}

POR = {TipoKit.PorRegla.PERSONA: "persona", TipoKit.PorRegla.FAMILIA: "familia", TipoKit.PorRegla.LACTANTE: "lactante"}

#: La cobertura se dice en horas hasta un día; desde ahí, en fecha y hora redondeadas a la media hora.
HORAS_EN_HORAS = 24


def cantidad_de_la_regla(cantidad):
    """«0,5», «1», «2,25»: sin ceros de más y con coma."""

    return number_format(cantidad.normalize() if hasattr(cantidad, "normalize") else cantidad)


def _regla_dicha(cantidad, por, modo, cada_dias, dotacion):
    base = f"{cantidad_de_la_regla(cantidad)} por {POR.get(por, por.lower())}"
    if modo == TipoKit.ModoRegla.DOTACION:
        return f"{base}{dotacion}"
    if cada_dias == 1:
        return f"{base} por día"
    return f"{base} cada {cada_dias} días"


def texto_de_la_regla(item, dotacion=" · dotación"):
    """«1 por persona · dotación», «0,5 por persona por día», «1 por familia cada 3 días».

    ``dotacion`` es cómo se dice la dotación al final: cada pantalla conserva su forma.
    """

    return _regla_dicha(item.cantidad, item.por, item.modo, item.cada_dias, dotacion)


def texto_de_consumo(tipo):
    """El consumo de un insumo del catálogo, dicho para «Insumos»: «1 por familia, una sola vez»."""

    if tipo.regla_modo == TipoKit.ModoRegla.SIN_REGLA or tipo.regla_cantidad is None:
        return TEXTO_SIN_ESTIMAR
    return _regla_dicha(tipo.regla_cantidad, tipo.regla_por, tipo.regla_modo, tipo.regla_cada_dias, ", una sola vez")


def _media_hora(momento):
    """El momento local redondeado a la media hora más cercana («≈ 10:30»)."""

    momento = local(momento)
    medias = round((momento.minute * 60 + momento.second) / 1800)
    return momento.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=30 * medias)


def texto_de_cobertura(item):
    """Hasta cuándo alcanza lo recibido (y lo en camino) de un ítem en un dispositivo."""

    cobertura = item.cobertura
    if cobertura is None:
        return "dotación"
    if cobertura.estado == SIN_CONSUMO:
        return SIN_DATO
    con_en_camino = " con lo en camino" if item.en_camino else ""
    if cobertura.estado == CUBRE:
        if cobertura.horas < HORAS_EN_HORAS:
            return f"cubre{con_en_camino} ≈ {numero(round(cobertura.horas))} h"
        hasta = _media_hora(cobertura.hasta)
        return f"cubre{con_en_camino} hasta el {DIAS[hasta.weekday()]} {hasta:%d/%m} ≈ {hasta:%H:%M}"
    if item.nunca_recibido:
        return "nunca recibido"
    horas = round(-cobertura.horas)
    return f"sin cubrir desde hace ≈ {numero(horas)} h" if horas else "sin cubrir"


NOTA_STOCK_REGISTRADO = " · el «Stock registrado» es lo cargado en la institución, no una estimación"


def nota(abastecimiento, *, con_stock=False):
    inicio = local(abastecimiento.inicio_evento)
    texto = (
        f"{RED_PROVINCIAL} · próximas 48 h · desde el inicio del evento ({inicio:%d/%m %H:%M}) · "
        "estimado con la regla de consumo de cada ítem; no es un inventario"
    )
    return f"{texto}{NOTA_STOCK_REGISTRADO}" if con_stock else texto


def tarjetas(abastecimiento):
    """La franja chica (B13), para ``_stat_card`` sin variante (la grande es la de arriba de las solapas)."""

    sin, nunca, sin_entrega = (
        abastecimiento.sin_cobertura,
        abastecimiento.nunca_recibieron,
        abastecimiento.sin_entrega_48h,
    )
    return [
        {
            "etiqueta": "Sin cobertura 48 h",
            "valor": numero(sin),
            "nota": f"de {numero(abastecimiento.con_gente)} con gente · estimado",
            "icono": "fa-triangle-exclamation",
            "tono": "danger" if sin else "success",
        },
        {
            "etiqueta": "Nunca recibieron",
            "valor": numero(nunca),
            "nota": "desde el inicio del evento",
            "icono": "fa-box-open",
            "tono": "danger" if nunca else "success",
        },
        {
            "etiqueta": "Sin entrega en 48 h",
            "valor": numero(sin_entrega),
            "nota": "incluye a los que nunca recibieron",
            "icono": "fa-truck",
            "tono": "warning" if sin_entrega else "success",
        },
        {
            "etiqueta": "Personas en dispositivos con faltantes",
            "valor": numero(abastecimiento.personas_con_faltantes),
            "nota": "estimado",
            "icono": "fa-people-group",
            "tono": "warning" if abastecimiento.personas_con_faltantes else "brand",
        },
    ]


def tabla_por_item(abastecimiento):
    """«Qué mandar en las próximas 48 h» (B14): los ítems con regla y, al final, los que no tienen."""

    filas = []
    for fila in abastecimiento.por_item:
        item = fila.item
        if not fila.con_regla:
            filas.append({"item": item.nombre, "unidad": item.unidad, "con_regla": False})
            continue
        filas.append(
            {
                "item": item.nombre,
                "unidad": item.unidad,
                "con_regla": True,
                "regla": texto_de_la_regla(item),
                "necesario": numero(fila.necesario),
                "en_camino": numero(fila.en_camino),
                "preparadas": numero(fila.preparadas),
                "demoradas": numero(fila.demoradas),
                "faltan": numero(fila.faltan),
                "falta": bool(fila.faltan),
            }
        )
    return filas


def _que_necesita(fila):
    partes = []
    for item in fila.items:
        if not item.faltan:
            continue
        partes.append(f"{item.item.nombre}: faltan {numero(item.faltan)} ({texto_de_cobertura(item)})")
    return "; ".join(partes)


def _ultima(fila, ahora):
    if fila.ultima_recepcion is None:
        return "Nunca"
    return f"hace {numero(int((ahora - fila.ultima_recepcion).total_seconds() // 3600))} h"


def _stock_registrado(fila, stock):
    """«Colchones: 3; Agua: 0»: lo que registra la institución de lo que le falta. «—» si su tipo no lleva stock."""

    if not fila.dispositivo.lleva_stock:
        return SIN_STOCK
    saldos = stock.get(fila.dispositivo.id, {})
    return "; ".join(f"{item.item.nombre}: {numero(saldos.get(item.item.id, 0))}" for item in fila.items if item.faltan)


def con_stock_registrado(abastecimiento):
    """Los ids de las instituciones con faltantes cuyo tipo lleva stock: lo único que la vista tiene que leer."""

    return [fila.dispositivo.id for fila in abastecimiento.dispositivos if fila.dispositivo.lleva_stock]


def lista_de_dispositivos(abastecimiento, ahora, *, opera, stock=None):
    """«Dispositivos con faltantes» (B15), en el orden de urgencia. Sin paginar (RN-009-20).

    ``stock`` es ``{dispositivo_id: {item_id: cantidad}}`` de ``stock_por_dispositivo_e_item`` (RN-010-20).
    """

    stock = stock or {}

    filas = []
    for fila in abastecimiento.dispositivos:
        dispositivo = fila.dispositivo
        etiqueta, tono = etiqueta_y_tono(fila.urgencia)
        personas = numero(fila.unidades.personas)
        if fila.ingresaron_hoy:
            personas = f"{personas} (+{numero(fila.ingresaron_hoy)} hoy)"
        estado = ""
        if dispositivo.estado and not dispositivo.activo:
            estado = Dispositivo.Estado(dispositivo.estado).label
        filas.append(
            {
                "nombre": nombre_visible(dispositivo),
                "estado": estado,
                "urgencia": badge(etiqueta, tono),
                "personas": personas,
                "ultima": _ultima(fila, ahora),
                "necesita": _que_necesita(fila),
                "stock": _stock_registrado(fila, stock),
                "url_preparar": (
                    f"{reverse('emergencia:entrega_nueva')}?dispositivo={dispositivo.id}"
                    if opera and dispositivo.activo
                    else ""
                ),
            }
        )
    return filas


def como_se_calcula(abastecimiento):
    """La regla de cada ítem con regla, para el plegable «Cómo se calcula»."""

    return [f"{item.nombre}: {texto_de_la_regla(item)}" for item in abastecimiento.items_con_regla]


def _url_insumos(supervisa):
    return reverse("emergencia:insumos") if supervisa else ""


def _url_plazos(supervisa):
    return reverse("emergencia:plazos") if supervisa else ""


def _vacio(vacio, url=""):
    """Un panel que no calcula: ``vacio`` (uno de los ``VACIO_*``) con su acción solo si hay URL."""

    panel = dict(vacio)
    panel["accion_url"] = url
    if not url:
        panel.pop("accion_texto", None)
        panel.pop("accion_icono", None)
    return {"calculado": False, "vacio": panel}


def panel_sin_calcular(*, pedido, inicio_evento, url_calcular, supervisa):
    """El panel cuando la solapa no calcula, o ``None`` si hay que calcularla. Sin consultas.

    Sin ``?tab=abastecimiento`` (``pedido`` falso), «Calcular el abastecimiento» con ``url_calcular``;
    sin ``inicio_evento``, el estado que lo pide (con el enlace a Plazos solo para ``supervisar``).
    """

    if not pedido:
        return _vacio(VACIO_SIN_PEDIR, url_calcular)
    if inicio_evento is None:
        return _vacio(VACIO_SIN_INICIO, _url_plazos(supervisa))
    return None


def contexto_de_abastecimiento(abastecimiento, ahora, *, opera, supervisa, stock=None):
    """Todo lo que dibuja la solapa calculada. Sin consultas.

    ``abastecimiento`` es el de ``armar_abastecimiento``; ``opera`` (``operar`` o ``supervisar``) decide
    los nombres de la salud y «Preparar entrega»; ``supervisa``, el enlace a Insumos; ``stock``, lo que leyó
    ``programas.selectors.stock.stock_por_dispositivo_e_item`` de las instituciones de :func:`con_stock_registrado`.
    """

    url_insumos = _url_insumos(supervisa)
    if not abastecimiento.hay_reglas:
        return _vacio(VACIO_SIN_REGLAS, url_insumos)
    if not abastecimiento.hay_alojados:
        return _vacio(VACIO_SIN_ALOJADOS)
    salud = presentar_salud(abastecimiento.salud, opera)
    con_stock = bool(con_stock_registrado(abastecimiento))
    return {
        "calculado": True,
        "vacio": None,
        "url_insumos": url_insumos,
        "nota": nota(abastecimiento, con_stock=con_stock),
        "con_stock": con_stock,
        "tarjetas": tarjetas(abastecimiento),
        "atencion": alertas_de_abastecimiento(abastecimiento, salud),
        "items": tabla_por_item(abastecimiento),
        "dispositivos": lista_de_dispositivos(abastecimiento, ahora, opera=opera, stock=stock),
        "con_accion": opera,
        "horas_demorada": EntregaKit.HORAS_PARA_DEMORADA,
        "reglas": como_se_calcula(abastecimiento),
        "hay_regla_lactante": bool(abastecimiento.salud.items_de_lactantes),
    }
