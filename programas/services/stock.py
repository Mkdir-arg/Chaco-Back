"""Stock de insumos por institución y edificio: el núcleo del servicio (análisis 010, PR 2a).

**Único escritor** de ``SaldoStock``, ``OperacionStock`` y ``MovimientoStock``: la web y la API llaman lo mismo, y
ninguna vista ni serializer decide un permiso ni un saldo. Este PR trae el ingreso manual, el ajuste por conteo y la
suma por recepción de kit; la entrega a persona y el traspaso llegan en el PR 2b y **comparten** el asiento
(:func:`_asentar`) y los candados (:func:`_preparar`), así que ninguno de los dos vuelve a decidir «nunca negativo».

Invariante de toda clave ``(dispositivo, edificio, item)`` (RN-010-05)::

    SaldoStock.cantidad == Σ MovimientoStock.cantidad == saldo_posterior del último movimiento

**Orden de candados** (RN-010-19), uno solo para todo el módulo, compatible con ``kits.crear_entrega``,
``kits.recibir_entrega`` y con «Inactivar» / «Desvincular» edificio (Dispositivo → Edificio)::

    entrega de kits (si la hay) → Dispositivo(s) por pk → Edificio(s) por pk → SaldoStock por (dispositivo, edificio, item)
    → INSERT de la operación y de los movimientos

* El ``Dispositivo`` se toma en **compartido** (``dispositivos.bloquear_instituciones``, la fuente única de ese orden):
  da el estado fresco de la institución sin frenar las plazas y las estadías, y frena «Inactivar» y «Cerrar».
* Los saldos que no existen se crean **antes** de bloquearlos con ``bulk_create(ignore_conflicts=True)``: nunca
  ``get_or_create`` bajo ``FOR UPDATE``, que en InnoDB toma *gap locks* y se traba entre dos altas.
* Nunca ``UniqueConstraint`` condicional (MySQL y MariaDB lo descartan en silencio): la idempotencia la ordena el
  UNIQUE de ``uuid_cliente`` y el de ``entrega_kit``, que son sobre columnas anulables.

Toda función que escribe exige su capacidad **dentro** del servicio (la vista no es la única barrera), vuelve a
leer el estado de la institución y del edificio bajo candado, y devuelve la operación con ``ya_existia``.
"""

from collections import defaultdict
from functools import reduce
from operator import or_

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from core import rbac
from core.db import q_uuid_en_texto
from programas.models import (
    Dispositivo,
    Edificio,
    MovimientoStock,
    OperacionStock,
    SaldoStock,
    TipoKit,
)
from programas.services.dispositivos import (
    CAP_STOCK_AJUSTAR,
    CAP_STOCK_ENTREGAR,
    CAP_STOCK_INGRESAR,
    CAP_STOCK_VER,
    bloquear_instituciones,
    puede_operar_edificio,
)
from programas.services.estadias import CAP_VER_CIUDADANO
from programas.services.kits import (
    CANTIDAD_INVALIDA,
    CANTIDAD_MAXIMA,
    ITEM_NO_DISPONIBLE,
    ITEM_REPETIDO,
    SIN_LINEAS,
    _como_uuid,
    _entero,
    _pares_de,
)

ORIGEN_DETALLE_MAXIMO = OperacionStock._meta.get_field("origen_detalle").max_length
COMPROBANTE_MAXIMO = OperacionStock._meta.get_field("comprobante").max_length
OBSERVACION_MAXIMA = OperacionStock._meta.get_field("observacion").max_length

#: Motivos de ajuste que obligan a explicar (RN-010-12).
_MOTIVOS_CON_DETALLE = frozenset({OperacionStock.MotivoAjuste.OTRO, OperacionStock.MotivoAjuste.CORRECCION_CARGA})

SIN_PERMISO_DE_STOCK = "No tenés permiso para esta acción sobre el stock de este edificio."
STOCK_NO_HABILITADO = "Esta institución no lleva stock."
INSTITUCION_NO_ACTIVA = "La institución no está activa: solo se puede traspasar o ajustar."
EDIFICIO_NO_ES_DE_LA_INSTITUCION = "El edificio no es de esta institución."
EDIFICIO_INACTIVO = "El edificio está inactivo: no se puede cargar stock en él."
INSTITUCION_INEXISTENTE = "La institución no existe."
SIN_EDIFICIO_EN_LA_ENTREGA = "La entrega no tiene edificio: elegí uno antes de sumarla al stock."
ORIGEN_INVALIDO = "Elegí de dónde viene el stock."
FALTA_EL_DETALLE_DEL_ORIGEN = "Contá de dónde viene: con «Otro» el detalle es obligatorio."
DETALLE_DEL_ORIGEN_LARGO = f"El detalle del origen no puede tener más de {ORIGEN_DETALLE_MAXIMO} caracteres."
COMPROBANTE_LARGO = f"El comprobante no puede tener más de {COMPROBANTE_MAXIMO} caracteres."
MOTIVO_INVALIDO = "Elegí el motivo del ajuste."
FALTA_EL_DETALLE_DEL_AJUSTE = "Explicá el ajuste: con este motivo el detalle es obligatorio."
OBSERVACION_LARGA = f"El detalle no puede tener más de {OBSERVACION_MAXIMA} caracteres."
CONTADO_INVALIDO = "La cantidad contada tiene que ser un número entero, cero o más."
SALDO_VISTO_INVALIDO = "Falta el saldo que se vio al abrir el ajuste."
AJUSTE_SIN_DIFERENCIA = "Contaste lo mismo que ya hay: no hay nada que ajustar."
AJUSTE_DE_INSUMO_INACTIVO = "Ese insumo está desactivado: solo se puede ajustar hacia abajo."
UUID_EN_USO = "Ese identificador de envío ya se usó en otra operación."


class SaldoInsuficiente(ValidationError):
    """No alcanza el saldo de alguna línea (RN-010-03). ``saldos_actuales`` es ``{item_id: cantidad}`` de **todas**
    las líneas de la operación, leído bajo candado; ``faltantes`` es ``{item_id: (pedido, hay)}`` de las que no alcanzan."""

    def __init__(self, message, saldos_actuales, faltantes):
        super().__init__(message, code="SALDO_INSUFICIENTE")
        self.saldos_actuales = saldos_actuales
        self.faltantes = faltantes


class SaldoCambio(ValidationError):
    """El saldo cambió entre que se abrió el ajuste y que se confirmó (RN-010-12). ``saldo_actual`` es el de ahora."""

    def __init__(self, saldo_actual, saldo_visto):
        super().__init__(
            f"El saldo cambió mientras contabas: ahora hay {saldo_actual} y habías visto {saldo_visto}. Volvé a contar.",
            code="SALDO_CAMBIO",
        )
        self.saldo_actual = saldo_actual
        self.saldo_visto = saldo_visto


class StockNoHabilitado(ValidationError):
    """La institución no lleva stock, o su estado o el del edificio no permite esa acción (RN-010-01, RN-010-14)."""

    def __init__(self, message=STOCK_NO_HABILITADO):
        super().__init__(message, code="STOCK_NO_HABILITADO")


class UuidEnUso(ValidationError):
    """El ``uuid_cliente`` ya lo usó otro usuario, u otra operación (RN-010-18)."""

    def __init__(self, message=UUID_EN_USO):
        super().__init__(message, code="UUID_EN_USO")


# ---------------------------------------------------------------------------
# Quién lleva stock y quién puede
# ---------------------------------------------------------------------------


def lleva_stock(dispositivo):
    """Si el tipo de la institución lleva stock (RN-010-01). Es lo que apaga el módulo entero."""

    return bool(dispositivo.tipo.maneja_stock)


def puede_ver_stock(user, dispositivo, edificio_id):
    return puede_operar_edificio(user, dispositivo, edificio_id, CAP_STOCK_VER)


def _puede_con(user, dispositivo, edificio_id, capacidad):
    """RN-010-13: cada acción exige su capacidad **y** ``stock.ver`` sobre el mismo edificio."""

    return puede_ver_stock(user, dispositivo, edificio_id) and puede_operar_edificio(
        user, dispositivo, edificio_id, capacidad
    )


def puede_entregar(user, dispositivo, edificio_id):
    """Entregar exige además ``ciudadano.ver``, como el ingreso de personas (``puede_ingresar_persona``)."""

    return _puede_con(user, dispositivo, edificio_id, CAP_STOCK_ENTREGAR) and rbac.puede(user, CAP_VER_CIUDADANO)


def puede_ingresar(user, dispositivo, edificio_id):
    return _puede_con(user, dispositivo, edificio_id, CAP_STOCK_INGRESAR)


def puede_ajustar(user, dispositivo, edificio_id):
    return _puede_con(user, dispositivo, edificio_id, CAP_STOCK_AJUSTAR)


def _exigir(permiso, user, dispositivo, edificio_id):
    if not permiso(user, dispositivo, edificio_id):
        raise PermissionDenied(SIN_PERMISO_DE_STOCK)


# ---------------------------------------------------------------------------
# Piezas comunes: resolver, validar, bloquear, asentar
# ---------------------------------------------------------------------------


def _dispositivo(valor):
    dispositivo = valor if isinstance(valor, Dispositivo) else Dispositivo.objects.filter(pk=valor).first()
    if dispositivo is None:
        raise ValidationError({"dispositivo": INSTITUCION_INEXISTENTE})
    return dispositivo


def _pk(valor):
    return getattr(valor, "pk", valor)


def _texto(valor):
    return (valor or "").strip()


def _validar_lineas(lineas, *, solo_activos):
    """RN-010-04: al menos una, cada insumo una sola vez, cantidades enteras de 1 a ``CANTIDAD_MAXIMA``.

    Devuelve ``[(TipoKit, cantidad)]``. Con ``solo_activos`` (ingreso manual, RN-010-17) el insumo tiene que estar
    activo **ahora**; sin él (entrega, traspaso) basta que exista: un insumo desactivado con saldo se sigue moviendo.
    """

    pares = _pares_de(lineas)
    if not pares:
        raise ValidationError({"lineas": SIN_LINEAS})
    ids = [_entero(item_id) for item_id, _cantidad in pares]
    if None in ids:
        raise ValidationError({"lineas": ITEM_NO_DISPONIBLE})
    if len(set(ids)) != len(ids):
        raise ValidationError({"lineas": ITEM_REPETIDO})
    cantidades = [_entero(cantidad) for _item, cantidad in pares]
    if any(cantidad is None or not 0 < cantidad <= CANTIDAD_MAXIMA for cantidad in cantidades):
        raise ValidationError({"lineas": CANTIDAD_INVALIDA})
    insumos = TipoKit.objects.filter(pk__in=ids, **({"activo": True} if solo_activos else {})).in_bulk()
    if len(insumos) != len(ids):
        raise ValidationError({"lineas": ITEM_NO_DISPONIBLE})
    return [(insumos[item_id], cantidad) for item_id, cantidad in zip(ids, cantidades, strict=True)]


def _operacion_de_ese_envio(uuid_cliente, usuario, tipo, dispositivo_id, edificio_id):
    """La operación que ya hizo ese ``uuid_cliente`` (con ``ya_existia``) o ``None`` (RN-010-18).

    Reenviarlo **el mismo usuario**, para la misma acción y el mismo lugar, es un reintento. En manos de otro, de
    otro tipo de operación o de otro edificio no lo es: :class:`UuidEnUso`, sin devolver una operación ajena.
    """

    existente = OperacionStock.objects.filter(q_uuid_en_texto("uuid_cliente", uuid_cliente)).first()
    if existente is None:
        return None
    if (existente.usuario_id, existente.tipo, existente.dispositivo_id, existente.edificio_id) != (
        usuario.pk,
        tipo,
        dispositivo_id,
        edificio_id,
    ):
        raise UuidEnUso()
    existente.ya_existia = True
    return existente


def _preparar(pares):
    """Bloquea **Dispositivo(s) → Edificio(s)** por pk (RN-010-19) y valida lo que no cambia con la acción.

    ``pares`` son ``(dispositivo_id, edificio_id)``. Devuelve ``({dispositivo_id: estado}, {edificio_id: activo})``,
    leídos **bajo candado**: el estado que cuenta es el de ahora, no el de la pantalla. Rechaza una institución que no
    lleva stock (``StockNoHabilitado``) y un edificio que no es de la institución (RN-010-02). Los saldos van después,
    con :func:`saldos_bloqueados`.
    """

    dispositivo_ids = sorted({dispositivo_id for dispositivo_id, _e in pares})
    edificio_ids = sorted({edificio_id for _d, edificio_id in pares})
    estados = bloquear_instituciones(dispositivo_ids)
    edificios = dict(
        Edificio.objects.select_for_update().filter(pk__in=edificio_ids).order_by("pk").values_list("pk", "activo")
    )
    if set(estados) != set(dispositivo_ids):
        raise ValidationError({"dispositivo": INSTITUCION_INEXISTENTE})
    llevan = dict(Dispositivo.objects.filter(pk__in=dispositivo_ids).values_list("pk", "tipo__maneja_stock"))
    if not all(llevan[dispositivo_id] for dispositivo_id in dispositivo_ids):
        raise StockNoHabilitado()
    vinculados = set(
        Edificio.dispositivos.through.objects.filter(
            dispositivo_id__in=dispositivo_ids, edificio_id__in=edificio_ids
        ).values_list("dispositivo_id", "edificio_id")
    )
    if any((dispositivo_id, edificio_id) not in vinculados for dispositivo_id, edificio_id in pares):
        raise ValidationError({"edificio": EDIFICIO_NO_ES_DE_LA_INSTITUCION})
    return estados, edificios


def _exigir_activos(dispositivo_id, edificio_id, estados, edificios):
    """RN-010-14: ingresar, entregar y recibir un traspaso piden institución ``ACTIVO`` y edificio activo."""

    if estados[dispositivo_id] != Dispositivo.Estado.ACTIVO:
        raise StockNoHabilitado(INSTITUCION_NO_ACTIVA)
    if not edificios[edificio_id]:
        raise StockNoHabilitado(EDIFICIO_INACTIVO)


def saldos_bloqueados(claves):
    """Los ``SaldoStock`` de ``claves`` —``(dispositivo_id, edificio_id, item_id)``— **bloqueados y en orden**.

    RN-010-19: crea los que faltan con ``bulk_create(ignore_conflicts=True)`` (una fila en cero no mueve nada) y
    recién después los bloquea con ``select_for_update`` ordenados por ``(dispositivo_id, edificio_id, item_id)``:
    dos operaciones que se cruzan piden las mismas filas en el mismo orden y no se matan. Sin ``select_related``: un
    ``FOR UPDATE`` con JOIN bloquearía también las filas de las otras tablas. Exige estar en una transacción.
    Devuelve ``{(dispositivo_id, edificio_id, item_id): SaldoStock}``.
    """

    claves = sorted(set(claves))
    if not claves:
        return {}
    SaldoStock.objects.bulk_create(
        [SaldoStock(dispositivo_id=d, edificio_id=e, item_id=i) for d, e, i in claves], ignore_conflicts=True
    )
    por_lugar = defaultdict(list)
    for dispositivo_id, edificio_id, item_id in claves:
        por_lugar[(dispositivo_id, edificio_id)].append(item_id)
    filtro = reduce(
        or_,
        (Q(dispositivo_id=d, edificio_id=e, item_id__in=items) for (d, e), items in por_lugar.items()),
    )
    filas = SaldoStock.objects.select_for_update().filter(filtro).order_by("dispositivo_id", "edificio_id", "item_id")
    return {(s.dispositivo_id, s.edificio_id, s.item_id): s for s in filas}


def _nombres_de(item_ids):
    return dict(TipoKit.objects.filter(pk__in=item_ids).values_list("pk", "nombre"))


def _asentar(*, usuario, tipo, dispositivo_id, edificio_id, cambios, uuid_cliente=None, previa=None, **campos):
    """Escribe la operación, sus movimientos y los saldos. **El único lugar donde un saldo cambia** (RN-010-03/05).

    ``cambios`` es ``[(SaldoStock bloqueado, delta, tipo de movimiento)]``. Todo o nada: si alguna salida no alcanza
    se levanta :class:`SaldoInsuficiente` **antes** de escribir nada, así que no queda operación ni movimiento, y el
    ``CHECK`` de la base queda como respaldo y no como regla. Una operación que llegó a la vez con el mismo
    ``uuid_cliente`` (o la misma entrega) la ordena el UNIQUE: se deshace este intento y se devuelve la del otro.
    """

    faltantes = {
        saldo.item_id: (-delta, saldo.cantidad) for saldo, delta, _tipo in cambios if saldo.cantidad + delta < 0
    }
    if faltantes:
        nombres = _nombres_de(faltantes)
        detalle = ", ".join(
            f"{nombres.get(i, i)} (hay {hay}, pediste {pedido})" for i, (pedido, hay) in faltantes.items()
        )
        raise SaldoInsuficiente(
            f"No alcanza el stock de: {detalle}. Recargá para ver el saldo actual.",
            saldos_actuales={saldo.item_id: saldo.cantidad for saldo, _d, _t in cambios},
            faltantes=faltantes,
        )
    ahora = timezone.now()
    try:
        # Anidada: si el UNIQUE salta, se deshace solo este alta y la transacción de afuera sigue sana.
        with transaction.atomic():
            operacion = OperacionStock.objects.create(
                tipo=tipo,
                dispositivo_id=dispositivo_id,
                edificio_id=edificio_id,
                usuario=usuario,
                uuid_cliente=uuid_cliente,
                **campos,
            )
    except IntegrityError:
        anterior = previa() if previa is not None else None
        if anterior is None:
            raise
        return anterior
    movimientos = []
    for saldo, delta, tipo_movimiento in cambios:
        saldo.cantidad += delta
        saldo.ultimo_movimiento_en = ahora
        saldo.save(update_fields=["cantidad", "ultimo_movimiento_en", "modificado"])
        movimientos.append(
            MovimientoStock(
                operacion=operacion,
                tipo=tipo_movimiento,
                dispositivo_id=saldo.dispositivo_id,
                edificio_id=saldo.edificio_id,
                item_id=saldo.item_id,
                cantidad=delta,
                saldo_posterior=saldo.cantidad,
            )
        )
    MovimientoStock.objects.bulk_create(movimientos)
    operacion.ya_existia = False
    return operacion


# ---------------------------------------------------------------------------
# Ingreso manual
# ---------------------------------------------------------------------------


@transaction.atomic
def ingresar_manual(
    usuario, dispositivo, edificio, lineas, origen, origen_detalle="", comprobante="", uuid_cliente=None
):
    """Suma stock cargado a mano (RN-010-08): donación, compra… Devuelve la :class:`OperacionStock`.

    * Exige ``stock.ingresar`` (y ``stock.ver``) sobre el edificio: la capacidad se mira **acá**.
    * Institución ``ACTIVO`` y edificio activo (RN-010-14); insumos **activos** (RN-010-17); líneas de RN-010-04.
    * ``origen`` de un catálogo cerrado; el detalle es obligatorio con «Otro». ``comprobante`` es texto libre y opcional.
    * Sin fecha retroactiva: el momento es el de la carga.
    * Idempotente por ``uuid_cliente`` (RN-010-18): un reenvío del mismo usuario devuelve la misma, con ``ya_existia``.
    """

    dispositivo = _dispositivo(dispositivo)
    edificio_id = _pk(edificio)
    _exigir(puede_ingresar, usuario, dispositivo, edificio_id)
    uuid_cliente = _como_uuid(uuid_cliente)
    tipo = OperacionStock.Tipo.INGRESO_MANUAL
    anterior = (
        _operacion_de_ese_envio(uuid_cliente, usuario, tipo, dispositivo.pk, edificio_id) if uuid_cliente else None
    )
    if anterior is not None:
        return anterior

    origen_detalle, comprobante = _texto(origen_detalle), _texto(comprobante)
    if origen not in OperacionStock.Origen.values:
        raise ValidationError({"origen": ORIGEN_INVALIDO})
    if origen == OperacionStock.Origen.OTRO and not origen_detalle:
        raise ValidationError({"origen_detalle": FALTA_EL_DETALLE_DEL_ORIGEN})
    if len(origen_detalle) > ORIGEN_DETALLE_MAXIMO:
        raise ValidationError({"origen_detalle": DETALLE_DEL_ORIGEN_LARGO})
    if len(comprobante) > COMPROBANTE_MAXIMO:
        raise ValidationError({"comprobante": COMPROBANTE_LARGO})
    validas = _validar_lineas(lineas, solo_activos=True)

    estados, edificios = _preparar([(dispositivo.pk, edificio_id)])
    _exigir_activos(dispositivo.pk, edificio_id, estados, edificios)
    # Con los candados ya tomados se vuelve a mirar: dos envíos a la vez del mismo armado se ordenan acá.
    anterior = (
        _operacion_de_ese_envio(uuid_cliente, usuario, tipo, dispositivo.pk, edificio_id) if uuid_cliente else None
    )
    if anterior is not None:
        return anterior
    saldos = saldos_bloqueados([(dispositivo.pk, edificio_id, item.pk) for item, _c in validas])
    cambios = [
        (saldos[(dispositivo.pk, edificio_id, item.pk)], cantidad, MovimientoStock.Tipo.INGRESO_MANUAL)
        for item, cantidad in validas
    ]
    return _asentar(
        usuario=usuario,
        tipo=tipo,
        dispositivo_id=dispositivo.pk,
        edificio_id=edificio_id,
        cambios=cambios,
        uuid_cliente=uuid_cliente,
        previa=lambda: _operacion_de_ese_envio(uuid_cliente, usuario, tipo, dispositivo.pk, edificio_id),
        origen=origen,
        origen_detalle=origen_detalle,
        comprobante=comprobante,
    )


# ---------------------------------------------------------------------------
# Ajuste por conteo
# ---------------------------------------------------------------------------


@transaction.atomic
def ajustar(
    usuario,
    dispositivo,
    edificio,
    item,
    cantidad_contada,
    saldo_visto,
    motivo,
    detalle="",
    uuid_cliente=None,
):
    """Lleva el saldo de un insumo a la cantidad **contada** (RN-010-12). El sistema calcula el delta.

    * Exige ``stock.ajustar`` (y ``stock.ver``) sobre el edificio.
    * ``saldo_visto`` es el que se vio al abrir el ajuste: si el saldo de ahora (bajo candado) es otro,
      :class:`SaldoCambio` y no se mueve nada. Contar lo mismo que hay es un rechazo: no deja un movimiento en cero.
    * ``motivo`` de un catálogo cerrado; el detalle es obligatorio con «Otro» y con «Corrección de carga».
    * Se permite con la institución **no** ``ACTIVO`` (para vaciar lo que queda). Hacia **arriba** (más de lo que hay)
      el edificio tiene que estar activo, y un insumo desactivado solo se ajusta hacia abajo (RN-010-17): si no, el
      stock quedaría en un lugar o con un insumo que no se ofrece.
    * Idempotente por ``uuid_cliente`` (RN-010-18).
    """

    dispositivo = _dispositivo(dispositivo)
    edificio_id = _pk(edificio)
    _exigir(puede_ajustar, usuario, dispositivo, edificio_id)
    uuid_cliente = _como_uuid(uuid_cliente)
    tipo = OperacionStock.Tipo.AJUSTE
    anterior = (
        _operacion_de_ese_envio(uuid_cliente, usuario, tipo, dispositivo.pk, edificio_id) if uuid_cliente else None
    )
    if anterior is not None:
        return anterior

    detalle = _texto(detalle)
    if motivo not in OperacionStock.MotivoAjuste.values:
        raise ValidationError({"motivo": MOTIVO_INVALIDO})
    if motivo in _MOTIVOS_CON_DETALLE and not detalle:
        raise ValidationError({"detalle": FALTA_EL_DETALLE_DEL_AJUSTE})
    if len(detalle) > OBSERVACION_MAXIMA:
        raise ValidationError({"detalle": OBSERVACION_LARGA})
    contada, visto = _entero(cantidad_contada), _entero(saldo_visto)
    if contada is None or not 0 <= contada <= CANTIDAD_MAXIMA:
        raise ValidationError({"cantidad_contada": CONTADO_INVALIDO})
    if visto is None or visto < 0:
        raise ValidationError({"saldo_visto": SALDO_VISTO_INVALIDO})
    insumo = TipoKit.objects.filter(pk=_pk(item)).first()
    if insumo is None:
        raise ValidationError({"item": ITEM_NO_DISPONIBLE})

    estados, edificios = _preparar([(dispositivo.pk, edificio_id)])
    anterior = (
        _operacion_de_ese_envio(uuid_cliente, usuario, tipo, dispositivo.pk, edificio_id) if uuid_cliente else None
    )
    if anterior is not None:
        return anterior
    clave = (dispositivo.pk, edificio_id, insumo.pk)
    saldo = saldos_bloqueados([clave])[clave]
    if saldo.cantidad != visto:
        raise SaldoCambio(saldo.cantidad, visto)
    delta = contada - saldo.cantidad
    if delta == 0:
        raise ValidationError({"cantidad_contada": AJUSTE_SIN_DIFERENCIA})
    if delta > 0:
        if not insumo.activo:
            raise ValidationError({"item": AJUSTE_DE_INSUMO_INACTIVO})
        if not edificios[edificio_id]:
            raise StockNoHabilitado(EDIFICIO_INACTIVO)
    return _asentar(
        usuario=usuario,
        tipo=tipo,
        dispositivo_id=dispositivo.pk,
        edificio_id=edificio_id,
        cambios=[(saldo, delta, MovimientoStock.Tipo.AJUSTE)],
        uuid_cliente=uuid_cliente,
        previa=lambda: _operacion_de_ese_envio(uuid_cliente, usuario, tipo, dispositivo.pk, edificio_id),
        motivo=motivo,
        observacion=detalle,
    )


# ---------------------------------------------------------------------------
# Recepción de un kit (la llamará ``kits.recibir_entrega`` en el PR 3)
# ---------------------------------------------------------------------------


@transaction.atomic
def sumar_recepcion_de_kit(entrega, usuario):
    """Suma lo recibido de ``entrega`` al stock de (su institución, su edificio) (RN-010-06). Devuelve la operación, o
    ``None`` si no hay nada que sumar.

    * La suma es **consecuencia** de la recepción: no pide capacidad de stock (la recepción ya exigió
      ``emergencia.recibir_kit``) ni mira el estado de la institución ni del edificio.
    * Una institución cuyo tipo no lleva stock no se toca. Sin edificio en la entrega, un rechazo: lo elige la guardia
      al recibir (RN-010-07).
    * Suma ``cantidad_recibida`` de cada línea **mayor que 0**: lo enviado no suma, y una línea en 0 no deja
      movimiento. Si ninguna línea suma, no hay operación.
    * Una entrega suma **una sola vez**: ``OperacionStock.entrega_kit`` es única. Si ya sumó, devuelve esa operación
      con ``ya_existia`` sin mover nada.

    Tiene que llamarse dentro de la transacción de la recepción, **después** de bloquear la entrega: el orden de
    candados es entrega → Dispositivo → Edificio → Saldo.
    """

    if not lleva_stock(entrega.dispositivo):
        return None
    if entrega.edificio_id is None:
        raise ValidationError({"edificio": SIN_EDIFICIO_EN_LA_ENTREGA})
    sumas = [
        (linea.item_id, linea.cantidad_recibida)
        for linea in entrega.lineas.all().order_by("item_id")
        if linea.cantidad_recibida
    ]
    if not sumas:
        return None

    def previa():
        existente = OperacionStock.objects.filter(entrega_kit=entrega).first()
        if existente is not None:
            existente.ya_existia = True
        return existente

    anterior = previa()
    if anterior is not None:
        return anterior
    dispositivo_id, edificio_id = entrega.dispositivo_id, entrega.edificio_id
    _preparar([(dispositivo_id, edificio_id)])
    saldos = saldos_bloqueados([(dispositivo_id, edificio_id, item_id) for item_id, _c in sumas])
    return _asentar(
        usuario=usuario,
        tipo=OperacionStock.Tipo.INGRESO_KIT,
        dispositivo_id=dispositivo_id,
        edificio_id=edificio_id,
        cambios=[
            (saldos[(dispositivo_id, edificio_id, item_id)], cantidad, MovimientoStock.Tipo.INGRESO_KIT)
            for item_id, cantidad in sumas
        ],
        previa=previa,
        entrega_kit=entrega,
    )
