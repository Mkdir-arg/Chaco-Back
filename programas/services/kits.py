"""Entregas de kits de Emergencia: armar, marcar en camino, cancelar, recibir y observar (etapa 4).

**Una entrega, una recepción.** Antes (RN-4.6) no había stock: las cantidades eran lo que decía un remito. El
módulo Stock (análisis 010, RN-010-06) **revirtió** esa regla: cuando el tipo de la institución lleva stock, lo
recibido se suma al stock de su edificio, dentro de la misma transacción que la recepción
(:func:`recibir_entrega` → ``stock.sumar_recepcion_de_kit``). Una institución que no lleva stock se comporta como
siempre. Este módulo **solo suma**: nunca descuenta, y ``stock`` es quien guarda saldos y movimientos.

**Toda regla de la entrega vive acá.** La mesa (E4, E5), la recepción web dentro del
dispositivo y la API de la app (M3) llaman a estas mismas funciones (RU-2). Lo que se lee
—listado, detalle, pendientes de un dispositivo— está en ``programas.selectors.kits``.

Cómo está hecha cada función
----------------------------

1. Exige la capacidad, sin confiar en que la vista se haya acordado:

   * la mesa (crear, marcar en camino, cancelar, observar) — ``emergencia.operar`` o
     ``emergencia.supervisar`` **en el programa EMERGENCIA**;
   * la guardia (recibir) — ``emergencia.recibir_kit`` evaluada con
     ``puede_operar_dispositivo`` sobre **el dispositivo de la entrega** (RU-8, hallazgo H3
     del plan): la capacidad en el programa Dispositivos **y** integrar el Equipo de esa
     institución. Tenerla en otro dispositivo no alcanza (RN-4.8).

2. Abre una transacción y **bloquea la fila de la entrega** (``select_for_update``, sin
   JOIN) antes de mirar nada. Lo que decide se lee de la fila bloqueada, no del objeto que
   llegó por parámetro.
3. Si la entrega ya no está en el estado que la acción necesita, levanta
   :class:`EstadoCambioEntrega` con el estado actual: la mesa canceló mientras la guardia
   cargaba, o la otra guardia la recibió desde el backoffice. La vista vuelve a la pantalla
   con el mensaje y la API contesta **409** ``{detail, estado_actual}``.
4. Deja una fila de ``TrazaEntrega`` en la misma transacción (RN-4.9, RU-15).

Devuelven **la fila recién leída y bloqueada**, no el objeto que recibieron.

El orden de los candados
------------------------

Una entrega no toca casos, derivaciones ni plazas, así que su orden es propio y corto::

    entrega original  ·  dispositivo destino  ·  edificio  ·  numerador (serie K)  ·  entrega nueva

``crear_entrega`` toma ese orden (la entrega original solo si repone; el edificio, el elegido, el único o el de la
original). La entrega va antes que el dispositivo porque cancelar una reposición bloquea original → reposición y
recibirla bloquea reposición → dispositivo (la bitácora): con el dispositivo primero, crear, cancelar y recibir cerraban
un ciclo de tres. El dispositivo va antes que el edificio porque «inactivar» y «desvincular» edificio van
Dispositivo → Edificio, y el ``INSERT`` pide un candado compartido sobre el dispositivo (FK). Las demás transiciones
bloquean solo la entrega (recibir sigue con el dispositivo). Ninguna toma el numerador y *después* una entrega, así que
no hay orden que cruzar.

``recibir_entrega`` sigue el orden de RN-010-19 (entrega → Dispositivo → Edificio → SaldoStock): bloquea la entrega, si
hay que elegir edificio toma el Dispositivo y después el Edificio antes de escribir, y ``stock`` toma los saldos al
final. ``stock`` importa de este módulo, así que acá se lo importa **dentro** de la función (import circular).

La carrera cancelar / recibir se resuelve sobre la misma fila: gana quien llega primero al
candado y el otro lee el estado nuevo y recibe :class:`EstadoCambioEntrega`. Las carreras
contra el motor real están en ``programas.tests.test_emergencia_kits`` con ``@tag("mysql")``
(en SQLite ``select_for_update`` es un no-op).
"""

import uuid as _uuid
from pathlib import Path

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from core.archivos import anotar_archivo_escrito, archivos_atomicos
from core.db import q_uuid_en_texto
from core.validators import ADJUNTO_MAX_BYTES, MENSAJE_ADJUNTO_TAMANIO, firma_coincide
from programas.models import (
    Dispositivo,
    EntradaBitacora,
    EntregaKit,
    LineaEntrega,
    NumeradorEmergencia,
    TipoKit,
    TrazaEntrega,
)
from programas.services.bitacora import anotar_novedad_automatica
from programas.services.bitacora_detalle import plural
from programas.services.dispositivos import alcance_de_edificios, puede_operar_edificio
from programas.services.emergencia import EstadoCambio, UuidEnUso, siguiente_correlativo
from programas.services.emergencia_comun import _hora
from programas.services.emergencia_programa import CAP_RECIBIR_KIT, puede_operar_la_mesa

Estado = EntregaKit.Estado
Accion = TrazaEntrega.Accion

#: Cómo se muestra cada estado de la entrega: texto y tono del badge. Es la **única**
#: tabla: la leen el listado, el detalle, la recepción web y la app.
ESTADOS_VISIBLES_ENTREGA = {
    Estado.PREPARADA: ("Preparada", "gray"),
    Estado.EN_CAMINO: ("En camino", "info"),
    Estado.RECIBIDA: ("Recibida", "success"),
    Estado.RECIBIDA_CON_DIFERENCIAS: ("Recibida con diferencias", "warning"),
    Estado.CANCELADA: ("Cancelada", "gray"),
}

#: El remito llega como lo saca la cámara de la app, que convierte y comprime (RN-4.3).
REMITO_EXTENSIONES = (".jpg", ".jpeg")
#: Tope de una cantidad: el de la columna (`PositiveIntegerField`).
CANTIDAD_MAXIMA = 2_147_483_647
MOTIVO_MAXIMO = EntregaKit._meta.get_field("motivo_cancelacion").max_length
TRANSPORTE_MAXIMO = EntregaKit._meta.get_field("transporte").max_length

SIN_PERMISO_DE_MESA = "No tenés permiso para armar entregas de kits: es tarea de la mesa de Emergencia."
SIN_PERMISO_DE_RECIBIR = "No formás parte del equipo que recibe los kits de este dispositivo."
SIN_LINEAS = "La entrega necesita al menos un ítem con cantidad."
ITEM_REPETIDO = "Cada ítem va una sola vez por entrega: sumá las cantidades en una sola línea."
CANTIDAD_INVALIDA = "Sacá el ítem o poné una cantidad: tiene que ser un número entero mayor que cero."
ITEM_NO_DISPONIBLE = "Ese ítem ya no está en el catálogo activo. Recargá la pantalla y elegí otro."
DISPOSITIVO_NO_ACTIVO = "Solo se envían kits a un dispositivo activo. Elegí otro destino."
REPOSICION_INVALIDA = "Solo se repone una entrega que ese mismo dispositivo recibió con diferencias."
REPOSICION_YA_HECHA = "La diferencia de la entrega {numero} ya está cerrada ({como}). Reponer se hace una sola vez."
FALTA_EL_MOTIVO_DE_LA_DIFERENCIA = "Indicá por qué se acepta la diferencia."
MOTIVO_DE_LA_DIFERENCIA_LARGO = "El motivo no puede tener más de {maximo} caracteres."
EDIFICIO_INACTIVO = (
    "El edificio {nombre} está inactivo y no recibe entregas nuevas. "
    "Reactivalo o, si el dispositivo tiene otro edificio, elegí ese."
)
SIN_EDIFICIO_PARA_EL_STOCK = (
    "{nombre} lleva stock y no tiene un edificio activo: vinculale uno antes de enviarle kits, "
    "porque lo que reciba se suma al stock de su edificio."
)
ELEGI_EL_EDIFICIO_DE_LA_RECEPCION = "Elegí en qué edificio se recibe: lo recibido se suma al stock de ese edificio."
EDIFICIO_NO_ES_DEL_DISPOSITIVO = "El edificio tiene que ser uno de los edificios vinculados a este dispositivo."
SIN_DIFERENCIA_QUE_CERRAR = "La entrega {numero} no tiene una diferencia para cerrar."
DIFERENCIA_YA_CERRADA = "La diferencia de la entrega {numero} ya está cerrada ({como}). Recargá la pantalla."
FALTA_EL_MOTIVO = "Indicá por qué se cancela la entrega."
MOTIVO_LARGO = f"El motivo no puede tener más de {MOTIVO_MAXIMO} caracteres."
TRANSPORTE_LARGO = f"El transporte no puede tener más de {TRANSPORTE_MAXIMO} caracteres."
HORA_FUTURA = "La hora de salida no puede ser posterior a este momento."
HORA_ANTERIOR_A_LA_ENTREGA = "La hora de salida no puede ser anterior a la hora en que se armó la entrega."
FALTA_EL_REMITO = "Falta la foto del remito."
REMITO_NO_ES_JPEG = "La foto del remito tiene que llegar en JPEG."
FALTAN_CANTIDADES = "Indicá cuánto llegó de cada ítem, aunque sea cero. Falta: {items}."
CANTIDAD_RECIBIDA_INVALIDA = "La cantidad recibida de {item} tiene que ser un número entero, cero o más."
ITEM_AJENO = "Hay cantidades de ítems que no son de esta entrega. Recargá la pantalla."
UUID_INVALIDO = "El identificador del envío no es válido."
UUID_EN_USO = "Ese identificador de envío ya se usó en otra recepción."
ARMADO_EN_USO = "Ese armado ya lo creó otra persona: empezá una entrega nueva desde «Armar entrega»."
FALTA_LA_OBSERVACION = "Escribí la observación."
SIN_MARCA_DE_SALIDA = "Recibida sin marca de salida"
YA_EN_CAMINO = "La entrega {numero} ya está en camino. Recargá la pantalla."
TODAVIA_NO_RECIBIDA = (
    "La entrega {numero} todavía no fue recibida: la observación de la mesa se carga después de la recepción."
)


class EstadoCambioEntrega(EstadoCambio):
    """La entrega ya no está en el estado que la acción necesitaba: alguien se adelantó.

    Es un :class:`~programas.services.emergencia.EstadoCambio` —quien atrapa aquel también
    atrapa este— con la entrega tal como quedó en ``entrega``. La API la traduce a **409**
    con ``{"detail": mensaje, "estado_actual": estado_actual}``.
    """

    def __init__(self, mensaje, *, entrega):
        self.entrega = entrega
        super().__init__(mensaje, estado_actual=entrega.estado)


# ---------------------------------------------------------------------------
# Piezas internas
# ---------------------------------------------------------------------------


def _nombre_de(usuario):
    if usuario is None:
        return "otra persona"
    return usuario.get_full_name().strip() or usuario.get_username()


def estado_visible_de_entrega(entrega):
    """``(texto, tono)`` del badge del estado. El template lo dibuja; no lo decide."""

    return ESTADOS_VISIBLES_ENTREGA.get(entrega.estado, (entrega.get_estado_display(), "gray"))


def _exigir_mesa(usuario):
    if not puede_operar_la_mesa(usuario):
        raise PermissionDenied(SIN_PERMISO_DE_MESA)


def puede_recibir(usuario, entrega):
    """¿``usuario`` recibe los kits del dispositivo de ``entrega``? La regla de RN-4.8, una sola vez."""

    # Con alcance Edificios, solo las de sus edificios; la que no tiene edificio, solo con alcance Institución.
    return puede_operar_edificio(usuario, entrega.dispositivo, entrega.edificio_id, CAP_RECIBIR_KIT)


def _bloquear_entrega(entrega):
    """La fila de la entrega con ``FOR UPDATE``, recién leída. Sin JOIN: no bloquea nada más."""

    return EntregaKit.objects.select_for_update().get(pk=getattr(entrega, "pk", entrega))


def mensaje_de_estado(entrega):
    """Qué le pasó a una entrega que ya no está abierta, y qué hacer (RU-20)."""

    if entrega.estado == Estado.CANCELADA:
        cancelacion = (
            TrazaEntrega.objects.filter(entrega=entrega, accion=Accion.CANCELADA).order_by("-creado_en", "-id").first()
        )
        cuando = f" a las {_hora(cancelacion.creado_en)}" if cancelacion else ""
        return f"Entrega {entrega.numero} cancelada por la mesa{cuando}. Ya no se puede recibir."
    if entrega.estado in EntregaKit.ESTADOS_RECIBIDOS:
        quien = _nombre_de(entrega.recibida_por) if entrega.recibida_por_id else "otra persona"
        cuando = f" a las {_hora(entrega.recibida_en)}" if entrega.recibida_en else ""
        return f"La entrega {entrega.numero} ya la recibió {quien}{cuando}. Recargá la pantalla."
    return f"La entrega {entrega.numero} cambió de estado. Recargá la pantalla."


def _exigir_estado(entrega, *estados, si_sigue_abierta=""):
    """La entrega bloqueada tiene que estar en uno de ``estados``; si no, :class:`EstadoCambioEntrega`.

    Recibida o cancelada, el mensaje es el de :func:`mensaje_de_estado`. ``si_sigue_abierta``
    es lo que se dice cuando la acción no corresponde a una entrega que todavía está abierta.
    """

    if entrega.estado in estados:
        return
    mensaje = si_sigue_abierta if entrega.abierta and si_sigue_abierta else mensaje_de_estado(entrega)
    raise EstadoCambioEntrega(mensaje, entrega=entrega)


def _trazar(entrega, usuario, accion, *, estado_anterior, detalle=""):
    """Una fila de ``TrazaEntrega``: aditiva e inmutable, en la transacción de la acción."""

    return TrazaEntrega.objects.create(
        entrega=entrega,
        usuario=usuario,
        accion=accion,
        estado_anterior=estado_anterior,
        estado_nuevo=entrega.estado,
        detalle=detalle,
    )


def _como_uuid(valor):
    if valor in (None, ""):
        return None
    if isinstance(valor, _uuid.UUID):
        return valor
    try:
        return _uuid.UUID(str(valor))
    except (AttributeError, TypeError, ValueError):
        raise ValidationError({"uuid_cliente": UUID_INVALIDO}) from None


def _entero(valor):
    """``valor`` como entero, o ``None`` si no lo es. Un booleano o un decimal no son una cantidad."""

    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor
    if isinstance(valor, str) and valor.strip().lstrip("+-").isdecimal():
        return int(valor.strip())
    return None


def siguiente_numero_de_entrega(momento=None):
    """El próximo «2026-K-000031»: el contador de la serie ``K`` con el formato de las entregas."""

    return EntregaKit.formatear_numero(*siguiente_correlativo(NumeradorEmergencia.Serie.KITS, momento))


# ---------------------------------------------------------------------------
# Crear
# ---------------------------------------------------------------------------


def _pares_de(lineas):
    """``lineas`` como lista de ``(item_id, cantidad)``, sin validar todavía.

    Se acepta un dict ``{item: cantidad}`` o un iterable de pares ``(item, cantidad)`` o de
    dicts ``{"item": …, "cantidad": …}``; ``item`` es un ``TipoKit`` o su id.
    """

    if isinstance(lineas, dict):
        lineas = lineas.items()
    pares = []
    for linea in lineas or ():
        item, cantidad = (linea.get("item"), linea.get("cantidad")) if isinstance(linea, dict) else linea
        pares.append((getattr(item, "pk", item), cantidad))
    return pares


def _validar_lineas(lineas):
    """RN-4.1: al menos una, ítems activos, sin repetir, cantidades enteras > 0. Devuelve ``[(TipoKit, int)]``."""

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
    # Una consulta: el ítem tiene que existir y estar activo **ahora**, no cuando se abrió la pantalla.
    activos = TipoKit.objects.filter(pk__in=ids, activo=True).in_bulk()
    if len(activos) != len(ids):
        raise ValidationError({"lineas": ITEM_NO_DISPONIBLE})
    return [(activos[item_id], cantidad) for item_id, cantidad in zip(ids, cantidades, strict=True)]


def _como_se_cerro(entrega):
    """«repuesta» o «aceptada»: cómo quedó cerrada la diferencia de ``entrega``."""

    return EntregaKit.CierreDiferencia(entrega.cierre_diferencia).label.lower()


def _bloquear_original(repone_a):
    """La fila de la entrega que se repone, con candado, o ``None``. Va **antes** que el destino (ver el orden de
    candados): se toma por pk y recién después se valida que sea de ese destino."""

    if repone_a is None:
        return None
    return EntregaKit.objects.select_for_update().filter(pk=getattr(repone_a, "pk", repone_a)).first()


def _validar_reposicion(repone_a, original, dispositivo):
    """HU-4.5: se repone una entrega que **ese** dispositivo recibió con diferencias, y **una sola vez**.

    ``original`` es la fila ya bloqueada por :func:`_bloquear_original` y se lee de ahí si ya se cerró: dos pedidos a
    la vez de «Reponer» no arman dos reposiciones, el segundo ve el cierre del primero (Cambio 586).
    """

    if repone_a is None:
        return None
    if (
        original is None
        or original.dispositivo_id != dispositivo.pk
        or original.estado != Estado.RECIBIDA_CON_DIFERENCIAS
    ):
        raise ValidationError({"repone_a": REPOSICION_INVALIDA})
    if original.cierre_diferencia is not None:
        raise _ReposicionYaHecha(
            {"repone_a": REPOSICION_YA_HECHA.format(numero=original.numero, como=_como_se_cerro(original))}
        )
    return original


class _ReposicionYaHecha(ValidationError):
    """La entrega a reponer ya tiene su diferencia cerrada. ``crear_entrega`` la distingue del resto: si la cerró **este
    mismo armado** (doble envío a la vez), devuelve esa entrega en vez de rechazar."""


def _cerrar_como_repuesta(original, reposicion, usuario, ahora):
    """Deja ``original`` como repuesta por ``reposicion``, con su traza. ``original`` viene bloqueada."""

    original.cierre_diferencia = EntregaKit.CierreDiferencia.REPUESTA
    original.cierre_diferencia_en = ahora
    original.cierre_diferencia_por = usuario
    original.save(update_fields=["cierre_diferencia", "cierre_diferencia_en", "cierre_diferencia_por", "modificado"])
    _trazar(
        original,
        usuario,
        Accion.DIFERENCIA_REPUESTA,
        estado_anterior=original.estado,
        detalle=f"Repuesta con la entrega {reposicion.numero}",
    )


def _edificio_de_la_entrega(destino, edificio, original):
    """El edificio de una entrega nueva (Cambio 523): el pedido, el de la que repone, o el único del destino.

    Un edificio pedido tiene que estar vinculado al destino. Con varios edificios y sin una entrega que reponer
    de la que sacarlo, elegirlo es obligatorio (decisión del PM, 21-nov-2026); con uno solo queda fijo, y un
    destino sin edificios vinculados la deja sin edificio.
    """

    from programas.models import Edificio

    vinculados = Edificio.objects.filter(dispositivos=destino)
    if edificio is not None:
        pk = getattr(edificio, "pk", edificio)
        if not vinculados.filter(pk=pk).exists():
            raise ValidationError({"edificio": "El edificio tiene que estar vinculado al dispositivo destino."})
        return _exigir_edificio_activo(pk)
    if original is not None and original.edificio_id is not None:
        if suma_al_stock(destino) and not vinculados.filter(pk=original.edificio_id).exists():
            # El edificio de la original se desvinculó después: con stock, recibir la reposición exige un edificio
            # vinculado (`stock._preparar`), así que se rechaza acá y no al recibir.
            raise ValidationError({"edificio": EDIFICIO_NO_ES_DEL_DISPOSITIVO})
        return _exigir_edificio_activo(original.edificio_id)
    activos = list(vinculados.filter(activo=True).values_list("pk", flat=True)[:2])
    if len(activos) > 1:
        raise ValidationError({"edificio": "Elegí el edificio al que va la entrega."})
    if activos:
        return _exigir_edificio_activo(activos[0])
    inactivo = vinculados.order_by("nombre").first()
    if inactivo is not None:
        # Todos sus edificios están inactivos: no se la deja sin edificio, se pide resolver el estado.
        raise ValidationError({"edificio": EDIFICIO_INACTIVO.format(nombre=inactivo.nombre)})
    return None


def _exigir_edificio_activo(pk):
    """Un edificio inactivo no recibe entregas nuevas (Cambio 586). Lo relee **con candado**, dentro de la transacción.

    «Inactivar edificio» cuenta las entregas por recibir bajo el candado del mismo edificio: o la entrega entra antes
    y la inactivación la ve, o la inactivación entra antes y acá se rechaza. Mismo patrón que
    ``plazas._exigir_edificio_del_dispositivo``.
    """

    from programas.models import Edificio

    bloqueado = Edificio.objects.select_for_update().filter(pk=pk).first()
    if bloqueado is None or not bloqueado.activo:
        nombre = bloqueado.nombre if bloqueado is not None else "elegido"
        raise ValidationError({"edificio": EDIFICIO_INACTIVO.format(nombre=nombre)})
    return bloqueado.pk


def _entrega_de_ese_armado(uuid_cliente, usuario):
    """La entrega que ya armó ese ``uuid_cliente`` (con ``ya_existia``) o ``None``. Ajena: :class:`UuidEnUso`."""

    existente = EntregaKit.objects.filter(q_uuid_en_texto("uuid_cliente", uuid_cliente)).first()
    if existente is None:
        return None
    if existente.armada_por_id != usuario.pk:
        # El mismo identificador en manos de otro no es un reenvío: no se le devuelve una entrega ajena.
        raise UuidEnUso(ARMADO_EN_USO)
    existente.ya_existia = True
    return existente


@transaction.atomic
def crear_entrega(
    usuario, dispositivo, lineas, observacion="", repone_a=None, edificio=None, uuid_cliente=None, enviar=False
):
    """Arma una entrega ``PREPARADA`` con sus líneas (HU-4.1). **La única función que crea entregas.**

    ``enviar`` (Cambio 586): crea y marca en camino en **la misma transacción** («Crear y enviar»); sin él queda
    ``PREPARADA``. Una entrega que ya existía por su ``uuid_cliente`` se devuelve tal cual, sin enviarla.

    * Exige trabajar en la mesa (``emergencia.operar`` o ``supervisar``).
    * **RN-4.2** — el destino tiene que estar ``ACTIVO`` (cualquier tipo). Se relee de la
      base: el estado que cuenta es el de ahora, no el de la pantalla.
    * **RN-4.1** — ``lineas`` (ver :func:`_pares_de`): al menos una, ítems del catálogo
      **activos**, cada ítem una sola vez y cantidades enteras > 0. ``ValidationError`` en
      la clave ``lineas``.
    * La ``unidad`` de cada línea se **copia** del catálogo (04 §10) y ``cantidad_recibida``
      nace ``NULL``.
    * ``repone_a`` (HU-4.5): la entrega que esta repone; tiene que ser del mismo dispositivo
      y estar ``RECIBIDA_CON_DIFERENCIAS`` **sin cerrar**. Se bloquea su fila y queda como ``REPUESTA`` en la misma
      transacción: reponer es una sola vez por entrega (Cambio 586).
    * ``edificio`` (Cambio 523): ver :func:`_edificio_de_la_entrega`; sin él sale de la entrega que repone o del
      único edificio del destino; con varios y sin de dónde sacarlo es obligatorio.
    * Numera con el contador de la serie ``K`` («2026-K-000031») y deja la primera traza.
    * **Idempotencia** (Cambio 535): ``uuid_cliente`` es el identificador que nació al abrir «Armar
      entrega». Si ya armó una entrega de este usuario, la devuelve tal cual, con
      ``entrega.ya_existia = True``, sin crear otra ni dejar traza: volver atrás en el navegador y
      reenviar no duplica. Usado por otro usuario, :class:`UuidEnUso`. Dos envíos a la vez los
      ordena el UNIQUE de la columna: el segundo vuelve a leer y devuelve la del primero.
    """

    _exigir_mesa(usuario)
    uuid_cliente = _como_uuid(uuid_cliente)
    if uuid_cliente is not None:
        existente = _entrega_de_ese_armado(uuid_cliente, usuario)
        if existente is not None:
            return existente
    # La entrega que se repone va primero, con candado y por pk: cancelar una reposición toma original → reposición y
    # recibirla toma reposición → Dispositivo (bitácora); tomar el Dispositivo antes que la original cerraba un ciclo.
    # Después el destino —«inactivar» y «desvincular» edificio van Dispositivo → Edificio y el INSERT pide un candado
    # compartido sobre el Dispositivo (FK)— y recién ahí se valida que la original sea de ese destino.
    bloqueada_original = _bloquear_original(repone_a)
    destino = Dispositivo.objects.select_for_update().filter(pk=getattr(dispositivo, "pk", dispositivo)).first()
    if destino is None or destino.estado != Dispositivo.Estado.ACTIVO:
        raise ValidationError({"dispositivo": DISPOSITIVO_NO_ACTIVO})
    validas = _validar_lineas(lineas)
    try:
        original = _validar_reposicion(repone_a, bloqueada_original, destino)
    except _ReposicionYaHecha:
        # Doble envío a la vez del mismo armado: el primero ya repuso y su fila existe. Bajo el candado de la original
        # se vuelve a mirar antes de rechazar, así el segundo recibe la entrega del primero y no un error.
        existente = _entrega_de_ese_armado(uuid_cliente, usuario) if uuid_cliente is not None else None
        if existente is None:
            raise
        return existente
    edificio_id = _edificio_de_la_entrega(destino, edificio, original)
    if edificio_id is None and suma_al_stock(destino):
        # RN-010-07: lo que reciba se suma al stock de un edificio, así que no se envía a una institución con stock que
        # no tiene a cuál sumarlo. Se pide vincular uno (decisión 10).
        raise ValidationError({"edificio": SIN_EDIFICIO_PARA_EL_STOCK.format(nombre=destino.nombre)})

    ahora = timezone.now()
    try:
        # Anidada: si el UNIQUE de `uuid_cliente` salta —el mismo armado llegó dos veces a la vez—,
        # se deshace este alta y la transacción de afuera sigue sana para devolver la primera.
        with transaction.atomic():
            entrega = EntregaKit.objects.create(
                numero=siguiente_numero_de_entrega(ahora),
                dispositivo=destino,
                edificio_id=edificio_id,
                estado=Estado.PREPARADA,
                armada_por=usuario,
                observacion_mesa=(observacion or "").strip(),
                repone_a=original,
                uuid_cliente=uuid_cliente,
            )
    except IntegrityError:
        existente = _entrega_de_ese_armado(uuid_cliente, usuario) if uuid_cliente is not None else None
        if existente is None:
            raise
        return existente
    LineaEntrega.objects.bulk_create(
        [
            LineaEntrega(entrega=entrega, item=item, nombre=item.nombre, unidad=item.unidad, cantidad_enviada=cantidad)
            for item, cantidad in validas
        ]
    )
    cuantos = "1 ítem" if len(validas) == 1 else f"{len(validas)} ítems"
    detalle = f"{cuantos} para {destino.nombre}"
    if original is not None:
        detalle = f"{detalle} · repone a la entrega {original.numero}"
    if entrega.observacion_mesa:
        # `observar_recepcion` reemplaza el campo: la nota original queda acá.
        detalle = f"{detalle} · nota para el dispositivo: {entrega.observacion_mesa}"
    _trazar(entrega, usuario, Accion.CREADA, estado_anterior="", detalle=detalle)
    if original is not None:
        _cerrar_como_repuesta(original, entrega, usuario, ahora)
    if enviar:
        entrega = marcar_en_camino(entrega, usuario)
    return entrega


# ---------------------------------------------------------------------------
# Marcar en camino y cancelar (la mesa)
# ---------------------------------------------------------------------------


@transaction.atomic
def marcar_en_camino(entrega, usuario, transporte="", hora=None):
    """``PREPARADA`` → ``EN_CAMINO`` (HU-4.2). ``despachada_en`` es ``hora`` o, sin ella, ahora.

    ``transporte`` (quién la lleva, patente…) y ``hora`` son opcionales; una hora de salida
    futura, o anterior a la que se armó la entrega, es un ``ValidationError``.
    """

    _exigir_mesa(usuario)
    transporte = (transporte or "").strip()
    if len(transporte) > TRANSPORTE_MAXIMO:
        raise ValidationError({"transporte": TRANSPORTE_LARGO})
    ahora = timezone.now()
    if hora is not None and hora > ahora:
        raise ValidationError({"hora": HORA_FUTURA})

    bloqueada = _bloquear_entrega(entrega)
    _exigir_estado(bloqueada, Estado.PREPARADA, si_sigue_abierta=YA_EN_CAMINO.format(numero=bloqueada.numero))
    # `datetime-local` no lleva segundos y `creado` sí: salir en el mismo minuto en que se armó es válido.
    if hora is not None and hora < bloqueada.creado.replace(second=0, microsecond=0):
        raise ValidationError({"hora": HORA_ANTERIOR_A_LA_ENTREGA})
    bloqueada.estado = Estado.EN_CAMINO
    bloqueada.despachada_en = hora or ahora
    bloqueada.transporte = transporte
    bloqueada.save(update_fields=["estado", "despachada_en", "transporte", "modificado"])
    detalle = f"Salió a las {_hora(bloqueada.despachada_en)}"
    if transporte:
        detalle = f"{detalle} · {transporte}"
    _trazar(bloqueada, usuario, Accion.EN_CAMINO, estado_anterior=Estado.PREPARADA, detalle=detalle)
    return bloqueada


@transaction.atomic
def cancelar_entrega(entrega, usuario, motivo):
    """``PREPARADA`` o ``EN_CAMINO`` → ``CANCELADA``, con motivo obligatorio (RU-22).

    Una entrega ya recibida o ya cancelada no se cancela: :class:`EstadoCambioEntrega`. Si era la única reposición viva
    de una entrega recibida con diferencias, esa entrega vuelve a «con diferencia sin cerrar» (Cambio 586).
    """

    _exigir_mesa(usuario)
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValidationError({"motivo": FALTA_EL_MOTIVO})
    if len(motivo) > MOTIVO_MAXIMO:
        raise ValidationError({"motivo": MOTIVO_LARGO})

    # Primero la original (si esta repone a otra), después la entrega: el mismo orden de candados que al reponer.
    original_bloqueada = (
        EntregaKit.objects.select_for_update().filter(pk=entrega.repone_a_id).first() if entrega.repone_a_id else None
    )
    bloqueada = _bloquear_entrega(entrega)
    _exigir_estado(bloqueada, *EntregaKit.ESTADOS_ABIERTOS)
    anterior = bloqueada.estado
    bloqueada.estado = Estado.CANCELADA
    bloqueada.motivo_cancelacion = motivo
    bloqueada.save(update_fields=["estado", "motivo_cancelacion", "modificado"])
    _trazar(bloqueada, usuario, Accion.CANCELADA, estado_anterior=anterior, detalle=motivo)
    if original_bloqueada is not None:
        _reabrir_si_no_queda_reposicion(original_bloqueada, bloqueada, usuario)
    return bloqueada


def _reabrir_si_no_queda_reposicion(original, cancelada, usuario):
    """Cancelar la única reposición viva devuelve la original a «con diferencia sin cerrar» (Cambio 586).

    «Una sola vez» es una sola reposición **viva** (preparada, en camino o recibida) por entrega: si la que se
    cancela era la última, no se repuso nada y la diferencia sigue abierta, así que se puede reponer de nuevo o
    aceptar. Una original ya cerrada de otra manera (aceptada) no se toca. ``original`` viene bloqueada.
    """

    if (
        original.estado != Estado.RECIBIDA_CON_DIFERENCIAS
        or original.cierre_diferencia != EntregaKit.CierreDiferencia.REPUESTA
    ):
        return
    if EntregaKit.objects.filter(repone_a=original).exclude(pk=cancelada.pk).exclude(estado=Estado.CANCELADA).exists():
        return
    original.cierre_diferencia = None
    original.cierre_diferencia_en = None
    original.cierre_diferencia_por = None
    original.save(update_fields=["cierre_diferencia", "cierre_diferencia_en", "cierre_diferencia_por", "modificado"])
    _trazar(
        original,
        usuario,
        Accion.DIFERENCIA_REABIERTA,
        estado_anterior=original.estado,
        detalle=f"Se canceló la entrega {cancelada.numero} que la reponía: la diferencia sigue sin cerrar",
    )


# ---------------------------------------------------------------------------
# Recibir (el dispositivo)
# ---------------------------------------------------------------------------


def validar_remito(remito):
    """RN-4.3: la foto del remito es obligatoria, JPEG de verdad y de hasta 5 MB."""

    if not remito:
        raise ValidationError({"remito": FALTA_EL_REMITO})
    extension = Path((getattr(remito, "name", "") or "").lower()).suffix
    if extension not in REMITO_EXTENSIONES or not firma_coincide(remito, extension):
        raise ValidationError({"remito": REMITO_NO_ES_JPEG})
    if (getattr(remito, "size", 0) or 0) > ADJUNTO_MAX_BYTES:
        raise ValidationError({"remito": MENSAJE_ADJUNTO_TAMANIO})
    return remito


def _validar_cantidades(lineas, cantidades):
    """RN-4.3: una cantidad entera ≥ 0 para **cada** línea, y ninguna de un ítem ajeno.

    ``cantidades`` es ``{item_id: cantidad}``. Devuelve ``{item_id: int}``.
    """

    recibidas = {}
    for item_id, cantidad in (cantidades or {}).items():
        clave = _entero(getattr(item_id, "pk", item_id))
        if clave is None:
            raise ValidationError({"cantidades": ITEM_AJENO})
        recibidas[clave] = cantidad
    de_la_entrega = {linea.item_id: linea for linea in lineas}
    if set(recibidas) - set(de_la_entrega):
        raise ValidationError({"cantidades": ITEM_AJENO})
    faltan = [linea.nombre_visible for linea in lineas if recibidas.get(linea.item_id) in (None, "")]
    if faltan:
        raise ValidationError({"cantidades": FALTAN_CANTIDADES.format(items=", ".join(faltan))})
    limpias = {}
    for item_id, cantidad in recibidas.items():
        entero = _entero(cantidad)
        if entero is None or not 0 <= entero <= CANTIDAD_MAXIMA:
            raise ValidationError(
                {"cantidades": CANTIDAD_RECIBIDA_INVALIDA.format(item=de_la_entrega[item_id].nombre_visible)}
            )
        limpias[item_id] = entero
    return limpias


def _exigir_uuid_libre(uuid_cliente, entrega):
    """El identificador de un envío es de **una** recepción: usado en otra entrega, se rechaza."""

    en_otra = EntregaKit.objects.filter(q_uuid_en_texto("uuid_cliente_recepcion", uuid_cliente)).exclude(pk=entrega.pk)
    if en_otra.exists():
        raise UuidEnUso(UUID_EN_USO)


def suma_al_stock(dispositivo):
    """Si lo que se recibe en ``dispositivo`` se suma al stock (RN-010-06): el tipo de la institución lleva stock.

    Es el predicado de ``stock.lleva_stock`` (importado acá y no arriba: ``stock`` importa de este módulo); los demás
    lugares de ``kits`` lo piden por esta función y no repiten la regla.
    """

    from programas.services import stock

    return stock.lleva_stock(dispositivo)


def edificios_para_recibir(usuario, entrega):
    """Entre qué edificios elige quien recibe ``entrega``, o ``[]`` si no hay nada que elegir (RN-010-07).

    Solo se elige cuando la entrega **no tiene edificio** (anteriores al Cambio 523) y la institución lleva stock: los
    edificios activos vinculados a la institución que alcanza ``usuario`` con ``emergencia.recibir_kit``. Es la misma
    regla que aplica :func:`recibir_entrega`; la pantalla solo la dibuja.
    """

    from programas.models import Edificio

    if entrega.edificio_id is not None or not suma_al_stock(entrega.dispositivo):
        return []
    alcance = alcance_de_edificios(usuario, entrega.dispositivo, CAP_RECIBIR_KIT)
    activos = Edificio.objects.filter(dispositivos=entrega.dispositivo, activo=True).order_by("nombre")
    return [edificio for edificio in activos if alcance.permite(edificio.pk)]


def _edificio_de_la_recepcion(usuario, entrega, edificio):
    """El edificio en que se recibe una entrega que no lo tenía, en una institución que lleva stock (RN-010-07).

    Lo elige quien recibe: tiene que estar vinculado a la institución, activo y dentro del alcance de
    ``emergencia.recibir_kit``. Toma los candados en el orden del módulo (entrega ya tomada → Dispositivo → Edificio) y
    **relee** el vínculo y el estado bajo ellos: «Inactivar» y «Desvincular» edificio piden ese mismo orden. Un edificio
    ajeno o fuera de alcance da el mismo rechazo que uno inexistente. Devuelve el pk.
    """

    from programas.models import Edificio

    pk = _entero(getattr(edificio, "pk", edificio))
    if pk is None:
        if not Edificio.objects.filter(dispositivos=entrega.dispositivo_id, activo=True).exists():
            # Sin edificios activos no hay qué elegir (la pantalla no dibuja el desplegable): se dice qué falta.
            raise ValidationError({"edificio": SIN_EDIFICIO_PARA_EL_STOCK.format(nombre=entrega.dispositivo.nombre)})
        raise ValidationError({"edificio": ELEGI_EL_EDIFICIO_DE_LA_RECEPCION})
    Dispositivo.objects.select_for_update().filter(pk=entrega.dispositivo_id).first()
    vinculado = Edificio.dispositivos.through.objects.filter(dispositivo_id=entrega.dispositivo_id, edificio_id=pk)
    # `puede_recibir` ya exigió alcance sobre TODA la institución (la entrega no tiene edificio), así que esta guarda no
    # debería dispararse hoy: queda como defensa en profundidad por si esa regla se afina por edificio.
    if not vinculado.exists() or not puede_operar_edificio(usuario, entrega.dispositivo, pk, CAP_RECIBIR_KIT):
        raise ValidationError({"edificio": EDIFICIO_NO_ES_DEL_DISPOSITIVO})
    return _exigir_edificio_activo(pk)


@archivos_atomicos
@transaction.atomic
def recibir_entrega(entrega, usuario, cantidades, remito, observacion="", uuid_cliente=None, edificio=None):
    """El dispositivo confirma qué llegó (HU-4.3). Deja la entrega ``RECIBIDA`` o ``RECIBIDA_CON_DIFERENCIAS``.

    1. **Alcance** (RN-4.8): ``emergencia.recibir_kit`` con ``puede_operar_dispositivo``
       sobre el dispositivo de la entrega. Sin eso, ``PermissionDenied`` y nada cambia —la
       vista y la API lo convierten en 404, igual que un id inexistente (plan §2, C2)—.
    2. **Idempotencia** (RN-4.4, RU-16): si ``uuid_cliente`` es el de la recepción que ya
       tiene esta entrega, la devuelve tal cual, con ``entrega.ya_existia = True``, sin
       validar ni reescribir nada.
    3. **Estado**: vale sobre ``EN_CAMINO`` y sobre ``PREPARADA`` (la mesa no la marcó, y la
       traza dice «Recibida sin marca de salida»). Ya recibida —con otro identificador o
       desde el backoffice— o cancelada: :class:`EstadoCambioEntrega`.
    4. **RN-4.3**: ``cantidades`` (``{item_id: cantidad}``) trae un entero ≥ 0 para **todas**
       las líneas; ``remito`` es obligatorio, JPEG y de hasta 5 MB. ``ValidationError`` por
       clave (``cantidades``, ``remito``, ``uuid_cliente``).
    5. Estado final: ``RECIBIDA_CON_DIFERENCIAS`` si alguna línea tiene
       ``recibida != enviada`` —llegar de más también es una diferencia—.
    6. **Stock** (RN-010-06, revierte RN-4.6): si el tipo de la institución lleva stock, lo recibido (cada línea
       mayor que 0) se suma al stock del edificio de la entrega con ``stock.sumar_recepcion_de_kit``, en esta misma
       transacción: si la suma falla, la entrega no queda recibida. Una entrega **sin edificio** (anteriores al
       Cambio 523) pide ``edificio`` —uno vinculado, activo y dentro del alcance—, que se guarda en la entrega; sin él,
       ``ValidationError`` en la clave ``edificio``. La rama idempotente no suma; una institución sin stock no se toca.
    7. Traza, y la novedad ``GENERAL`` automática «Kit recibido N.° X» en la bitácora del
       dispositivo (RU-15); sin turno vigente no se escribe, como toda automática.

    El archivo y la fila son una sola unidad (``archivos_atomicos``): si algo falla, el
    remito no queda huérfano en ``media/``. **La recepción no se edita después** (RN-4.5):
    no hay función que cambie las cantidades de una entrega recibida.
    """

    if not puede_recibir(usuario, entrega):
        raise PermissionDenied(SIN_PERMISO_DE_RECIBIR)
    uuid_cliente = _como_uuid(uuid_cliente)

    bloqueada = _bloquear_entrega(entrega)
    if uuid_cliente is not None and bloqueada.uuid_cliente_recepcion == uuid_cliente:
        bloqueada.ya_existia = True
        return bloqueada
    _exigir_estado(bloqueada, *EntregaKit.ESTADOS_ABIERTOS)

    lineas = list(LineaEntrega.objects.filter(entrega=bloqueada).select_related("item").order_by("id"))
    recibidas = _validar_cantidades(lineas, cantidades)
    validar_remito(remito)
    if uuid_cliente is not None:
        _exigir_uuid_libre(uuid_cliente, bloqueada)

    lleva_stock = suma_al_stock(bloqueada.dispositivo)
    edificio_elegido = None
    if lleva_stock and bloqueada.edificio_id is None:
        edificio_elegido = _edificio_de_la_recepcion(usuario, bloqueada, edificio)
        bloqueada.edificio_id = edificio_elegido

    ahora = timezone.now()
    anterior = bloqueada.estado
    for linea in lineas:
        linea.cantidad_recibida = recibidas[linea.item_id]
        linea.modificado = ahora
    con_diferencia = sum(1 for linea in lineas if linea.cantidad_recibida != linea.cantidad_enviada)

    bloqueada.estado = Estado.RECIBIDA_CON_DIFERENCIAS if con_diferencia else Estado.RECIBIDA
    bloqueada.recibida_en = ahora
    bloqueada.recibida_por = usuario
    bloqueada.observacion_dispositivo = (observacion or "").strip()
    bloqueada.uuid_cliente_recepcion = uuid_cliente
    bloqueada.remito = remito
    try:
        # Anidada: si el UNIQUE del identificador salta —el mismo envío llegó a la vez para
        # otra entrega—, la transacción de afuera sigue sana y el error es de dominio.
        with transaction.atomic():
            bloqueada.save(
                update_fields=[
                    "estado",
                    "recibida_en",
                    "recibida_por",
                    "observacion_dispositivo",
                    "uuid_cliente_recepcion",
                    "remito",
                    "modificado",
                    *(["edificio"] if edificio_elegido is not None else []),
                ]
            )
    except IntegrityError:
        raise UuidEnUso(UUID_EN_USO) from None
    anotar_archivo_escrito(bloqueada.remito, asignado=remito)
    LineaEntrega.objects.bulk_update(lineas, ["cantidad_recibida", "modificado"])
    if lleva_stock:
        # Después de guardar las líneas (la suma las lee de la base) y antes de la novedad. Perezoso: `stock` importa de acá.
        from programas.services import stock

        stock.sumar_recepcion_de_kit(bloqueada, usuario)

    if con_diferencia:
        detalle = "1 ítem con diferencia" if con_diferencia == 1 else f"{con_diferencia} ítems con diferencia"
    else:
        detalle = "Recibida completa"
    if anterior == Estado.PREPARADA:
        detalle = f"{detalle} · {SIN_MARCA_DE_SALIDA}"
    _trazar(bloqueada, usuario, Accion.RECIBIDA, estado_anterior=anterior, detalle=detalle)
    anotar_novedad_automatica(
        dispositivo=bloqueada.dispositivo,
        tipo=EntradaBitacora.Tipo.GENERAL,
        texto=f"Kit recibido N.° {bloqueada.numero}",
        momento=ahora,
        usuario=usuario,
        edificio_id=bloqueada.edificio_id,
    )
    bloqueada.ya_existia = False
    return bloqueada


# ---------------------------------------------------------------------------
# Observar (la mesa, después de la recepción)
# ---------------------------------------------------------------------------


@transaction.atomic
def observar_recepcion(entrega, usuario, texto):
    """La observación de la mesa sobre una entrega ya recibida (RN-4.5).

    Es la única corrección posible después de la recepción: **no cambia las cantidades ni
    el estado**. Reemplaza ``observacion_mesa`` y deja el texto completo en la traza, así
    que lo que decía antes no se pierde. Sobre una entrega que no fue recibida,
    :class:`EstadoCambioEntrega`.
    """

    _exigir_mesa(usuario)
    texto = (texto or "").strip()
    if not texto:
        raise ValidationError({"texto": FALTA_LA_OBSERVACION})

    bloqueada = _bloquear_entrega(entrega)
    _exigir_estado(
        bloqueada, *EntregaKit.ESTADOS_RECIBIDOS, si_sigue_abierta=TODAVIA_NO_RECIBIDA.format(numero=bloqueada.numero)
    )
    bloqueada.observacion_mesa = texto
    bloqueada.save(update_fields=["observacion_mesa", "modificado"])
    _trazar(bloqueada, usuario, Accion.OBSERVADA, estado_anterior=bloqueada.estado, detalle=texto)
    return bloqueada


@transaction.atomic
def aceptar_diferencia(entrega, usuario, motivo):
    """Cierra la diferencia de una entrega recibida sin reponerla: queda ``ACEPTADA``, con motivo obligatorio.

    Es una de las dos salidas de «Qué hacer ahora» (la otra es reponer, que va en :func:`crear_entrega` con
    ``repone_a``). Solo sobre una entrega ``RECIBIDA_CON_DIFERENCIAS`` y **sin cerrar**: ya repuesta o ya aceptada, o
    sin diferencia, :class:`EstadoCambioEntrega`. Bloquea la fila antes de leer el cierre, así que aceptar y reponer a
    la vez no se pisan: gana quien llega primero al candado. No cambia las cantidades (RN-4.5). Deja la traza con el
    motivo completo.
    """

    _exigir_mesa(usuario)
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValidationError({"motivo": FALTA_EL_MOTIVO_DE_LA_DIFERENCIA})
    maximo = EntregaKit._meta.get_field("cierre_diferencia_motivo").max_length
    if len(motivo) > maximo:
        raise ValidationError({"motivo": MOTIVO_DE_LA_DIFERENCIA_LARGO.format(maximo=maximo)})

    bloqueada = _bloquear_entrega(entrega)
    if bloqueada.estado != Estado.RECIBIDA_CON_DIFERENCIAS:
        raise EstadoCambioEntrega(SIN_DIFERENCIA_QUE_CERRAR.format(numero=bloqueada.numero), entrega=bloqueada)
    if bloqueada.cierre_diferencia is not None:
        raise EstadoCambioEntrega(
            DIFERENCIA_YA_CERRADA.format(numero=bloqueada.numero, como=_como_se_cerro(bloqueada)), entrega=bloqueada
        )
    bloqueada.cierre_diferencia = EntregaKit.CierreDiferencia.ACEPTADA
    bloqueada.cierre_diferencia_en = timezone.now()
    bloqueada.cierre_diferencia_por = usuario
    bloqueada.cierre_diferencia_motivo = motivo
    bloqueada.save(
        update_fields=[
            "cierre_diferencia",
            "cierre_diferencia_en",
            "cierre_diferencia_por",
            "cierre_diferencia_motivo",
            "modificado",
        ]
    )
    _trazar(bloqueada, usuario, Accion.DIFERENCIA_ACEPTADA, estado_anterior=bloqueada.estado, detalle=motivo)
    return bloqueada


def url_de_kits_del_edificio(url_pagina, entrega=None):
    """La solapa Kits de la página del edificio (``url_pagina``), abierta en ``entrega`` si se pasa (id o instancia).

    **Único lugar** donde se arma ese enlace: lo usan la recepción de la mesa, la lista y el detalle de la solapa y el
    ítem «Recibir kit» del menú del edificio (Cambio 586).
    """

    pk = getattr(entrega, "pk", entrega)
    return f"{url_pagina}?tab=kits&entrega={pk}" if pk else f"{url_pagina}?tab=kits"


def aviso_de_kits_por_recibir(cantidad, url, *, en_este_edificio=False, mas_vieja=None):
    """El aviso de entregas de kits por recibir (``components/_alerta.html``) o ``None`` si no hay ninguna. Sin consultas.

    ``cantidad`` cuenta las entregas abiertas (en camino o preparadas) y ``url`` es la recepción de la única, o la
    lista de varias. Con ``en_este_edificio`` el título dice «en este edificio»; sin él, «para esta institución» (la
    ficha de la institución, cuyo enlace es siempre la lista de entregas: el botón dice «Recibir kits»).
    ``mas_vieja`` es el número de la entrega que lleva más tiempo abierta (``2026-K-000031``); si viene, el texto lo
    nombra. La salida de la página del edificio, que no lo pasa, no cambia.
    """

    if not cantidad:
        return None
    texto = "Hasta que se confirme la recepción, la mesa de Emergencia las sigue viendo abiertas."
    if mas_vieja:
        texto = f"La más vieja es la entrega {mas_vieja}. {texto}"
    if en_este_edificio:
        donde, accion = "en este edificio", "Recibir kit" if cantidad == 1 else "Ver entregas"
    else:
        donde, accion = "para esta institución", "Recibir kits"
    return {
        "tono": "warning",
        "icono": "boxes-stacked",
        "titulo": f"{plural(cantidad, 'entrega de kits', 'entregas de kits')} por recibir {donde}",
        "texto": texto,
        "accion_url": url,
        "accion_texto": accion,
    }
