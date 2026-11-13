"""Reservas de derivación de Emergencia sobre las plazas de un dispositivo.

Salen de `programas.services.estadias`, que sigue siendo dueño de los candados de plaza,
reserva y persona: este módulo usa sus helpers (`_bloquear_plaza`, `_exigir_plaza_libre`,
`_crear_reserva`, `ingresar_persona`, `liberar_reserva`) y no inventa ninguno.

Una reserva con `ReservaPlaza.derivacion` es una de las N camas que el dispositivo le guardó
a **la familia** de un caso de Emergencia al aceptar su derivación. Lleva en `ciudadano` al
responsable del grupo —la columna es obligatoria y los demás integrantes todavía no tienen
legajo—, pero **no es una reserva de esa persona**: son siete camas para siete personas que
se van a ir identificando en la puerta. Por eso tiene caminos propios y queda **afuera** de
los caminos «de la persona», que filtran `derivacion__isnull=True`:

* `reserva_propia_vigente` —y con ella `_exigir_persona_sin_alojamiento_ni_reserva`, el
  paso de plaza del asistente (`ingreso.plaza_reservada_de`) y la reserva que
  `confirmar_ingreso` consume— no la ven: «una reserva vigente por persona y por
  dispositivo» sigue valiendo para las reservas comunes del responsable, y las N de la
  familia no cuentan ni chocan con ella.
* `ingreso._reservas_abiertas_de` no la ve: el ingreso del responsable por el asistente
  normal **no libera** las camas de su familia. La decisión D2 del PM (Cambio 409: al
  ingresar se cierran todas las reservas de la persona, en cualquier dispositivo) no
  cambia para ninguna otra reserva, y `consumir_reserva_de_derivacion` también la aplica:
  quien entra por una cama de la familia pierde sus reservas **comunes** abiertas.

Para todo lo demás **es una reserva como cualquiera**: toma la plaza (`_plaza_tomada_por`,
`ocupacion`), el mapa la dibuja reservada, impide sacar la plaza de servicio y dar de baja
el sector, y el operador la puede liberar desde el mapa con `liberar_reserva`.

Las escribe y las resuelve solo este módulo:

* `reservar_plazas_de_derivacion` crea las N, todo o nada. No aplica «una por persona» ni
  rechaza al responsable que ya está alojado en la red (RN-2.15: es un dato, no un freno).
* `consumir_reserva_de_derivacion` aloja a un integrante en una de ellas: con la plaza, la
  reserva y la persona bloqueadas, pone la reserva a nombre de quien ingresa y delega en
  `ingresar_persona`, que la valida como propia y la consume. La reasignación solo se hace
  después de comprobar, con la fila bloqueada, que la reserva **es de derivación**: una
  reserva común de otra persona sigue rechazada por `_bloquear_reserva_propia` (MAJOR 1 de
  #802), que no se tocó. Como `ingreso.confirmar_ingreso`, libera además las reservas comunes
  abiertas de quien ingresa, en cualquier dispositivo.
* `liberar_reservas_de_derivacion` suelta las que quedan vigentes (cierre con diferencia,
  cancelación del ingreso, vencimiento).

**Orden de candados global con Emergencia: caso → derivación → plazas (por pk) → reservas →
persona.** El caso y la derivación los bloquea el servicio de Emergencia que llama, antes de
entrar acá; estas funciones no los bloquean ni los releen, y por eso confían en la
derivación que reciben. Adentro vale el orden de siempre, con dos cuidados:

* cuando son varias plazas se bloquean **todas de una vez, ordenadas por pk** (igual que
  `ingreso.confirmar_ingreso`), antes de tocar ninguna reserva; en
  `consumir_reserva_de_derivacion` son la de la cama y las de las reservas comunes a liberar;
* `consumir_reserva_de_derivacion` bloquea a la persona que ingresa **antes** de escribirla
  en la reserva. El `UPDATE` de `ciudadano_id` revalida la FK y pide un lock **compartido**
  sobre la fila de la persona; si después `ingresar_persona` pidiera el exclusivo, dos
  transacciones con el compartido se esperarían en cruz al subirlo (`ERROR 1213`).
  `reservar_plazas_de_derivacion` no bloquea al responsable: no decide nada sobre él, y el
  compartido que toma el `INSERT` nunca se sube.

Y un candado que **no** hay que tomar. Liberar una reserva de derivación desde el mapa
(`liberar_reserva`, sin pasar por Emergencia) bloquea plaza → reserva y **no** toca la
derivación: por eso `ReservaPlaza` no tiene un índice `(derivacion, estado)`. Con uno,
InnoDB lo adoptaría para la FK y el `UPDATE` de `estado` pediría un lock compartido sobre la
fila de la derivación *después* de la plaza —lo mismo que arriba se cuenta de `(plaza,
estado)`—, y se cruzaría con la mesa que tiene la derivación bloqueada y va por esa plaza
(cancelar, vencer, cerrar con diferencia). Con el índice implícito de la FK, de una sola
columna, cambiar `estado` no revalida nada. El único lock sobre la derivación que nace acá
es el compartido del `INSERT` de `reservar_plazas_de_derivacion`, que corre con la
derivación ya bloqueada por quien llama.
"""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from programas.models import Dispositivo, Plaza, ReservaPlaza, Sector
from programas.services.dispositivos import puede_operar_dispositivo
from programas.services.estadias import (
    CAP_ADMITIR,
    PLAZA_FUERA_DEL_DISPOSITIVO,
    SIN_ALCANCE_PARA_RESERVAR,
    _bloquear_plaza,
    _crear_reserva,
    _exigir_desde_no_futuro,
    _exigir_plaza_libre,
    ingresar_persona,
    liberar_reserva,
)
from programas.services.ingreso import (
    MOTIVO_RESERVA_CERRADA_POR_INGRESO,
    RESERVA_NUEVA_DURANTE_EL_INGRESO,
    _bloquear_persona,
    _reservas_abiertas_de,
)
from programas.services.nombre_plaza import plaza_con_sector

#: Lo que recibe quien opera el dispositivo y pasa una reserva común (o una que se borró
#: entre la lectura y el candado). Sin alcance no se llega acá: es `PermissionDenied`.
RESERVA_NO_ES_DE_DERIVACION = "La reserva no es de una derivación de Emergencia."
RESERVA_YA_NO_VIGENTE = "La reserva ya no está vigente."
DERIVACION_NO_VIGENTE = "La derivación ya no está vigente: no se le pueden guardar plazas."


def motivo_de_reserva_de_derivacion(derivacion):
    """«Emergencia caso N.° 2026-000184»: lo que dice la reserva sobre por qué existe."""

    return f"Emergencia caso N.° {derivacion.caso.numero}"


@transaction.atomic
def reservar_plazas_de_derivacion(*, derivacion, plazas, usuario, momento=None):
    """Guarda `plazas` para la familia de `derivacion`. Devuelve las `ReservaPlaza`, por pk de plaza.

    **Todo o nada**: si una sola plaza no se puede tomar —no es del dispositivo de la
    derivación, está fuera de servicio, en un sector dado de baja, ocupada o ya reservada—
    falla con `ValidationError` y no queda ninguna reserva. El error de una plaza tomada la
    nombra, para que quien eligió las camas sepa cuál cambiar.

    No decide **qué** plazas: recibe la lista (instancias o ids) de quien las eligió. Cada
    reserva nace `VIGENTE`, de tipo `RESERVA`, sin vencimiento, a nombre del responsable del
    grupo y con `derivacion` puesta. A diferencia de `reservar_plaza`, **no** exige que el
    responsable no tenga otra reserva ni que no esté alojado en la red: las camas son de la
    familia (ver «Reservas de derivación» en el módulo).

    Lo autoriza `dispositivo.admitir` sobre el dispositivo de la derivación, que tiene que
    estar activo. `momento` es el `desde` de las reservas (por omisión, ahora) y no puede ser
    futuro: una reserva nace vigente.

    **Candados**: quien llama ya bloqueó el caso y la derivación —acá no se bloquean ni se
    releen—. Se toman todas las plazas de una vez, ordenadas por pk, y recién después se
    escribe. No se bloquea al responsable.
    """

    dispositivo = derivacion.dispositivo
    if not puede_operar_dispositivo(usuario, dispositivo, CAP_ADMITIR):
        raise PermissionDenied(SIN_ALCANCE_PARA_RESERVAR)
    if dispositivo.estado != Dispositivo.Estado.ACTIVO:
        raise ValidationError({"dispositivo": "Solo se reservan plazas en un dispositivo activo."})
    if not derivacion.vigente:
        raise ValidationError({"derivacion": DERIVACION_NO_VIGENTE})

    ahora = timezone.now()
    desde = momento or ahora
    _exigir_desde_no_futuro(desde, ahora)

    ids = [plaza.pk if isinstance(plaza, Plaza) else plaza for plaza in plazas]
    if not ids:
        raise ValidationError({"plaza": "Elegí al menos una plaza para reservar."})
    if None in ids or len(set(ids)) != len(ids):
        raise ValidationError({"plaza": "La lista de plazas a reservar tiene una plaza repetida o inválida."})

    # Resueltas dentro del dispositivo **antes** de bloquear, como `_bloquear_plaza`: ni se
    # toma `FOR UPDATE` sobre una plaza ajena, ni la inexistente y la ajena dan errores distintos.
    propias = Plaza.objects.filter(pk__in=ids, sector__dispositivo_id=dispositivo.pk).count()
    if propias != len(ids):
        raise ValidationError({"plaza": PLAZA_FUERA_DEL_DISPOSITIVO})
    # Todas de una vez y por pk: dos aceptaciones con plazas en común se forman en la primera
    # que comparten, sin esperarse en cruz. Sin JOIN, para no bloquear también los sectores.
    bloqueadas = list(Plaza.objects.select_for_update().filter(pk__in=ids).order_by("pk"))
    if len(bloqueadas) != len(ids):
        raise ValidationError({"plaza": PLAZA_FUERA_DEL_DISPOSITIVO})  # la borraron en el medio

    # Los sectores en una sola consulta: `_exigir_plaza_libre` y la traza los leen por plaza.
    sectores = Sector.objects.in_bulk({plaza.sector_id for plaza in bloqueadas})
    for plaza in bloqueadas:
        plaza.sector = sectores[plaza.sector_id]
        try:
            _exigir_plaza_libre(plaza, momento=ahora)
        except ValidationError as error:
            raise ValidationError(
                {"plaza": [f"{plaza_con_sector(plaza)}: {mensaje}" for mensaje in error.messages]}
            ) from error

    responsable_id = derivacion.caso.grupo.responsable_id
    motivo = motivo_de_reserva_de_derivacion(derivacion)
    reservas = []
    for plaza in bloqueadas:
        reservas.append(
            _crear_reserva(
                dispositivo,
                usuario,
                de_quien=f"derivación {derivacion.pk} · {motivo}",
                plaza=plaza,
                ciudadano_id=responsable_id,
                tipo=ReservaPlaza.Tipo.RESERVA,
                desde=desde,
                hasta=None,
                motivo=motivo,
                derivacion=derivacion,
            )
        )
    return reservas


@transaction.atomic
def consumir_reserva_de_derivacion(*, reserva, ciudadano, usuario, fecha_ingreso=None):
    """Aloja a `ciudadano` en la plaza de una reserva de derivación. Devuelve la `Estadia` abierta.

    Es el ingreso de un integrante de la familia: cualquiera de ellos, no solo el
    responsable a cuyo nombre nació la reserva. Hace lo mismo que cualquier ingreso —lo
    delega en `ingresar_persona`, con sus mismas reglas, su movimiento, su `INGRESO` en la
    bitácora y su traza— y deja la reserva `CONSUMIDA` a nombre de quien entró.

    Falla con `PermissionDenied` sin `dispositivo.admitir` sobre el dispositivo de la plaza
    (también si la reserva no existe: no se distingue), con `ValidationError` si la reserva
    no es de derivación o ya no está vigente, y con lo que falle `ingresar_persona`
    (`AlojamientoEnLaRed` si la persona ya está alojada, plaza fuera de servicio, fechas…).
    **Si algo falla, la reserva queda como estaba**: vigente y a nombre de quien estaba.

    Por qué reasignar antes de ingresar no rompe el MAJOR 1 de #802
    ---------------------------------------------------------------

    `_bloquear_reserva_propia` sigue exigiendo que la reserva sea de quien ingresa, y no se
    tocó. Lo que cambia es **quién puede poner su nombre** en una reserva: solo esta función,
    solo sobre una reserva que —releída con `FOR UPDATE`— tiene `derivacion`, está vigente y
    está en una plaza del dispositivo que el usuario opera. Una reserva común (`derivacion`
    en NULL) se rechaza acá, antes de escribir nada, y por `ingresar_persona(reserva=…)`
    directo sigue dando «La reserva es de otra persona». La reasignación y el ingreso van
    en la misma transacción (un savepoint si ya hay una abierta): si el ingreso falla, la
    excepción deshace también el cambio de nombre.

    **Las reservas comunes de quien ingresa se liberan** (D2 del Cambio 409), en este
    dispositivo y en cualquier otro, igual que en `ingreso.confirmar_ingreso` y con su mismo
    motivo: una persona que ya está adentro no puede seguir bloqueando plazas. Las de
    derivación no, que son de su familia.

    **Candados**: plaza → reserva → persona, el orden de siempre. Si hay reservas comunes que
    liberar, sus plazas y la de la cama se bloquean primero, de una vez y ordenadas por pk. La
    persona se bloquea **antes** del `UPDATE` que la escribe en la reserva (ver el docstring
    del módulo) y, con ella bloqueada, se vuelve a mirar que no le hayan guardado otra plaza.
    `ingresar_persona` vuelve a pedir los tres, ya tomados por esta transacción.
    """

    pk = reserva.pk if isinstance(reserva, ReservaPlaza) else reserva
    # Sin bloquear: `plaza_id` es estable (ningún servicio mueve una reserva de plaza) y de
    # acá solo sale a qué dispositivo preguntarle el alcance.
    fila = ReservaPlaza.objects.filter(pk=pk).values_list("plaza_id", "plaza__sector__dispositivo_id").first()
    dispositivo = Dispositivo.objects.select_related("tipo").filter(pk=fila[1]).first() if fila else None
    if dispositivo is None or not puede_operar_dispositivo(usuario, dispositivo, CAP_ADMITIR):
        # El mismo error para la reserva inexistente y para la de una institución sin alcance.
        raise PermissionDenied("No tenés alcance para alojar personas en este dispositivo.")

    comunes = _reservas_abiertas_de(ciudadano.pk)
    if comunes:
        # Solo el candado: `_bloquear_plaza` y `liberar_reserva` vuelven a tomar cada plaza.
        list(
            Plaza.objects.select_for_update()
            .filter(pk__in={fila[0]} | {comun.plaza_id for comun in comunes})
            .order_by("pk")
            .values_list("pk", flat=True)
        )
    plaza = _bloquear_plaza(fila[0], dispositivo)
    reserva = ReservaPlaza.objects.select_for_update().filter(pk=pk).first()
    # La guarda que sostiene el MAJOR 1 de #802: solo una reserva de derivación cambia de
    # nombre. Es la única; no hay otra línea que la cubra si esta se va.
    if reserva is None or reserva.derivacion_id is None:
        raise ValidationError({"reserva": RESERVA_NO_ES_DE_DERIVACION})
    if reserva.estado != ReservaPlaza.Estado.VIGENTE:
        raise ValidationError({"reserva": RESERVA_YA_NO_VIGENTE})

    for comun in comunes:
        try:
            liberar_reserva(
                reserva=comun, usuario=usuario, motivo=MOTIVO_RESERVA_CERRADA_POR_INGRESO, verificar_alcance=False
            )
        except ValidationError:
            continue  # ya la resolvió otro: lo que importa es que no quede bloqueando

    # La persona, con el exclusivo, antes de nombrarla en la reserva: el UPDATE de abajo toma
    # el compartido de su fila por la FK, y subirlo después es lo que arma el deadlock.
    _bloquear_persona(ciudadano)
    # Con la persona bloqueada nadie le puede guardar otra plaza: una que apareció entre la
    # lectura y el bloqueo quedaría tomando una plaza de alguien que ya está adentro.
    if _reservas_abiertas_de(ciudadano.pk):
        raise ValidationError(RESERVA_NUEVA_DURANTE_EL_INGRESO)
    if reserva.ciudadano_id != ciudadano.pk:
        reserva.ciudadano = ciudadano
        reserva.save(update_fields=["ciudadano", "modificado"])

    return ingresar_persona(
        ciudadano=ciudadano,
        dispositivo=dispositivo,
        usuario=usuario,
        plaza=plaza,
        fecha_ingreso=fecha_ingreso,
        reserva=reserva,
    )


@transaction.atomic
def liberar_reservas_de_derivacion(*, derivacion, usuario, motivo, verificar_alcance=True):
    """Suelta las reservas de la derivación que siguen vigentes. Devuelve cuántas liberó.

    Para el cierre con diferencia (sobraron camas), la cancelación del ingreso y el
    vencimiento de la derivación. Las ya consumidas o liberadas no se tocan, y sin ninguna
    vigente devuelve 0 sin error: es idempotente. Cada una pasa por `liberar_reserva`, así
    que queda `LIBERADA`, con `motivo` y con su traza `PLAZA_LIBERADA`, igual que la que el
    operador libera desde el mapa.

    `verificar_alcance=False` es para quien no actúa como operador del dispositivo —la mesa
    que cancela, el vencimiento por cron—: igual que en `liberar_reserva`, no es una
    decisión sobre esa plaza sino la consecuencia de que la derivación terminó.

    **Candados**: quien llama ya bloqueó el caso y la derivación. Acá, todas las plazas de
    una vez ordenadas por pk y después cada reserva (`liberar_reserva` vuelve a pedir su
    plaza, ya tomada). Una reserva que se sume a la derivación después de esa lectura no se
    libera en esta llamada: su plaza no está bloqueada, y bloquearla ahora sería pedir una
    plaza después de una reserva.
    """

    if verificar_alcance and not puede_operar_dispositivo(usuario, derivacion.dispositivo, CAP_ADMITIR):
        raise PermissionDenied("No tenés alcance para liberar plazas en este dispositivo.")

    vigentes = list(
        ReservaPlaza.objects.abiertas()
        .filter(derivacion=derivacion)
        .select_related("plaza__sector__dispositivo")
        .order_by("plaza_id", "id")
    )
    if not vigentes:
        return 0
    # Solo el candado: `liberar_reserva` vuelve a tomar cada plaza y relee la reserva con bloqueo.
    list(
        Plaza.objects.select_for_update()
        .filter(pk__in={reserva.plaza_id for reserva in vigentes})
        .order_by("pk")
        .values_list("pk", flat=True)
    )
    # El de Emergencia puede traer una observación más larga que la columna, y MariaDB en modo
    # estricto rechaza el `UPDATE` entero en vez de recortar.
    motivo = (motivo or "").strip()[: ReservaPlaza._meta.get_field("motivo").max_length]
    liberadas = 0
    for reserva in vigentes:
        try:
            liberar_reserva(reserva=reserva, usuario=usuario, motivo=motivo, verificar_alcance=False)
        except ValidationError:
            continue  # la consumió o la liberó otro entre la lectura y el candado: ya no hay nada que soltar
        liberadas += 1
    return liberadas
