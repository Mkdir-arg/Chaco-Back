"""Stock de insumos para la app de campo (análisis 010, PR 7a): solo lectura.

Es lo que la web muestra en la solapa Stock del edificio con **el mismo alcance y las mismas reglas**: nada de reglas
nuevas, solo otra forma de entregarlas. Quién ve qué sale de ``stock.ver`` (``q_edificios_en_alcance`` /
``alcance_de_edificios``) sobre instituciones cuyo tipo lleva stock (RN-010-01); qué puede hacer con cada edificio,
de los mismos predicados que aplican las escrituras (``services.stock.puede_entregar|ingresar|ajustar``). La lista
de pares calcula ``puede`` en forma de conjunto (una consulta por capacidad, no por fila) y un test la compara con
los predicados del servicio: las dos formas no pueden divergir.

Nada de acá escribe: ni el saldo, ni el libro, ni el legajo de la persona (``persona_del_stock`` no da de alta).

Costo constante respecto de la cantidad de insumos, de movimientos y de edificios: la lista de pares son 6 consultas
fijas; el saldo, 2 más las capacidades; el libro, 1.
"""

from django.db.models import Count

from core import rbac
from programas.models import MovimientoStock, SaldoStock, TipoKit
from programas.selectors import stock as selectores
from programas.services import stock as servicio
from programas.services.dispositivos import (
    CAP_STOCK_AJUSTAR,
    CAP_STOCK_ENTREGAR,
    CAP_STOCK_INGRESAR,
    CAP_STOCK_VER,
    pares_en_alcance,
)
from programas.services.edificio_operativo import edificio_de_la_institucion
from programas.services.estadias import CAP_VER_CIUDADANO
from programas.services.stock_personas import PersonaSinDatos

#: De a cuántos movimientos se pagina el libro (análisis 010, §12.2).
MOVIMIENTOS_POR_PAGINA = 50


# ---------------------------------------------------------------------------
# Qué ve el usuario
# ---------------------------------------------------------------------------


def _pares(user, capacidad):
    """Los vínculos institución-edificio que ``user`` alcanza con ``capacidad``, de instituciones que llevan stock."""

    return pares_en_alcance(user, capacidad).filter(dispositivo__tipo__maneja_stock=True)


def _pares_visibles(user):
    """Los pares que lista la app: ``stock.ver`` sobre un edificio **activo** (RN-010-21: sin edificio activo no se opera)."""

    return _pares(user, CAP_STOCK_VER).filter(edificio__activo=True)


def ve_stock(user):
    """¿``user`` ve el stock de al menos un edificio? Es la clave ``stock`` del perfil y el permiso «stock» de la API."""

    if user is None or not getattr(user, "is_authenticated", False):
        return False
    return _pares_visibles(user).exists()


def edificio_de_stock(user, dispositivo, edificio_pk):
    """El edificio, o ``None``: vinculado a ``dispositivo`` y dentro del alcance de ``stock.ver`` de ``user``.

    ``None`` es el 404 de la vista, igual para un edificio que no existe, que no es de la institución o que queda
    fuera del alcance de quien mira.
    """

    return edificio_de_la_institucion(user, dispositivo, edificio_pk, CAP_STOCK_VER)


def _breve(objeto):
    return {"id": objeto.pk, "nombre": objeto.nombre}


def puede_en(user, dispositivo, edificio_id):
    """Qué puede hacer ``user`` con el stock de este edificio: los predicados del servicio, uno por acción."""

    return {
        "entregar": servicio.puede_entregar(user, dispositivo, edificio_id),
        "ingresar": servicio.puede_ingresar(user, dispositivo, edificio_id),
        "ajustar": servicio.puede_ajustar(user, dispositivo, edificio_id),
    }


# ---------------------------------------------------------------------------
# GET stock/: los pares
# ---------------------------------------------------------------------------


def stock_de_la_app(user):
    """Un ítem por par institución-edificio en el alcance de ``stock.ver``, por nombre. Sin paginar.

    ``insumos_con_saldo`` cuenta los insumos con saldo mayor que 0 (una consulta agrupada para todos los pares).
    ``puede`` se arma por conjuntos: ``entregar`` además exige ``ciudadano.ver`` (``services.stock.puede_entregar``).
    """

    pares = list(
        _pares_visibles(user)
        .select_related("dispositivo", "edificio")
        .only("dispositivo_id", "edificio_id", "dispositivo__nombre", "edificio__nombre")
        .order_by("dispositivo__nombre", "dispositivo_id", "edificio__nombre", "edificio_id")
    )
    if not pares:
        return []
    con_saldo = {
        (fila["dispositivo_id"], fila["edificio_id"]): fila["insumos"]
        for fila in SaldoStock.objects.filter(
            dispositivo_id__in={par.dispositivo_id for par in pares},
            edificio_id__in={par.edificio_id for par in pares},
            cantidad__gt=0,
        )
        .values("dispositivo_id", "edificio_id")
        .annotate(insumos=Count("item_id"))
    }
    alcanzados = {
        capacidad: set(_pares(user, capacidad).values_list("dispositivo_id", "edificio_id"))
        for capacidad in (CAP_STOCK_ENTREGAR, CAP_STOCK_INGRESAR, CAP_STOCK_AJUSTAR)
    }
    ve_ciudadano = rbac.puede(user, CAP_VER_CIUDADANO)
    filas = []
    for par in pares:
        clave = (par.dispositivo_id, par.edificio_id)
        filas.append(
            {
                "dispositivo": _breve(par.dispositivo),
                "edificio": _breve(par.edificio),
                "insumos_con_saldo": con_saldo.get(clave, 0),
                "puede": {
                    "entregar": clave in alcanzados[CAP_STOCK_ENTREGAR] and ve_ciudadano,
                    "ingresar": clave in alcanzados[CAP_STOCK_INGRESAR],
                    "ajustar": clave in alcanzados[CAP_STOCK_AJUSTAR],
                },
            }
        )
    return filas


# ---------------------------------------------------------------------------
# El saldo de un edificio
# ---------------------------------------------------------------------------


def stock_del_edificio(user, dispositivo, edificio):
    """El saldo de (``dispositivo``, ``edificio``) y los insumos activos que se pueden cargar. 2 consultas más las capacidades."""

    saldos = [
        {
            "item_id": saldo.item_id,
            "nombre": saldo.item.nombre,
            "unidad": saldo.item.unidad,
            "cantidad": saldo.cantidad,
            "activo": saldo.item.activo,
        }
        for saldo in selectores.saldos_de(dispositivo, edificio)
    ]
    activos = [
        {"item_id": item.pk, "nombre": item.nombre, "unidad": item.unidad}
        for item in TipoKit.objects.filter(activo=True).only("nombre", "unidad").order_by("nombre", "pk")
    ]
    return {
        "dispositivo": _breve(dispositivo),
        "edificio": _breve(edificio),
        "puede": puede_en(user, dispositivo, edificio.pk),
        "saldos": saldos,
        "insumos_activos": activos,
    }


# ---------------------------------------------------------------------------
# El libro
# ---------------------------------------------------------------------------


def _detalle(movimiento):
    """El texto de «detalle» de un movimiento, **sin datos personales ni nombres de otras instituciones**.

    La entrega a una persona no nombra a la persona ni copia la observación (texto libre): el nombre lo decide
    ``ciudadano.ver`` en la web (PR 6b) y la app no lo necesita en el libro. Un traspaso dice si fue a otro edificio
    de la misma institución o a otra institución, sin nombrar el otro lado: quien mira puede no alcanzarlo.
    """

    operacion = movimiento.operacion
    tipo = movimiento.tipo
    if tipo == MovimientoStock.Tipo.INGRESO_MANUAL:
        origen = operacion.get_origen_display() or "Ingreso manual"
        partes = [f"{origen}: {operacion.origen_detalle}" if operacion.origen_detalle else origen]
        if operacion.comprobante:
            partes.append(f"comprobante {operacion.comprobante}")
        return " · ".join(partes)
    if tipo == MovimientoStock.Tipo.AJUSTE:
        motivo = operacion.get_motivo_display() or "Ajuste por conteo"
        return f"{motivo}: {operacion.observacion}" if operacion.observacion else motivo
    if tipo == MovimientoStock.Tipo.TRASPASO_SALIDA:
        misma = operacion.destino_dispositivo_id == operacion.dispositivo_id
        return "Traspaso a otro edificio de la institución" if misma else "Traspaso a otra institución"
    if tipo == MovimientoStock.Tipo.TRASPASO_ENTRADA:
        misma = operacion.dispositivo_id == movimiento.dispositivo_id
        return "Traspaso desde otro edificio de la institución" if misma else "Traspaso desde otra institución"
    return movimiento.get_tipo_display()


def movimientos_del_edificio(dispositivo, edificio, tipo="", item=None, cursor=None):
    """Una página del libro de (``dispositivo``, ``edificio``), del más nuevo al más viejo: ``(filas, siguiente)``.

    ``siguiente`` es el ``cursor`` de la página que sigue (el ``id`` del último movimiento devuelto) o ``None`` si no
    hay más. Se pagina por ``id`` (crece con el momento) y no por posición: un movimiento nuevo no corre la página.
    Una consulta: trae el insumo, la operación y su responsable juntos.
    """

    consulta = selectores.movimientos_de(dispositivo, edificio, {"item": item, "tipo": tipo}).order_by("-id")
    if cursor:
        consulta = consulta.filter(id__lt=cursor)
    movimientos = list(consulta[: MOVIMIENTOS_POR_PAGINA + 1])
    hay_mas = len(movimientos) > MOVIMIENTOS_POR_PAGINA
    movimientos = movimientos[:MOVIMIENTOS_POR_PAGINA]
    filas = [
        {
            "id": movimiento.pk,
            "tipo": movimiento.tipo,
            "item_id": movimiento.item_id,
            "nombre": movimiento.item.nombre,
            "unidad": movimiento.item.unidad,
            "cantidad": movimiento.cantidad,
            "saldo_posterior": movimiento.saldo_posterior,
            "creado_en": movimiento.creado_en,
            "usuario": movimiento.operacion.usuario.get_full_name() or movimiento.operacion.usuario.get_username(),
            "detalle": _detalle(movimiento),
        }
        for movimiento in movimientos
    ]
    return filas, (movimientos[-1].pk if hay_mas else None)


# ---------------------------------------------------------------------------
# Traspasos y personas
# ---------------------------------------------------------------------------


def destinos_del_traspaso(user, dispositivo, edificio):
    """``[{dispositivo, edificio}]`` a los que ``user`` puede traspasar desde este edificio (``services.stock``)."""

    return [
        {"dispositivo": _breve(destino), "edificio": _breve(destino_edificio)}
        for destino, destino_edificio in servicio.destinos_de_traspaso(user, dispositivo, edificio)
    ]


def persona_del_stock(user, dispositivo, edificio, dni, sexo=""):
    """A quién se le va a entregar y qué recibió antes: ``{"persona": {...} | None, "historial": [...]}``. **No escribe.**

    Es ``services.stock.consultar_persona``: exige ``stock.entregar`` y ``ciudadano.ver`` sobre el edificio
    (``PermissionDenied`` si no) **antes** de tocar el padrón, no da de alta el legajo, y el historial nombra la
    institución solo si es esta (RNF-010-07). Si no alcanza para identificarla (sin legajo y sin sexo, o el Registro
    no la tiene) devuelve ``persona: null``: quien entrega carga nombre y apellido al entregar. ``ValidationError``
    (DNI inválido, sexo fuera de la lista, persona fallecida) llega tal cual.
    """

    try:
        persona, historial = servicio.consultar_persona(user, dispositivo, edificio, dni, sexo)
    except PersonaSinDatos:
        return {"persona": None, "historial": []}
    return {
        "persona": {"dni": persona.dni, "nombre": persona.nombre, "apellido": persona.apellido},
        "historial": [
            {"creado_en": entrega["creado_en"], "institucion": entrega["institucion"], "lineas": entrega["lineas"]}
            for entrega in historial
        ],
    }
