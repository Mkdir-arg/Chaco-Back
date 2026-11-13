"""El caso de Emergencia y la mesa: crear, tomar, soltar, reasignar, priorizar, contactar,
derivar, cancelar y cerrar (etapas 1 y 2 del módulo).

**Toda regla del caso vive acá.** La vista web, la API de la app y el ingreso directo
llaman a estas mismas funciones (RU-2): una regla que solo esté en una vista o en un
serializer es un defecto. Lo que se lee —bandeja, semáforo, panel de derivar— está en
``programas.selectors.emergencia``. El alta —el Formulario 1 y ``crear_caso``— vive en
``programas.services.emergencia_alta``, y la traza, el permiso de la mesa y el numerador
que comparten los dos en ``programas.services.emergencia_comun``; todo eso se sigue
pudiendo importar desde acá.

Cómo está hecha cada función
----------------------------

1. Exige la capacidad **con alcance sobre el programa EMERGENCIA** (RU-6, RU-7). No confía
   en que la vista se haya acordado.
2. Abre una transacción y **bloquea la fila del caso** (``select_for_update``) antes de
   mirar nada. Lo que decide se lee de la fila bloqueada, no del objeto que llegó por
   parámetro: ese es el de la pantalla, y puede ser de hace diez minutos.
3. Si el caso ya no está en el estado que la acción necesita, levanta
   :class:`EstadoCambio` con el estado actual: alguien se adelantó (otra pestaña, otro
   operador, el dispositivo, el cron). La vista lo traduce a un 409 y recarga.
4. Deja una fila de ``TrazaCaso`` en la misma transacción (RU-15).

Devuelven **la fila recién leída y bloqueada**, no el objeto que recibieron.

El orden de los candados
------------------------

Es global para todo el módulo, y es el de Dispositivos con dos escalones adelante (plan
§8, R1)::

    caso → derivación → plazas (por pk) → reservas → persona

* Toda función de Emergencia bloquea **primero el caso**. Las de esta etapa no pasan de
  la derivación: derivar **no reserva plazas** (las reserva el dispositivo al aceptar) y
  solo *lee* la ocupación, sin candado.
* ``cancelar_derivacion`` recibe una derivación y aun así bloquea antes el caso: aceptar
  (etapa 3) y vencer (el cron) van a competir por las mismas dos filas, y si cada camino
  las pidiera en su orden InnoDB cortaría a uno con ``ERROR 1213`` en vez de dar el error
  de dominio.
* Los candados del caso y de la derivación van **sin JOIN**: un ``FOR UPDATE`` con
  ``select_related`` bloquea también las filas que trae, y metería en el orden filas que
  nadie pidió.
* El numerador (``NumeradorEmergencia``) es una hoja: se bloquea en ``crear_caso``,
  cuando todavía no hay caso que bloquear, y después de él solo hay altas.

``OrdenDeLosCandadosEmergenciaTests`` fija este orden por la secuencia de llamadas (en
SQLite ``select_for_update`` es un no-op) y ``programas.tests.test_emergencia_concurrencia``
corre las carreras contra el motor real.

Que el bloqueo alcance depende del nivel de aislamiento, igual que en
``programas.services.estadias``: el proyecto fija ``READ COMMITTED``, así que la lectura
que sigue al candado ve lo que commiteó el que ganó.

Dueño y supervisor (RU-12, RU-13)
---------------------------------

«Dueño» es ``caso.tomado_por == usuario``. Quien opera la mesa actúa sobre los casos que
tiene tomados; quien supervisa actúa sobre cualquiera **sin tomarlo**, y la traza queda
marcada ``por_supervisor`` y lo dice en el detalle.
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from programas.models import CasoEmergencia, ContactoCaso, Derivacion, TrazaCaso
from programas.selectors.emergencia import dispositivo_elegible
from programas.services.configuracion_emergencia import sla_vigente

# El alta del caso se mudó a `emergencia_alta`; se reexporta para que los imports de siempre
# (la API, el ingreso directo, los formularios, los tests) sigan andando.
from programas.services.emergencia_alta import (  # noqa: F401
    CAP_ADMITIR,
    NECESIDADES,
    NECESIDADES_CRITICAS,
    PRIMERA_TRAZA,
    SIN_PERMISO_DE_INGRESO_DIRECTO,
    SIN_PERMISO_DE_RELEVAR,
    UUID_EN_USO,
    _caso_de_ese_envio,
    _como_uuid,
    crear_caso,
    prioridad_sugerida,
)
from programas.services.emergencia_comun import (  # noqa: F401
    SIN_PERMISO_DE_MESA,
    _bloquear_numerador,
    _exigir_mesa,
    _trazar,
    siguiente_numero,
)
from programas.services.emergencia_programa import puede_operar_la_mesa, puede_supervisar_la_mesa
from programas.services.ocupacion import ocupacion_de_plazas

Estado = CasoEmergencia.Estado
Origen = CasoEmergencia.Origen
Prioridad = CasoEmergencia.Prioridad
Accion = TrazaCaso.Accion

#: Cómo se muestra cada estado del caso: texto y tono del badge. Es la **única** tabla: la
#: leen la bandeja, la ficha y la app, así que el mismo caso no puede verse con dos rótulos.
ESTADOS_VISIBLES_CASO = {
    Estado.NUEVO: ("Nuevo", "info"),
    Estado.EN_GESTION: ("En gestión", "warning"),
    Estado.DERIVADO: ("Derivado", "brand"),
    Estado.INGRESO_EN_CURSO: ("Ingreso en curso", "brand"),
    Estado.ALOJADO: ("Alojado", "success"),
    Estado.CERRADO: ("Cerrado", "gray"),
}

#: Lo mismo para la prioridad.
PRIORIDADES_VISIBLES = {
    Prioridad.ALTA: ("Alta", "danger"),
    Prioridad.MEDIA: ("Media", "warning"),
    Prioridad.BAJA: ("Baja", "gray"),
}


def estado_visible_de_caso(caso):
    """``(texto, tono)`` del badge del estado. El template lo dibuja; no lo decide."""

    return ESTADOS_VISIBLES_CASO.get(caso.estado, (caso.get_estado_display(), "gray"))


def prioridad_visible(caso):
    """``(texto, tono)`` del badge de la prioridad."""

    return PRIORIDADES_VISIBLES.get(caso.prioridad, (caso.get_prioridad_display(), "gray"))


#: Los motivos que elige una persona al cerrar sin alojamiento (E3-modal). «Todos
#: egresados» no está: lo pone el egreso del último integrante.
MOTIVOS_DE_CIERRE_MANUAL = (
    CasoEmergencia.MotivoCierre.NO_REQUIERE,
    CasoEmergencia.MotivoCierre.SIN_CONTACTO,
    CasoEmergencia.MotivoCierre.ASISTIDO_DOMICILIO,
    CasoEmergencia.MotivoCierre.POR_SU_CUENTA,
    CasoEmergencia.MotivoCierre.OTRO,
)

SIN_PERMISO_DE_SUPERVISAR = "Solo quien supervisa la mesa puede reasignar un caso."
NO_ES_EL_DUENIO = "Solo quien tiene tomado el caso, o quien supervisa la mesa, puede hacer esto."
CASO_CERRADO = "El caso está cerrado y no se reabre. Si hace falta, cargá uno nuevo."
SIN_PLAZAS = "El dispositivo no tiene plazas libres. Elegí otro."
DISPOSITIVO_NO_ELEGIBLE = "A ese dispositivo no se le pueden derivar familias: no está activo o no maneja camas."


# ---------------------------------------------------------------------------
# Excepciones de dominio
# ---------------------------------------------------------------------------


class EstadoCambio(Exception):
    """El caso ya no está en el estado que la acción necesitaba: alguien se adelantó.

    No es un error de validación (no hay nada que corregir en lo que se mandó) ni de
    permisos: la pantalla quedó vieja. La vista y la API la traducen a **409** con
    ``{"detail": mensaje, "estado_actual": estado_actual}`` y recargan.

    * ``mensaje`` — qué pasó y qué hacer (RU-20).
    * ``estado_actual`` — el ``CasoEmergencia.Estado`` de la fila bloqueada.
    * ``caso`` — la fila tal como quedó, para volver a dibujarla sin otra consulta.
    """

    def __init__(self, mensaje, *, estado_actual, caso=None):
        self.mensaje = mensaje
        self.estado_actual = estado_actual
        self.caso = caso
        super().__init__(mensaje)


class CasoTomadoPorOtro(EstadoCambio):
    """Quiso tomar un caso que otro operador tomó antes (RN-2.1).

    Es un :class:`EstadoCambio` —quien atrapa aquel también atrapa este— con quién lo
    tiene y desde cuándo: ``tomado_por`` (``User`` o ``None``) y ``tomado_en``.
    """

    def __init__(self, caso):
        self.tomado_por = caso.tomado_por
        self.tomado_en = caso.tomado_en
        quien = _nombre_de(caso.tomado_por) if caso.tomado_por_id else "otro operador"
        super().__init__(
            f"El caso {caso.numero} ya lo tomó {quien}. Recargá la bandeja.",
            estado_actual=caso.estado,
            caso=caso,
        )


class FaltanPlazas(ValidationError):
    """El dispositivo tiene menos plazas libres que las pedidas y nadie confirmó seguir (RN-2.5).

    Es un ``ValidationError`` (400): se resuelve reenviando con
    ``confirmar_faltantes=True``. Trae ``libres``, ``pedidas`` y ``faltan`` para armar la
    pregunta «Vas a reservar 5 de 7 plazas. ¿Seguís?».
    """

    def __init__(self, *, libres, pedidas):
        self.libres = libres
        self.pedidas = pedidas
        self.faltan = pedidas - libres
        super().__init__(
            f"El dispositivo tiene {libres} de las {pedidas} plazas pedidas. "
            "Confirmá que querés derivar igual, o elegí otro."
        )


# ---------------------------------------------------------------------------
# Piezas internas
# ---------------------------------------------------------------------------


def _nombre_de(usuario):
    if usuario is None:
        return "nadie"
    return usuario.get_full_name().strip() or usuario.get_username()


def _hora(momento):
    return f"{timezone.localtime(momento):%H:%M}"


def _bloquear_caso(caso):
    """La fila del caso con ``FOR UPDATE``, recién leída. **Siempre el primer candado.**

    Sin ``select_related``: un JOIN acá bloquearía también las filas que trae.
    """

    return CasoEmergencia.objects.select_for_update().get(pk=getattr(caso, "pk", caso))


def _exigir_estado(caso, *estados, mensaje):
    """El caso bloqueado tiene que estar en uno de ``estados``; si no, :class:`EstadoCambio`."""

    if caso.estado in estados:
        return
    if caso.estado == Estado.CERRADO:
        mensaje = CASO_CERRADO
    raise EstadoCambio(mensaje, estado_actual=caso.estado, caso=caso)


def _exigir_abierto(caso):
    if caso.estado == Estado.CERRADO:
        raise EstadoCambio(CASO_CERRADO, estado_actual=caso.estado, caso=caso)


def _exigir_duenio_o_supervisor(caso, usuario):
    """RU-12 y RU-13 sobre la fila bloqueada. Devuelve si actúa **como supervisor**."""

    if caso.tomado_por_id is not None and caso.tomado_por_id == usuario.pk:
        return False
    if puede_supervisar_la_mesa(usuario):
        return True
    raise PermissionDenied(NO_ES_EL_DUENIO)


# ---------------------------------------------------------------------------
# Tomar, soltar, reasignar
# ---------------------------------------------------------------------------


@transaction.atomic
def tomar_caso(caso, usuario):
    """Toma un caso ``NUEVO``: pasa a ``EN_GESTION`` a nombre de ``usuario`` (HU-2.1, RN-2.1).

    El candado sobre la fila es lo que hace que de dos operadores gane uno: el segundo
    espera, lee el caso ya tomado y recibe :class:`CasoTomadoPorOtro`. ``tomado_en`` se
    escribe solo la primera vez (RN-2.9).

    Si quien lo pide **ya lo tiene tomado** (doble clic, segunda pestaña) devuelve el caso
    sin tocar nada ni dejar traza.
    """

    _exigir_mesa(usuario)
    caso = _bloquear_caso(caso)
    _exigir_abierto(caso)
    if caso.estado == Estado.EN_GESTION and caso.tomado_por_id == usuario.pk:
        return caso
    if caso.tomado_por_id is not None and caso.tomado_por_id != usuario.pk:
        raise CasoTomadoPorOtro(caso)
    _exigir_estado(caso, Estado.NUEVO, mensaje=f"El caso {caso.numero} ya no está para tomar. Recargá la bandeja.")
    ahora = timezone.now()
    caso.estado = Estado.EN_GESTION
    caso.tomado_por = usuario
    caso.marcar("tomado_en", ahora)
    caso.save(update_fields=["estado", "tomado_por", "tomado_en", "modificado"])
    _trazar(caso, usuario, Accion.TOMADO, estado_anterior=Estado.NUEVO, detalle=f"Tomado por {_nombre_de(usuario)}")
    return caso


@transaction.atomic
def soltar_caso(caso, usuario):
    """Devuelve a la bandeja un caso ``EN_GESTION``: vuelve a ``NUEVO``, sin dueño.

    El operador suelta lo suyo; quien supervisa, cualquiera. ``tomado_en`` **se conserva**
    (RN-2.9): el tramo del SLA sigue corriendo desde la primera vez que se tomó.
    """

    _exigir_mesa(usuario)
    caso = _bloquear_caso(caso)
    _exigir_estado(caso, Estado.EN_GESTION, mensaje=f"El caso {caso.numero} ya no está en gestión. Recargá la ficha.")
    por_supervisor = _exigir_duenio_o_supervisor(caso, usuario)
    anterior = caso.tomado_por
    caso.estado = Estado.NUEVO
    caso.tomado_por = None
    caso.save(update_fields=["estado", "tomado_por", "modificado"])
    _trazar(
        caso,
        usuario,
        Accion.SOLTADO,
        estado_anterior=Estado.EN_GESTION,
        detalle=f"Devuelto a la bandeja (lo tenía {_nombre_de(anterior)})",
        por_supervisor=por_supervisor,
    )
    return caso


@transaction.atomic
def reasignar_caso(caso, usuario, operador):
    """Le pasa el caso a ``operador``. **Solo quien supervisa** (HU-2.6, RU §6 n.° 1).

    Vale para cualquier caso abierto. Uno ``NUEVO`` pasa a ``EN_GESTION`` a nombre del
    operador (y gana ``tomado_en`` si no lo tenía); en los demás estados solo cambia quién
    lo tiene. El reloj del tramo **no** se reinicia (RN-2.9).

    ``operador`` tiene que estar activo y trabajar en la mesa; si ya lo tiene,
    ``ValidationError``.
    """

    if not puede_supervisar_la_mesa(usuario):
        raise PermissionDenied(SIN_PERMISO_DE_SUPERVISAR)
    # Recién leído: `rbac` memoiza las capacidades en el objeto que llegó.
    operador = User.objects.filter(pk=getattr(operador, "pk", operador)).first()
    if operador is None or not operador.is_active or not puede_operar_la_mesa(operador):
        raise ValidationError({"operador": "Elegí a alguien que opere la mesa de Emergencia."})
    caso = _bloquear_caso(caso)
    _exigir_abierto(caso)
    if caso.tomado_por_id == operador.pk:
        raise ValidationError({"operador": f"{_nombre_de(operador)} ya tiene tomado el caso."})
    anterior = caso.tomado_por
    estado_anterior = caso.estado
    campos = ["tomado_por", "modificado"]
    caso.tomado_por = operador
    if caso.estado == Estado.NUEVO:
        caso.estado = Estado.EN_GESTION
        caso.marcar("tomado_en", timezone.now())
        campos += ["estado", "tomado_en"]
    caso.save(update_fields=campos)
    _trazar(
        caso,
        usuario,
        Accion.REASIGNADO,
        estado_anterior=estado_anterior,
        detalle=f"Reasignado de {_nombre_de(anterior)} a {_nombre_de(operador)}",
        por_supervisor=True,
    )
    return caso


# ---------------------------------------------------------------------------
# Prioridad y contactos
# ---------------------------------------------------------------------------


@transaction.atomic
def cambiar_prioridad(caso, usuario, prioridad):
    """Cambia la prioridad de un caso abierto y deja el valor anterior y el nuevo (RN-2.11).

    El dueño o quien supervisa. La prioridad no dispara ninguna regla: solo ordena la
    bandeja. Si es la que ya tenía, no cambia nada ni deja traza.
    """

    _exigir_mesa(usuario)
    if prioridad not in Prioridad.values:
        raise ValidationError({"prioridad": "Elegí una prioridad: alta, media o baja."})
    caso = _bloquear_caso(caso)
    _exigir_abierto(caso)
    por_supervisor = _exigir_duenio_o_supervisor(caso, usuario)
    if caso.prioridad == prioridad:
        return caso
    anterior = caso.get_prioridad_display()
    caso.prioridad = prioridad
    caso.save(update_fields=["prioridad", "modificado"])
    _trazar(
        caso,
        usuario,
        Accion.PRIORIDAD,
        estado_anterior=caso.estado,
        detalle=f"Prioridad: {anterior} → {caso.get_prioridad_display()}",
        por_supervisor=por_supervisor,
    )
    return caso


@transaction.atomic
def registrar_contacto(caso, usuario, *, canal, resultado, observacion="", momento=None):
    """Anota un contacto con la familia en un caso abierto (HU-2.4, RN-2.12).

    El dueño o quien supervisa. Es un registro manual: no envía nada (RU-21). ``momento``
    es cuándo fue el contacto; sin él, ahora. Devuelve el ``ContactoCaso``.
    """

    _exigir_mesa(usuario)
    caso = _bloquear_caso(caso)
    _exigir_abierto(caso)
    por_supervisor = _exigir_duenio_o_supervisor(caso, usuario)
    contacto = ContactoCaso(
        caso=caso,
        canal=canal,
        resultado=resultado,
        observacion=(observacion or "").strip(),
        por=usuario,
        momento=momento or timezone.now(),
    )
    contacto.full_clean()
    contacto.save()
    _trazar(
        caso,
        usuario,
        Accion.CONTACTO,
        estado_anterior=caso.estado,
        detalle=f"{contacto.get_canal_display()} · {contacto.get_resultado_display()}",
        por_supervisor=por_supervisor,
    )
    return contacto


# ---------------------------------------------------------------------------
# Derivar y cancelar
# ---------------------------------------------------------------------------


def _mensaje_ya_derivado(caso):
    vigente = Derivacion.objects.filter(clave_vigente=caso.pk).select_related("dispositivo").first()
    if vigente is None:
        return f"El caso {caso.numero} ya no está en gestión. Recargá la ficha."
    return f"El caso ya fue derivado a {vigente.dispositivo.nombre} a las {_hora(vigente.creado)}. Recargá la ficha."


@transaction.atomic
def derivar_caso(caso, usuario, dispositivo, plazas_pedidas, confirmar_faltantes=False):
    """Deriva un caso ``EN_GESTION`` a ``dispositivo``: queda ``DERIVADO`` con una derivación ``PENDIENTE``.

    El dueño o quien supervisa (HU-2.3). Reglas:

    * El dispositivo tiene que ser elegible (``selectors.emergencia.dispositivo_elegible``).
    * Las plazas libres son las de ``ocupacion_de_plazas``, la misma cuenta que ve la
      institución (RN-2.3). Con **0 libres** no se deriva (``ValidationError``). Con menos
      libres que ``plazas_pedidas`` hace falta ``confirmar_faltantes=True``; si no,
      :class:`FaltanPlazas` (RN-2.5). ``plazas_pedidas`` guarda lo pedido.
    * **No reserva plazas**: las reserva el dispositivo al aceptar, que es quien elige las
      camas. Por eso la cuenta se lee sin candado: es una foto para decidir, no una
      garantía.
    * ``vence_en`` es ahora más la vigencia configurada en E7 (RN-2.7).
    * Un caso tiene a lo sumo una derivación vigente (RN-2.6). Si el caso ya está derivado
      —la segunda pestaña— levanta :class:`EstadoCambio` diciendo a dónde y a qué hora. Si
      el estado dice «en gestión» pero la base ya tiene una vigente, el ``UNIQUE`` de
      ``clave_vigente`` la rechaza y eso también es un :class:`EstadoCambio`, nunca un
      ``IntegrityError`` crudo.

    Devuelve la ``Derivacion``.
    """

    _exigir_mesa(usuario)
    try:
        plazas_pedidas = int(plazas_pedidas)
    except (TypeError, ValueError):
        plazas_pedidas = 0
    if plazas_pedidas < 1:
        raise ValidationError({"plazas_pedidas": "Pedí al menos una plaza."})

    caso = _bloquear_caso(caso)
    if caso.estado != Estado.EN_GESTION:
        _exigir_estado(caso, Estado.EN_GESTION, mensaje=_mensaje_ya_derivado(caso))
    por_supervisor = _exigir_duenio_o_supervisor(caso, usuario)

    if not dispositivo_elegible(dispositivo):
        raise ValidationError({"dispositivo": DISPOSITIVO_NO_ELEGIBLE})
    libres = max(ocupacion_de_plazas(dispositivo).de(dispositivo).conteo.disponibles, 0)
    if libres < 1:
        raise ValidationError({"dispositivo": SIN_PLAZAS})
    if libres < plazas_pedidas and not confirmar_faltantes:
        raise FaltanPlazas(libres=libres, pedidas=plazas_pedidas)

    ahora = timezone.now()
    derivacion = Derivacion(
        caso=caso,
        dispositivo=dispositivo,
        estado=Derivacion.Estado.PENDIENTE,
        plazas_pedidas=plazas_pedidas,
        vence_en=ahora + timedelta(minutes=sla_vigente().vigencia_derivacion_min),
        derivada_por=usuario,
    )
    try:
        # Anidada: el UNIQUE de `clave_vigente` deja sana la transacción de afuera.
        with transaction.atomic():
            derivacion.save()
    except IntegrityError:
        raise EstadoCambio(
            f"El caso {caso.numero} ya tiene una derivación vigente. Recargá la ficha.",
            estado_actual=caso.estado,
            caso=caso,
        ) from None

    caso.estado = Estado.DERIVADO
    caso.marcar("derivado_en", ahora)
    caso.save(update_fields=["estado", "derivado_en", "modificado"])
    faltan = f" · faltan {plazas_pedidas - libres}" if libres < plazas_pedidas else ""
    _trazar(
        caso,
        usuario,
        Accion.DERIVADO,
        estado_anterior=Estado.EN_GESTION,
        detalle=f"Derivado a {dispositivo.nombre} · {plazas_pedidas} plazas pedidas{faltan}",
        por_supervisor=por_supervisor,
    )
    return derivacion


@transaction.atomic
def cancelar_derivacion(derivacion, usuario, motivo):
    """Cancela una derivación ``PENDIENTE``: el caso vuelve a ``EN_GESTION`` con el mismo dueño.

    El dueño del caso o quien supervisa, con motivo obligatorio. Bloquea **primero el
    caso y después la derivación** (ver el orden de candados del módulo). Si el
    dispositivo ya la aceptó o la rechazó, o ya venció, levanta :class:`EstadoCambio`.
    ``derivado_en`` no se borra (RN-2.9). Devuelve la ``Derivacion``.
    """

    _exigir_mesa(usuario)
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValidationError({"motivo": "Indicá por qué se cancela la derivación."})
    if len(motivo) > 200:
        raise ValidationError({"motivo": "El motivo no puede tener más de 200 caracteres."})

    caso = _bloquear_caso(derivacion.caso_id)
    derivacion = Derivacion.objects.select_for_update().get(pk=derivacion.pk)
    if derivacion.estado != Derivacion.Estado.PENDIENTE or caso.estado != Estado.DERIVADO:
        raise EstadoCambio(
            f"La derivación ya no está pendiente ({derivacion.get_estado_display().lower()}). Recargá la ficha.",
            estado_actual=caso.estado,
            caso=caso,
        )
    por_supervisor = _exigir_duenio_o_supervisor(caso, usuario)

    ahora = timezone.now()
    derivacion.estado = Derivacion.Estado.CANCELADA
    derivacion.motivo = motivo
    derivacion.respondida_por = usuario
    derivacion.respondida_en = ahora
    derivacion.save(update_fields=["estado", "motivo", "respondida_por", "respondida_en", "modificado"])
    caso.estado = Estado.EN_GESTION
    caso.save(update_fields=["estado", "modificado"])
    _trazar(
        caso,
        usuario,
        Accion.DERIVACION_CANCELADA,
        estado_anterior=Estado.DERIVADO,
        detalle=f"Derivación a {derivacion.dispositivo.nombre} cancelada: {motivo}",
        por_supervisor=por_supervisor,
    )
    return derivacion


# ---------------------------------------------------------------------------
# Cerrar
# ---------------------------------------------------------------------------


@transaction.atomic
def cerrar_sin_alojamiento(caso, usuario, motivo, observacion=""):
    """Cierra un caso ``EN_GESTION`` que no necesita alojamiento (HU-2.7, RN-2.13).

    El dueño o quien supervisa. El motivo sale de :data:`MOTIVOS_DE_CIERRE_MANUAL`; con
    «Otro» la observación es obligatoria. ``CERRADO`` es terminal: no se reabre.

    Un caso ``DERIVADO`` no se cierra: primero se cancela la derivación (RN-2.6). Eso, y
    cualquier otro estado, es un :class:`EstadoCambio`.
    """

    _exigir_mesa(usuario)
    observacion = (observacion or "").strip()
    if motivo not in MOTIVOS_DE_CIERRE_MANUAL:
        raise ValidationError({"motivo": "Elegí el motivo del cierre."})
    if motivo == CasoEmergencia.MotivoCierre.OTRO and not observacion:
        raise ValidationError({"observacion": "Con el motivo «Otro», contá qué pasó."})

    caso = _bloquear_caso(caso)
    mensaje = f"El caso {caso.numero} ya no está en gestión. Recargá la ficha."
    if caso.estado == Estado.DERIVADO:
        mensaje = "El caso está derivado: cancelá la derivación antes de cerrarlo."
    _exigir_estado(caso, Estado.EN_GESTION, mensaje=mensaje)
    por_supervisor = _exigir_duenio_o_supervisor(caso, usuario)

    caso.estado = Estado.CERRADO
    caso.marcar("cerrado_en", timezone.now())
    caso.motivo_cierre = motivo
    caso.observacion_cierre = observacion
    caso.save(update_fields=["estado", "cerrado_en", "motivo_cierre", "observacion_cierre", "modificado"])
    _trazar(
        caso,
        usuario,
        Accion.CERRADO,
        estado_anterior=Estado.EN_GESTION,
        detalle=f"Cerrado sin alojamiento: {caso.get_motivo_cierre_display()}",
        por_supervisor=por_supervisor,
    )
    return caso
