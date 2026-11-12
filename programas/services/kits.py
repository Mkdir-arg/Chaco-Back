"""Entregas de kits de Emergencia: armar, marcar en camino, cancelar, recibir y observar (etapa 4).

**Una entrega, una recepción.** No hay stock ni depósitos (RN-4.6): nada de este módulo
suma ni descuenta existencias, y las cantidades son lo que dice un remito.

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

    numerador (serie K)  ·  entrega

``crear_entrega`` bloquea solo el numerador (todavía no hay entrega); las transiciones
bloquean solo la entrega. Ninguna función toma los dos, así que no hay orden que cruzar.
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
from programas.services.dispositivos import dispositivos_en_alcance, puede_operar_dispositivo
from programas.services.emergencia import EstadoCambio, siguiente_correlativo
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
FALTA_EL_MOTIVO = "Indicá por qué se cancela la entrega."
MOTIVO_LARGO = f"El motivo no puede tener más de {MOTIVO_MAXIMO} caracteres."
TRANSPORTE_LARGO = f"El transporte no puede tener más de {TRANSPORTE_MAXIMO} caracteres."
HORA_FUTURA = "La hora de salida no puede ser posterior a este momento."
FALTA_EL_REMITO = "Falta la foto del remito."
REMITO_NO_ES_JPEG = "La foto del remito tiene que llegar en JPEG."
FALTAN_CANTIDADES = "Indicá cuánto llegó de cada ítem, aunque sea cero. Falta: {items}."
CANTIDAD_RECIBIDA_INVALIDA = "La cantidad recibida de {item} tiene que ser un número entero, cero o más."
ITEM_AJENO = "Hay cantidades de ítems que no son de esta entrega. Recargá la pantalla."
UUID_INVALIDO = "El identificador del envío no es válido."
UUID_EN_USO = "Ese identificador de envío ya se usó en otra recepción."
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


def _hora(momento):
    return f"{timezone.localtime(momento):%H:%M}"


def estado_visible_de_entrega(entrega):
    """``(texto, tono)`` del badge del estado. El template lo dibuja; no lo decide."""

    return ESTADOS_VISIBLES_ENTREGA.get(entrega.estado, (entrega.get_estado_display(), "gray"))


def _exigir_mesa(usuario):
    if not puede_operar_la_mesa(usuario):
        raise PermissionDenied(SIN_PERMISO_DE_MESA)


def puede_recibir(usuario, entrega):
    """¿``usuario`` recibe los kits del dispositivo de ``entrega``? La regla de RN-4.8, una sola vez."""

    return puede_operar_dispositivo(usuario, entrega.dispositivo, CAP_RECIBIR_KIT)


def recibe_kits(usuario):
    """¿``usuario`` recibe kits en **algún** dispositivo? Lo que abre «Recepción de kits» (web y M3).

    ``emergencia.recibir_kit`` con alcance: en el Equipo de alguna institución, o en todas si
    además administra el programa Dispositivos. La capacidad tildada en un rol **sin** Equipo
    no alcanza: no hay dispositivo sobre el que ejercerla. Quien no pasa esto recibe 403; quien
    lo pasa y pide un dispositivo o una entrega que no son suyos, 404 (plan §2, C2).
    """

    if usuario is None or not getattr(usuario, "is_authenticated", False):
        return False
    return dispositivos_en_alcance(usuario, CAP_RECIBIR_KIT).exists()


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


def _validar_reposicion(repone_a, dispositivo):
    """HU-4.5: se repone una entrega que **ese** dispositivo recibió con diferencias."""

    if repone_a is None:
        return None
    original = EntregaKit.objects.filter(pk=getattr(repone_a, "pk", repone_a)).first()
    if (
        original is None
        or original.dispositivo_id != dispositivo.pk
        or original.estado != Estado.RECIBIDA_CON_DIFERENCIAS
    ):
        raise ValidationError({"repone_a": REPOSICION_INVALIDA})
    return original


@transaction.atomic
def crear_entrega(usuario, dispositivo, lineas, observacion="", repone_a=None):
    """Arma una entrega ``PREPARADA`` con sus líneas (HU-4.1). **La única función que crea entregas.**

    * Exige trabajar en la mesa (``emergencia.operar`` o ``supervisar``).
    * **RN-4.2** — el destino tiene que estar ``ACTIVO`` (cualquier tipo). Se relee de la
      base: el estado que cuenta es el de ahora, no el de la pantalla.
    * **RN-4.1** — ``lineas`` (ver :func:`_pares_de`): al menos una, ítems del catálogo
      **activos**, cada ítem una sola vez y cantidades enteras > 0. ``ValidationError`` en
      la clave ``lineas``.
    * La ``unidad`` de cada línea se **copia** del catálogo (04 §10) y ``cantidad_recibida``
      nace ``NULL``.
    * ``repone_a`` (HU-4.5): la entrega que esta repone; tiene que ser del mismo dispositivo
      y estar ``RECIBIDA_CON_DIFERENCIAS``.
    * Numera con el contador de la serie ``K`` («2026-K-000031») y deja la primera traza.
    """

    _exigir_mesa(usuario)
    destino = Dispositivo.objects.filter(pk=getattr(dispositivo, "pk", dispositivo)).first()
    if destino is None or destino.estado != Dispositivo.Estado.ACTIVO:
        raise ValidationError({"dispositivo": DISPOSITIVO_NO_ACTIVO})
    validas = _validar_lineas(lineas)
    original = _validar_reposicion(repone_a, destino)

    ahora = timezone.now()
    entrega = EntregaKit.objects.create(
        numero=siguiente_numero_de_entrega(ahora),
        dispositivo=destino,
        estado=Estado.PREPARADA,
        armada_por=usuario,
        observacion_mesa=(observacion or "").strip(),
        repone_a=original,
    )
    LineaEntrega.objects.bulk_create(
        [
            LineaEntrega(entrega=entrega, item=item, unidad=item.unidad, cantidad_enviada=cantidad)
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
    return entrega


# ---------------------------------------------------------------------------
# Marcar en camino y cancelar (la mesa)
# ---------------------------------------------------------------------------


@transaction.atomic
def marcar_en_camino(entrega, usuario, transporte="", hora=None):
    """``PREPARADA`` → ``EN_CAMINO`` (HU-4.2). ``despachada_en`` es ``hora`` o, sin ella, ahora.

    ``transporte`` (quién la lleva, patente…) y ``hora`` son opcionales; una hora de salida
    futura es un ``ValidationError``.
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

    Una entrega ya recibida o ya cancelada no se cancela: :class:`EstadoCambioEntrega`.
    """

    _exigir_mesa(usuario)
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValidationError({"motivo": FALTA_EL_MOTIVO})
    if len(motivo) > MOTIVO_MAXIMO:
        raise ValidationError({"motivo": MOTIVO_LARGO})

    bloqueada = _bloquear_entrega(entrega)
    _exigir_estado(bloqueada, *EntregaKit.ESTADOS_ABIERTOS)
    anterior = bloqueada.estado
    bloqueada.estado = Estado.CANCELADA
    bloqueada.motivo_cancelacion = motivo
    bloqueada.save(update_fields=["estado", "motivo_cancelacion", "modificado"])
    _trazar(bloqueada, usuario, Accion.CANCELADA, estado_anterior=anterior, detalle=motivo)
    return bloqueada


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
    faltan = [linea.item.nombre for linea in lineas if recibidas.get(linea.item_id) in (None, "")]
    if faltan:
        raise ValidationError({"cantidades": FALTAN_CANTIDADES.format(items=", ".join(faltan))})
    limpias = {}
    for item_id, cantidad in recibidas.items():
        entero = _entero(cantidad)
        if entero is None or not 0 <= entero <= CANTIDAD_MAXIMA:
            raise ValidationError(
                {"cantidades": CANTIDAD_RECIBIDA_INVALIDA.format(item=de_la_entrega[item_id].item.nombre)}
            )
        limpias[item_id] = entero
    return limpias


def _exigir_uuid_libre(uuid_cliente, entrega):
    """El identificador de un envío es de **una** recepción: usado en otra entrega, se rechaza."""

    en_otra = EntregaKit.objects.filter(q_uuid_en_texto("uuid_cliente_recepcion", uuid_cliente)).exclude(pk=entrega.pk)
    if en_otra.exists():
        raise ValidationError({"uuid_cliente": UUID_EN_USO})


@archivos_atomicos
@transaction.atomic
def recibir_entrega(entrega, usuario, cantidades, remito, observacion="", uuid_cliente=None):
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
    6. Traza, y la novedad ``GENERAL`` automática «Kit recibido N.° X» en la bitácora del
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
                ]
            )
    except IntegrityError:
        raise ValidationError({"uuid_cliente": UUID_EN_USO}) from None
    anotar_archivo_escrito(bloqueada.remito, asignado=remito)
    LineaEntrega.objects.bulk_update(lineas, ["cantidad_recibida", "modificado"])

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
