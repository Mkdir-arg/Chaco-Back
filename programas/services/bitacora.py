"""Turnos y bitácora del dispositivo (MVP v2, etapa 3 · #695).

Reemplaza al parte diario, que era una fila por turno que el turno siguiente
sobrescribía. Acá viven tres cosas:

1. **El turno vigente y la fecha operativa** (`turno_vigente`, `turnos_del_dia`). Es el
   único lugar que sabe que la Noche 22-06 que empieza el lunes es **del lunes** aunque
   sea martes 03:00. El censo por turno y por día (task 31) se apoya en esto: no hay
   otra cuenta de la fecha operativa en el sistema.
2. **La configuración de turnos**, con la regla que el esquema no puede decir: dos
   turnos activos del mismo dispositivo no se superponen, porque si no «el turno
   vigente» deja de ser uno solo.
3. **La bitácora**: cargar una novedad y corregirla. Corregir **agrega** una versión;
   la anterior sigue ahí. Ver el docstring de `programas.models.EntradaBitacora`.
4. **Las novedades automáticas** (`anotar_en_bitacora`): el ingreso, el egreso y el
   cambio de plaza dejan la suya, como en P10, en la misma transacción que el cambio y
   colgadas del `MovimientoEstadia` que las generó, que es lo que impide duplicarlas.

Hora local, siempre
-------------------

Todo se calcula sobre `timezone.localtime(momento)` y en Python. Nada de `__date` ni de
`Trunc*` sobre un `DateTimeField`: en ECOM la base no tiene tablas de zona horaria,
Django lo traduce a `CONVERT_TZ` y la consulta devuelve `NULL` solo en producción. Por
eso la entrada **guarda** su fecha operativa en un `DateField`.

Lo que no está acá
------------------

El pase de guardia (abrir y cerrar el turno, quién entregó y quién recibió) y la
regularización de días anteriores. Mientras la regularización no exista, una novedad
solo se carga —y solo se corrige— **dentro del turno en curso**. Las automáticas son la
excepción a esa ventana, y por el mismo motivo: no las escribe un operador, las escribe
un hecho, y el hecho puede haber pasado en un turno anterior.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from core.archivos import anotar_archivo_escrito, archivos_atomicos
from core.validators import validar_adjunto
from programas.models import (
    AdjuntoBitacora,
    Dispositivo,
    EntradaBitacora,
    Estadia,
    MovimientoEstadia,
    TrazaDispositivo,
    Turno,
)
from programas.services.dispositivos import puede_operar_dispositivo

#: Cargar y corregir novedades del turno.
CAP_BITACORA = "dispositivo.bitacora"
#: Los turnos son la organización de la institución, como sus sectores: se configuran
#: con la misma capacidad que el resto del legajo.
CAP_EDITAR = "dispositivo.editar"

_SEGUNDOS_DEL_DIA = 24 * 60 * 60

#: Cuántos archivos puede llevar una entrada, sumando los heredados de la versión que
#: corrige. Un acta, unas fotos: más que esto no es una novedad, es un expediente.
MAX_ADJUNTOS_POR_ENTRADA = 10


# --------------------------------------------------------------------------- #
# Turno vigente y fecha operativa
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class TurnoOperativo:
    """Un turno situado en el calendario: cuál, de qué fecha operativa y su ventana.

    `inicio` y `fin` son instantes con zona, y la ventana es `[inicio, fin)`: las 14:00
    en punto ya son de la Tarde. Son lo que el censo necesita para contar ingresos y
    egresos del turno comparando instantes, sin truncar fechas en la base.
    """

    turno: Turno
    fecha_operativa: date
    inicio: datetime
    fin: datetime


def _segundos(hora: time) -> int:
    return hora.hour * 3600 + hora.minute * 60 + hora.second


def _fecha_operativa_si_contiene(turno: Turno, hora: time, dia: date) -> date | None:
    """La fecha operativa del turno si la hora local cae adentro, o `None`.

    `dia` es la fecha local del momento. Un turno que cruza la medianoche contiene la
    hora de dos maneras: después de su inicio (es de hoy) o antes de su fin (empezó
    ayer, y es de ayer).
    """

    desde, hasta = turno.hora_desde, turno.hora_hasta
    if desde < hasta:
        return dia if desde <= hora < hasta else None
    # Nocturno (22-06) o guardia de 24 h (08-08).
    if hora >= desde:
        return dia
    if hora < hasta:
        return dia - timedelta(days=1)
    return None


def turnos_activos(dispositivo):
    """Los turnos activos del dispositivo, en su orden. Una consulta."""

    return list(Turno.objects.filter(dispositivo=dispositivo, activo=True).order_by("orden", "hora_desde", "id"))


def turno_vigente(dispositivo, momento=None, *, turnos=None) -> TurnoOperativo | None:
    """El turno que rige en `momento` y la fecha operativa a la que pertenece.

    `None` si el dispositivo no tiene turnos o el momento cae en un hueco entre dos.
    `turnos` permite pasar la lista ya cargada (`turnos_activos`) para resolver muchos
    momentos sin una consulta por cada uno, que es lo que hace el censo.
    """

    local = timezone.localtime(momento or timezone.now())
    hora, dia = local.time(), local.date()
    for turno in turnos if turnos is not None else turnos_activos(dispositivo):
        fecha = _fecha_operativa_si_contiene(turno, hora, dia)
        if fecha is not None:
            inicio, fin = turno.ventana(fecha)
            return TurnoOperativo(turno=turno, fecha_operativa=fecha, inicio=inicio, fin=fin)
    return None


def turnos_del_dia(dispositivo, fecha_operativa, *, turnos=None) -> list[TurnoOperativo]:
    """Los turnos de una fecha operativa, ordenados por su inicio.

    La ventana del día es de la primera hora del primer turno a la última del último:
    con Mañana 06-14, Tarde 14-22 y Noche 22-06, el lunes va del lunes 06:00 al martes
    06:00. Lo que el censo diario suma son estas ventanas, no el día de calendario.
    """

    situados = []
    for turno in turnos if turnos is not None else turnos_activos(dispositivo):
        inicio, fin = turno.ventana(fecha_operativa)
        situados.append(TurnoOperativo(turno=turno, fecha_operativa=fecha_operativa, inicio=inicio, fin=fin))
    return sorted(situados, key=lambda situado: situado.inicio)


# --------------------------------------------------------------------------- #
# Configuración de turnos
# --------------------------------------------------------------------------- #


def _tramos(desde: time, hasta: time) -> list[tuple[int, int]]:
    """El turno como tramos de segundos dentro de un día: el nocturno son dos."""

    a, b = _segundos(desde), _segundos(hasta)
    if a < b:
        return [(a, b)]
    if a == b:  # guardia de 24 h
        return [(0, _SEGUNDOS_DEL_DIA)]
    return [(a, _SEGUNDOS_DEL_DIA), (0, b)]


def _se_superponen(desde_a, hasta_a, desde_b, hasta_b) -> bool:
    return any(
        inicio_a < fin_b and inicio_b < fin_a
        for inicio_a, fin_a in _tramos(desde_a, hasta_a)
        for inicio_b, fin_b in _tramos(desde_b, hasta_b)
    )


def _exigir_sin_superposicion(dispositivo, *, nombre, hora_desde, hora_hasta, excepto=None):
    """Falla si el horario pisa el de otro turno activo. Con el dispositivo ya bloqueado."""

    otros = Turno.objects.filter(dispositivo=dispositivo, activo=True)
    if excepto is not None:
        otros = otros.exclude(pk=excepto.pk)
    for otro in otros:
        if _se_superponen(hora_desde, hora_hasta, otro.hora_desde, otro.hora_hasta):
            raise ValidationError({"hora_desde": f"El horario de «{nombre}» se superpone con el turno «{otro}»."})


def _bloquear_dispositivo(dispositivo):
    """Serializa a quienes configuran turnos del mismo dispositivo.

    Sin el bloqueo, dos altas simultáneas de turnos superpuestos pasan las dos el
    control —cada una mira la base sin la otra— y el turno vigente deja de ser uno.
    """

    return Dispositivo.objects.select_for_update().get(pk=dispositivo.pk)


def _horario(turno):
    return f"{turno.nombre} · {turno.hora_desde:%H:%M}–{turno.hora_hasta:%H:%M}"


def _trazar_turno(dispositivo, usuario, accion, detalle):
    """La configuración de turnos deja rastro en el historial del dispositivo (#699)."""

    TrazaDispositivo.objects.create(dispositivo=dispositivo, usuario=usuario, accion=accion, detalle=detalle)


@transaction.atomic
def crear_turno(*, dispositivo, usuario, nombre, hora_desde, hora_hasta, orden=0):
    """Da de alta un turno del dispositivo. Falla si se superpone con otro activo."""

    if not puede_operar_dispositivo(usuario, dispositivo, CAP_EDITAR):
        raise PermissionDenied("No tenés alcance para configurar los turnos de este dispositivo.")
    nombre = (nombre or "").strip()
    if not nombre:
        raise ValidationError({"nombre": "El turno necesita un nombre."})

    dispositivo = _bloquear_dispositivo(dispositivo)
    if Turno.objects.filter(dispositivo=dispositivo, nombre=nombre).exists():
        raise ValidationError({"nombre": "Ya hay un turno con ese nombre en este dispositivo."})
    _exigir_sin_superposicion(dispositivo, nombre=nombre, hora_desde=hora_desde, hora_hasta=hora_hasta)
    turno = Turno.objects.create(
        dispositivo=dispositivo,
        nombre=nombre,
        hora_desde=hora_desde,
        hora_hasta=hora_hasta,
        orden=orden,
    )
    _trazar_turno(dispositivo, usuario, "TURNO_CREADO", _horario(turno))
    return turno


@transaction.atomic
def editar_turno(*, turno, usuario, nombre=None, hora_desde=None, hora_hasta=None, orden=None, activo=None):
    """Cambia el horario, el nombre o el orden de un turno, o lo da de baja.

    Las entradas ya cargadas no se mueven: guardan su turno y su fecha operativa, así
    que cambiar el horario rige de acá en adelante. Un turno **no se borra** —sus
    entradas lo apuntan con `PROTECT`—: se desactiva.
    """

    if not puede_operar_dispositivo(usuario, turno.dispositivo, CAP_EDITAR):
        raise PermissionDenied("No tenés alcance para configurar los turnos de este dispositivo.")

    dispositivo = _bloquear_dispositivo(turno.dispositivo)
    turno = Turno.objects.get(pk=turno.pk)
    antes = _horario(turno)
    estaba_activo = turno.activo
    if nombre is not None:
        nombre = nombre.strip()
        if not nombre:
            raise ValidationError({"nombre": "El turno necesita un nombre."})
        if Turno.objects.filter(dispositivo=dispositivo, nombre=nombre).exclude(pk=turno.pk).exists():
            raise ValidationError({"nombre": "Ya hay un turno con ese nombre en este dispositivo."})
        turno.nombre = nombre
    if hora_desde is not None:
        turno.hora_desde = hora_desde
    if hora_hasta is not None:
        turno.hora_hasta = hora_hasta
    if orden is not None:
        turno.orden = orden
    if activo is not None:
        turno.activo = bool(activo)
    if turno.activo:
        _exigir_sin_superposicion(
            dispositivo, nombre=turno.nombre, hora_desde=turno.hora_desde, hora_hasta=turno.hora_hasta, excepto=turno
        )
    turno.save()
    despues = _horario(turno)
    detalle = despues if despues == antes else f"{antes} → {despues}"
    if estaba_activo and not turno.activo:
        detalle += " · dado de baja"
    elif turno.activo and not estaba_activo:
        detalle += " · reactivado"
    _trazar_turno(dispositivo, usuario, "TURNO_EDITADO", detalle)
    return turno


# --------------------------------------------------------------------------- #
# Bitácora
# --------------------------------------------------------------------------- #

#: Un solo mensaje para la estadía de otro dispositivo, la que no existe y la de alguien
#: que no estaba alojado en ese momento: distinguirlos sería un oráculo de estadías ajenas.
PERSONAS_FUERA_DEL_TURNO = "Alguna de las personas no estaba alojada en este dispositivo en ese momento."


def _exigir_turno_en_curso(dispositivo, momento, ahora):
    """El turno de `momento`, que tiene que ser el que está en curso.

    Cargar una novedad de un turno que ya terminó es **regularizar**, y la
    regularización de días anteriores no es parte de esta etapa (P14 la prevé con su
    ventana configurable y P15 con su propia capacidad).
    """

    turnos = turnos_activos(dispositivo)
    en_curso = turno_vigente(dispositivo, ahora, turnos=turnos)
    if en_curso is None:
        raise ValidationError({"turno": "El dispositivo no tiene un turno configurado para este horario."})
    del_momento = turno_vigente(dispositivo, momento, turnos=turnos)
    if (
        del_momento is None
        or del_momento.turno.pk != en_curso.turno.pk
        or del_momento.fecha_operativa != en_curso.fecha_operativa
    ):
        raise ValidationError(
            {"momento": "Solo se cargan y corrigen novedades del turno en curso. Los turnos anteriores se regularizan."}
        )
    return en_curso


def _estadias_del_momento(dispositivo, personas, momento):
    """Las estadías involucradas, que tienen que ser de acá y estar abiertas en ese momento."""

    ids = set()
    for persona in personas or ():
        valor = persona.pk if isinstance(persona, Estadia) else persona
        # Del formulario llegan como texto: «5» y 5 son la misma estadía, y «abc» es un
        # dato inválido —un 400—, no un `ValueError` del ORM que termina en 500.
        try:
            ids.add(int(str(valor).strip()))
        except (TypeError, ValueError):
            raise ValidationError({"personas": PERSONAS_FUERA_DEL_TURNO}) from None
    if not ids:
        return []
    estadias = list(
        Estadia.objects.filter(pk__in=ids, dispositivo=dispositivo, fecha_ingreso__lte=momento).filter(
            Q(fecha_egreso__isnull=True) | Q(fecha_egreso__gte=momento)
        )
    )
    if len(estadias) != len(ids):
        raise ValidationError({"personas": PERSONAS_FUERA_DEL_TURNO})
    return estadias


def _guardar_adjuntos(dispositivo, usuario, archivos, *, heredados=0):
    """Valida **todos** los archivos antes de escribir el primero, y anota lo escrito.

    Con `archivos_atomicos` por arriba, si después algo falla los archivos ya escritos
    se borran: el storage no vuelve atrás con la transacción. `heredados` son los que la
    entrada ya trae de la versión que corrige, y cuentan para el tope.
    """

    archivos = list(archivos or ())
    if heredados + len(archivos) > MAX_ADJUNTOS_POR_ENTRADA:
        raise ValidationError({"adjuntos": f"Una novedad lleva hasta {MAX_ADJUNTOS_POR_ENTRADA} archivos."})
    for archivo in archivos:
        validar_adjunto(archivo)
    adjuntos = []
    for archivo in archivos:
        adjunto = AdjuntoBitacora(
            dispositivo=dispositivo,
            archivo=archivo,
            nombre_original=(getattr(archivo, "name", "") or "")[:255],
            subido_por=usuario,
        )
        adjunto.save()
        anotar_archivo_escrito(adjunto.archivo, asignado=archivo)
        adjuntos.append(adjunto)
    return adjuntos


@archivos_atomicos
@transaction.atomic
def registrar_entrada(*, dispositivo, usuario, tipo, texto, momento=None, personas=(), adjuntos=()):
    """Carga una novedad del turno en curso. Devuelve la `EntradaBitacora` (versión 1).

    `momento` es cuándo pasó; por omisión, ahora. Puede ser anterior a la carga —se
    anota a las 16:52 lo que pasó a las 16:10— pero tiene que caer en el turno en curso.
    `personas` son estadías del dispositivo abiertas en ese momento; `adjuntos`, los
    archivos subidos.
    """

    if not puede_operar_dispositivo(usuario, dispositivo, CAP_BITACORA):
        raise PermissionDenied("No tenés alcance para cargar la bitácora de este dispositivo.")
    if dispositivo.estado != Dispositivo.Estado.ACTIVO:
        raise ValidationError({"dispositivo": "Solo se carga la bitácora de un dispositivo activo."})

    ahora = timezone.now()
    momento = momento or ahora
    if momento > ahora:
        raise ValidationError({"momento": "La novedad no puede ser futura."})
    situado = _exigir_turno_en_curso(dispositivo, momento, ahora)

    entrada = EntradaBitacora(
        dispositivo=dispositivo,
        turno=situado.turno,
        fecha_operativa=situado.fecha_operativa,
        momento=momento,
        responsable=usuario,
        tipo=tipo,
        origen=EntradaBitacora.Origen.MANUAL,
        texto=(texto or "").strip(),
    )
    entrada.clean()
    estadias = _estadias_del_momento(dispositivo, personas, momento)
    archivos = _guardar_adjuntos(dispositivo, usuario, adjuntos)
    entrada.save()
    _vincular(entrada, estadias, archivos)
    return entrada


def _vincular(entrada, estadias, adjuntos):
    """Las personas y los adjuntos de una versión, **una sola vez**, al crearla.

    Fuera de acá el modelo los rechaza (`m2m_changed`): una versión ya guardada no cambia
    sus relaciones, igual que no cambia su texto. La marca vale solo mientras dura esto.
    """

    entrada._relaciones_abiertas = True
    try:
        if estadias:
            entrada.personas.set(estadias)
        if adjuntos:
            entrada.adjuntos.set(adjuntos)
    finally:
        entrada._relaciones_abiertas = False


# --------------------------------------------------------------------------- #
# Novedades automáticas (P10: «automática»)
# --------------------------------------------------------------------------- #

#: Qué novedad deja cada movimiento de la estadía. Los tipos ya estaban en el modelo
#: desde el Cambio 274 y **ningún servicio los escribía**: P10 los muestra como entradas
#: «automática» del turno (el ingreso, el egreso y el cambio de plaza), y de ahí salen.
#: `CAMBIO_ESTADO` no está porque ningún servicio lo emite.
NOVEDAD_POR_MOVIMIENTO = {
    MovimientoEstadia.Tipo.INGRESO: EntradaBitacora.Tipo.INGRESO,
    MovimientoEstadia.Tipo.EGRESO: EntradaBitacora.Tipo.EGRESO,
    MovimientoEstadia.Tipo.CAMBIO_PLAZA: EntradaBitacora.Tipo.MOVIMIENTO,
    MovimientoEstadia.Tipo.CAMBIO_SECTOR: EntradaBitacora.Tipo.MOVIMIENTO,
}


def _texto_automatico(movimiento) -> str:
    """Qué dice la novedad, **sin el nombre de la persona**.

    El mockup pone el nombre en negrita; acá va en `personas`, que es lo que la pantalla
    muestra solo con `ciudadano.ver` (Cambio 271). Si el nombre estuviera en el texto, la
    bitácora se lo contaría a cualquiera que tenga `dispositivo.ver`, que es menos.

    Las plazas se nombran por su código y nunca por su sector: el movimiento trae la
    plaza que el servicio ya tenía en la mano, y leerle el sector sería una consulta más
    dentro de la transacción que aloja o egresa a alguien.
    """

    tipo = movimiento.tipo
    if tipo == MovimientoEstadia.Tipo.INGRESO:
        destino = movimiento.plaza_destino
        texto = f"Ingreso · plaza {destino.codigo}" if destino is not None else "Ingreso · sin plaza asignada"
    elif tipo == MovimientoEstadia.Tipo.EGRESO:
        texto = "Egreso"
    else:
        origen = movimiento.plaza_origen
        texto = (
            f"{movimiento.get_tipo_display()} · "
            f"{origen.codigo if origen is not None else 'sin plaza'} → {movimiento.plaza_destino.codigo}"
        )
    return f"{texto} · motivo: {movimiento.motivo}" if movimiento.motivo else texto


def anotar_en_bitacora(movimiento):
    """La novedad automática de un movimiento de estadía. Devuelve la entrada, o `None`.

    La llaman `ingresar_persona`, `egresar_persona` y `cambiar_plaza` **en la misma
    transacción** que el cambio: si el alta se deshace, la novedad también. No pide
    capacidad ni mira el estado del dispositivo —quien llegó hasta acá ya pasó el control
    del servicio que la genera, y lo que se registra es un hecho que el sistema aceptó—,
    y no pasa por `_exigir_turno_en_curso`: un ingreso se puede cargar tarde, y su novedad
    es del turno en el que **pasó**, no del que corre cuando se escribió.

    `None` en dos casos, y ninguno inventa nada:

    * **El momento cae en un hueco sin turno**, o el dispositivo no tiene turnos
      configurados. Una entrada necesita turno y fecha operativa, y no hay de dónde
      sacarlos; la alerta «dispositivo activo sin turnos activos» (Cambio 281) ya avisa.
    * El movimiento no tiene responsable (solo los que reconstruyó `programas.0089`).

    **No se duplica.** La entrada cuelga del movimiento con un uno a uno, y el movimiento
    es nuevo en cada llamada: un reintento que vuelva a correr el servicio crea otro
    movimiento o falla antes (la clave de alojamiento, la estadía ya cerrada, la plaza que
    ya es la suya), y escribir dos novedades del **mismo** movimiento lo rechaza la base.
    """

    tipo = NOVEDAD_POR_MOVIMIENTO.get(movimiento.tipo)
    if tipo is None or movimiento.responsable_id is None:
        return None
    situado = turno_vigente(movimiento.dispositivo_id, movimiento.momento)
    if situado is None:
        return None

    entrada = EntradaBitacora(
        dispositivo_id=movimiento.dispositivo_id,
        turno=situado.turno,
        fecha_operativa=situado.fecha_operativa,
        momento=movimiento.momento,
        responsable_id=movimiento.responsable_id,
        tipo=tipo,
        origen=EntradaBitacora.Origen.AUTOMATICA,
        movimiento=movimiento,
        texto=_texto_automatico(movimiento),
    )
    entrada.clean()
    entrada.save()
    # La persona involucrada es la estadía, como en cualquier novedad: su id alcanza, y
    # deja la novedad colgando de la estadía para la solapa Novedades de P7.
    _vincular(entrada, [movimiento.estadia_id], [])
    return entrada


CORRECCION_CONCURRENTE = (
    "La entrada ya fue corregida mientras la editabas: revisá la versión vigente y, si hace falta, corregí esa."
)


@archivos_atomicos
@transaction.atomic
def corregir_entrada(
    *, entrada, usuario, texto, tipo=None, personas=None, adjuntos_nuevos=(), quitar_adjuntos=(), motivo=""
):
    """Corrige una novedad **agregando** una versión. La que se corrige no se toca.

    `entrada` es la versión que el operador tenía delante. Si otro ya la corrigió, falla
    con `CORRECCION_CONCURRENTE` y no se pisa nada: las dos correcciones nunca se
    mezclan, y el segundo ve la del primero antes de decidir.

    Lo que no se pasa se hereda de la versión corregida: el tipo, las personas y los
    adjuntos. `quitar_adjuntos` saca de **esta** versión adjuntos que la anterior tenía
    —el archivo y la versión anterior quedan—. El momento, el turno y la fecha operativa
    no se corrigen: son de cuándo pasó, no de lo que se dijo.
    """

    if not puede_operar_dispositivo(usuario, entrada.dispositivo, CAP_BITACORA):
        raise PermissionDenied("No tenés alcance para cargar la bitácora de este dispositivo.")

    # Primero la original, siempre: es la fila común a todas las correcciones de la
    # cadena, así que dos operadores que corrigen la misma entrada se forman acá, en el
    # mismo orden, y el segundo ve la versión del primero. Sin `select_related`: en
    # MySQL un `FOR UPDATE` con JOIN bloquea también las filas unidas.
    EntradaBitacora.objects.select_for_update().get(pk=entrada.raiz_id)
    corregida = EntradaBitacora.objects.select_related("dispositivo").get(pk=entrada.pk)
    if EntradaBitacora.objects.filter(version_anterior=corregida).exists():
        raise ValidationError({"entrada": CORRECCION_CONCURRENTE})
    if corregida.origen != EntradaBitacora.Origen.MANUAL:
        raise ValidationError({"entrada": "Las novedades automáticas se corrigen desde la estadía que las generó."})
    if corregida.dispositivo.estado != Dispositivo.Estado.ACTIVO:
        raise ValidationError({"dispositivo": "Solo se carga la bitácora de un dispositivo activo."})

    # Contra el turno y la fecha **guardados** en la entrada, no recalculados desde su
    # momento: si la configuración de turnos cambió después, recalcular podría ubicar
    # una novedad del turno que ya terminó en el que rige ahora, y dejarla corregir.
    en_curso = turno_vigente(corregida.dispositivo, timezone.now())
    if (
        en_curso is None
        or en_curso.turno.pk != corregida.turno_id
        or en_curso.fecha_operativa != corregida.fecha_operativa
    ):
        raise ValidationError(
            {"entrada": "Solo se corrigen novedades del turno en curso. Los turnos anteriores se regularizan."}
        )

    nueva = EntradaBitacora(
        dispositivo=corregida.dispositivo,
        turno_id=corregida.turno_id,
        fecha_operativa=corregida.fecha_operativa,
        momento=corregida.momento,
        responsable=usuario,
        tipo=tipo or corregida.tipo,
        origen=corregida.origen,
        texto=(texto or "").strip(),
        version=corregida.version + 1,
        entrada_original_id=corregida.raiz_id,
        version_anterior=corregida,
        motivo_correccion=(motivo or "").strip()[:255],
    )
    nueva.clean()
    if personas is None:
        estadias = list(corregida.personas.all())
    else:
        estadias = _estadias_del_momento(corregida.dispositivo, personas, corregida.momento)
    quitar = {adjunto.pk if isinstance(adjunto, AdjuntoBitacora) else adjunto for adjunto in quitar_adjuntos or ()}
    heredados = [adjunto for adjunto in corregida.adjuntos.all() if adjunto.pk not in quitar]
    archivos = _guardar_adjuntos(corregida.dispositivo, usuario, adjuntos_nuevos, heredados=len(heredados))
    try:
        # La red de abajo: si alguien llegara sin pasar por el bloqueo de arriba, el
        # UNIQUE de `version_anterior` rechaza la segunda corrección de la misma versión.
        with transaction.atomic():
            nueva.save()
    except IntegrityError as error:
        raise ValidationError({"entrada": CORRECCION_CONCURRENTE}) from error
    _vincular(nueva, estadias, [*heredados, *archivos])
    return nueva
