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
de los edificios que ocupa: es la solapa Infraestructura (P19).

Lo que define el Ministerio y acá es un default
----------------------------------------------

La escala de criticidad y los estados viven en el modelo como `TextChoices`. Que el agente
sea **externo a la institución** relevada es :data:`AGENTE_DEBE_SER_EXTERNO`: el mockup
(P21) lo dice —«nunca se asigna al personal de la institución relevada»— y se aplica, pero
apagarlo es cambiar esa constante. «Personal» es tener un rol activo asignado
(`AsignacionDispositivo`) a alguno de los dispositivos que ocupan el edificio.

La consulta del semáforo
------------------------

:func:`ultimas_inspecciones_por_edificio` y :func:`ultimas_inspecciones_de_dispositivos`
son lo que va a leer el semáforo de la task 40. Devuelven ``None`` para el edificio **sin
relevar** —que no es lo mismo que relevado y sano, una inspección con criticidad
``BAJA``— y un diccionario vacío para el dispositivo que no tiene edificio cargado. Son
consultas fijas: no crecen con la cantidad de edificios ni de dispositivos.
"""

from functools import reduce
from operator import or_

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import OuterRef, Q, Subquery
from django.utils import timezone

from core import rbac
from core.archivos import anotar_archivo_escrito, archivos_atomicos
from programas.models import AsignacionDispositivo, Edificio, FotoInspeccion, InspeccionEdificio
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


def _personal_del_edificio(edificio):
    """Ids de usuario con un rol activo asignado a alguna institución del edificio."""

    return AsignacionDispositivo.objects.filter(
        dispositivo_id__in=_EdificioDispositivo.objects.filter(edificio=edificio).values("dispositivo_id"),
        activo=True,
        rol__meta__activo=True,
    ).values("rol__user")


def agentes_asignables(edificio):
    """Candidatos para el selector de P21: usuarios activos que pueden relevar en Dispositivos.

    Por capacidad (un rol activo del programa con ``inspeccion.relevar``), nunca por
    nombre de grupo. Con :data:`AGENTE_DEBE_SER_EXTERNO`, sin el personal del edificio.
    """

    programa = programa_dispositivos()
    if programa is None:
        return get_user_model().objects.none()
    candidatos = get_user_model().objects.filter(
        is_active=True,
        groups__meta__activo=True,
        groups__meta__programa=programa,
        groups__permissions__codename=rbac.codename_de(CAP_RELEVAR),
    )
    if AGENTE_DEBE_SER_EXTERNO:
        candidatos = candidatos.exclude(pk__in=_personal_del_edificio(edificio))
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


# --------------------------------------------------------------------------- #
# Coordinador: crear, reasignar, cancelar
# --------------------------------------------------------------------------- #


@transaction.atomic
def crear_inspeccion(usuario, *, edificio, asignado_a, fecha_vencimiento, indicaciones=""):
    """El coordinador crea la tarea y se la asigna a un agente.

    Un edificio tiene **un solo relevamiento en curso**: el segundo se rechaza y lo que
    corresponde es reasignar el que está. Como MySQL y MariaDB no tienen índices parciales
    (un `UniqueConstraint` con `condition=` no existiría en producción), la regla la
    sostiene el bloqueo de la fila del edificio.
    """

    _exigir_alcance_coordinador(usuario, edificio)
    edificio = Edificio.objects.select_for_update().get(pk=edificio.pk)
    if not edificio.activo:
        raise ValidationError({"edificio": "El edificio está inactivo."})
    if fecha_vencimiento < timezone.localdate():
        raise ValidationError({"fecha_vencimiento": "El vencimiento no puede ser anterior a hoy."})
    if edificio.inspecciones.filter(estado=InspeccionEdificio.Estado.ASIGNADA).exists():
        raise ValidationError({"edificio": "El edificio ya tiene un relevamiento en curso: reasignalo."})
    _validar_agente(asignado_a, edificio)
    return InspeccionEdificio.objects.create(
        edificio=edificio,
        asignado_a=asignado_a,
        creado_por=usuario,
        fecha_vencimiento=fecha_vencimiento,
        indicaciones=indicaciones.strip(),
    )


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
    inspeccion.asignado_a = asignado_a
    inspeccion.save(update_fields=["asignado_a", "modificado"])
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
    return inspeccion


# --------------------------------------------------------------------------- #
# Agente: resultado y fotos
# --------------------------------------------------------------------------- #


def _bloquear_como_agente(usuario, inspeccion):
    """La guarda de «solo lo asignado»: la capacidad sola no alcanza."""

    if not puede_en_programa_dispositivos(usuario, CAP_RELEVAR):
        raise PermissionDenied("No tenés la capacidad de relevar edificios.")
    inspeccion = _bloquear(inspeccion)
    if inspeccion.asignado_a_id != usuario.pk:
        raise PermissionDenied("Solo el agente asignado carga este relevamiento.")
    return inspeccion


def _guardar_foto(inspeccion, usuario, archivo, descripcion=""):
    foto = FotoInspeccion(inspeccion=inspeccion, archivo=archivo, descripcion=descripcion[:120], cargada_por=usuario)
    foto.full_clean()
    foto.save()
    anotar_archivo_escrito(foto.archivo, asignado=archivo)
    return foto


@archivos_atomicos
@transaction.atomic
def registrar_resultado(usuario, inspeccion, *, criticidad, observaciones="", fotos=()):
    """El agente asignado cierra el relevamiento: criticidad, observaciones y fotos.

    ``fotos`` es una lista de archivos o de pares ``(archivo, descripcion)``. Si algo
    falla, la base vuelve atrás y las fotos ya escritas se borran (`core.archivos`).
    """

    inspeccion = _bloquear_como_agente(usuario, inspeccion)
    if not inspeccion.en_curso:
        raise ValidationError("Este relevamiento ya no está en curso.")
    if criticidad not in InspeccionEdificio.Criticidad.values:
        raise ValidationError({"criticidad": "Elegí una criticidad válida."})
    inspeccion.estado = InspeccionEdificio.Estado.REALIZADA
    inspeccion.criticidad = criticidad
    inspeccion.observaciones = (observaciones or "").strip()
    inspeccion.realizada_en = timezone.now()
    inspeccion.realizada_por = usuario
    inspeccion.save(
        update_fields=["estado", "criticidad", "observaciones", "realizada_en", "realizada_por", "modificado"]
    )
    for foto in fotos:
        archivo, descripcion = foto if isinstance(foto, tuple) else (foto, "")
        _guardar_foto(inspeccion, usuario, archivo, descripcion)
    return inspeccion


@archivos_atomicos
@transaction.atomic
def agregar_foto(usuario, inspeccion, archivo, descripcion=""):
    """Una foto más, en curso o ya realizado: la app sin conexión puede mandarlas después.

    Cada carga es una fila nueva; ninguna pisa a otra. Un relevamiento cancelado no
    recibe fotos.
    """

    inspeccion = _bloquear_como_agente(usuario, inspeccion)
    if inspeccion.estado == InspeccionEdificio.Estado.CANCELADA:
        raise ValidationError("El relevamiento está cancelado.")
    return _guardar_foto(inspeccion, usuario, archivo, descripcion)


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
    ultima = (
        InspeccionEdificio.objects.filter(edificio=OuterRef("pk"), estado=InspeccionEdificio.Estado.REALIZADA)
        .order_by("-realizada_en", "-pk")
        .values("pk")[:1]
    )
    pares = dict(
        Edificio.objects.filter(pk__in=ids)
        .annotate(ultima_id=Subquery(ultima))
        .order_by()
        .values_list("pk", "ultima_id")
    )
    filas = InspeccionEdificio.objects.in_bulk([pk for pk in pares.values() if pk is not None])
    return {edificio_id: filas.get(ultima_id) for edificio_id, ultima_id in pares.items()}


def ultimas_inspecciones_de_dispositivos(dispositivo_ids):
    """``{dispositivo_id: {edificio_id: InspeccionEdificio | None}}`` en tres consultas.

    Un dispositivo puede ocupar más de un edificio, así que cada uno trae las de todos los
    suyos: qué color gana (el peor, el del edificio principal…) es decisión del semáforo.
    Un dispositivo **sin edificio cargado** trae ``{}``, que no es lo mismo que un edificio
    sin relevar.
    """

    ids = {pk for pk in dispositivo_ids if pk is not None}
    vinculos = list(
        _EdificioDispositivo.objects.filter(dispositivo_id__in=ids).values_list("dispositivo_id", "edificio_id")
    )
    por_edificio = ultimas_inspecciones_por_edificio({edificio_id for _d, edificio_id in vinculos})
    resultado = {pk: {} for pk in ids}
    for dispositivo_id, edificio_id in vinculos:
        resultado[dispositivo_id][edificio_id] = por_edificio.get(edificio_id)
    return resultado


def inspecciones_de_dispositivo(dispositivo, *, incluir_canceladas=False):
    """Los relevamientos de los edificios que ocupa el dispositivo: los del predio compartido también.

    No aplica alcance: es la lectura de la solapa, que ya entró por ``dispositivo.ver``
    sobre este dispositivo. Para un listado por usuario está :func:`inspecciones_visibles`.
    """

    qs = InspeccionEdificio.objects.filter(
        edificio_id__in=_EdificioDispositivo.objects.filter(dispositivo=dispositivo).values("edificio_id")
    ).select_related("edificio", "asignado_a", "realizada_por")
    if not incluir_canceladas:
        qs = qs.exclude(estado=InspeccionEdificio.Estado.CANCELADA)
    return qs
