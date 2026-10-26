"""Autorización y reglas del legajo institucional de Dispositivos."""

import json

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from core import rbac
from programas.services.programa_cache import clave_de, programa_por_codigo

PROGRAMA_DISPOSITIVOS_CODIGO = "DISPOSITIVOS"
CAP_CONFIGURAR = "programa.configurar"
CAP_VER = "dispositivo.ver"
# `CAP_ADMITIR` vivía acá para que `core.views.media` dejara al admisor bajar el F-00
# que él mismo había subido. Se fue con la admisión vieja (MVP v2, release A); la
# capacidad sigue en el catálogo y la repone la E2 con el ingreso contra `Estadia`.
#: Se conserva el nombre: la clave la deriva ``programa_cache.clave_de`` (RED-80).
_CACHE_KEY = clave_de(PROGRAMA_DISPOSITIVOS_CODIGO)
_CAMPOS_REQUERIDOS_VALIDACION = (
    "tipo",
    "codigo",
    "nombre",
    "categoria",
    "area_ministerio",
    "localidad",
    "domicilio",
    "responsable_nombre",
    "contacto_telefono",
)

# El mismo mapa para el encabezado y las filas del legajo institucional.
TONOS_ESTADO = {
    "BORRADOR": "white",
    "PENDIENTE_VALIDACION": "info",
    "ACTIVO": "success",
    "OBSERVADO": "warning",
    "RECHAZADO": "danger",
    "INACTIVO": "gray",
    "CERRADO": "gray",
}


def estado_de_dispositivo(dispositivo):
    return {"texto": dispositivo.get_estado_display(), "tono": TONOS_ESTADO.get(dispositivo.estado, "gray")}


def estado_de_tipo(tipo):
    return {"texto": "Activo" if tipo.activo else "Inactivo", "tono": "success" if tipo.activo else "gray"}


def normalizar_codigo_institucional(codigo):
    return " ".join(codigo.split()).upper()


def programa_dispositivos(user=None):
    """Obtiene el programa y lo memoiza durante la request.

    Fachada sobre :func:`programas.services.programa_cache.programa_por_codigo`: hasta
    RED-80 esta función era una copia de ``programa_becas`` con **otra** invalidación —de
    hecho, ninguna: nadie borraba ``programas:dispositivos``—.
    """
    return programa_por_codigo(PROGRAMA_DISPOSITIVOS_CODIGO, user=user)


def puede_configurar_dispositivos(user):
    """Exige la capacidad existente con alcance sobre DISPOSITIVOS."""

    programa = programa_dispositivos(user)
    return programa is not None and rbac.puede(user, CAP_CONFIGURAR, programa=programa)


def puede_en_programa_dispositivos(user, capacidad):
    """Evalúa una capacidad de Dispositivos con alcance al programa correcto."""

    programa = programa_dispositivos(user)
    return programa is not None and rbac.puede(user, capacidad, programa=programa)


def puede_operar_dispositivo(user, dispositivo, capacidad):
    """Evalúa capacidad de Programa más el alcance fino del dispositivo.

    Los administradores del programa y los superusuarios conservan alcance total.
    El resto necesita una asignación activa sobre el dispositivo concreto.
    """

    if user is None or not getattr(user, "is_authenticated", False):
        return False

    programa = programa_dispositivos(user)
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

    return dispositivos_en_alcance(user, CAP_VER)


def dispositivos_en_alcance(user, capacidad):
    """Dispositivos sobre los que el usuario tiene ``capacidad``, con el alcance fino.

    La misma regla que :func:`puede_operar_dispositivo`, en forma de queryset: la
    capacidad en el programa, y después todo (admin del programa) o solo los
    dispositivos donde un rol activo **que tiene esa capacidad** está asignado.
    """

    from programas.models import AsignacionDispositivo, Dispositivo

    programa = programa_dispositivos(user)
    if programa is None or not rbac.puede(user, capacidad, programa=programa):
        return Dispositivo.objects.none()
    if puede_configurar_dispositivos(user):
        return Dispositivo.objects.all()
    asignados = AsignacionDispositivo.objects.filter(
        rol__user=user,
        rol__meta__activo=True,
        rol__meta__programa=programa,
        rol__permissions__codename=rbac.codename_de(capacidad),
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

    codigo_normalizado = normalizar_codigo_institucional(codigo)
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


def campos_para_validacion():
    """Campos del circuito existente, también usados por el resumen del formulario."""
    return _CAMPOS_REQUERIDOS_VALIDACION


def puede_enviar_desde_formulario(usuario, dispositivo):
    """Una institución nueva todavía no tiene asignaciones: exige alcance total."""
    from programas.models import Dispositivo

    if dispositivo.estado not in (Dispositivo.Estado.BORRADOR, Dispositivo.Estado.OBSERVADO):
        return False
    if not dispositivo.pk:
        return puede_configurar_dispositivos(usuario) and puede_en_programa_dispositivos(usuario, "dispositivo.editar")
    return puede_operar_dispositivo(usuario, dispositivo, "dispositivo.editar")


def enviar_desde_formulario(dispositivo, usuario):
    """El mismo permiso de P4 antes de ejecutar su transición, dentro del guardado atómico."""
    from django.core.exceptions import PermissionDenied

    if not puede_operar_dispositivo(usuario, dispositivo, "dispositivo.editar"):
        raise PermissionDenied
    return enviar_a_validacion(dispositivo, usuario)


def _exigir_campos_para_validacion(dispositivo):
    faltantes = [campo for campo in campos_para_validacion() if not getattr(dispositivo, campo)]
    if faltantes:
        raise ValidationError("Completá los campos obligatorios antes de validar el dispositivo.")


def _exigir_formulario_del_tipo(dispositivo):
    """Los obligatorios visibles del formulario «Crear dispositivo» de su tipo (P17).

    Se exigen al **enviar** a validación, como los datos del legajo: el borrador los
    guarda incompletos. Contra el formulario vigente del tipo y lo ya guardado.
    """
    from programas.services.respuestas_dispositivo import faltantes_formulario_alta

    faltantes = faltantes_formulario_alta(dispositivo)
    if faltantes:
        raise ValidationError(
            "Completá las preguntas obligatorias del formulario del tipo antes de enviar a validación: "
            + ", ".join(faltantes)
            + ".",
            code="formulario_tipo_incompleto",
        )


def _transicionar(
    dispositivo, usuario, *, origenes, destino, accion, detalle="", exige_datos=False, exige_formulario=False
):
    from programas.models import Dispositivo

    with transaction.atomic():
        dispositivo = Dispositivo.objects.select_for_update().get(pk=dispositivo.pk)
        if dispositivo.estado not in origenes:
            raise ValidationError("La transición de estado solicitada no está permitida.")
        if exige_datos:
            _exigir_campos_para_validacion(dispositivo)
        if exige_formulario:
            _exigir_formulario_del_tipo(dispositivo)

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
        exige_formulario=True,
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
        # Con el campo nombrado: así el modal de P4 lo pinta bajo «Motivo» en vez de
        # mandarlo a un aviso general. Sin JS, `error.messages[0]` sigue siendo el texto.
        raise ValidationError({"motivo": "Indicá el motivo de la observación."})
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
        raise ValidationError({"motivo": "Indicá el motivo del rechazo."})
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
