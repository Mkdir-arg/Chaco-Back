"""Ingreso, egreso y reserva de plazas (MVP v2, etapa 2 · #689).

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

La verificación en toda la red
------------------------------

`verificar_alojamiento_en_red` es lo único que puede preguntar por una persona **fuera
del alcance de quien pregunta**, y por eso su resultado está partido en dos:

* **Dentro del alcance** (`dispositivos_visibles`, por capacidad y asignación, nunca por
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
from django.utils import timezone

from programas.models import Dispositivo, Estadia, Plaza, ReservaPlaza, TrazaDispositivo
from programas.services.dispositivos import dispositivos_visibles, puede_operar_dispositivo

CAP_ADMITIR = "dispositivo.admitir"
CAP_EGRESAR = "dispositivo.egresar"
#: Sacar y reponer plazas es configuración de la capacidad instalada, no operación diaria.
CAP_EDITAR = "dispositivo.editar"

#: A quién se le pide que resuelva una estadía abierta fuera del alcance de quien pregunta.
REFERENTE_FUERA_DE_ALCANCE = "la coordinación del Programa Dispositivos"


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

    Dos consultas: la estadía abierta por su clave, y si la institución está dentro del
    alcance del usuario. El alcance sale de `dispositivos_visibles`, que evalúa capacidad
    y asignación; `usuario=None` es «nadie», o sea el recorte más angosto.
    """

    clave = Estadia.clave_para(ciudadano)
    estadia = Estadia.objects.de_la_red(clave).select_related("dispositivo", "plaza").first()
    if estadia is None:
        return VerificacionAlojamiento(clave=clave)

    dentro = dispositivos_visibles(usuario).filter(pk=estadia.dispositivo_id).exists()
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


def _plaza_tomada_por(plaza, *, excepto_reserva=None, momento=None):
    """Qué tiene tomada la plaza ahora mismo, o cadena vacía si está libre.

    Se llama **con la fila de la plaza ya bloqueada**: fuera de ese bloqueo la respuesta
    envejece en el acto.
    """

    if Estadia.objects.activas().filter(plaza=plaza).exists():
        return "una estadía activa"
    reservas = ReservaPlaza.objects.vigentes(momento).filter(plaza=plaza)
    if excepto_reserva is not None:
        reservas = reservas.exclude(pk=excepto_reserva.pk)
    reserva = reservas.first()
    if reserva is not None:
        return "un préstamo vigente" if reserva.tipo == ReservaPlaza.Tipo.PRESTAMO else "una reserva vigente"
    return ""


def _tomar_plaza(plaza, dispositivo, *, excepto_reserva=None, momento=None):
    """Bloquea la fila de la plaza y la devuelve si está en condiciones de recibir a alguien.

    El `select_for_update()` es la regla 2 de la etapa 2 y no se puede reemplazar por un
    constraint: ver el docstring del módulo.
    """

    plaza = (
        Plaza.objects.select_for_update().select_related("sector").get(pk=plaza.pk if hasattr(plaza, "pk") else plaza)
    )
    if plaza.sector.dispositivo_id != dispositivo.pk:
        raise ValidationError({"plaza": "La plaza tiene que ser del dispositivo de la estadía."})
    if not plaza.sector.activo:
        raise ValidationError({"plaza": "El sector de la plaza está dado de baja."})
    if plaza.estado == Plaza.Estado.FUERA_SERVICIO:
        raise ValidationError({"plaza": "La plaza está fuera de servicio."})
    tomada = _plaza_tomada_por(plaza, excepto_reserva=excepto_reserva, momento=momento)
    if tomada:
        raise ValidationError({"plaza": f"La plaza ya tiene {tomada}."})
    return plaza


@transaction.atomic
def ingresar_persona(*, ciudadano, dispositivo, usuario, plaza=None, fecha_ingreso=None, reserva=None):
    """Aloja a una persona. Devuelve la `Estadia` abierta.

    Falla con `AlojamientoEnLaRed` si la persona ya tiene una estadía abierta en
    cualquier dispositivo, y con `ValidationError` si la plaza no está en condiciones.
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

    if plaza is not None:
        plaza = _tomar_plaza(plaza, dispositivo, excepto_reserva=reserva, momento=ahora)
    elif dispositivo.tipo.plaza_obligatoria_al_ingresar:
        raise ValidationError({"plaza": "Este tipo de dispositivo exige asignar una plaza al ingresar."})

    verificacion = verificar_alojamiento_en_red(ciudadano, usuario)
    if verificacion.alojada:
        raise AlojamientoEnLaRed(verificacion)

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
        # El punto en el que la garantía deja de ser una consulta: entre la verificación
        # y este alta puede haber ganado otro operador, de otra institución, al que esta
        # transacción no vio. El UNIQUE de `clave_alojamiento` lo rechaza igual.
        with transaction.atomic():
            estadia.save()
    except IntegrityError as error:
        if "clave_alojamiento" not in str(error):
            raise
        raise AlojamientoEnLaRed(verificar_alojamiento_en_red(ciudadano, usuario)) from error

    if reserva is not None:
        ReservaPlaza.objects.filter(pk=reserva.pk).update(estado=ReservaPlaza.Estado.CONSUMIDA)

    _trazar(
        dispositivo,
        usuario,
        "ESTADIA_INGRESO",
        estado_nuevo=Estadia.Estado.ACTIVA,
        detalle=f"Estadía {estadia.pk} · ciudadano {ciudadano.pk} · plaza {plaza.codigo if plaza else '—'}",
    )
    return estadia


@transaction.atomic
def egresar_persona(*, estadia, usuario, fecha_egreso=None, motivo=""):
    """Cierra la estadía y suelta la clave de alojamiento y la plaza.

    Soltar la clave es lo que devuelve a la persona al circuito: desde ese momento
    cualquier dispositivo de la red la puede volver a alojar.
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

    estadia.fecha_egreso = fecha_egreso
    estadia.estado = Estadia.Estado.EGRESADA
    estadia.motivo_egreso = motivo
    estadia.egresada_por = usuario
    # La clave se suelta en el mismo `UPDATE` que cierra la estadía: el constraint de
    # coherencia no admite ningún estado intermedio entre las dos cosas.
    estadia.clave_alojamiento = None
    estadia.clean()
    estadia.save(
        update_fields=["fecha_egreso", "estado", "motivo_egreso", "egresada_por", "clave_alojamiento", "modificado"]
    )

    _trazar(
        estadia.dispositivo,
        usuario,
        "ESTADIA_EGRESO",
        estado_anterior=Estadia.Estado.ACTIVA,
        estado_nuevo=Estadia.Estado.EGRESADA,
        detalle=f"Estadía {estadia.pk} · ciudadano {estadia.ciudadano_id} · motivo: {motivo or '—'}",
    )
    return estadia


@transaction.atomic
def reservar_plaza(*, plaza, ciudadano, usuario, tipo=ReservaPlaza.Tipo.RESERVA, desde=None, hasta=None, motivo=""):
    """Toma una plaza para alguien que todavía no está adentro: reserva o préstamo.

    Pasa por el mismo bloqueo que el ingreso, porque compite por lo mismo: una plaza
    reservada mientras alguien la está ocupando sería la contradicción que el mapa no
    puede mostrar.
    """

    dispositivo = plaza.sector.dispositivo
    if not puede_operar_dispositivo(usuario, dispositivo, CAP_ADMITIR):
        raise PermissionDenied("No tenés alcance para reservar plazas en este dispositivo.")

    ahora = timezone.now()
    desde = desde or ahora
    plaza = _tomar_plaza(plaza, dispositivo, momento=max(desde, ahora))

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
    """

    motivo = (motivo or "").strip()
    if not motivo:
        raise ValidationError({"motivo_fuera_servicio": "Sacar una plaza de servicio exige un motivo."})

    dispositivo = plaza.sector.dispositivo
    if not puede_operar_dispositivo(usuario, dispositivo, CAP_EDITAR):
        raise PermissionDenied("No tenés alcance para cambiar las plazas de este dispositivo.")

    plaza = Plaza.objects.select_for_update().select_related("sector").get(pk=plaza.pk)
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
    """Repone una plaza. No compite con nadie: una plaza fuera de servicio no está tomada."""

    dispositivo = plaza.sector.dispositivo
    if not puede_operar_dispositivo(usuario, dispositivo, CAP_EDITAR):
        raise PermissionDenied("No tenés alcance para cambiar las plazas de este dispositivo.")

    plaza = Plaza.objects.select_for_update().select_related("sector").get(pk=plaza.pk)
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
