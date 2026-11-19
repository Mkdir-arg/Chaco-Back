"""Lo que muestra la solapa «Abastecimiento» de E8 (análisis 009, §3.9 y §12): lo armado, escrito.

Nada de acá consulta la base ni decide una regla: los números salen de
``services.abastecimiento_emergencia`` y las alertas AE-8 a AE-10 de
``services.alertas_situacion_emergencia``. Acá se escriben (miles con punto, «≈», la regla de cada
ítem, la cobertura en horas o en fecha) y se decide qué enlace viaja según quién mira:

* **Todo rotulado «estimado»; nunca «stock»** (RNF-009-13): la nota de arriba dice que no es un
  inventario.
* **«Preparar entrega»** (paso 2 de E4) solo con ``operar`` o ``supervisar`` y el dispositivo
  ``ACTIVO``: sin eso, la URL ni se calcula.
* **Enlace a E7** (Configuración de la mesa) solo con ``supervisar``.
* **Ubicación reservada** (RN-009-13): «Dispositivo de ubicación reservada», sin nombre ni localidad.
"""

from datetime import timedelta

from django.urls import reverse
from django.utils.formats import number_format

from programas.models import Dispositivo, TipoKit
from programas.selectors.emergencia_tablero import ZONA_OPERATIVA
from programas.services.abastecimiento_emergencia import CUBRE, SIN_CONSUMO, nombre_visible, presentar_salud
from programas.services.alertas_situacion_emergencia import alertas_de_abastecimiento
from programas.services.ocupacion import etiqueta_y_tono
from programas.services.pantalla_situacion_emergencia import DIAS, ICONOS_DE_TONO, RED_PROVINCIAL, SIN_DATO, numero

#: Los estados de la solapa: sin pedir (se mira otra), sin inicio del evento, sin reglas, sin alojados, calculada.
SIN_PEDIR = "sin_pedir"
SIN_INICIO = "sin_inicio"
SIN_REGLAS = "sin_reglas"
SIN_ALOJADOS = "sin_alojados"
CALCULADO = "calculado"

POR = {TipoKit.PorRegla.PERSONA: "persona", TipoKit.PorRegla.FAMILIA: "familia", TipoKit.PorRegla.LACTANTE: "lactante"}

#: La cobertura se dice en horas hasta un día; desde ahí, en fecha y hora redondeadas a la media hora.
HORAS_EN_HORAS = 24


def _local(momento):
    return momento.astimezone(ZONA_OPERATIVA)


def cantidad_de_la_regla(cantidad):
    """«0,5», «1», «2,25»: sin ceros de más y con coma."""

    return number_format(cantidad.normalize() if hasattr(cantidad, "normalize") else cantidad)


def texto_de_la_regla(item):
    """«1 por persona · dotación», «0,5 por persona por día», «1 por familia cada 3 días»."""

    base = f"{cantidad_de_la_regla(item.cantidad)} por {POR.get(item.por, item.por.lower())}"
    if item.modo == TipoKit.ModoRegla.DOTACION:
        return f"{base} · dotación"
    if item.cada_dias == 1:
        return f"{base} por día"
    return f"{base} cada {item.cada_dias} días"


def _media_hora(momento):
    """El momento local redondeado a la media hora más cercana («≈ 10:30»)."""

    local = _local(momento)
    medias = round((local.minute * 60 + local.second) / 1800)
    return local.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=30 * medias)


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


def nota(abastecimiento):
    inicio = _local(abastecimiento.inicio_evento)
    return (
        f"{RED_PROVINCIAL} · próximas 48 h · desde el inicio del evento ({inicio:%d/%m %H:%M}) · "
        "estimado con la regla de consumo de cada ítem; no es un inventario"
    )


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


def lista_de_dispositivos(abastecimiento, ahora, *, opera):
    """«Dispositivos con faltantes» (B15), en el orden de urgencia. Sin paginar (RN-009-20)."""

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
                "urgencia": {"texto": etiqueta, "tono": tono, "icono": ICONOS_DE_TONO[tono]},
                "personas": personas,
                "ultima": _ultima(fila, ahora),
                "necesita": _que_necesita(fila),
                "url_preparar": (
                    reverse("emergencia:entrega_nueva_items", args=[dispositivo.id])
                    if opera and dispositivo.activo
                    else ""
                ),
            }
        )
    return filas


def como_se_calcula(abastecimiento):
    """La regla de cada ítem con regla, para el plegable «Cómo se calcula»."""

    return [f"{item.nombre}: {texto_de_la_regla(item)}" for item in abastecimiento.items_con_regla]


def contexto_de_abastecimiento(abastecimiento, ahora, *, opera, supervisa):
    """Todo lo que dibuja la solapa calculada. Sin consultas.

    ``abastecimiento`` es el de ``armar_abastecimiento``; ``opera`` (``operar`` o ``supervisar``) decide
    los nombres de la salud y «Preparar entrega»; ``supervisa``, el enlace a E7.
    """

    url_configuracion = reverse("emergencia:configuracion") if supervisa else ""
    if not abastecimiento.hay_reglas:
        return {"estado": SIN_REGLAS, "url_configuracion": url_configuracion}
    if not abastecimiento.hay_alojados:
        return {"estado": SIN_ALOJADOS, "url_configuracion": url_configuracion}
    salud = presentar_salud(abastecimiento.salud, opera)
    return {
        "estado": CALCULADO,
        "url_configuracion": url_configuracion,
        "nota": nota(abastecimiento),
        "tarjetas": tarjetas(abastecimiento),
        "atencion": alertas_de_abastecimiento(abastecimiento, salud),
        "items": tabla_por_item(abastecimiento),
        "dispositivos": lista_de_dispositivos(abastecimiento, ahora, opera=opera),
        "con_accion": opera,
        "reglas": como_se_calcula(abastecimiento),
        "hay_regla_lactante": bool(abastecimiento.salud.items_de_lactantes),
    }
