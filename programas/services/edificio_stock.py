"""Solapa «Stock» de la página operativa del edificio (análisis 010, PR 4): el saldo por insumo y los últimos movimientos.

Es de **lectura**: no escribe nada ni decide un saldo (eso es de ``services.stock``). La solapa existe solo si el tipo de
la institución lleva stock **y** quien mira tiene ``stock.ver`` sobre este edificio (``puede_solapa``); sin una de las dos
no hay solapa, ni contador, ni panel, igual que Kits sin ``emergencia.recibir_kit``.

Las acciones del panel («Entregar a persona», «Ingresar», «Traspasar», y «Ajustar» por fila) se ofrecen con la
capacidad de cada una **y** solo si su ruta existe: las pantallas llegan con los PR 5 y 6, y mientras no estén el
panel no dibuja botones que llevan a un 404. El servidor las vuelve a exigir en su propia ruta.

Costo
-----

Constante: el saldo (1 consulta) y los últimos movimientos (1, con todo lo que nombran traído en la misma consulta).
No hay consultas por insumo ni por movimiento (RNF-010-04). El contador del botón de la solapa es una consulta agrupada
cuando la solapa no está abierta, y ninguna cuando lo está (sale de la lista).
"""

from django.urls import reverse

from core.rbac import puede
from programas.models import MovimientoStock
from programas.selectors import stock as selectores
from programas.selectors.kits import fecha_hora, nombre_de
from programas.services import stock as servicio
from programas.services.dispositivos import fecha_corta
from programas.services.estadias import CAP_VER_CIUDADANO

#: Cuántos movimientos muestra la solapa antes del «Ver todos» (el listado paginado de ``stock_movimientos``).
MOVIMIENTOS_EN_LA_SOLAPA = 20

#: El parámetro de la página del edificio que abre el modal «Ajustar» de ese insumo.
PARAMETRO_AJUSTAR = "ajustar"

#: Texto de la fila «Stock» de la tarjeta de edificio cuando todavía no se cargó nada.
SIN_STOCK_CARGADO = "Sin stock cargado"


def url_abrir_ajuste(dispositivo, edificio, item_id):
    """URL de la solapa Stock del edificio con el modal «Ajustar» abierto sobre ``item_id``.

    Es la única que la arma: el botón de cada fila y el reintento tras ``SaldoCambio`` / ``UuidEnUso`` abren el mismo modal.
    """

    pagina = reverse("dispositivos:edificio_operativo", args=[dispositivo.pk, edificio.pk])
    return f"{pagina}?tab=stock&{PARAMETRO_AJUSTAR}={item_id}"


_MENOS = "\N{MINUS SIGN}"

#: El tono del badge de cada tipo de movimiento: lo que suma es verde, lo que sale a una persona es informativo.
_TONO_DEL_TIPO = {
    MovimientoStock.Tipo.INGRESO_KIT: "success",
    MovimientoStock.Tipo.INGRESO_MANUAL: "success",
    MovimientoStock.Tipo.ENTREGA_PERSONA: "info",
    MovimientoStock.Tipo.TRASPASO_SALIDA: "gray",
    MovimientoStock.Tipo.TRASPASO_ENTRADA: "gray",
    MovimientoStock.Tipo.AJUSTE: "warning",
}


def puede_solapa(user, dispositivo, edificio_pk):
    """Si la solapa «Stock» existe para ``user`` en este edificio: el tipo lleva stock y tiene ``stock.ver`` ahí.

    Con un tipo que no lleva stock no consulta nada (el módulo apagado no cuesta).
    """

    return servicio.lleva_stock(dispositivo) and servicio.puede_ver_stock(user, dispositivo, edificio_pk)


def texto_de_resumen(insumos, sin_existencia):
    """«3 insumos · 1 sin existencia», o «Sin stock cargado»: lo que dicen la solapa y la tarjeta del edificio."""

    if not insumos:
        return SIN_STOCK_CARGADO
    plural = "insumo" if insumos == 1 else "insumos"
    return f"{insumos} {plural} · {sin_existencia} sin existencia"


def contar_insumos(dispositivo, edificio):
    """Los insumos que la solapa muestra en este edificio (el número del botón de la solapa). Una consulta."""

    resumen = selectores.resumen_de_insumos_por_edificio(dispositivo, [edificio.pk])
    return resumen.get(edificio.pk, {}).get("insumos", 0)


def aviso_sin_edificio_activo(dispositivo, url_vincular=""):
    """El aviso de la ficha de una institución que lleva stock y no tiene ningún edificio **activo** vinculado, o ``None``.

    Sin edificio activo no se opera y la mesa no puede enviarle kits (RN-010-21). Una consulta, y ninguna si el tipo no
    lleva stock. ``url_vincular`` es la acción «Vincular edificio»: la manda la vista solo a quien puede editar el legajo.
    """

    if not servicio.lleva_stock(dispositivo) or dispositivo.edificios.filter(activo=True).exists():
        return None
    return {
        "tono": "warning",
        "icono": "triangle-exclamation",
        "titulo": "Esta institución lleva stock y no tiene un edificio activo",
        "texto": "Sin un edificio activo no se puede cargar ni entregar insumos, y la mesa no puede enviarle kits. "
        "Vinculá un edificio o reactivá uno de los vinculados.",
        "accion_url": url_vincular,
        "accion_texto": "Vincular edificio" if url_vincular else "",
    }


def _url_de_accion(nombre_de_ruta, dispositivo, edificio):
    """La ruta de una acción del edificio. Todas existen: un nombre mal escrito rompe (``NoReverseMatch``) en vez de
    esconder el botón. ``RutasDeStockTests`` fija que cada nombre resuelve."""

    return reverse(nombre_de_ruta, args=[dispositivo.pk, edificio.pk])


def _acciones(user, dispositivo, edificio, ve):
    """Los botones del panel, **solo** los que ``user`` puede usar hoy sobre este edificio: ``[{texto, icono, url, variante}]``.

    Un edificio inactivo no ofrece ninguna (no puede tener saldo: RN-010-15). Con la institución no activa solo
    queda traspasar y ajustar, para vaciar lo que quede (RN-010-14). ``ve`` es ``stock.ver``: sin él no hay botones.
    ``servicio.puede_ver_stock`` está memoizado en el ``user``, así que cada ``puede_*`` lo pide sin pagarlo de nuevo,
    y cada permiso se decide una sola vez aunque lo compartan dos botones (Ingresar y Traspasar piden
    ``stock.ingresar``): el alcance por edificios cuesta consultas.
    """

    if not edificio.activo or not ve:
        return []
    institucion_activa = dispositivo.estado == dispositivo.Estado.ACTIVO
    candidatas = (
        (
            "dispositivos:stock_entregar",
            "Entregar a persona",
            "fa-hand-holding-heart",
            "brand",
            servicio.puede_entregar,
            True,
        ),
        ("dispositivos:stock_ingresar", "Ingresar", "fa-plus", "secondary", servicio.puede_ingresar, True),
        ("dispositivos:stock_traspasar", "Traspasar", "fa-right-left", "secondary", servicio.puede_ingresar, False),
    )
    acciones = []
    decididos = {}
    for ruta, texto, icono, variante, permiso, exige_activa in candidatas:
        if exige_activa and not institucion_activa:
            continue
        if permiso not in decididos:
            decididos[permiso] = permiso(user, dispositivo, edificio.pk)
        if decididos[permiso]:
            acciones.append(
                {
                    "texto": texto,
                    "icono": icono,
                    "url": _url_de_accion(ruta, dispositivo, edificio),
                    "variante": variante,
                }
            )
    return acciones


def _detalle(movimiento, *, puede_ver_persona):
    """La columna «Detalle» de un movimiento: de dónde vino o a dónde fue, sin nombrar lo que quien mira no debe ver.

    * La persona que recibió una entrega solo se nombra con ``ciudadano.ver``.
    * Un traspaso nombra el edificio de la otra punta si es de **esta** institución; si no, dice «otra institución»
      (el nombre de otra institución no se revela: puede ser de ubicación reservada).
    """

    operacion = movimiento.operacion
    tipo = movimiento.tipo
    if tipo == MovimientoStock.Tipo.INGRESO_KIT:
        return f"Entrega {operacion.entrega_kit.numero}" if operacion.entrega_kit_id else "Entrega de kits"
    if tipo == MovimientoStock.Tipo.INGRESO_MANUAL:
        partes = [operacion.get_origen_display(), operacion.origen_detalle]
        if operacion.comprobante:
            partes.append(f"Comprobante {operacion.comprobante}")
        return " · ".join(parte for parte in partes if parte)
    if tipo == MovimientoStock.Tipo.ENTREGA_PERSONA:
        if not puede_ver_persona or not operacion.ciudadano_id:
            # Ni el nombre ni la observación (texto libre sobre la persona) salen sin ``ciudadano.ver``.
            return "Entrega a una persona"
        persona = operacion.ciudadano
        quien = f"A {persona.apellido}, {persona.nombre} · DNI {persona.dni}"
        return " · ".join(parte for parte in (quien, operacion.observacion) if parte)
    if tipo == MovimientoStock.Tipo.TRASPASO_SALIDA:
        misma = operacion.destino_dispositivo_id == movimiento.dispositivo_id
        return (
            f"A {operacion.destino_edificio.nombre}"
            if misma and operacion.destino_edificio_id
            else "A otra institución"
        )
    if tipo == MovimientoStock.Tipo.TRASPASO_ENTRADA:
        misma = operacion.dispositivo_id == movimiento.dispositivo_id
        return f"Desde {operacion.edificio.nombre}" if misma else "Desde otra institución"
    return " · ".join(parte for parte in (operacion.get_motivo_display(), operacion.observacion) if parte)


def fila_de_movimiento(movimiento, *, puede_ver_persona):
    """Una fila de ``components/_tabla_movimientos.html``: todo ya en texto; el template no calcula nada.

    ``cantidad_texto`` lleva el signo escrito (``+8`` / ``−3``): el color nunca es el único portador del sentido.
    """

    delta = movimiento.cantidad
    return {
        "fecha": fecha_hora(movimiento.creado_en),
        "tipo_texto": movimiento.get_tipo_display(),
        "tipo_tono": _TONO_DEL_TIPO.get(movimiento.tipo, "gray"),
        "insumo": movimiento.item.nombre,
        "unidad": movimiento.item.unidad,
        "cantidad_texto": f"+{delta}" if delta > 0 else f"{_MENOS}{abs(delta)}",
        "suma": delta > 0,
        "queda": movimiento.saldo_posterior,
        "quien": nombre_de(movimiento.operacion.usuario),
        "detalle": _detalle(movimiento, puede_ver_persona=puede_ver_persona),
    }


def _fila_de_saldo(saldo, url_abrir_ajuste):
    item = saldo.item
    return {
        "item_id": item.pk,
        "nombre": item.nombre,
        "unidad": item.unidad,
        "cantidad": saldo.cantidad,
        "sin_existencia": saldo.cantidad == 0,
        "desactivado": not item.activo,
        "ultimo": fecha_corta(saldo.ultimo_movimiento_en) if saldo.ultimo_movimiento_en else "—",
        "url_ajustar": url_abrir_ajuste,
    }


def contexto_de_la_solapa(user, dispositivo, edificio):
    """Lo que dibuja el panel: ``resumen``, ``filas`` de saldo, ``movimientos`` y los botones que ``user`` puede usar.

    «Ajustar» por fila no navega a otra pantalla: abre el modal de la misma página con ``?tab=stock&ajustar=<insumo>``
    (``url_ajustar`` de cada fila), y el modal manda su POST a ``url_enviar_ajuste``. ``url_movimientos`` es el «Ver
    todos» del listado paginado.
    """

    saldos = list(selectores.saldos_de(dispositivo, edificio))
    ve = servicio.puede_ver_stock(user, dispositivo, edificio.pk)
    puede_ver_persona = puede(user, CAP_VER_CIUDADANO)
    movimientos = selectores.movimientos_de(dispositivo, edificio, con_persona=puede_ver_persona)[
        :MOVIMIENTOS_EN_LA_SOLAPA
    ]
    puede_ajustar = ve and edificio.activo and servicio.puede_ajustar(user, dispositivo, edificio.pk)
    sin_existencia = sum(1 for saldo in saldos if saldo.cantidad == 0)
    return {
        "insumos": len(saldos),
        "resumen": texto_de_resumen(len(saldos), sin_existencia),
        "filas": [
            _fila_de_saldo(saldo, url_abrir_ajuste(dispositivo, edificio, saldo.item_id) if puede_ajustar else "")
            for saldo in saldos
        ],
        "movimientos": [fila_de_movimiento(m, puede_ver_persona=puede_ver_persona) for m in movimientos],
        "acciones": _acciones(user, dispositivo, edificio, ve),
        "puede_ajustar": bool(puede_ajustar),
        "url_enviar_ajuste": _url_de_accion("dispositivos:stock_ajustar", dispositivo, edificio),
        "url_movimientos": _url_de_accion("dispositivos:stock_movimientos", dispositivo, edificio) if ve else "",
    }


__all__ = [
    "MOVIMIENTOS_EN_LA_SOLAPA",
    "PARAMETRO_AJUSTAR",
    "SIN_STOCK_CARGADO",
    "contar_insumos",
    "contexto_de_la_solapa",
    "fila_de_movimiento",
    "puede_solapa",
    "texto_de_resumen",
    "url_abrir_ajuste",
]
