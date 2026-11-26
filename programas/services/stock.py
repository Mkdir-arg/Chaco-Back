"""Stock de insumos por institución y edificio: el núcleo del servicio (análisis 010, PR 2a).

**Único escritor** de ``SaldoStock``, ``OperacionStock`` y ``MovimientoStock``: la web y la API llaman lo mismo, y
ninguna vista ni serializer decide un permiso ni un saldo. Este PR trae el ingreso manual, el ajuste por conteo y la
suma por recepción de kit y, desde el PR 2b, la entrega a una persona y el traspaso, que **comparten** el asiento
(:func:`_asentar`) y los candados (:func:`_preparar`): ninguno vuelve a decidir «nunca negativo».

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
from functools import partial, reduce
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
from programas.selectors import stock as selectores
from programas.services.dispositivos import (
    CAP_STOCK_AJUSTAR,
    CAP_STOCK_ENTREGAR,
    CAP_STOCK_INGRESAR,
    CAP_STOCK_VER,
    bloquear_instituciones,
    dispositivos_en_alcance,
    puede_operar_edificio,
    q_edificios_en_alcance,
)
from programas.services.estadias import CAP_VER_CIUDADANO
from programas.services.kits import (
    CANTIDAD_MAXIMA,
    ITEM_NO_DISPONIBLE,
    _como_uuid,
    _entero,
    _validar_lineas,
)
from programas.services.stock_personas import dar_de_alta, resolver_persona

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
DESTINO_INVALIDO = "El destino no es válido para este traspaso."
TRASPASO_AL_MISMO_LUGAR = "El destino tiene que ser otro edificio u otra institución."
DESTINO_INACTIVO = "La institución o el edificio de destino está inactivo."
SALDO_EXCEDIDO = "Con esa cantidad el saldo superaría el máximo que se puede registrar. Revisá las cantidades."


class SaldoInsuficiente(ValidationError):
    """No alcanza el saldo de alguna línea (RN-010-03). ``saldos_actuales`` es ``{item_id: cantidad}`` de **todas**
    las líneas que salen (la entrega, o el origen de un traspaso), leído bajo candado; ``faltantes`` es ``{item_id: (pedido, hay)}`` de las que no alcanzan."""

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


def exigir_sin_saldo_para_dejar_de_llevar(tipo, *, bloquear):
    """RN-010-16: un tipo no deja de llevar stock mientras alguna institución suya tenga saldo mayor que 0.

    ``ValidationError({"maneja_stock": …})`` con cuántas instituciones lo impiden. Con ``bloquear=True`` toma, **en
    exclusivo** y por pk, las filas de las instituciones del tipo antes de contar: una entrega o un ingreso en curso
    las tiene en compartido y se espera a que termine, y una que llegue después espera a este commit y encuentra el
    tipo ya sin stock (``_preparar`` lo vuelve a leer bajo candado). Sin el candado, contar y destildar dejaban una
    ventana: el tipo quedaba sin stock y con saldo. Hay que llamarlo **dentro** de la transacción que guarda el tipo.
    Sin ``bloquear`` es la lectura rápida de la validación del formulario, que avisa antes de guardar.
    """

    instituciones = Dispositivo.objects.filter(tipo=tipo)
    if bloquear:
        instituciones = instituciones.select_for_update().order_by("pk")
    ids = list(instituciones.values_list("pk", flat=True))
    con_saldo = (
        SaldoStock.objects.filter(dispositivo_id__in=ids, cantidad__gt=0).values("dispositivo_id").distinct().count()
    )
    if con_saldo:
        cuantas = "Hay 1 institución" if con_saldo == 1 else f"Hay {con_saldo} instituciones"
        raise ValidationError(
            {
                "maneja_stock": f"{cuantas} de este tipo con stock cargado: "
                "no se puede dejar de llevar stock mientras haya saldo."
            }
        )


# ---------------------------------------------------------------------------
# Piezas comunes: resolver, validar, bloquear, asentar
# ---------------------------------------------------------------------------


def _dispositivo(valor):
    """La institución (un ``Dispositivo`` o su id); un id inexistente o no numérico es ``ValidationError``."""

    if isinstance(valor, Dispositivo):
        return valor
    dispositivo_id = _entero(valor)
    dispositivo = Dispositivo.objects.filter(pk=dispositivo_id).first() if dispositivo_id is not None else None
    if dispositivo is None:
        raise ValidationError({"dispositivo": INSTITUCION_INEXISTENTE})
    return dispositivo


def _pk(valor):
    return getattr(valor, "pk", valor)


def _edificio_id(valor):
    """El id del edificio (un ``Edificio`` o su id) como entero, o ``None`` si no lo es (queda como «sin edificio»)."""

    return _entero(_pk(valor))


def _texto(valor):
    return (valor or "").strip()


def _operacion_de_ese_envio(uuid_cliente, usuario, tipo, dispositivo_id, edificio_id, destino=(None, None)):
    """La operación que ya hizo ese ``uuid_cliente`` (con ``ya_existia``) o ``None`` (RN-010-18).

    Sin ``uuid_cliente`` devuelve ``None``. Reenviarlo **el mismo usuario**, para la misma acción y el mismo lugar
    —y en un traspaso, el mismo destino—, es un reintento. En manos de otro, de otro tipo de operación, de otro
    edificio o de otro destino no lo es: :class:`UuidEnUso`, sin devolver una operación ajena.
    """

    if not uuid_cliente:
        return None
    existente = OperacionStock.objects.filter(q_uuid_en_texto("uuid_cliente", uuid_cliente)).first()
    if existente is None:
        return None
    if (
        existente.usuario_id,
        existente.tipo,
        existente.dispositivo_id,
        existente.edificio_id,
        existente.destino_dispositivo_id,
        existente.destino_edificio_id,
    ) != (usuario.pk, tipo, dispositivo_id, edificio_id, *destino):
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
    ``FOR UPDATE`` con JOIN bloquearía también las filas de las otras tablas.

    **Precondición**: estar en una transacción y **haber tomado antes** Dispositivo → Edificio con :func:`_preparar`.
    El orden de las filas de saldo solo evita el interbloqueo si el Edificio ya serializa a quienes compiten: sin él,
    dos ``INSERT IGNORE`` sobre una fila que ya existe dejan candados compartidos y después los dos piden
    ``FOR UPDATE`` (el motor corta a uno con 1213). Es pública solo porque la prueban los tests de candados.
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


def _exigir_saldo(cambios):
    """RN-010-03: ninguna salida deja un saldo negativo. Levanta :class:`SaldoInsuficiente` sin escribir nada.

    ``saldos_actuales`` trae **todas** las líneas que salen (las de la entrega o las del origen de un traspaso), no
    solo las que no alcanzan: la pantalla las muestra juntas. Las entradas no entran: en un traspaso el mismo insumo
    tiene un saldo de salida y otro de entrada, y pisarían la clave.
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
            saldos_actuales={saldo.item_id: saldo.cantidad for saldo, delta, _t in cambios if delta < 0},
            faltantes=faltantes,
        )


def _exigir_tope(cambios):
    """RN-010-04: ninguna entrada hace pasar un saldo de ``CANTIDAD_MAXIMA``.

    Cada línea ya se validó por separado, pero la **suma** con lo que hay puede no entrar en la columna: sin esta guarda, MariaDB en modo estricto devuelve ``DataError`` (500) y SQLite no lo ve.
    """

    if any(saldo.cantidad + delta > CANTIDAD_MAXIMA for saldo, delta, _tipo in cambios if delta > 0):
        raise ValidationError({"lineas": SALDO_EXCEDIDO})


def _asentar(*, usuario, tipo, dispositivo_id, edificio_id, cambios, uuid_cliente=None, previa=None, **campos):
    """Escribe la operación, sus movimientos y los saldos. **El único lugar donde un saldo cambia** (RN-010-03/05).

    ``cambios`` es ``[(SaldoStock bloqueado, delta, tipo de movimiento)]``. Todo o nada: si alguna salida no alcanza
    se levanta :class:`SaldoInsuficiente` **antes** de escribir nada, así que no queda operación ni movimiento, y el
    ``CHECK`` de la base queda como respaldo y no como regla. Una operación que llegó a la vez con el mismo
    ``uuid_cliente`` (o la misma entrega) la ordena el UNIQUE: se deshace este intento y se devuelve la del otro.
    """

    _exigir_saldo(cambios)
    _exigir_tope(cambios)
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
    edificio_id = _edificio_id(edificio)
    _exigir(puede_ingresar, usuario, dispositivo, edificio_id)
    uuid_cliente = _como_uuid(uuid_cliente)
    tipo = OperacionStock.Tipo.INGRESO_MANUAL
    reenvio = partial(_operacion_de_ese_envio, uuid_cliente, usuario, tipo, dispositivo.pk, edificio_id)
    anterior = reenvio()
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
    validas = _validar_lineas(lineas)

    estados, edificios = _preparar([(dispositivo.pk, edificio_id)])
    _exigir_activos(dispositivo.pk, edificio_id, estados, edificios)
    # Con los candados ya tomados se vuelve a mirar: dos envíos a la vez del mismo armado se ordenan acá.
    anterior = reenvio()
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
        previa=reenvio,
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
    edificio_id = _edificio_id(edificio)
    _exigir(puede_ajustar, usuario, dispositivo, edificio_id)
    uuid_cliente = _como_uuid(uuid_cliente)
    tipo = OperacionStock.Tipo.AJUSTE
    reenvio = partial(_operacion_de_ese_envio, uuid_cliente, usuario, tipo, dispositivo.pk, edificio_id)
    anterior = reenvio()
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
    item_id = _entero(_pk(item))
    insumo = TipoKit.objects.filter(pk=item_id).first() if item_id is not None else None
    if insumo is None:
        raise ValidationError({"item": ITEM_NO_DISPONIBLE})

    estados, edificios = _preparar([(dispositivo.pk, edificio_id)])
    anterior = reenvio()
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
        previa=reenvio,
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


# ---------------------------------------------------------------------------
# Entrega a una persona
# ---------------------------------------------------------------------------


def consultar_persona(usuario, dispositivo, edificio, dni, sexo="", nombre="", apellido="", persona=None):
    """A quién se le va a entregar y qué recibió antes, **sin escribir nada**. Devuelve ``(persona, historial)``.

    Es lo único que expone identidad sin entregar (el GET de la pantalla y de la API): exige lo mismo que entregar,
    ``stock.entregar`` y ``ciudadano.ver`` sobre el edificio, para que nadie consulte el padrón por acá. ``persona``
    es una :class:`~programas.services.stock_personas.PersonaResuelta` y ``historial`` las últimas entregas de esa
    persona en toda la red, con las de otras instituciones sin nombre (``selectors.stock.historial_de_persona``). Una
    persona que todavía no tiene legajo no tiene historial. ``PersonaSinDatos`` y ``ValidationError`` de
    :func:`~programas.services.stock_personas.resolver_persona` llegan tal cual. ``persona`` es una
    ``PersonaResuelta`` que el llamador ya tiene (la de un rechazo de ``entregar_a_persona``): no se consulta de nuevo
    al Registro, pero los permisos se exigen igual.
    """

    dispositivo = _dispositivo(dispositivo)
    _exigir(puede_entregar, usuario, dispositivo, _edificio_id(edificio))
    if not lleva_stock(dispositivo):
        raise StockNoHabilitado()
    if persona is None:
        persona = resolver_persona(dni, sexo, nombre, apellido)
    historial = selectores.historial_de_persona(persona.ciudadano, dispositivo) if persona.ciudadano else []
    return persona, historial


def entregar_a_persona(
    usuario,
    dispositivo,
    edificio,
    dni,
    lineas,
    sexo="",
    nombre="",
    apellido="",
    observacion="",
    uuid_cliente=None,
):
    """Descuenta insumos del stock del edificio y los asienta a nombre de una persona (RN-010-09). Devuelve la operación.

    * Exige ``stock.entregar`` **y** ``ciudadano.ver`` (y ``stock.ver``) sobre el edificio: se mira **acá**, antes de
      consultar a nadie, para que una entrega sin permiso no sirva de consulta al padrón.
    * Institución ``ACTIVO`` y edificio activo (RN-010-14). Los insumos se entregan mientras tengan saldo, estén o no
      activos (RN-010-17). Líneas de RN-010-04.
    * La persona sale de :func:`~programas.services.stock_personas.resolver_persona` (legajo → Registro → alta
      mínima) **antes** de abrir la transacción, porque la consulta al Registro es de red y no se hace con la conexión
      ni los metadata locks tomados. La transacción empieza en los candados; el alta del legajo va **adentro** y
      después de verificar el saldo, y si la entrega falla no queda un legajo huérfano. Una persona con legajo
      fallecido se rechaza (decisión por defecto, como la que responde el Registro).
    * Nunca negativo: se valida contra el saldo leído **bajo candado** (:class:`SaldoInsuficiente`, todo o nada).
    * No se anula una entrega: un error de carga se corrige con un ajuste «Corrección de carga».
    * Idempotente por ``uuid_cliente`` (RN-010-18).
    """

    dispositivo = _dispositivo(dispositivo)
    edificio_id = _edificio_id(edificio)
    _exigir(puede_entregar, usuario, dispositivo, edificio_id)
    uuid_cliente = _como_uuid(uuid_cliente)
    tipo = OperacionStock.Tipo.ENTREGA_PERSONA
    reenvio = partial(_operacion_de_ese_envio, uuid_cliente, usuario, tipo, dispositivo.pk, edificio_id)
    anterior = reenvio()
    if anterior is not None:
        return anterior

    if not lleva_stock(dispositivo):
        raise StockNoHabilitado()
    observacion = _texto(observacion)
    if len(observacion) > OBSERVACION_MAXIMA:
        raise ValidationError({"observacion": OBSERVACION_LARGA})
    validas = _validar_lineas(lineas, solo_activos=False)
    persona = resolver_persona(dni, sexo, nombre, apellido)  # red: fuera de la transacción

    try:
        with transaction.atomic():
            estados, edificios = _preparar([(dispositivo.pk, edificio_id)])
            _exigir_activos(dispositivo.pk, edificio_id, estados, edificios)
            anterior = reenvio()
            if anterior is not None:
                return anterior
            saldos = saldos_bloqueados([(dispositivo.pk, edificio_id, item.pk) for item, _c in validas])
            cambios = [
                (saldos[(dispositivo.pk, edificio_id, item.pk)], -cantidad, MovimientoStock.Tipo.ENTREGA_PERSONA)
                for item, cantidad in validas
            ]
            # Antes del alta: sin saldo no se escribe ni el legajo.
            _exigir_saldo(cambios)
            ciudadano = dar_de_alta(persona)
            return _asentar(
                usuario=usuario,
                tipo=tipo,
                dispositivo_id=dispositivo.pk,
                edificio_id=edificio_id,
                cambios=cambios,
                uuid_cliente=uuid_cliente,
                previa=reenvio,
                ciudadano=ciudadano,
                observacion=observacion,
            )
    except ValidationError as error:
        # La persona ya se resolvió (red): quien muestre el rechazo la reutiliza en vez de consultar al Registro otra vez.
        error.persona = persona
        raise


# ---------------------------------------------------------------------------
# Traspaso entre dos edificios
# ---------------------------------------------------------------------------


def destinos_de_traspaso(usuario, dispositivo, edificio):
    """Los pares ``(Dispositivo, Edificio)`` a los que ``usuario`` puede traspasar desde ``(dispositivo, edificio)``.

    La decisión por defecto (RN-010-11): **solo dentro del alcance de** ``stock.ingresar`` **de quien traspasa** (y
    ``stock.ver``, como toda acción); el administrador del programa, a cualquiera. Son instituciones que llevan
    stock y están ``ACTIVO``, con edificio activo, sin el propio origen. Es el mismo predicado que
    :func:`traspasar` aplica al destino, en una consulta. Exige poder traspasar desde el origen.
    """

    dispositivo = _dispositivo(dispositivo)
    edificio_id = _edificio_id(edificio)
    _exigir(puede_ingresar, usuario, dispositivo, edificio_id)
    pares = Edificio.dispositivos.through.objects.filter(
        dispositivo__tipo__maneja_stock=True, dispositivo__estado=Dispositivo.Estado.ACTIVO, edificio__activo=True
    )
    for capacidad in (CAP_STOCK_VER, CAP_STOCK_INGRESAR):
        pares = pares.filter(dispositivo__in=dispositivos_en_alcance(usuario, capacidad)).filter(
            q_edificios_en_alcance(usuario, capacidad, "dispositivo_id", "edificio_id")
        )
    pares = (
        pares.exclude(dispositivo_id=dispositivo.pk, edificio_id=edificio_id)
        .select_related("dispositivo", "edificio")
        .order_by("dispositivo__nombre", "dispositivo_id", "edificio__nombre", "edificio_id")
    )
    return [(par.dispositivo, par.edificio) for par in pares]


def _destino_de_traspaso(usuario, destino_ids):
    """El ``(Dispositivo, edificio_id)`` de destino, o ``ValidationError({"destino": …})``.

    ``destino_ids`` es ``(dispositivo_id, edificio_id)`` ya interpretado por :func:`traspasar` (el mismo par que ató
    el ``uuid_cliente``): el destino se lee **una** vez, así que la clave de idempotencia y la validación no pueden
    discrepar.

    Un mismo mensaje para el que no existe, el que no está vinculado y el que queda fuera del alcance de
    ``stock.ingresar`` de quien traspasa: la respuesta no cuenta qué instituciones existen fuera de su alcance.
    """

    dispositivo_id, edificio_id = destino_ids
    destino = (
        Dispositivo.objects.select_related("tipo").filter(pk=dispositivo_id).first()
        if dispositivo_id is not None
        else None
    )
    vinculado = (
        edificio_id is not None
        and destino is not None
        and Edificio.dispositivos.through.objects.filter(dispositivo_id=destino.pk, edificio_id=edificio_id).exists()
    )
    if not vinculado or not puede_ingresar(usuario, destino, edificio_id):
        raise ValidationError({"destino": DESTINO_INVALIDO})
    return destino, edificio_id


@transaction.atomic
def traspasar(
    usuario,
    dispositivo,
    edificio,
    destino_dispositivo,
    destino_edificio,
    lineas,
    observacion="",
    uuid_cliente=None,
):
    """Pasa insumos de ``(dispositivo, edificio)`` a ``(destino_dispositivo, destino_edificio)`` en una sola operación.

    Por cada insumo deja **dos** movimientos, ``TRASPASO_SALIDA`` y ``TRASPASO_ENTRADA``, que suman cero (RN-010-11).

    * Exige ``stock.ingresar`` (y ``stock.ver``) sobre el **origen**, y sobre el **destino** (que es lo que limita a
      dónde se puede mandar): un destino fuera de ese alcance, que no existe o no está vinculado es
      ``ValidationError`` en ``destino``, con el mismo texto para los tres.
    * El destino tiene que ser **otro** par; la institución destino lleva stock y está ``ACTIVO`` y el edificio
      destino está activo. El origen puede no estar activo: se permite vaciarlo (RN-010-14).
    * Inmediato: el destino no confirma. Nunca negativo: la salida se valida contra el saldo del origen bajo candado.
    * Candados de los **dos** pares por pk ascendente (Dispositivos, Edificios y Saldos juntos): A→B y B→A a la vez
      piden las mismas filas en el mismo orden y no se matan (RN-010-19).
    * Idempotente por ``uuid_cliente``, que además queda atado a este destino (RN-010-18).
    """

    dispositivo = _dispositivo(dispositivo)
    edificio_id = _edificio_id(edificio)
    _exigir(puede_ingresar, usuario, dispositivo, edificio_id)
    uuid_cliente = _como_uuid(uuid_cliente)
    tipo = OperacionStock.Tipo.TRASPASO
    destino_ids = (_entero(_pk(destino_dispositivo)), _edificio_id(destino_edificio))
    reenvio = partial(_operacion_de_ese_envio, uuid_cliente, usuario, tipo, dispositivo.pk, edificio_id, destino_ids)
    anterior = reenvio()
    if anterior is not None:
        return anterior

    destino, destino_edificio_id = _destino_de_traspaso(usuario, destino_ids)
    if edificio_id is None:
        raise ValidationError({"edificio": EDIFICIO_NO_ES_DE_LA_INSTITUCION})
    if (destino.pk, destino_edificio_id) == (dispositivo.pk, edificio_id):
        raise ValidationError({"destino": TRASPASO_AL_MISMO_LUGAR})
    observacion = _texto(observacion)
    if len(observacion) > OBSERVACION_MAXIMA:
        raise ValidationError({"observacion": OBSERVACION_LARGA})
    validas = _validar_lineas(lineas, solo_activos=False)

    estados, edificios = _preparar([(dispositivo.pk, edificio_id), (destino.pk, destino_edificio_id)])
    if estados[destino.pk] != Dispositivo.Estado.ACTIVO or not edificios[destino_edificio_id]:
        raise StockNoHabilitado(DESTINO_INACTIVO)
    anterior = reenvio()
    if anterior is not None:
        return anterior
    origen_de = {item.pk: (dispositivo.pk, edificio_id, item.pk) for item, _c in validas}
    destino_de = {item.pk: (destino.pk, destino_edificio_id, item.pk) for item, _c in validas}
    saldos = saldos_bloqueados([*origen_de.values(), *destino_de.values()])
    cambios = []
    for item, cantidad in validas:
        cambios.append((saldos[origen_de[item.pk]], -cantidad, MovimientoStock.Tipo.TRASPASO_SALIDA))
        cambios.append((saldos[destino_de[item.pk]], cantidad, MovimientoStock.Tipo.TRASPASO_ENTRADA))
    return _asentar(
        usuario=usuario,
        tipo=tipo,
        dispositivo_id=dispositivo.pk,
        edificio_id=edificio_id,
        cambios=cambios,
        uuid_cliente=uuid_cliente,
        previa=reenvio,
        destino_dispositivo_id=destino.pk,
        destino_edificio_id=destino_edificio_id,
        observacion=observacion,
    )
