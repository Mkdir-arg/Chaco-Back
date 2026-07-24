"""Autorización y reglas del legajo institucional de Dispositivos."""

import json

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from core import rbac

PROGRAMA_DISPOSITIVOS_CODIGO = "DISPOSITIVOS"
CAP_CONFIGURAR = "programa.configurar"
CAP_VER = "dispositivo.ver"
_CACHE_KEY = "programas:dispositivos"
_CAMPOS_REQUERIDOS_VALIDACION = (
    "tipo",
    "codigo",
    "nombre",
    "localidad",
    "domicilio",
    "responsable_nombre",
    "contacto_telefono",
)


def programa_dispositivos():
    from programas.models import Programa

    programa = cache.get(_CACHE_KEY)
    if programa is None:
        programa = Programa.objects.filter(codigo=PROGRAMA_DISPOSITIVOS_CODIGO).first()
        if programa is not None:
            cache.set(_CACHE_KEY, programa, 300)
    return programa


def puede_configurar_dispositivos(user):
    """Exige la capacidad existente con alcance sobre DISPOSITIVOS."""

    programa = programa_dispositivos()
    return programa is not None and rbac.puede(user, CAP_CONFIGURAR, programa=programa)


def puede_en_programa_dispositivos(user, capacidad):
    """Evalúa una capacidad de Dispositivos con alcance al programa correcto."""

    programa = programa_dispositivos()
    return programa is not None and rbac.puede(user, capacidad, programa=programa)


def puede_operar_dispositivo(user, dispositivo, capacidad):
    """Evalúa capacidad de Programa más el alcance fino del dispositivo.

    Los administradores del programa y los superusuarios conservan alcance total.
    El resto necesita una asignación activa sobre el dispositivo concreto.
    """

    if user is None or not getattr(user, "is_authenticated", False):
        return False

    programa = programa_dispositivos()
    if programa is None or not rbac.puede(user, capacidad, programa=programa):
        return False
    if puede_configurar_dispositivos(user):
        return True

    from programas.models import AsignacionDispositivo

    return AsignacionDispositivo.objects.filter(
        dispositivo=dispositivo,
        rol__user=user,
        rol__meta__activo=True,
        rol__meta__programa=programa,
        rol__permissions__codename=rbac.codename_de(capacidad),
        activo=True,
    ).exists()


def dispositivos_visibles(user):
    """Queryset de dispositivos que el usuario puede consultar dentro de su alcance."""

    from programas.models import AsignacionDispositivo, Dispositivo

    programa = programa_dispositivos()
    if programa is None or not rbac.puede(user, CAP_VER, programa=programa):
        return Dispositivo.objects.none()
    if puede_configurar_dispositivos(user):
        return Dispositivo.objects.all()
    asignados = AsignacionDispositivo.objects.filter(
        rol__user=user,
        rol__meta__activo=True,
        rol__meta__programa=programa,
        rol__permissions__codename=rbac.codename_de(CAP_VER),
        activo=True,
    ).values("dispositivo_id")
    return Dispositivo.objects.filter(pk__in=asignados)


def _registrar_traza(dispositivo, usuario, accion, estado_anterior, estado_nuevo, detalle=""):
    from programas.models import TrazaDispositivo

    TrazaDispositivo.objects.create(
        dispositivo=dispositivo,
        usuario=usuario,
        accion=accion,
        estado_anterior=estado_anterior,
        estado_nuevo=estado_nuevo,
        detalle=detalle,
    )


def registrar_alta_dispositivo(dispositivo, usuario):
    _registrar_traza(
        dispositivo,
        usuario,
        "CREADO",
        "",
        dispositivo.estado,
    )


def registrar_edicion_dispositivo(dispositivo, usuario, cambios):
    """Conserva valores anterior/nuevo en la auditoría aditiva del legajo."""

    if not cambios:
        return
    _registrar_traza(
        dispositivo,
        usuario,
        "EDITADO",
        dispositivo.estado,
        dispositivo.estado,
        json.dumps(cambios, ensure_ascii=False, default=str),
    )


def buscar_posibles_duplicados(*, codigo="", nombre="", localidad=""):
    """Busca coincidencias blandas y determina si el código ya está tomado.

    El código es el único bloqueo duro. Nombre y localidad se informan para que
    quien carga decida si se trata de otra institución.
    """

    from programas.models import Dispositivo

    codigo_normalizado = " ".join(codigo.split()).upper()
    nombre = nombre.strip()
    localidad = localidad.strip()

    coincidencias = Q()
    if codigo_normalizado:
        coincidencias |= Q(codigo__iexact=codigo_normalizado)
    if nombre and localidad:
        coincidencias |= Q(nombre__iexact=nombre, localidad__iexact=localidad)

    queryset = Dispositivo.objects.none() if not coincidencias else Dispositivo.objects.filter(coincidencias)
    return {
        "codigo_duplicado": bool(codigo_normalizado and queryset.filter(codigo__iexact=codigo_normalizado).exists()),
        "dispositivos": queryset.select_related("tipo").order_by("nombre"),
    }


def _exigir_campos_para_validacion(dispositivo):
    faltantes = [campo for campo in _CAMPOS_REQUERIDOS_VALIDACION if not getattr(dispositivo, campo)]
    if faltantes:
        raise ValidationError("Completá los campos obligatorios antes de validar el dispositivo.")


def _transicionar(dispositivo, usuario, *, origenes, destino, accion, detalle="", exige_datos=False):
    from programas.models import Dispositivo

    with transaction.atomic():
        dispositivo = Dispositivo.objects.select_for_update().get(pk=dispositivo.pk)
        if dispositivo.estado not in origenes:
            raise ValidationError("La transición de estado solicitada no está permitida.")
        if exige_datos:
            _exigir_campos_para_validacion(dispositivo)

        anterior = dispositivo.estado
        dispositivo.estado = destino
        dispositivo.save(update_fields=["estado", "modificado"])
        _registrar_traza(dispositivo, usuario, accion, anterior, destino, detalle)
        return dispositivo


def enviar_a_validacion(dispositivo, usuario):
    from programas.models import Dispositivo

    return _transicionar(
        dispositivo,
        usuario,
        origenes=(Dispositivo.Estado.BORRADOR, Dispositivo.Estado.OBSERVADO),
        destino=Dispositivo.Estado.PENDIENTE_VALIDACION,
        accion="ENVIADO_VALIDACION",
        exige_datos=True,
    )


def validar_dispositivo(dispositivo, usuario):
    from programas.models import Dispositivo

    return _transicionar(
        dispositivo,
        usuario,
        origenes=(Dispositivo.Estado.PENDIENTE_VALIDACION,),
        destino=Dispositivo.Estado.ACTIVO,
        accion="VALIDADO",
        exige_datos=True,
    )


def observar_dispositivo(dispositivo, usuario, motivo):
    from programas.models import Dispositivo

    motivo = (motivo or "").strip()
    if not motivo:
        raise ValidationError("Indicá el motivo de la observación.")
    return _transicionar(
        dispositivo,
        usuario,
        origenes=(Dispositivo.Estado.PENDIENTE_VALIDACION,),
        destino=Dispositivo.Estado.OBSERVADO,
        accion="OBSERVADO",
        detalle=motivo,
    )


def rechazar_dispositivo(dispositivo, usuario, motivo):
    from programas.models import Dispositivo

    motivo = (motivo or "").strip()
    if not motivo:
        raise ValidationError("Indicá el motivo del rechazo.")
    return _transicionar(
        dispositivo,
        usuario,
        origenes=(Dispositivo.Estado.PENDIENTE_VALIDACION,),
        destino=Dispositivo.Estado.RECHAZADO,
        accion="RECHAZADO",
        detalle=motivo,
    )


def inactivar_dispositivo(dispositivo, usuario):
    from programas.models import Dispositivo

    return _transicionar(
        dispositivo,
        usuario,
        origenes=(Dispositivo.Estado.ACTIVO,),
        destino=Dispositivo.Estado.INACTIVO,
        accion="INACTIVADO",
    )


def cerrar_dispositivo(dispositivo, usuario):
    from programas.models import Dispositivo

    return _transicionar(
        dispositivo,
        usuario,
        origenes=(Dispositivo.Estado.ACTIVO, Dispositivo.Estado.INACTIVO, Dispositivo.Estado.RECHAZADO),
        destino=Dispositivo.Estado.CERRADO,
        accion="CERRADO",
    )
