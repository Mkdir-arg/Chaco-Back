"""Relevamiento edilicio de Dispositivos (MVP v2, etapa 4 · #700).

En pantalla es **«Relevamiento»**; en el código, `InspeccionEdificio`, porque
`Relevamiento` es de Becas. Cuelga del **edificio**: un predio compartido se releva una
vez y el resultado lo ven todas las instituciones que lo ocupan.

Dos personas, dos capacidades del `CATALOGO` (módulo ``inspecciones``):

* **El coordinador** (``inspeccion.asignar``) crea la tarea eligiendo el edificio y el
  agente, y la reasigna o la cancela mientras está en curso. Su alcance son los edificios
  que ocupa algún dispositivo donde un rol suyo **con esa capacidad** está asignado
  (`dispositivos_en_alcance`); el admin del programa los ve todos.
* **El agente** (``inspeccion.relevar``) registra el resultado —criticidad, observaciones
  y fotos— **solo de lo que tiene asignado**. No elige qué relevar y no ve las tareas de
  otro agente: la guarda es `asignado_a`, no el alcance sobre el dispositivo.

Quien opera el dispositivo (``dispositivo.ver`` con su alcance) **lee** los relevamientos
de los edificios que ocupa: es la solapa Infraestructura (P19), y el informe de cada uno
(:func:`informe_de_relevamiento`). Lo que **no** ve es de quién es la tarea: el nombre del
agente asignado y las indicaciones de la coordinación son :func:`ve_la_asignacion`, porque
el agente externo solo sirve si la institución no sabe de antemano quién va a ir.

Lo que define el Ministerio y acá es un default
----------------------------------------------

La escala de criticidad y los estados viven en el modelo como `TextChoices`. Que el agente
sea **externo a la institución** relevada es :data:`AGENTE_DEBE_SER_EXTERNO`: el mockup
(P21) lo dice —«nunca se asigna al personal de la institución relevada»— y se aplica, pero
apagarlo es cambiar esa constante. «Personal» es tener un rol activo asignado
(`AsignacionDispositivo`) a alguno de los dispositivos que ocupan el edificio.

La app de campo (tasks 38 y 39)
-------------------------------

La API de ``/api/dispositivos/`` (`programas/api/views_inspecciones.py`) no decide reglas:
llama a :func:`registrar_resultado` y :func:`agregar_foto`. Para la app sin conexión las dos
son **idempotentes** por el identificador que genera el celular (``uuid_resultado`` y
``uuid_cliente``): el reenvío devuelve lo que ya quedó. Lo que cambió en el servidor mientras
el celular estaba sin señal sale como :class:`InspeccionEnConflicto` (cancelado, ya realizado
con otro envío) o :class:`InspeccionReasignada`, que la API traduce a 409 con un código.

La consulta del semáforo
------------------------

El listado usa :func:`semaforos_de_dispositivos`: combina la criticidad de la última
realizada con los relevamientos en curso vencidos, en consultas fijas por lote. Distingue
**sin relevar** de relevado y sano y de **sin edificio cargado**.
:func:`ultimas_inspecciones_por_edificio` trae los resultados completos para los
consumidores que los necesitan, también con costo fijo.
"""

import uuid
from dataclasses import dataclass
from datetime import timedelta
from functools import reduce
from operator import or_

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, OuterRef, Q, Subquery
from django.utils import timezone
from django.utils.formats import date_format

from core import rbac
from core.archivos import anotar_archivo_escrito, archivos_atomicos
from core.db import q_uuid_en_texto
from programas.models import AsignacionDispositivo, Edificio, FotoInspeccion, InspeccionEdificio, TrazaInspeccion
from programas.services.dispositivos import (
    CAP_VER,
    dispositivos_en_alcance,
    programa_dispositivos,
    puede_configurar_dispositivos,
    puede_en_programa_dispositivos,
)

CAP_ASIGNAR = "inspeccion.asignar"
CAP_RELEVAR = "inspeccion.relevar"

#: Default a confirmar con el Ministerio: el agente no puede ser personal de ninguna de
#: las instituciones que ocupan el edificio (mockup P21).
AGENTE_DEBE_SER_EXTERNO = True

_EdificioDispositivo = Edificio.dispositivos.through
_AgenteAnterior = InspeccionEdificio.agentes_anteriores.through

# Códigos de conflicto (409) que la app muestra. Son contrato con `Chaco-mobile`.
CONFLICTO_CANCELADA = "CANCELADA"
CONFLICTO_YA_REALIZADA = "YA_REALIZADA"
CONFLICTO_REASIGNADA = "REASIGNADA"
CONFLICTO_UUID_EN_USO = "UUID_EN_USO"
#: Red de contención: el relevamiento está en un estado que la app no conoce. Los estados
#: son «defaults a confirmar con el Ministerio» (ver `InspeccionEdificio`), así que agregar
#: uno —«vencido», por ejemplo— no puede hacer que el agente lo cierre igual. La app lo
#: muestra como conflicto genérico y manda a refrescar; el `estado` del cuerpo dice cuál es.
CONFLICTO_ESTADO = "ESTADO_NO_ADMITE"


class InspeccionEnConflicto(ValidationError):
    """El servidor cambió mientras la app estaba sin conexión y el envío ya no se aplica.

    Es un `ValidationError` para quien no lo distinga (el backoffice); la API lo contesta
    409 con ``codigo``.
    """

    def __init__(self, codigo, mensaje):
        super().__init__(mensaje, code=codigo)
        self.codigo = codigo


class InspeccionReasignada(PermissionDenied):
    """El usuario **tuvo** asignado el relevamiento y se lo reasignaron a otro agente.

    Es un `PermissionDenied` —ya no lo puede cargar—, pero a diferencia de lo ajeno se le
    puede decir: el relevamiento ya estaba en su celular, no hay existencia que revelar.
    """

    codigo = CONFLICTO_REASIGNADA


# --------------------------------------------------------------------------- #
# Alcance
# --------------------------------------------------------------------------- #


def _edificios_de(dispositivos):
    """Ids de los edificios que ocupa alguno de ``dispositivos`` (subconsulta, sin JOIN)."""

    return _EdificioDispositivo.objects.filter(dispositivo_id__in=dispositivos.values("pk")).values("edificio_id")


def edificios_en_alcance(user, capacidad=CAP_ASIGNAR):
    """Edificios sobre los que el usuario puede ejercer ``capacidad``."""

    if not puede_en_programa_dispositivos(user, capacidad):
        return Edificio.objects.none()
    if puede_configurar_dispositivos(user):
        return Edificio.objects.all()
    return Edificio.objects.filter(pk__in=_edificios_de(dispositivos_en_alcance(user, capacidad)))


def inspecciones_visibles(user):
    """Los relevamientos que el usuario puede ver. Una sola regla para listados, detalle y fotos.

    Se suman tres caminos, cada uno por su capacidad: el coordinador ve los de su alcance,
    el agente **solo los que tiene asignados**, y quien opera un dispositivo ve los de los
    edificios que ese dispositivo ocupa.
    """

    if user is None or not getattr(user, "is_authenticated", False):
        return InspeccionEdificio.objects.none()
    if puede_configurar_dispositivos(user) and puede_en_programa_dispositivos(user, CAP_ASIGNAR):
        return InspeccionEdificio.objects.all()

    caminos = []
    if puede_en_programa_dispositivos(user, CAP_ASIGNAR):
        caminos.append(Q(edificio_id__in=_edificios_de(dispositivos_en_alcance(user, CAP_ASIGNAR))))
    if puede_en_programa_dispositivos(user, CAP_RELEVAR):
        caminos.append(Q(asignado_a=user))
    if puede_en_programa_dispositivos(user, CAP_VER):
        caminos.append(Q(edificio_id__in=_edificios_de(dispositivos_en_alcance(user, CAP_VER))))
    if not caminos:
        return InspeccionEdificio.objects.none()
    return InspeccionEdificio.objects.filter(reduce(or_, caminos))


def inspecciones_asignadas(user):
    """Las tareas en curso del agente: lo que le llega a la app. Nada más."""

    if not puede_en_programa_dispositivos(user, CAP_RELEVAR):
        return InspeccionEdificio.objects.none()
    return InspeccionEdificio.objects.filter(asignado_a=user, estado=InspeccionEdificio.Estado.ASIGNADA).select_related(
        "edificio"
    )


def inspecciones_del_agente(user):
    """Todo lo que el agente tiene asignado, en cualquier estado: el detalle de la app.

    Un relevamiento cancelado lo sigue viendo, con su motivo, para que la app lo saque de
    la agenda; uno reasignado ya no es suyo y no está acá.
    """

    if not puede_en_programa_dispositivos(user, CAP_RELEVAR):
        return InspeccionEdificio.objects.none()
    return InspeccionEdificio.objects.filter(asignado_a=user)


def inspecciones_para_envio(user):
    """A qué relevamientos puede **intentar** enviarles algo la app: los suyos y los que tuvo.

    Los que tuvo están para contestar «se reasignó» (409) en vez de «no existe»; el servicio
    igual rechaza la carga. Lo de otro agente que nunca fue suyo no está, y la API contesta
    404, el mismo que para un id que no existe.
    """

    if not puede_en_programa_dispositivos(user, CAP_RELEVAR):
        return InspeccionEdificio.objects.none()
    tuvo = _AgenteAnterior.objects.filter(user=user).values("inspeccionedificio_id")
    return InspeccionEdificio.objects.filter(Q(asignado_a=user) | Q(pk__in=tuvo))


def _personal_del_edificio(edificio):
    """Ids de usuario con un rol activo asignado a alguna institución del edificio."""

    return AsignacionDispositivo.objects.filter(
        dispositivo_id__in=_EdificioDispositivo.objects.filter(edificio=edificio).values("dispositivo_id"),
        activo=True,
        rol__meta__activo=True,
    ).values("rol__user")


def _candidatos_a_relevar():
    """Usuarios activos con un rol activo del programa que tenga ``inspeccion.relevar``."""

    programa = programa_dispositivos()
    if programa is None:
        return get_user_model().objects.none()
    return get_user_model().objects.filter(
        is_active=True,
        groups__meta__activo=True,
        groups__meta__programa=programa,
        groups__permissions__codename=rbac.codename_de(CAP_RELEVAR),
    )


def agentes_asignables(edificio):
    """Candidatos para el selector de P21: usuarios activos que pueden relevar en Dispositivos.

    Por capacidad (un rol activo del programa con ``inspeccion.relevar``), nunca por
    nombre de grupo. Con :data:`AGENTE_DEBE_SER_EXTERNO`, sin el personal del edificio.
    """

    candidatos = _candidatos_a_relevar()
    if AGENTE_DEBE_SER_EXTERNO:
        candidatos = candidatos.exclude(pk__in=_personal_del_edificio(edificio))
    return candidatos.distinct().order_by("first_name", "last_name", "username")


def agentes_asignables_para(edificios):
    """El selector de agentes cuando el edificio se elige en el mismo modal (P4).

    Es la unión de :func:`agentes_asignables` sobre ``edificios``: queda afuera solo quien es
    personal de **todos** (cada edificio con su propio personal, en una consulta y no una por
    edificio). Con uno solo es exactamente ``agentes_asignables(edificio)``. El agente que
    resulta válido para un edificio y no para otro lo rechaza el servicio al crear
    (:func:`_validar_agente`), con el edificio ya elegido: la regla vive ahí, no acá.
    """

    ids = [edificio.pk for edificio in edificios]
    candidatos = _candidatos_a_relevar()
    if AGENTE_DEBE_SER_EXTERNO and ids:
        pares = AsignacionDispositivo.objects.filter(
            dispositivo__edificios__in=ids, activo=True, rol__meta__activo=True
        ).values_list("dispositivo__edificios", "rol__user")
        personal = {pk: set() for pk in ids}
        for edificio_id, usuario_id in pares:
            personal[edificio_id].add(usuario_id)
        en_todos = set.intersection(*personal.values())
        candidatos = candidatos.exclude(pk__in=en_todos)
    return candidatos.distinct().order_by("first_name", "last_name", "username")


def _validar_agente(agente, edificio):
    if agente is None or not agente.is_active:
        raise ValidationError({"asignado_a": "Elegí un agente activo."})
    if not puede_en_programa_dispositivos(agente, CAP_RELEVAR):
        raise ValidationError({"asignado_a": "El agente elegido no puede relevar en el Programa Dispositivos."})
    if AGENTE_DEBE_SER_EXTERNO and _personal_del_edificio(edificio).filter(rol__user=agente).exists():
        raise ValidationError(
            {"asignado_a": "El relevamiento no se asigna al personal de una institución que ocupa el edificio."}
        )


def _exigir_alcance_coordinador(usuario, edificio):
    if not edificios_en_alcance(usuario, CAP_ASIGNAR).filter(pk=edificio.pk).exists():
        raise PermissionDenied("No tenés alcance para asignar relevamientos de este edificio.")


def _bloquear(inspeccion):
    return InspeccionEdificio.objects.select_for_update().get(pk=inspeccion.pk)


def _nombre(usuario):
    return (usuario.get_full_name() or usuario.get_username()) if usuario is not None else "—"


def _trazar(inspeccion, usuario, accion, detalle):
    """Una línea de auditoría por acción, en la misma transacción que el cambio (#699).

    El detalle se escribe legible ahora: es lo que va a leer el historial del dispositivo.
    """

    TrazaInspeccion.objects.create(inspeccion=inspeccion, usuario=usuario, accion=accion, detalle=detalle)


# --------------------------------------------------------------------------- #
# Coordinador: crear, reasignar, cancelar y revisar
# --------------------------------------------------------------------------- #


@transaction.atomic
def crear_inspeccion(usuario, *, edificio, asignado_a, fecha_vencimiento, indicaciones=""):
    """El coordinador crea la tarea y se la asigna a un agente.

    Un edificio tiene **un solo relevamiento en curso**: el segundo se rechaza y lo que
    corresponde es reasignar el que está. Como MySQL y MariaDB no tienen índices parciales
    (un `UniqueConstraint` con `condition=` no existiría en producción), la regla la
    sostiene el bloqueo de la fila del edificio.
    """

    edificio = Edificio.objects.select_for_update().get(pk=edificio.pk)
    # Comparte candado con la última desvinculación. El alcance se vuelve a leer
    # después de esperar: antes del lock todavía podía existir el último vínculo.
    _exigir_alcance_coordinador(usuario, edificio)
    if not edificio.dispositivos.exists():
        raise ValidationError({"edificio": "El edificio necesita al menos un dispositivo vinculado."})
    if not edificio.activo:
        raise ValidationError({"edificio": "El edificio está inactivo."})
    if fecha_vencimiento < timezone.localdate():
        raise ValidationError({"fecha_vencimiento": "El vencimiento no puede ser anterior a hoy."})
    if edificio.inspecciones.filter(estado=InspeccionEdificio.Estado.ASIGNADA).exists():
        raise ValidationError({"edificio": "El edificio ya tiene un relevamiento en curso: reasignalo."})
    _validar_agente(asignado_a, edificio)
    inspeccion = InspeccionEdificio.objects.create(
        edificio=edificio,
        asignado_a=asignado_a,
        creado_por=usuario,
        fecha_vencimiento=fecha_vencimiento,
        indicaciones=indicaciones.strip(),
    )
    _trazar(
        inspeccion,
        usuario,
        TrazaInspeccion.Accion.ASIGNADA,
        f"Edificio {edificio.nombre} · agente {_nombre(asignado_a)} · vence el {fecha_vencimiento:%d/%m/%Y}",
    )
    return inspeccion


@transaction.atomic
def reasignar_inspeccion(usuario, inspeccion, asignado_a):
    """Cambia el agente de un relevamiento en curso. El anterior deja de verlo."""

    _exigir_alcance_coordinador(usuario, inspeccion.edificio)
    inspeccion = _bloquear(inspeccion)
    if not inspeccion.en_curso:
        raise ValidationError("Solo se reasigna un relevamiento en curso.")
    if asignado_a is not None and asignado_a.pk == inspeccion.asignado_a_id:
        raise ValidationError({"asignado_a": "El relevamiento ya está asignado a ese agente."})
    _validar_agente(asignado_a, inspeccion.edificio)
    anterior = inspeccion.asignado_a
    # El anterior queda anotado: si su app manda algo después, se le contesta «se reasignó».
    inspeccion.agentes_anteriores.add(inspeccion.asignado_a_id)
    inspeccion.asignado_a = asignado_a
    inspeccion.save(update_fields=["asignado_a", "modificado"])
    _trazar(
        inspeccion,
        usuario,
        TrazaInspeccion.Accion.REASIGNADA,
        f"Edificio {inspeccion.edificio.nombre} · de {_nombre(anterior)} a {_nombre(asignado_a)}",
    )
    return inspeccion


@transaction.atomic
def cancelar_inspeccion(usuario, inspeccion, motivo):
    _exigir_alcance_coordinador(usuario, inspeccion.edificio)
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValidationError({"motivo_cancelacion": "Cancelar un relevamiento exige un motivo."})
    inspeccion = _bloquear(inspeccion)
    if not inspeccion.en_curso:
        raise ValidationError("Solo se cancela un relevamiento en curso.")
    inspeccion.estado = InspeccionEdificio.Estado.CANCELADA
    inspeccion.motivo_cancelacion = motivo[:200]
    inspeccion.save(update_fields=["estado", "motivo_cancelacion", "modificado"])
    _trazar(
        inspeccion,
        usuario,
        TrazaInspeccion.Accion.CANCELADA,
        f"Edificio {inspeccion.edificio.nombre} · motivo: {inspeccion.motivo_cancelacion}",
    )
    return inspeccion


# --------------------------------------------------------------------------- #
# Agente: resultado y fotos
# --------------------------------------------------------------------------- #


@transaction.atomic
def marcar_revisado(usuario, inspeccion):
    """La coordinación revisa una sola vez un resultado, sin cambiar REALIZADA."""

    inspeccion = _bloquear(inspeccion)
    _exigir_alcance_coordinador(usuario, inspeccion.edificio)
    if inspeccion.estado != InspeccionEdificio.Estado.REALIZADA:
        raise ValidationError("Solo se puede revisar un relevamiento completado.")
    if inspeccion.revisado_en is not None:
        raise ValidationError("El relevamiento ya está revisado.")
    inspeccion.revisado_en = timezone.now()
    inspeccion.revisado_por = usuario
    inspeccion.save(update_fields=["revisado_en", "revisado_por", "modificado"])
    _trazar(
        inspeccion,
        usuario,
        TrazaInspeccion.Accion.REVISADA,
        f"Edificio {inspeccion.edificio.nombre} · revisado por {_nombre(usuario)}",
    )
    return inspeccion


def puede_revisar(usuario, inspeccion, *, edificios_gestionables=None):
    """Disponibilidad de la acción; el POST vuelve a validar bajo el candado."""

    if inspeccion.estado != InspeccionEdificio.Estado.REALIZADA or inspeccion.revisado_en is not None:
        return False
    if edificios_gestionables is not None:
        return inspeccion.edificio_id in edificios_gestionables
    return edificios_en_alcance(usuario, CAP_ASIGNAR).filter(pk=inspeccion.edificio_id).exists()


def _exigir_capacidad_de_agente(usuario):
    if not puede_en_programa_dispositivos(usuario, CAP_RELEVAR):
        raise PermissionDenied("No tenés la capacidad de relevar edificios.")


def _exigir_asignado(usuario, inspeccion):
    """La guarda de «solo lo asignado»: la capacidad sola no alcanza."""

    if inspeccion.asignado_a_id == usuario.pk:
        return
    if inspeccion.agentes_anteriores.filter(pk=usuario.pk).exists():
        raise InspeccionReasignada("El relevamiento se reasignó a otro agente.")
    raise PermissionDenied("Solo el agente asignado carga este relevamiento.")


def _bloquear_como_agente(usuario, inspeccion):
    _exigir_capacidad_de_agente(usuario)
    inspeccion = _bloquear(inspeccion)
    _exigir_asignado(usuario, inspeccion)
    return inspeccion


def _como_uuid(valor):
    if valor is None or isinstance(valor, uuid.UUID):
        return valor
    try:
        return uuid.UUID(str(valor))
    except (TypeError, ValueError, AttributeError):
        raise ValidationError({"uuid_cliente": "El identificador del envío no es un UUID válido."}) from None


def _conflicto_cancelada(inspeccion):
    motivo = f": {inspeccion.motivo_cancelacion}" if inspeccion.motivo_cancelacion else "."
    return InspeccionEnConflicto(CONFLICTO_CANCELADA, f"El relevamiento fue cancelado{motivo}")


def _conflicto_uuid_en_uso():
    return InspeccionEnConflicto(CONFLICTO_UUID_EN_USO, "Ese identificador ya se usó para otra foto.")


def _conflicto_estado():
    return InspeccionEnConflicto(CONFLICTO_ESTADO, "El relevamiento ya no admite esta operación.")


def _guardar_foto(inspeccion, usuario, archivo, descripcion="", uuid_cliente=None):
    foto = FotoInspeccion(
        inspeccion=inspeccion,
        archivo=archivo,
        descripcion=descripcion[:120],
        cargada_por=usuario,
        uuid_cliente=uuid_cliente,
    )
    # El único de `uuid_cliente` lo resuelve `agregar_foto` con `q_uuid_en_texto`: el
    # chequeo de `full_clean` usa el lookup del ORM, que en MariaDB no ve la otra forma.
    foto.full_clean(validate_unique=False)
    try:
        with transaction.atomic():
            foto.save()
    except IntegrityError:
        # Solo puede ser el `UNIQUE` de `uuid_cliente`: el mismo identificador llegó a la vez
        # para otro relevamiento. El archivo ya se escribió: se anota para que el rollback
        # de la operación lo borre.
        anotar_archivo_escrito(foto.archivo, asignado=archivo)
        raise _conflicto_uuid_en_uso() from None
    anotar_archivo_escrito(foto.archivo, asignado=archivo)
    foto.ya_existia = False
    return foto


@archivos_atomicos
@transaction.atomic
def registrar_resultado(usuario, inspeccion, *, criticidad, observaciones="", fotos=(), uuid_resultado=None):
    """El agente asignado cierra el relevamiento: criticidad, observaciones y fotos.

    ``fotos`` es una lista de archivos o de pares ``(archivo, descripcion)``. Si algo
    falla, la base vuelve atrás y las fotos ya escritas se borran (`core.archivos`).

    ``uuid_resultado`` es el identificador que generó la app (task 39): reenviar el mismo
    sobre un relevamiento ya realizado devuelve el relevamiento como quedó, sin tocarlo;
    cualquier otro envío sobre uno realizado es :data:`CONFLICTO_YA_REALIZADA`, y sobre uno
    cancelado, :data:`CONFLICTO_CANCELADA`.
    """

    uuid_resultado = _como_uuid(uuid_resultado)
    inspeccion = _bloquear_como_agente(usuario, inspeccion)
    if inspeccion.estado == InspeccionEdificio.Estado.REALIZADA:
        if uuid_resultado is not None and inspeccion.uuid_resultado == uuid_resultado:
            return inspeccion
        raise InspeccionEnConflicto(CONFLICTO_YA_REALIZADA, "Este relevamiento ya tiene un resultado registrado.")
    if inspeccion.estado == InspeccionEdificio.Estado.CANCELADA:
        raise _conflicto_cancelada(inspeccion)
    # Lista blanca, no negra: los dos chequeos de arriba son por su código, pero lo único
    # que se cierra es un relevamiento **en curso**. Un estado nuevo cae acá, no al cuerpo.
    if not inspeccion.en_curso:
        raise _conflicto_estado()
    if criticidad not in InspeccionEdificio.Criticidad.values:
        raise ValidationError({"criticidad": "Elegí una criticidad válida."})
    inspeccion.estado = InspeccionEdificio.Estado.REALIZADA
    inspeccion.criticidad = criticidad
    inspeccion.observaciones = (observaciones or "").strip()
    inspeccion.realizada_en = timezone.now()
    inspeccion.realizada_por = usuario
    inspeccion.uuid_resultado = uuid_resultado
    inspeccion.save(
        update_fields=[
            "estado",
            "criticidad",
            "observaciones",
            "realizada_en",
            "realizada_por",
            "uuid_resultado",
            "modificado",
        ]
    )
    cantidad = 0
    for foto in fotos:
        archivo, descripcion = foto if isinstance(foto, tuple) else (foto, "")
        _guardar_foto(inspeccion, usuario, archivo, descripcion)
        cantidad += 1
    # Una sola línea para el resultado y sus fotos: es una acción, no una por archivo.
    detalle = f"Edificio {inspeccion.edificio.nombre} · criticidad {inspeccion.get_criticidad_display()}"
    if cantidad:
        detalle += f" · {cantidad} foto{'s' if cantidad != 1 else ''}"
    _trazar(inspeccion, usuario, TrazaInspeccion.Accion.REALIZADA, detalle)
    return inspeccion


@archivos_atomicos
@transaction.atomic
def agregar_foto(usuario, inspeccion, archivo, descripcion="", *, uuid_cliente=None):
    """Una foto más, en curso o ya realizado: la app sin conexión puede mandarlas después.

    Cada carga es una fila nueva; ninguna pisa a otra. Un relevamiento cancelado no
    recibe fotos (:data:`CONFLICTO_CANCELADA`), ni uno ya revisado admite fotos nuevas.

    Con ``uuid_cliente`` (task 39) es idempotente: si esa foto ya llegó —del mismo agente y
    al mismo relevamiento— se devuelve la fila que quedó, con ``ya_existia = True``, aunque
    después el relevamiento se haya cancelado o reasignado: el reenvío no cambia nada. El
    mismo identificador en otra foto es :data:`CONFLICTO_UUID_EN_USO`.
    """

    uuid_cliente = _como_uuid(uuid_cliente)
    _exigir_capacidad_de_agente(usuario)
    inspeccion = _bloquear(inspeccion)
    previa = None
    if uuid_cliente is not None:
        previa = FotoInspeccion.objects.filter(q_uuid_en_texto("uuid_cliente", uuid_cliente)).first()
        if previa is not None and previa.inspeccion_id == inspeccion.pk and previa.cargada_por_id == usuario.pk:
            previa.ya_existia = True
            return previa
    _exigir_asignado(usuario, inspeccion)
    if previa is not None:
        raise _conflicto_uuid_en_uso()
    if inspeccion.estado == InspeccionEdificio.Estado.CANCELADA:
        raise _conflicto_cancelada(inspeccion)
    # Igual que en `registrar_resultado`: acá la lista blanca son dos estados —en curso y
    # realizado—, y cualquier otro se rechaza en vez de caer en el alta.
    if inspeccion.revisado_en is not None or not (
        inspeccion.en_curso or inspeccion.estado == InspeccionEdificio.Estado.REALIZADA
    ):
        raise _conflicto_estado()
    foto = _guardar_foto(inspeccion, usuario, archivo, descripcion, uuid_cliente)
    # La traza cuelga del alta, no de la llamada: el reenvío idempotente ya volvió arriba y no
    # deja una segunda línea de auditoría por la misma foto.
    _trazar(inspeccion, usuario, TrazaInspeccion.Accion.FOTO, f"Edificio {inspeccion.edificio.nombre}")
    return foto


# --------------------------------------------------------------------------- #
# Listado del coordinador (P21): situación derivada, resumen y edificios para asignar
# --------------------------------------------------------------------------- #

#: Un relevamiento en curso está «por vencer» cuando le quedan estos días o menos (mockup P21).
DIAS_POR_VENCER = 30


class Situacion:
    """Lo que dice el badge de Estado de P21. **No es un estado del modelo**: dentro de lo que
    está en curso, «vencido», «por vencer» y «al día» se derivan del vencimiento (Cambio 275).

    Los rótulos viven acá para que la tarjeta, el badge y la píldora digan lo mismo.
    """

    VENCIDA = "VENCIDA"
    POR_VENCER = "POR_VENCER"
    AL_DIA = "AL_DIA"
    REALIZADA = InspeccionEdificio.Estado.REALIZADA.value
    CANCELADA = InspeccionEdificio.Estado.CANCELADA.value

    ETIQUETAS = {
        VENCIDA: "Vencido",
        POR_VENCER: "Por vencer",
        AL_DIA: "Al día",
        REALIZADA: "Completado",
        CANCELADA: "Cancelado",
    }
    #: Las tres situaciones de lo que está en curso: la píldora «Estado» de la solapa En curso.
    EN_CURSO = (
        (VENCIDA, "Vencidos"),
        (POR_VENCER, "Por vencer"),
        (AL_DIA, "Al día"),
    )


def situacion_de(inspeccion, hoy=None):
    """La situación de un relevamiento: vencido / por vencer / al día si está en curso, o su estado."""

    if not inspeccion.en_curso:
        return inspeccion.estado
    hoy = hoy or timezone.localdate()
    if inspeccion.fecha_vencimiento < hoy:
        return Situacion.VENCIDA
    if inspeccion.fecha_vencimiento <= hoy + timedelta(days=DIAS_POR_VENCER):
        return Situacion.POR_VENCER
    return Situacion.AL_DIA


def _condicion_situacion(situacion, hoy):
    """``Q`` de una situación en curso; ``None`` si no es una de :attr:`Situacion.EN_CURSO`."""

    from programas.selectors.vencimiento_inspecciones import condicion_relevamiento_vencido

    limite = hoy + timedelta(days=DIAS_POR_VENCER)
    en_curso = Q(estado=InspeccionEdificio.Estado.ASIGNADA)
    condiciones = {
        Situacion.VENCIDA: condicion_relevamiento_vencido(hoy),
        Situacion.POR_VENCER: en_curso & Q(fecha_vencimiento__gte=hoy, fecha_vencimiento__lte=limite),
        Situacion.AL_DIA: en_curso & Q(fecha_vencimiento__gt=limite),
    }
    return condiciones.get(situacion)


def filtrar_por_situacion(queryset, situacion, hoy=None):
    """Acota ``queryset`` a una situación en curso (vencido, por vencer, al día). Otra no filtra."""

    condicion = _condicion_situacion(situacion, hoy or timezone.localdate())
    return queryset if condicion is None else queryset.filter(condicion)


def resumen_listado(queryset, *, situacion="", asignado_a_id=None, hoy=None):
    """Los números de P21 en **una** consulta: las tarjetas y los contadores de las solapas.

    Las tarjetas son sobre todo ``queryset`` (``asignados`` = en curso, que se parte en
    ``al_dia`` + ``por_vencer`` + ``vencidos``). Los contadores de las solapas cuentan lo que
    cada una muestra: el agente filtra las tres y la situación solo la de En curso.
    """

    hoy = hoy or timezone.localdate()
    estado = InspeccionEdificio.Estado
    en_curso = Q(estado=estado.ASIGNADA)
    por_agente = Q(asignado_a_id=asignado_a_id) if asignado_a_id else Q()
    totales = queryset.aggregate(
        asignados=Count("pk", filter=en_curso),
        vencidos=Count("pk", filter=_condicion_situacion(Situacion.VENCIDA, hoy)),
        por_vencer=Count("pk", filter=_condicion_situacion(Situacion.POR_VENCER, hoy)),
        al_dia=Count("pk", filter=_condicion_situacion(Situacion.AL_DIA, hoy)),
        solapa_en_curso=Count("pk", filter=(_condicion_situacion(situacion, hoy) or en_curso) & por_agente),
        solapa_completados=Count("pk", filter=Q(estado=estado.REALIZADA) & por_agente),
        solapa_revisados=Count("pk", filter=Q(estado=estado.REALIZADA, revisado_en__isnull=False) & por_agente),
        solapa_cancelados=Count("pk", filter=Q(estado=estado.CANCELADA) & por_agente),
    )
    return {clave: valor or 0 for clave, valor in totales.items()}


def edificios_para_asignar(user):
    """En alcance, activos, con dispositivos vinculados y **sin uno en curso**.

    Es la misma regla que hace cumplir :func:`crear_inspeccion`; acá es la lista del selector.
    """

    return (
        edificios_en_alcance(user, CAP_ASIGNAR)
        .filter(activo=True, pk__in=_EdificioDispositivo.objects.values("edificio_id"))
        .exclude(inspecciones__estado=InspeccionEdificio.Estado.ASIGNADA)
        .order_by("nombre", "pk")
    )


def edificios_para_asignar_del_dispositivo(user, dispositivo):
    """Los edificios de ``dispositivo`` que ``user`` puede asignar ahora: lo que ofrece P4.

    Es :func:`edificios_para_asignar` acotada al dispositivo, en una sola consulta y ya como
    lista (el botón, el selector y el POST miran la misma). Sin ``inspeccion.asignar`` o sin
    alcance sobre el edificio no hay ninguno; uno con relevamiento en curso tampoco.
    """

    return list(edificios_para_asignar(user).filter(dispositivos=dispositivo))


def edificios_sin_relevar(user):
    """La solapa «Sin relevar nunca» de P21: edificios del alcance **sin ninguna realizada**.

    Es una lista de **edificios**, no de relevamientos: lo que falta no tiene fila en
    `InspeccionEdificio` y por eso no puede salir de las otras tres solapas. «Sin relevar»
    es lo mismo que mide el semáforo (:data:`SIN_RELEVAR`): uno en curso todavía no cuenta,
    y uno cancelado tampoco —no dejó resultado—, así que el edificio sigue acá hasta que
    alguien cierre un relevamiento.

    Solo los activos con dispositivos vinculados: `crear_inspeccion` rechaza los
    inactivos y huérfanos, y listarlos sería ofrecer una acción que no existe.
    """

    return (
        edificios_en_alcance(user, CAP_ASIGNAR)
        .filter(activo=True, pk__in=_EdificioDispositivo.objects.values("edificio_id"))
        .exclude(inspecciones__estado=InspeccionEdificio.Estado.REALIZADA)
        .order_by("nombre", "pk")
    )


def inspecciones_en_curso_por_edificio(edificio_ids):
    """``{edificio_id: InspeccionEdificio}`` de lo que está en curso, en una consulta.

    Para la solapa «Sin relevar nunca»: un edificio que nunca se relevó puede tener un
    relevamiento **en curso**, y ahí no se vuelve a asignar (es la regla de
    :func:`crear_inspeccion`). Sin una fila por edificio no habría cómo decirlo sin una
    consulta por fila.
    """

    ids = {pk for pk in edificio_ids if pk is not None}
    if not ids:
        return {}
    en_curso = InspeccionEdificio.objects.filter(
        edificio_id__in=ids, estado=InspeccionEdificio.Estado.ASIGNADA
    ).select_related("asignado_a")
    return {inspeccion.edificio_id: inspeccion for inspeccion in en_curso}


# --------------------------------------------------------------------------- #
# Lecturas: la última de cada edificio (semáforo) y las de un dispositivo (P19)
# --------------------------------------------------------------------------- #


def ultima_inspeccion(edificio):
    """La última realizada del edificio, o ``None`` si nunca se relevó."""

    return (
        InspeccionEdificio.objects.filter(edificio=edificio, estado=InspeccionEdificio.Estado.REALIZADA)
        .order_by("-realizada_en", "-pk")
        .first()
    )


def subconsulta_ultima_realizada():
    """El id de la última realizada del edificio de la fila (``OuterRef("pk")``), para anotar.

    Es la única definición de «la última»: la usan el semáforo y las alertas del dispositivo.
    Escalar con ``LIMIT 1`` en el ``SELECT``: MySQL no admite ``LIMIT`` dentro de un ``IN``.
    """

    return Subquery(
        InspeccionEdificio.objects.filter(edificio=OuterRef("pk"), estado=InspeccionEdificio.Estado.REALIZADA)
        .order_by("-realizada_en", "-pk")
        .values("pk")[:1]
    )


def ultimas_inspecciones_por_edificio(edificio_ids):
    """``{edificio_id: InspeccionEdificio | None}`` en dos consultas, sin importar cuántos.

    ``None`` es **sin relevar**: el edificio está en el diccionario y no tiene ninguna
    realizada. Un edificio relevado y sano trae su inspección con criticidad ``BAJA``. La
    última va como subconsulta escalar con ``LIMIT 1`` en el ``SELECT`` —MySQL no admite
    ``LIMIT`` dentro de un ``IN``— y las filas se traen después por id.
    """

    ids = {pk for pk in edificio_ids if pk is not None}
    if not ids:
        return {}
    pares = dict(
        Edificio.objects.filter(pk__in=ids)
        .annotate(ultima_id=subconsulta_ultima_realizada())
        .order_by()
        .values_list("pk", "ultima_id")
    )
    filas = InspeccionEdificio.objects.in_bulk([pk for pk in pares.values() if pk is not None])
    return {edificio_id: filas.get(ultima_id) for edificio_id, ultima_id in pares.items()}


# --------------------------------------------------------------------------- #
# Semáforo de criticidad del edificio (task 40 · #705)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Semaforo:
    """Lo que dibuja el badge: ``texto`` y ``tono`` (`badge-{{ tono }}`). El template no decide nada.

    ``nivel`` es el código estable que usan los tests y el orden de gravedad: la criticidad
    de la última realizada (``ALTA``, ``MEDIA``, ``BAJA``), :data:`SIN_RELEVAR`,
    :data:`SIN_EDIFICIO` o :data:`VENCIDO` (relevamiento en curso con fecha pasada).
    """

    nivel: str
    texto: str
    tono: str


SIN_RELEVAR = "SIN_RELEVAR"
SIN_EDIFICIO = "SIN_EDIFICIO"
VENCIDO = "VENCIDO"

#: Vocabulario operativo del semáforo: el texto dice el estado sin depender del color. «Bueno» y
#: «Regular» son los del mockup (P19, «Estado físico»); «Crítico» es el nivel que el mockup no
#: muestra y la escala del modelo sí tiene («requiere intervención»).
SEMAFOROS = {
    VENCIDO: Semaforo(VENCIDO, "Vencido", "warning"),
    InspeccionEdificio.Criticidad.ALTA: Semaforo(InspeccionEdificio.Criticidad.ALTA, "Crítico", "danger"),
    InspeccionEdificio.Criticidad.MEDIA: Semaforo(InspeccionEdificio.Criticidad.MEDIA, "Regular", "warning"),
    InspeccionEdificio.Criticidad.BAJA: Semaforo(InspeccionEdificio.Criticidad.BAJA, "Bueno", "success"),
    SIN_RELEVAR: Semaforo(SIN_RELEVAR, "Sin relevar", "gray"),
    SIN_EDIFICIO: Semaforo(SIN_EDIFICIO, "Sin edificio cargado", "gray"),
}

#: Qué gana cuando un dispositivo ocupa más de un edificio: el peor. «Sin relevar» va por encima
#: de «Bueno» porque no saber cómo está un edificio no es lo mismo que saber que está sano: si
#: ganara el sano, el edificio que nadie miró quedaría escondido detrás de él.
_GRAVEDAD = {
    InspeccionEdificio.Criticidad.ALTA: 4,
    VENCIDO: 3,
    InspeccionEdificio.Criticidad.MEDIA: 2,
    SIN_RELEVAR: 1,
    InspeccionEdificio.Criticidad.BAJA: 0,
}


def semaforo_de_inspeccion(inspeccion, *, vencido=False):
    """Crítico prevalece; luego vencimiento en curso y última realizada (``None`` = sin relevar)."""

    if inspeccion is not None and inspeccion.criticidad == InspeccionEdificio.Criticidad.ALTA:
        return SEMAFOROS[InspeccionEdificio.Criticidad.ALTA]
    if vencido:
        return SEMAFOROS[VENCIDO]
    if inspeccion is None:
        return SEMAFOROS[SIN_RELEVAR]
    semaforo = SEMAFOROS.get(inspeccion.criticidad)
    if semaforo is None:
        # Una escala que el Ministerio cambie y que este mapa todavía no conozca: se muestra
        # con su etiqueta y sin color, en lugar de romper la pantalla.
        return Semaforo(inspeccion.criticidad, inspeccion.get_criticidad_display(), "gray")
    return semaforo


def semaforo_de_ultimas(ultimas, *, vencidos=()):
    """El semáforo de un dispositivo: ``ultimas`` es ``{edificio_id: InspeccionEdificio | None}``.

    Sin edificios cargados es :data:`SIN_EDIFICIO`; con varios, gana el más grave.
    """

    if not ultimas:
        return SEMAFOROS[SIN_EDIFICIO]
    semaforos = [
        semaforo_de_inspeccion(inspeccion, vencido=edificio_id in vencidos)
        for edificio_id, inspeccion in ultimas.items()
    ]
    return max(semaforos, key=lambda semaforo: _GRAVEDAD.get(semaforo.nivel, 1))


def semaforos_de_dispositivos(dispositivo_ids):
    """``{dispositivo_id: Semaforo}`` en tres consultas fijas: el listado no hace una por fila."""

    from programas.selectors.vencimiento_inspecciones import tiene_relevamiento_vencido

    ids = {pk for pk in dispositivo_ids if pk is not None}
    vinculos = list(
        _EdificioDispositivo.objects.filter(dispositivo_id__in=ids)
        .annotate(vencido=tiene_relevamiento_vencido("edificio_id"))
        .values_list("dispositivo_id", "edificio_id", "vencido")
    )
    ultimas = ultimas_inspecciones_por_edificio({e for _d, e, _v in vinculos})
    por_dispositivo = {pk: {} for pk in ids}
    vencidos = set()
    for dispositivo_id, edificio_id, vencido in vinculos:
        por_dispositivo[dispositivo_id][edificio_id] = ultimas.get(edificio_id)
        if vencido:
            vencidos.add(edificio_id)
    return {pk: semaforo_de_ultimas(filas, vencidos=vencidos) for pk, filas in por_dispositivo.items()}


# --------------------------------------------------------------------------- #
# Quién ve la asignación, la galería y el informe de un relevamiento
# --------------------------------------------------------------------------- #

#: El tope que dibuja `components/_galeria_fotos.html`: la tanda se recorta acá, no en la pieza.
FOTOS_POR_TANDA = 24

#: Formatos que un navegador no dibuja en un `<img>`. Desde el rechazo de HEIC/HEIF
#: (`core.validators.FOTO_EXTENSIONES`) no entra ninguno nuevo; el manejo queda por las
#: fotos que ya hubieran entrado antes.
_SIN_VISTA_PREVIA = (".heic", ".heif")


def ve_la_asignacion(usuario, inspeccion):
    """Si ``usuario`` ve **de quién es** el relevamiento: el agente y las indicaciones.

    Decisión del juez (MVP v2, etapa 4): **la institución relevada no ve el nombre del
    agente asignado**. Un relevamiento en curso le dice «en curso» y nada más. El agente
    externo es la garantía de que no se omitan irregularidades (`AGENTE_DEBE_SER_EXTERNO`)
    y saber de antemano quién va a ir —y qué le pidieron mirar— la desarma.

    Lo ven dos: el **coordinador** del edificio (``inspeccion.asignar`` con alcance sobre
    él, que es quien asigna y reasigna) y el **propio agente**. Las indicaciones van con el
    nombre porque son de la misma conversación: lo que la coordinación le encarga al agente,
    no el resultado del relevamiento.

    La regla vive acá y no en el template: el template no evalúa permisos, y el nombre que
    no se puede mostrar **no se le pasa**.
    """

    if usuario is None or not getattr(usuario, "is_authenticated", False):
        return False
    if inspeccion.asignado_a_id is not None and inspeccion.asignado_a_id == usuario.pk:
        return True
    return inspeccion.edificio_id in edificios_con_asignacion_visible(usuario, [inspeccion.edificio_id])


def edificios_con_asignacion_visible(usuario, edificio_ids):
    """La versión por lote de :func:`ve_la_asignacion`: ids de edificio, en **una** consulta.

    La usa la solapa Infraestructura, que dibuja varios relevamientos: preguntar por fila
    sería un N+1 proporcional a la página. Sin la capacidad no consulta nada
    (`edificios_en_alcance` devuelve `none()`).
    """

    ids = {pk for pk in edificio_ids if pk is not None}
    if not ids:
        return set()
    return set(edificios_en_alcance(usuario, CAP_ASIGNAR).filter(pk__in=ids).values_list("pk", flat=True))


def edificios_de_dispositivo_con_asignacion_visible(usuario, dispositivo):
    """Lo mismo, acotado a los edificios de un dispositivo, **sin pedir antes sus ids**.

    La usa la solapa Historial del detalle, que lee las trazas por el dispositivo y no tiene
    la lista de edificios a mano: así resuelve el alcance en una consulta en vez de dos.
    """

    return set(edificios_en_alcance(usuario, CAP_ASIGNAR).filter(dispositivos=dispositivo).values_list("pk", flat=True))


def _fecha_corta(momento):
    return date_format(timezone.localtime(momento), "d/m/Y")


def fotos_para_galeria(inspeccion, fotos, tope=FOTOS_POR_TANDA):
    """Los dicts que pide `components/_galeria_fotos.html` para la tanda de un relevamiento.

    Una sola definición para la línea de tiempo de P19 y para el informe. La URL es la de
    `/media/`, que está **detrás de login** y con la misma regla de alcance que el
    relevamiento (`core.views.media`): nunca una URL pública.

    Una foto vieja en HEIC/HEIF va sin URL y la pieza dibuja la celda gris con cámara en vez
    de una imagen rota; ninguna nueva puede serlo.
    """

    fecha = _fecha_corta(inspeccion.realizada_en or inspeccion.creado)
    galeria = []
    for numero, foto in enumerate(fotos[:tope], start=1):
        rotulo = foto.descripcion or f"Foto {numero}"
        galeria.append(
            {
                "url": "" if foto.archivo.name.lower().endswith(_SIN_VISTA_PREVIA) else foto.archivo.url,
                "alt": f"{rotulo} · {inspeccion.edificio.nombre} · relevamiento del {fecha}",
                "rotulo": rotulo,
                "fecha": foto.creado,
            }
        )
    return galeria


#: Los tonos que el sistema de diseño sabe colorear en una stat card; el resto va con el de marca.
_TONOS_CON_COLOR = ("success", "warning", "danger")

#: Color del badge de cada situación en curso, para que el informe diga lo mismo que P21.
_TONOS_DE_SITUACION = {
    Situacion.VENCIDA: "danger",
    Situacion.POR_VENCER: "warning",
    Situacion.AL_DIA: "success",
}


def _indicadores_del_informe(inspeccion, semaforo, situacion_texto, total_fotos, hoy):
    """Las tres cifras del encabezado del informe, ya formateadas. El template no decide nada."""

    if semaforo is not None:
        estado = {"valor": semaforo.texto, "tono": semaforo.tono, "nota": "criticidad del último resultado"}
        cuando = {
            "etiqueta": "Relevado el",
            "valor": _fecha_corta(inspeccion.realizada_en),
            "icono": "fa-calendar-check",
            "nota": "queda en el registro del edificio",
        }
    else:
        estado = {
            "valor": situacion_texto,
            "tono": _TONOS_DE_SITUACION.get(situacion_de(inspeccion, hoy), "gray"),
            "nota": "todavía no hay resultado cargado",
        }
        cuando = {
            "etiqueta": "Vence el",
            "valor": date_format(inspeccion.fecha_vencimiento, "d/m/Y"),
            "icono": "fa-calendar-day",
            "nota": "fecha límite para cargar el resultado",
        }
    return [
        {
            "etiqueta": "Estado edilicio",
            "valor": estado["valor"],
            "icono": "fa-building",
            # La stat card chica no tiene gris: sin color, va con el de marca y el texto manda.
            "tono": estado["tono"] if estado["tono"] in _TONOS_CON_COLOR else "brand",
            "nota": estado["nota"],
        },
        {**cuando, "tono": "brand"},
        {
            "etiqueta": "Fotos",
            "valor": total_fotos,
            "icono": "fa-camera",
            "tono": "brand",
            "nota": "evidencia cargada por el agente",
        },
    ]


def informe_de_relevamiento(usuario, inspeccion, *, hoy=None):
    """Resultado y galería, con revisión disponible solo para su coordinación.

    Quién **entra** ya lo decidió `inspecciones_visibles` (ajeno e inexistente dan el mismo
    404); acá se decide **qué ve**: el resultado lo lee cualquiera que vea el relevamiento,
    y el agente y las indicaciones solo quien pasa :func:`ve_la_asignacion`.

    Costo fijo: el total de fotos y la tanda de la página (2 consultas), más la del alcance
    cuando el usuario puede coordinar. No crece con las fotos: la galería se recorta en
    :data:`FOTOS_POR_TANDA`.
    """

    hoy = hoy or timezone.localdate()
    realizada = inspeccion.estado == InspeccionEdificio.Estado.REALIZADA
    situacion = situacion_de(inspeccion, hoy)
    situacion_texto = Situacion.ETIQUETAS.get(situacion, situacion)
    semaforo = semaforo_de_inspeccion(inspeccion) if realizada else None
    total_fotos = inspeccion.fotos.count()
    fotos = list(inspeccion.fotos.order_by("creado", "pk")[:FOTOS_POR_TANDA])
    ve_asignacion = ve_la_asignacion(usuario, inspeccion)
    return {
        "relevamiento": inspeccion,
        "edificio": inspeccion.edificio,
        "realizada": realizada,
        "situacion": situacion,
        "situacion_texto": situacion_texto,
        "semaforo": semaforo,
        "relevo": _nombre(inspeccion.realizada_por) if realizada else "",
        "revisor": _nombre(inspeccion.revisado_por) if inspeccion.revisado_en else "",
        "puede_revisar": puede_revisar(usuario, inspeccion),
        # Vacío = no se muestra. El nombre que no se puede ver no llega al template.
        "agente": _nombre(inspeccion.asignado_a) if ve_asignacion else "",
        "indicaciones": inspeccion.indicaciones if ve_asignacion else "",
        "fotos": fotos_para_galeria(inspeccion, fotos),
        "total_fotos": total_fotos,
        "indicadores": _indicadores_del_informe(inspeccion, semaforo, situacion_texto, total_fotos, hoy),
    }


def inspecciones_de_dispositivo(dispositivo, *, incluir_canceladas=False):
    """Los relevamientos de los edificios que ocupa el dispositivo: los del predio compartido también.

    No aplica alcance: es la lectura de la solapa, que ya entró por ``dispositivo.ver``
    sobre este dispositivo. Para un listado por usuario está :func:`inspecciones_visibles`.
    """

    qs = InspeccionEdificio.objects.filter(
        edificio_id__in=_EdificioDispositivo.objects.filter(dispositivo=dispositivo).values("edificio_id")
    ).select_related("edificio", "asignado_a", "realizada_por", "revisado_por")
    if not incluir_canceladas:
        qs = qs.exclude(estado=InspeccionEdificio.Estado.CANCELADA)
    return qs
