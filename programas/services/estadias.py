"""Ingreso, egreso, cambio de plaza y reserva de plazas (MVP v2, etapas 2 y 3 · #689, #694).

Acá viven las tres reglas de la etapa 2 que **ninguna restricción de la base cubre**, y
el servicio existe justamente porque no se pueden delegar al esquema:

1. **`FUERA_SERVICIO` no se declara sobre una plaza tomada.** Sacar de servicio una
   plaza con estadía activa, reserva o préstamo vigente **falla**: primero se reubica.
   Así el mapa nunca muestra OCUPADA y FUERA_SERVICIO a la vez, que es la contradicción
   que `Plaza.estado` evita guardando solo lo operativo.
2. **La exclusión mutua va con `select_for_update()`, no con un `UniqueConstraint`
   condicional.** Ver el porqué completo en el docstring de `programas.models.Estadia`:
   un constraint con `condition=` Django lo **ignora** en MySQL y en MariaDB, pasa los
   tests en SQLite y no existe en producción. Acá la plaza se toma bloqueando su fila
   dentro de `transaction.atomic()`.
3. **Un solo origen.** Nada de lo derivado se cuenta acá: las cifras salen de
   `programas.services.ocupacion`.

Desde la etapa 3, cada cambio que le pasa a la persona —ingreso, cambio de sector o de
plaza, egreso— deja además su `MovimientoEstadia` en la misma transacción, por
`programas.services.movimientos.registrar_movimiento`. La línea de tiempo de la estadía
sale de ahí y de ningún otro lado.

Y desde ese mismo movimiento —en la misma transacción— sale la **novedad automática de
la bitácora del turno** (`programas.services.bitacora.anotar_en_bitacora`), que es lo
que P10 muestra como «automática». Cuelga del movimiento con un uno a uno, así que no
se puede duplicar, y si el dispositivo no tiene un turno para ese momento no se escribe
ninguna: no se inventa un turno.

Por qué el bloqueo alcanza
--------------------------

`_tomar_plaza` hace `SELECT ... FOR UPDATE` sobre la fila de la plaza **antes** de
preguntar si está libre. Quien compita por la misma plaza queda esperando esa fila, así
que las comprobaciones y el alta corren serializadas. Que las comprobaciones vean el
alta del que ganó depende del nivel de aislamiento, y el proyecto lo fija explícito:
`config/settings.py` manda `"isolation_level": "read committed"` en las `OPTIONS` de la
base, y en READ COMMITTED cada consulta toma su propia foto. Con el REPEATABLE READ por
omisión de InnoDB esto **no** sería cierto: la foto se toma en la primera lectura no
bloqueante de la transacción —la del control de permisos, antes del `FOR UPDATE`— y el
segundo operador no vería la estadía del primero.

El orden de los candados: plaza y después reserva
-------------------------------------------------

`ingresar_persona` y `liberar_reserva` piden las dos filas en ese orden. Invertirlo
puede formar un ciclo: InnoDB aborta una transacción con `ERROR 1213`, que el servicio
no traduce a un error de dominio.

Lo que lo hace fácil de romper es que la mitad de los candados no se ven en el código.
`ReservaPlaza` y `Estadia` declaran un índice `(plaza, estado)` con `plaza_id` a la
izquierda. Cuando InnoDB usa ese índice para la FK, un `UPDATE` que cambie
`estado` reescribe esa entrada y puede pedir un **lock compartido sobre la fila de
la plaza**. O sea que escribir una reserva toma la plaza aunque el código no la nombre.
Por eso `liberar_reserva` bloquea la plaza antes de la reserva aunque no tenga nada que
preguntarle. Lo verifica `programas.tests.test_dispositivos_concurrencia`.

Al ordenar candados hay que contemplar también los que toma InnoDB al modificar
índices usados por una FK. `OrdenDeLosCandadosTests` fija el orden por la secuencia de
llamadas en SQLite; `programas.tests.test_dispositivos_concurrencia` corre la carrera real.

La verificación en toda la red
------------------------------

`verificar_alojamiento_en_red` es lo único que puede preguntar por una persona **fuera
del alcance de quien pregunta**. Por eso exige ella misma `dispositivo.admitir` en el
programa —no confía en que la vista se acuerde— y su resultado está partido en dos:

* **Dentro del alcance** (`dispositivos_en_alcance`, por capacidad y asignación, nunca por
  nombre de grupo): se devuelve todo —institución, plaza, desde cuándo y a quién
  reclamarle—.
* **Fuera del alcance**: se devuelve **que existe** una estadía abierta y nada más. Ni
  el dispositivo, ni su código, ni la localidad, ni la plaza, ni la fecha. Lo que viaja
  es la clave de alojamiento, que se deriva de la persona que el usuario ya tiene
  delante: no agrega ni un dato nuevo sobre la institución y alcanza para que la
  coordinación del programa encuentre la estadía y la resuelva.

La existencia se filtra a propósito: sin ella no hay forma de explicar por qué el
ingreso se rechaza, y el rechazo es el requisito.
"""

from dataclasses import dataclass
from datetime import datetime

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.utils import timezone

from core import rbac
from legajos.models import Ciudadano
from programas.models import (
    Dispositivo,
    Estadia,
    MotivoEgreso,
    MovimientoEstadia,
    Plaza,
    ReservaPlaza,
    TrazaDispositivo,
)
from programas.services.bitacora import anotar_en_bitacora
from programas.services.dispositivos import (
    dispositivos_en_alcance,
    puede_en_programa_dispositivos,
    puede_operar_dispositivo,
)
from programas.services.movimientos import plaza_ocupada_despues_de, registrar_movimiento, ultimo_momento

CAP_ADMITIR = "dispositivo.admitir"
CAP_EGRESAR = "dispositivo.egresar"
#: Sacar y reponer plazas es configuración de la capacidad instalada, no operación diaria.
CAP_EDITAR = "dispositivo.editar"
#: El asistente de ingreso muestra y busca personas del padrón: además de admitir pide verlas.
CAP_VER_CIUDADANO = "ciudadano.ver"


def puede_ingresar_persona(user, dispositivo):
    """Quién puede abrir el asistente de ingreso: `dispositivo.admitir` con alcance Y `ciudadano.ver`.

    Es la única fuente de la regla: la vista del asistente la usa de gate y el detalle del
    dispositivo la usa para ofrecer (o no) «Ingresar persona», así que el botón nunca
    aparece donde el asistente respondería 403.
    """

    return puede_operar_dispositivo(user, dispositivo, CAP_ADMITIR) and rbac.puede(user, CAP_VER_CIUDADANO)


#: A quién se le pide que resuelva una estadía abierta fuera del alcance de quien pregunta.
REFERENTE_FUERA_DE_ALCANCE = "la coordinación del Programa Dispositivos"

#: Cómo se muestra cada estado de la estadía: texto (el del mockup) y tono del badge. Es la
#: **única** tabla: la leen el detalle del dispositivo (P4) y la solapa del legajo (P16), así
#: que la misma estadía no puede verse con dos rótulos ni dos colores.
ESTADOS_VISIBLES = {
    Estadia.Estado.ACTIVA: ("Alojada", "info"),
    Estadia.Estado.EGRESADA: ("Egresada", "gray"),
}


def estado_visible(estadia):
    """``(texto, tono)`` del badge de una estadía. El template lo dibuja; no lo decide."""

    return ESTADOS_VISIBLES.get(estadia.estado, (estadia.get_estado_display(), "gray"))


class AlojamientoEnLaRed(ValidationError):
    """La persona ya está alojada en algún dispositivo. Trae la verificación que lo explica."""

    def __init__(self, verificacion):
        self.verificacion = verificacion
        super().__init__(verificacion.mensaje)


@dataclass(frozen=True)
class VerificacionAlojamiento:
    """Lo que se puede contar sobre la estadía abierta de una persona, según quién pregunta.

    Los campos del dispositivo llegan vacíos cuando la institución está fuera del alcance
    del usuario: no es que no existan, es que no se cuentan. `dentro_del_alcance` lo dice
    sin que la pantalla tenga que deducirlo de un campo vacío.
    """

    clave: str
    alojada: bool = False
    dentro_del_alcance: bool = False
    estadia_id: int | None = None
    dispositivo_id: int | None = None
    dispositivo: str = ""
    responsable: str = ""
    plaza: str = ""
    desde: datetime | None = None

    @property
    def mensaje(self) -> str:
        if not self.alojada:
            return "La persona no figura alojada en ningún dispositivo de la red."
        if not self.dentro_del_alcance:
            return (
                "La persona ya figura alojada en un dispositivo de la red que está fuera de tu "
                f"alcance. Pedí a {REFERENTE_FUERA_DE_ALCANCE} que registre el egreso o el "
                f"traslado citando la clave de alojamiento {self.clave}."
            )
        donde = self.dispositivo
        if self.plaza:
            donde = f"{donde} ({self.plaza})"
        reclamo = f" Resolvelo con {self.responsable}." if self.responsable else ""
        return (
            f"La persona ya figura alojada en {donde} desde el "
            f"{timezone.localtime(self.desde):%d/%m/%Y %H:%M}. Registrá el egreso o el traslado "
            f"antes de alojarla de nuevo.{reclamo}"
        )


def verificar_alojamiento_en_red(ciudadano, usuario=None):
    """¿Esta persona ya está alojada en algún dispositivo? Con el recorte de quien pregunta.

    **Exige `dispositivo.admitir` en el Programa Dispositivos**, y lo exige la función
    misma, no la vista que la llame: es la única pregunta del sistema que cruza el
    alcance de quien la hace —contesta «sí, está alojada» aunque la institución sea
    ajena—, así que una vista futura que la llamara sin gate le diría a cualquier
    usuario autenticado si una persona está alojada en algún lugar de la red. Sin
    usuario, o sin la capacidad, `PermissionDenied`.

    `admitir` y no `ver`: la existencia de una estadía fuera del alcance solo la
    necesita quien está por alojar a esa persona —es el motivo de que exista la
    verificación—. Quien solo mira el legajo institucional no tiene por qué enterarse de
    dónde está alguien en el resto de la red. Se evalúa **con alcance de programa**, no
    de dispositivo, porque la pregunta es de red: el operador de A pregunta por una
    estadía que puede estar en B.

    Después, dos consultas: la estadía abierta por su clave, y si la institución está
    dentro del alcance de admisión del usuario (por capacidad y asignación).
    """

    if usuario is None or not puede_en_programa_dispositivos(usuario, CAP_ADMITIR):
        raise PermissionDenied("No tenés alcance para verificar alojamientos en la red.")

    clave = Estadia.clave_para(ciudadano)
    estadia = Estadia.objects.de_la_red(clave).select_related("dispositivo", "plaza").first()
    if estadia is None:
        return VerificacionAlojamiento(clave=clave)

    dentro = dispositivos_en_alcance(usuario, CAP_ADMITIR).filter(pk=estadia.dispositivo_id).exists()
    if not dentro:
        # Nada de la institución cruza el límite: ni nombre, ni código, ni localidad, ni
        # fecha. El id tampoco, que enumerado contra el listado propio diría cuál es.
        return VerificacionAlojamiento(clave=clave, alojada=True)

    return VerificacionAlojamiento(
        clave=clave,
        alojada=True,
        dentro_del_alcance=True,
        estadia_id=estadia.pk,
        dispositivo_id=estadia.dispositivo_id,
        dispositivo=estadia.dispositivo.nombre,
        responsable=estadia.dispositivo.responsable_nombre,
        plaza=estadia.plaza.codigo if estadia.plaza_id else "",
        desde=estadia.fecha_ingreso,
    )


def _trazar(dispositivo, usuario, accion, *, estado_anterior="", estado_nuevo="", detalle=""):
    """Traza sobre el patrón de `TrazaDispositivo`: aditiva, inmutable, sin nombres propios.

    El detalle va con identificadores y no con el nombre de la persona: el historial del
    legajo institucional lo lee todo el que opera el dispositivo, y la ficha de la
    persona vive en su propio legajo, con su propio control de acceso.
    """

    TrazaDispositivo.objects.create(
        dispositivo=dispositivo,
        usuario=usuario,
        accion=accion,
        estado_anterior=estado_anterior,
        estado_nuevo=estado_nuevo,
        detalle=detalle,
    )


def _reservas_que_toman(plaza, momento):
    """Las reservas que toman la plaza desde ahora: las vigentes **y las que todavía no empezaron**.

    No es `ReservaPlaza.objects.vigentes()`, y la diferencia es el MAJOR 2 de la revisión
    de #802: `vigentes()` contesta «¿cuenta hoy en el mapa?» y mira un instante; acá la
    pregunta es «¿puedo dar esta plaza?», que es un intervalo que arranca ahora y no
    termina. Una reserva con `desde` dentro de una hora no cuenta hoy, pero si se aloja
    a alguien encima, al llegar su `desde` la plaza queda ocupada **y** reservada, y el
    mapa muestra `disponibles` negativos.

    Lo único que libera la plaza es que la reserva haya **terminado**: resuelta
    (consumida o liberada) o con `hasta` pasado. `reservar_plaza` ya no crea reservas a
    futuro, así que esto es la red para las que entren por otro camino.
    """

    return ReservaPlaza.objects.filter(plaza=plaza, estado=ReservaPlaza.Estado.VIGENTE).filter(
        Q(hasta__isnull=True) | Q(hasta__gte=momento)
    )


def reservas_abiertas(plaza_ids):
    """Las reservas y préstamos **sin resolver** de esas plazas: ``VIGENTE``, venzan o no.

    La tercera pregunta sobre una reserva, distinta de las otras dos:

    * ``ReservaPlaza.objects.vigentes()`` contesta «¿cuenta hoy en el mapa?» y mira un
      instante;
    * :func:`_reservas_que_toman` contesta «¿puedo dar esta plaza?» y mira de ahora en
      adelante;
    * esta contesta **«¿queda algo que liberar?»**, y la respuesta no depende del
      vencimiento: una reserva con el ``hasta`` pasado que nadie liberó sigue abierta.

    Es justo el caso que enciende la alerta «Préstamo vencido sin liberar» de P4 —la plaza
    ya cuenta como disponible y la reserva sigue ahí—, y por eso el mapa necesita esta
    lectura y no la de `vigentes()`: con esa, la plaza de esa alerta sale «Disponible» y
    la única acción que ofrecería sería sacarla de servicio, que no resuelve nada.
    """

    return ReservaPlaza.objects.filter(plaza_id__in=plaza_ids, estado=ReservaPlaza.Estado.VIGENTE)


def reserva_abierta_de(plaza):
    """La reserva sin resolver de una plaza, o ``None``. La más vieja si hubiera más de una.

    Más de una no puede pasar —la plaza se toma con la fila bloqueada—, pero si pasara,
    liberar la más vieja primero es determinista y la pantalla vuelve a ofrecer la que
    queda.
    """

    return reservas_abiertas([getattr(plaza, "pk", plaza)]).order_by("id").first()


def _plaza_tomada_por(plaza, *, excepto_reserva=None, momento=None):
    """Qué tiene tomada la plaza desde ahora, o cadena vacía si está libre.

    Se llama **con la fila de la plaza ya bloqueada**: fuera de ese bloqueo la respuesta
    envejece en el acto.
    """

    if Estadia.objects.activas().filter(plaza=plaza).exists():
        return "una estadía activa"
    reservas = _reservas_que_toman(plaza, momento or timezone.now())
    if excepto_reserva is not None:
        reservas = reservas.exclude(pk=excepto_reserva.pk)
    reserva = reservas.first()
    if reserva is not None:
        return "un préstamo vigente" if reserva.tipo == ReservaPlaza.Tipo.PRESTAMO else "una reserva vigente"
    return ""


#: La estadía que ya tiene plaza no se asigna: se cambia.
YA_TIENE_PLAZA = "Esta persona ya tiene plaza: usá «Cambiar plaza»."

#: El mismo para una plaza que no existe y para una de otra institución: dos mensajes
#: distintos serían un oráculo para enumerar los ids de las plazas ajenas.
PLAZA_FUERA_DEL_DISPOSITIVO = "La plaza no es de este dispositivo."


def _bloquear_plaza(plaza, dispositivo):
    """Resuelve la plaza **dentro del dispositivo** y recién entonces bloquea su fila.

    En ese orden por dos motivos (MINOR de la revisión de #802). Uno: bloquear antes de
    mirar de quién es dejaba que un operador con `admitir` en A tomara `FOR UPDATE` sobre
    una plaza de B. Dos: la inexistente daba `DoesNotExist` —un 500— y la ajena un
    `ValidationError`, un oráculo de existencia de ids. Ahora las dos dan el mismo error.

    El `FOR UPDATE` va sobre la plaza sola, sin `select_related`: en MySQL y en MariaDB
    un `SELECT ... FOR UPDATE` con JOIN bloquea también las filas de la tabla unida, y con
    el sector adentro dos ingresos en plazas **distintas** del mismo sector se esperarían
    entre sí.
    """

    pk = plaza.pk if isinstance(plaza, Plaza) else plaza
    if pk is None or not Plaza.objects.filter(pk=pk, sector__dispositivo_id=dispositivo.pk).exists():
        raise ValidationError({"plaza": PLAZA_FUERA_DEL_DISPOSITIVO})
    return Plaza.objects.select_for_update().get(pk=pk)


def _bloquear_reserva_propia(reserva, *, plaza, ciudadano, momento):
    """Relee con bloqueo la reserva que un ingreso dice consumir, y exige que sea suya.

    MAJOR 1 de la revisión de #802: la reserva se usaba para excluirla del control de
    plaza tomada y para marcarla consumida, sin mirar de quién era, de qué plaza, ni si
    seguía vigente. Así entraba B en la plaza reservada para A pasando la reserva de A, y
    se «consumían» reservas ya liberadas.

    El bloqueo de la reserva es el que serializa dos ingresos que la consumen a la vez:
    el de la plaza solo serializa a los que compiten por la misma plaza.
    """

    pk = reserva.pk if isinstance(reserva, ReservaPlaza) else reserva
    reserva = ReservaPlaza.objects.select_for_update().filter(pk=pk).first()
    if reserva is None or reserva.plaza_id != plaza.pk:
        raise ValidationError({"reserva": "La reserva no es de esta plaza."})
    if reserva.ciudadano_id != ciudadano.pk:
        raise ValidationError({"reserva": "La reserva es de otra persona."})
    if reserva.estado != ReservaPlaza.Estado.VIGENTE or (reserva.hasta is not None and reserva.hasta < momento):
        raise ValidationError({"reserva": "La reserva ya no está vigente."})
    return reserva


def _tomar_plaza(plaza, dispositivo, *, momento=None):
    """Bloquea la fila de la plaza y la devuelve si está en condiciones de recibir a alguien.

    El `select_for_update()` es la regla 2 de la etapa 2 y no se puede reemplazar por un
    constraint: ver el docstring del módulo.
    """

    plaza = _bloquear_plaza(plaza, dispositivo)
    _exigir_plaza_libre(plaza, momento=momento)
    return plaza


#: El egreso sin motivo del catálogo: lo rechaza el servicio, no el formulario.
EGRESO_SIN_MOTIVO = "El egreso exige un motivo del catálogo."
EGRESO_SIN_DESTINO = "Indicá a dónde va la persona."

ALOJAMIENTO_SOLAPADO = (
    "La persona tiene otra estadía en la red que se superpone con esas fechas. "
    "Revisá las fechas o pedí a la coordinación del Programa Dispositivos que revise su trayectoria."
)


def _exigir_intervalo_sin_alojamiento(ciudadano_id, *, desde, hasta=None, excepto=None, campo):
    """Exclusión histórica de la persona, incluso sin plaza y en la misma institución.

    Intervalos semiabiertos: egresar e ingresar en el mismo instante está permitido.
    No se filtra por estado ni alcance: el historial cerrado también cuenta. Solo se
    revela el conflicto, sin ids, nombres, plazas ni fechas de la institución ajena.
    """

    if hasta == desde:
        return  # Un ingreso y egreso simultáneos no ocupan ningún intervalo.
    otras = Estadia.objects.filter(ciudadano_id=ciudadano_id)
    if excepto is not None:
        otras = otras.exclude(pk=excepto)
    otras = otras.exclude(fecha_egreso=F("fecha_ingreso"))
    otras = otras.filter(Q(fecha_egreso__isnull=True) | Q(fecha_egreso__gt=desde))
    if hasta is not None:
        otras = otras.filter(fecha_ingreso__lt=hasta)
    if otras.exists():
        raise ValidationError({campo: ALOJAMIENTO_SOLAPADO})


#: Una carga retroactiva sobre una plaza que otra persona usó en el medio.
PLAZA_OCUPADA_EN_EL_MEDIO = (
    "La plaza estuvo ocupada después de ese momento: con esa fecha quedarían dos personas en la misma plaza."
)


def _exigir_plaza_libre_desde(plaza, *, desde, ahora, campo):
    """Falla si la plaza —**ya bloqueada**— tuvo a alguien entre ``desde`` y ahora.

    Lo que `_exigir_plaza_libre` no ve: mira la plaza **ahora**. Un ingreso o un cambio
    fechados hace dos días en una plaza que otra persona dejó ayer pasan ese control y
    dejan a dos personas en la misma plaza durante un día entero, que es lo que después
    leen la línea de tiempo y el censo. Solo cuesta una consulta cuando la carga es
    retroactiva; con la fecha de ahora no hay nada en el medio.
    """

    if desde < ahora and plaza_ocupada_despues_de(plaza, desde):
        raise ValidationError({campo: PLAZA_OCUPADA_EN_EL_MEDIO})


def _exigir_plaza_libre(plaza, *, excepto_reserva=None, momento=None):
    """Falla si la plaza —**ya bloqueada**— no puede recibir a nadie.

    `excepto_reserva` es la que el ingreso consume, y tiene que venir validada y
    bloqueada por `_bloquear_reserva_propia`: es la única que no cuenta como tomada.
    """

    if not plaza.sector.activo:
        raise ValidationError({"plaza": "El sector de la plaza está dado de baja."})
    if plaza.estado == Plaza.Estado.FUERA_SERVICIO:
        raise ValidationError({"plaza": "La plaza está fuera de servicio."})
    tomada = _plaza_tomada_por(plaza, excepto_reserva=excepto_reserva, momento=momento)
    if tomada:
        raise ValidationError({"plaza": f"La plaza ya tiene {tomada}."})


@transaction.atomic
def ingresar_persona(*, ciudadano, dispositivo, usuario, plaza=None, fecha_ingreso=None, reserva=None):
    """Aloja a una persona. Devuelve la `Estadia` abierta.

    Falla con `AlojamientoEnLaRed` si la persona ya tiene una estadía abierta en
    cualquier dispositivo, y con `ValidationError` si su historial se superpone o si
    la plaza no está en condiciones.
    `reserva` es la reserva que este ingreso consume —la de la lista de espera—, y es la
    única que no bloquea su propia plaza.
    """

    if not puede_operar_dispositivo(usuario, dispositivo, CAP_ADMITIR):
        raise PermissionDenied("No tenés alcance para alojar personas en este dispositivo.")
    if dispositivo.estado != Dispositivo.Estado.ACTIVO:
        raise ValidationError({"dispositivo": "Solo se puede alojar en un dispositivo activo."})

    ahora = timezone.now()
    fecha_ingreso = fecha_ingreso or ahora
    if fecha_ingreso > ahora:
        raise ValidationError({"fecha_ingreso": "El ingreso no puede ser futuro."})

    if reserva is not None and plaza is None:
        raise ValidationError({"plaza": "Un ingreso con reserva va a la plaza reservada."})
    if plaza is not None:
        plaza = _bloquear_plaza(plaza, dispositivo)
        if reserva is not None:
            # Primero la plaza y después la reserva: el mismo orden en todos los caminos
            # que bloquean las dos, para que dos transacciones no se esperen en cruz.
            reserva = _bloquear_reserva_propia(reserva, plaza=plaza, ciudadano=ciudadano, momento=ahora)
        _exigir_plaza_libre(plaza, excepto_reserva=reserva, momento=ahora)
        _exigir_plaza_libre_desde(plaza, desde=fecha_ingreso, ahora=ahora, campo="fecha_ingreso")
    elif dispositivo.tipo.plaza_obligatoria_al_ingresar:
        raise ValidationError({"plaza": "Este tipo de dispositivo exige asignar una plaza al ingresar."})

    # Después de plaza y reserva: sus escrituras también toman la FK de la persona.
    # La fila estable serializa ingresos aun si el ganador egresa antes del commit
    # y libera el UNIQUE. READ COMMITTED permite releer entonces su historial cerrado.
    Ciudadano.objects.select_for_update().only("pk").get(pk=ciudadano.pk)
    verificacion = verificar_alojamiento_en_red(ciudadano, usuario)
    if verificacion.alojada:
        raise AlojamientoEnLaRed(verificacion)
    _exigir_intervalo_sin_alojamiento(ciudadano.pk, desde=fecha_ingreso, campo="fecha_ingreso")

    estadia = Estadia(
        ciudadano=ciudadano,
        dispositivo=dispositivo,
        plaza=plaza,
        fecha_ingreso=fecha_ingreso,
        estado=Estadia.Estado.ACTIVA,
        clave_alojamiento=Estadia.clave_para(ciudadano),
        ingresada_por=usuario,
    )
    # `clean()` y no `full_clean()`: lo caro de `full_clean` es `validate_constraints`,
    # que evalúa cada `CheckConstraint` con una consulta propia —tres por alta— para
    # repetir en Python lo que la base ya rechaza. Las reglas de negocio están validadas
    # arriba; los constraints son la red de abajo, no un paso del camino feliz.
    estadia.clean()
    try:
        # Defensa del motor ante escrituras que no siguen el bloqueo de persona:
        # el UNIQUE de `clave_alojamiento` las rechaza aunque las lecturas no las vean.
        with transaction.atomic():
            estadia.save()
    except IntegrityError as error:
        if "clave_alojamiento" not in str(error):
            raise
        raise AlojamientoEnLaRed(verificar_alojamiento_en_red(ciudadano, usuario)) from error

    if reserva is not None:
        # Filtrado por estado y verificado: con la fila bloqueada no debería fallar nunca,
        # y si falla es que alguien la cambió por un camino que no bloquea. Mejor una
        # excepción —que deshace la estadía— que una reserva consumida dos veces.
        consumidas = ReservaPlaza.objects.filter(pk=reserva.pk, estado=ReservaPlaza.Estado.VIGENTE).update(
            estado=ReservaPlaza.Estado.CONSUMIDA
        )
        if consumidas != 1:
            raise ValidationError({"reserva": "La reserva ya no está vigente."})

    # El movimiento lleva la fecha del ingreso y no la de la carga: es lo que hace que la
    # permanencia calculada y la línea de tiempo coincidan.
    movimiento = registrar_movimiento(
        estadia=estadia,
        tipo=MovimientoEstadia.Tipo.INGRESO,
        momento=fecha_ingreso,
        responsable=usuario,
        plaza_destino=plaza,
        estado_nuevo=Estadia.Estado.ACTIVA,
    )
    anotar_en_bitacora(movimiento)

    _trazar(
        dispositivo,
        usuario,
        "ESTADIA_INGRESO",
        estado_nuevo=Estadia.Estado.ACTIVA,
        detalle=f"Estadía {estadia.pk} · ciudadano {ciudadano.pk} · plaza {plaza.codigo if plaza else '—'}",
    )
    return estadia


@transaction.atomic
def egresar_persona(
    *, estadia, usuario, fecha_egreso=None, motivo="", motivo_egreso=None, destino="", pertenencias_devueltas=False
):
    """Cierra la estadía y suelta la clave de alojamiento y la plaza.

    Soltar la clave es lo que devuelve a la persona al circuito: desde ese momento
    cualquier dispositivo de la red la puede volver a alojar.

    `motivo_egreso` es el `MotivoEgreso` del catálogo (#691), es **obligatorio** y tiene
    que estar activo; `motivo` sigue siendo el texto libre de observaciones, que es lo que
    ya recibía. El destino también es obligatorio y se guarda sin espacios exteriores.

    La obligatoriedad vive acá y no solo en `EgresoForm` (pendiente del Cambio 269): es la
    misma trampa que la revisión del Cambio 262 marcó en la verificación de alojamiento
    —que la regla dependa de que la vista se acuerde—. El historial no puede perder la
    razón de un egreso, y la razón es la del catálogo: `motivo` es texto libre y no
    sustituye a ninguna opción. Las estadías **ya egresadas** sin motivo no se tocan: la
    regla rige para los egresos nuevos.
    """

    if not puede_operar_dispositivo(usuario, estadia.dispositivo, CAP_EGRESAR):
        raise PermissionDenied("No tenés alcance para registrar egresos en este dispositivo.")

    # Se relee con la fila bloqueada: el objeto que llega puede venir de una pantalla
    # abierta hace diez minutos, y dos egresos simultáneos de la misma estadía escribirían
    # los dos su motivo y su responsable, sin que nadie se entere de que hubo dos.
    estadia = Estadia.objects.select_for_update().get(pk=estadia.pk)
    if not estadia.activa:
        raise ValidationError({"estado": "La estadía ya está cerrada."})

    ahora = timezone.now()
    fecha_egreso = fecha_egreso or ahora
    if fecha_egreso > ahora:
        raise ValidationError({"fecha_egreso": "El egreso no puede ser futuro."})
    if fecha_egreso < estadia.fecha_ingreso:
        raise ValidationError({"fecha_egreso": "El egreso no puede ser anterior al ingreso."})
    if fecha_egreso < ultimo_momento(estadia):
        # Un egreso fechado antes del último cambio de plaza dejaría a la persona
        # moviéndose de plaza después de haberse ido.
        raise ValidationError({"fecha_egreso": "El egreso no puede ser anterior al último movimiento de la estadía."})

    if motivo_egreso is None:
        raise ValidationError({"motivo": EGRESO_SIN_MOTIVO})
    if not MotivoEgreso.objects.filter(pk=motivo_egreso.pk, activo=True).exists():
        raise ValidationError({"motivo": "El motivo elegido ya no está disponible."})
    destino = (destino or "").strip()
    if not destino:
        raise ValidationError({"destino": EGRESO_SIN_DESTINO})

    # El egreso solo acorta el intervalo: un solapamiento histórico no debe impedir
    # cerrar la estadía y liberar la clave. La exclusión se valida al ingresar.
    estadia.fecha_egreso = fecha_egreso
    estadia.estado = Estadia.Estado.EGRESADA
    estadia.motivo_egreso = motivo
    estadia.motivo = motivo_egreso
    estadia.destino_egreso = destino
    estadia.pertenencias_devueltas = bool(pertenencias_devueltas)
    estadia.egresada_por = usuario
    # La clave se suelta en el mismo `UPDATE` que cierra la estadía: el constraint de
    # coherencia no admite ningún estado intermedio entre las dos cosas.
    estadia.clave_alojamiento = None
    estadia.clean()
    estadia.save(
        update_fields=[
            "fecha_egreso",
            "estado",
            "motivo_egreso",
            "motivo",
            "destino_egreso",
            "pertenencias_devueltas",
            "egresada_por",
            "clave_alojamiento",
            "modificado",
        ]
    )

    # El movimiento lleva el motivo **del catálogo** y nunca las observaciones: son texto
    # libre, pueden traer datos de la persona, y la línea de tiempo la lee todo el que opera
    # el dispositivo. Las observaciones quedan solo en `Estadia.motivo_egreso`.
    movimiento = registrar_movimiento(
        estadia=estadia,
        tipo=MovimientoEstadia.Tipo.EGRESO,
        momento=fecha_egreso,
        responsable=usuario,
        motivo=motivo_egreso.nombre,
        plaza_origen=estadia.plaza_id,
        estado_anterior=Estadia.Estado.ACTIVA,
        estado_nuevo=Estadia.Estado.EGRESADA,
    )
    anotar_en_bitacora(movimiento)

    _trazar(
        estadia.dispositivo,
        usuario,
        "ESTADIA_EGRESO",
        estado_anterior=Estadia.Estado.ACTIVA,
        estado_nuevo=Estadia.Estado.EGRESADA,
        detalle=f"Estadía {estadia.pk} · ciudadano {estadia.ciudadano_id} · motivo: {motivo_egreso.nombre}",
    )
    return estadia


@transaction.atomic
def cambiar_plaza(*, estadia, plaza, usuario, motivo, momento=None):
    """Mueve a una persona alojada a otra plaza **del mismo dispositivo** (#694).

    Devuelve el `MovimientoEstadia` que lo registra: de sector si la plaza nueva es de
    otro sector, de plaza si es del mismo. Un cambio a otra institución no es esto: es un
    traslado, que cierra la estadía y abre otra.

    Pasa por las mismas reglas que el ingreso, porque compite por lo mismo: la plaza de
    destino se resuelve dentro del dispositivo y se bloquea (`_bloquear_plaza`), y tiene
    que estar libre según `_exigir_plaza_libre` —ni fuera de servicio, ni en un sector
    dado de baja, ni con una estadía activa, ni con una reserva o un préstamo que la tome
    desde ahora, aunque sea para la misma persona—. La plaza de origen no se toca: queda
    libre sola, porque la ocupación se deriva de las estadías activas
    (`programas.services.ocupacion`).

    Lo autoriza `dispositivo.admitir` sobre el dispositivo —asignar plaza es parte de
    alojar—, igual que el ingreso. El motivo es obligatorio: es lo que la línea de
    tiempo cuenta del cambio. `momento` puede ser anterior a ahora (carga tardía), pero
    nunca anterior al último movimiento de la estadía, y la plaza de destino tiene que
    haber estado libre **desde** ese momento, no solo ahora (`_exigir_plaza_libre_desde`).
    """

    dispositivo = estadia.dispositivo
    if not puede_operar_dispositivo(usuario, dispositivo, CAP_ADMITIR):
        raise PermissionDenied("No tenés alcance para cambiar de plaza a personas de este dispositivo.")

    motivo = (motivo or "").strip()
    if not motivo:
        raise ValidationError({"motivo": "El cambio de plaza exige un motivo."})

    ahora = timezone.now()
    momento = momento or ahora
    if momento > ahora:
        raise ValidationError({"momento": "El cambio no puede ser futuro."})

    # Primero la plaza y después la estadía, el mismo orden que el ingreso con reserva
    # (plaza y después reserva): dos transacciones que bloquean las dos cosas no se
    # esperan en cruz. El dispositivo de la estadía no cambia nunca, así que leerlo del
    # objeto que llega antes de bloquearla es seguro.
    plaza = _bloquear_plaza(plaza, dispositivo)
    estadia = Estadia.objects.select_for_update().get(pk=estadia.pk)
    if not estadia.activa:
        raise ValidationError({"estado": "La estadía ya está cerrada."})
    if estadia.plaza_id == plaza.pk:
        raise ValidationError({"plaza": "La persona ya está en esa plaza."})
    if momento < ultimo_momento(estadia):
        raise ValidationError({"momento": "El cambio no puede ser anterior al último movimiento de la estadía."})
    _exigir_plaza_libre(plaza, momento=ahora)
    _exigir_plaza_libre_desde(plaza, desde=momento, ahora=ahora, campo="momento")

    origen = estadia.plaza
    cambia_de_sector = origen is not None and origen.sector_id != plaza.sector_id
    tipo = MovimientoEstadia.Tipo.CAMBIO_SECTOR if cambia_de_sector else MovimientoEstadia.Tipo.CAMBIO_PLAZA

    estadia.plaza = plaza
    estadia.save(update_fields=["plaza", "modificado"])

    movimiento = registrar_movimiento(
        estadia=estadia,
        tipo=tipo,
        momento=momento,
        responsable=usuario,
        motivo=motivo,
        plaza_origen=origen,
        plaza_destino=plaza,
    )
    anotar_en_bitacora(movimiento)

    _trazar(
        dispositivo,
        usuario,
        "ESTADIA_CAMBIO_PLAZA",
        detalle=(
            f"Estadía {estadia.pk} · ciudadano {estadia.ciudadano_id} · "
            f"plaza {origen.codigo if origen else '—'} → {plaza.codigo}"
        ),
    )
    return movimiento


@transaction.atomic
def asignar_plaza(*, estadia, plaza, usuario, motivo="", momento=None):
    """Da plaza a una persona alojada **sin plaza** (el ingreso «Sin plaza»).

    Función propia y no un `cambiar_plaza` que acepte origen vacío: las reglas se
    parecen en la plaza de destino —y por eso se reusan las mismas piezas: `_bloquear_plaza`,
    `_exigir_plaza_libre` y `_exigir_plaza_libre_desde`, con el mismo orden de bloqueo plaza
    y después estadía— pero la pregunta es la inversa: acá la estadía **no** puede tener plaza
    (si la tiene, el camino es «Cambiar plaza»), el motivo es **opcional** y el tipo de
    dispositivo tiene que manejar plazas. Mezclarlas obligaba a `cambiar_plaza` a bifurcar
    la validación, el texto y la traza en cada línea.

    Deja un `MovimientoEstadia` de tipo `CAMBIO_PLAZA` con `plaza_origen` vacío: el modelo ya
    admite origen nulo, y las lecturas (`tramos_por_plaza`, línea de tiempo, bitácora)
    lo tratan como «de sin plaza a X». No hace falta un tipo nuevo ni una migración.
    La persona cuenta en la plaza **desde `momento`**: antes de eso su tramo es el de sin plaza.
    Lo autoriza `dispositivo.admitir`, como el ingreso y el cambio.
    """

    dispositivo = estadia.dispositivo
    if not puede_operar_dispositivo(usuario, dispositivo, CAP_ADMITIR):
        raise PermissionDenied("No tenés alcance para asignar plaza a personas de este dispositivo.")
    if not dispositivo.tipo.maneja_plazas:
        raise ValidationError({"plaza": "Este tipo de dispositivo no maneja plazas."})

    ahora = timezone.now()
    momento = momento or ahora
    if momento > ahora:
        raise ValidationError({"momento": "La asignación no puede ser futura."})

    # Mismo orden que `cambiar_plaza`: primero la plaza y después la estadía.
    plaza = _bloquear_plaza(plaza, dispositivo)
    estadia = Estadia.objects.select_for_update().get(pk=estadia.pk)
    if not estadia.activa:
        raise ValidationError({"estado": "La estadía ya está cerrada."})
    if estadia.plaza_id is not None:
        raise ValidationError({"plaza": YA_TIENE_PLAZA})
    if momento < ultimo_momento(estadia):
        raise ValidationError({"momento": "La asignación no puede ser anterior al último movimiento de la estadía."})
    _exigir_plaza_libre(plaza, momento=ahora)
    _exigir_plaza_libre_desde(plaza, desde=momento, ahora=ahora, campo="momento")

    estadia.plaza = plaza
    estadia.save(update_fields=["plaza", "modificado"])

    movimiento = registrar_movimiento(
        estadia=estadia,
        tipo=MovimientoEstadia.Tipo.CAMBIO_PLAZA,
        momento=momento,
        responsable=usuario,
        motivo=motivo,
        plaza_origen=None,
        plaza_destino=plaza,
    )
    anotar_en_bitacora(movimiento)

    _trazar(
        dispositivo,
        usuario,
        "ESTADIA_ASIGNACION_PLAZA",
        detalle=f"Estadía {estadia.pk} · ciudadano {estadia.ciudadano_id} · plaza {plaza.codigo}",
    )
    return movimiento


@transaction.atomic
def reservar_plaza(*, plaza, ciudadano, usuario, tipo=ReservaPlaza.Tipo.RESERVA, desde=None, hasta=None, motivo=""):
    """Toma una plaza para alguien que todavía no está adentro: reserva o préstamo.

    Pasa por el mismo bloqueo que el ingreso, porque compite por lo mismo: una plaza
    reservada mientras alguien la está ocupando sería la contradicción que el mapa no
    puede mostrar.

    **La reserva nace vigente: `desde` no puede ser futuro** (MAJOR 2 de la revisión de
    #802). El mockup no tiene reservas a futuro —la de la lista de espera se toma en el
    momento, y el préstamo es «por 12 o 24 h» a partir de ahora: «a quién, por cuánto,
    vencimiento»—, y admitirlas obligaba a comparar intervalos en cada ingreso y en cada
    reserva para que dos de ellas, o una reserva y una estadía, no se pisaran al llegar
    su `desde`. Sin futuro, cualquier reserva que exista ya está tomando la plaza, y el
    bloqueo de la plaza alcanza.
    """

    ahora = timezone.now()
    desde = desde or ahora
    if desde > ahora:
        raise ValidationError({"desde": "Una reserva empieza en el momento en que se toma: no puede ser futura."})
    if hasta is not None and hasta <= ahora:
        raise ValidationError({"hasta": "El vencimiento tiene que ser posterior a este momento."})

    pk = plaza.pk if isinstance(plaza, Plaza) else plaza
    dispositivo_id = Plaza.objects.filter(pk=pk).values_list("sector__dispositivo_id", flat=True).first()
    dispositivo = Dispositivo.objects.filter(pk=dispositivo_id).first() if dispositivo_id else None
    if dispositivo is None or not puede_operar_dispositivo(usuario, dispositivo, CAP_ADMITIR):
        # El mismo error para la plaza inexistente y para la de una institución sin
        # alcance: no se distingue «no existe» de «no es tuya».
        raise PermissionDenied("No tenés alcance para reservar plazas en este dispositivo.")
    plaza = _tomar_plaza(pk, dispositivo, momento=ahora)

    reserva = ReservaPlaza(
        plaza=plaza,
        ciudadano=ciudadano,
        tipo=tipo,
        estado=ReservaPlaza.Estado.VIGENTE,
        desde=desde,
        hasta=hasta,
        motivo=motivo,
        creada_por=usuario,
    )
    reserva.clean()
    reserva.save()

    _trazar(
        dispositivo,
        usuario,
        "PLAZA_RESERVADA",
        estado_nuevo=ReservaPlaza.Estado.VIGENTE,
        detalle=f"Plaza {plaza.codigo} · {reserva.get_tipo_display()} · ciudadano {ciudadano.pk}",
    )
    return reserva


@transaction.atomic
def liberar_reserva(*, reserva, usuario, motivo=""):
    """Suelta una reserva o un préstamo antes de su vencimiento."""

    dispositivo = reserva.plaza.sector.dispositivo
    if not puede_operar_dispositivo(usuario, dispositivo, CAP_ADMITIR):
        raise PermissionDenied("No tenés alcance para liberar plazas en este dispositivo.")

    # Plaza y después reserva, igual que el ingreso: el UPDATE de estado puede tomar
    # también la plaza al revalidar la FK por su índice (plaza, estado). Con el orden
    # inverso se forma un deadlock (ERROR 1213) en vez del error de reserva no vigente.
    # plaza_id es estable: ningún servicio mueve una reserva de plaza. Sin JOIN para
    # no bloquear también el sector.
    Plaza.objects.select_for_update().filter(pk=reserva.plaza_id).first()
    # Releída con bloqueo, como en el ingreso que la consume: sin esto, liberar con un
    # objeto viejo pisaría con LIBERADA una reserva que un ingreso acaba de consumir.
    reserva = ReservaPlaza.objects.select_for_update().get(pk=reserva.pk)
    if reserva.estado != ReservaPlaza.Estado.VIGENTE:
        raise ValidationError({"estado": "La reserva ya no está vigente."})

    reserva.estado = ReservaPlaza.Estado.LIBERADA
    reserva.motivo = motivo or reserva.motivo
    reserva.save(update_fields=["estado", "motivo", "modificado"])

    _trazar(
        dispositivo,
        usuario,
        "PLAZA_LIBERADA",
        estado_anterior=ReservaPlaza.Estado.VIGENTE,
        estado_nuevo=ReservaPlaza.Estado.LIBERADA,
        detalle=f"Plaza {reserva.plaza.codigo} · {reserva.get_tipo_display()}",
    )
    return reserva


@transaction.atomic
def sacar_plaza_de_servicio(*, plaza, usuario, motivo):
    """Regla 1 de la etapa 2: **falla** si la plaza está tomada; primero se reubica.

    Vive en este módulo y no en el de plazas porque la condición que la gobierna es la
    estadía: hasta que `Estadia` y `ReservaPlaza` existieron, no había nada que mirar.

    El `FOR UPDATE` va **sobre la plaza sola**, sin `select_related("sector")`, por lo
    mismo que `_bloquear_plaza`: en MySQL y en MariaDB un `SELECT ... FOR UPDATE` con
    JOIN bloquea también las filas de la tabla unida, así que con el sector adentro sacar
    de servicio una plaza dejaba esperando a cualquier ingreso o cambio de plaza de
    **otra** plaza del mismo sector. Nada de acá lee el sector: el dispositivo se resuelve
    arriba, con el objeto que llega.
    """

    motivo = (motivo or "").strip()
    if not motivo:
        raise ValidationError({"motivo_fuera_servicio": "Sacar una plaza de servicio exige un motivo."})

    dispositivo = plaza.sector.dispositivo
    if not puede_operar_dispositivo(usuario, dispositivo, CAP_EDITAR):
        raise PermissionDenied("No tenés alcance para cambiar las plazas de este dispositivo.")

    plaza = Plaza.objects.select_for_update().get(pk=plaza.pk)
    if plaza.estado == Plaza.Estado.FUERA_SERVICIO:
        return plaza
    tomada = _plaza_tomada_por(plaza)
    if tomada:
        raise ValidationError({"estado": f"La plaza tiene {tomada}: reubicá antes de sacarla de servicio."})

    plaza.estado = Plaza.Estado.FUERA_SERVICIO
    plaza.motivo_fuera_servicio = motivo
    plaza.save(update_fields=["estado", "motivo_fuera_servicio", "modificado"])

    _trazar(
        dispositivo,
        usuario,
        "PLAZA_FUERA_SERVICIO",
        estado_anterior=Plaza.Estado.OPERATIVA,
        estado_nuevo=Plaza.Estado.FUERA_SERVICIO,
        detalle=f"Plaza {plaza.codigo} · motivo: {motivo}",
    )
    return plaza


@transaction.atomic
def volver_plaza_a_servicio(*, plaza, usuario):
    """Repone una plaza. No compite con nadie: una plaza fuera de servicio no está tomada.

    El `FOR UPDATE` va sobre la plaza sola, sin `select_related("sector")`, por el mismo
    motivo que en :func:`sacar_plaza_de_servicio`: el JOIN bloquearía el sector entero.
    """

    dispositivo = plaza.sector.dispositivo
    if not puede_operar_dispositivo(usuario, dispositivo, CAP_EDITAR):
        raise PermissionDenied("No tenés alcance para cambiar las plazas de este dispositivo.")

    plaza = Plaza.objects.select_for_update().get(pk=plaza.pk)
    if plaza.estado == Plaza.Estado.OPERATIVA:
        return plaza

    plaza.estado = Plaza.Estado.OPERATIVA
    plaza.motivo_fuera_servicio = ""
    plaza.save(update_fields=["estado", "motivo_fuera_servicio", "modificado"])

    _trazar(
        dispositivo,
        usuario,
        "PLAZA_EN_SERVICIO",
        estado_anterior=Plaza.Estado.FUERA_SERVICIO,
        estado_nuevo=Plaza.Estado.OPERATIVA,
        detalle=f"Plaza {plaza.codigo}",
    )
    return plaza
