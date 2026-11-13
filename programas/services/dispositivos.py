"""Autorización y reglas del legajo institucional de Dispositivos."""

import json

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Exists, OuterRef, Q

from core import rbac
from programas.services.programa_cache import clave_de, programa_por_codigo

PROGRAMA_DISPOSITIVOS_CODIGO = "DISPOSITIVOS"
CAP_CONFIGURAR = "programa.configurar"
CAP_VER = "dispositivo.ver"
CAP_VER_TODOS = "dispositivo.ver_todos"
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


def q_membresia_vigente(programa):
    """``Q`` sobre ``MiembroEquipoDispositivo``: la fila vale (Cambio 414).

    Vale la fila activa cuyo rol es del programa y está activo, y que la persona TODAVÍA tiene
    (si se le sacó el rol, la fila no cuenta). Es la única escritura de «membresía vigente»: la
    comparten ``membresias_vigentes``, los responsables activos y la solapa Equipo. La pertenencia
    al rol va con ``Exists`` para no multiplicar filas cuando se usa en un ``annotate``.
    """

    from django.contrib.auth import get_user_model

    tiene_el_rol = get_user_model().groups.through.objects.filter(
        user_id=OuterRef("usuario_id"), group_id=OuterRef("rol_id")
    )
    return Q(activo=True, rol__meta__activo=True, rol__meta__programa=programa) & Exists(tiene_el_rol)


def membresias_vigentes(user, programa):
    """Filas activas del Equipo (Cambio 410) de ``user`` que todavía valen (``q_membresia_vigente``).

    La usan el alcance y la gestión del Equipo.
    """

    from programas.models import MiembroEquipoDispositivo

    return MiembroEquipoDispositivo.objects.filter(q_membresia_vigente(programa), usuario=user)


def responsables_vigentes(dispositivo):
    """Responsables del Equipo de ``dispositivo`` cuya membresía todavía vale (``q_membresia_vigente``).

    La usan la gestión del Equipo (no dejarlo sin responsables) y el contacto del legajo (Cambio 457).
    """

    from programas.models import MiembroEquipoDispositivo

    return MiembroEquipoDispositivo.objects.filter(
        q_membresia_vigente(programa_dispositivos()), dispositivo=dispositivo, es_responsable=True
    )


# Contacto del legajo (Cambios 450 y 457). Vive acá y no en `equipo_dispositivo` porque las
# transiciones de este módulo lo sincronizan antes de exigir los datos: así el import va en
# un solo sentido (equipo_dispositivo → dispositivos) y no abre un ciclo.


def nombre_de_persona(usuario):
    return usuario.get_full_name().strip() or usuario.get_username()


def datos_de_contacto(usuario):
    """Responsable y contacto del legajo tomados de la persona (Cambios 450 y 457).

    Ni el alta ni la edición los piden a mano: salen del primer responsable (el elegido en el
    alta, después el del Equipo: ``contacto_del_equipo``). Sin perfil, documento y teléfono quedan vacíos.
    Cada valor pasa por la misma regla que el campo escrito a mano; el que no la cumple queda
    vacío (un teléfono inválido del perfil cuenta como «sin teléfono» y no traba la edición).
    """

    from programas.validacion_contacto import (
        normalizar_documento_responsable,
        normalizar_telefono,
        validar_nombre_responsable,
    )

    def _con_regla(regla, valor):
        valor = (valor or "").strip()
        if not valor:
            return ""
        try:
            return regla(valor)
        except ValidationError:
            return ""

    perfil = getattr(usuario, "profile", None)
    return {
        "responsable_nombre": _con_regla(validar_nombre_responsable, nombre_de_persona(usuario))[:200],
        "responsable_documento": _con_regla(normalizar_documento_responsable, getattr(perfil, "dni", None)),
        "contacto_telefono": _con_regla(normalizar_telefono, getattr(perfil, "telefono", None)),
        "contacto_email": (usuario.email or "").strip(),
    }


def responsable_de_contacto(dispositivo):
    """La persona de la que sale el contacto del legajo: el primer responsable vigente del Equipo.

    Vigente como en la solapa Equipo (``responsables_vigentes``): quien perdió el rol no cuenta.
    En el mismo orden que el buscador del alta (apellido, nombre, usuario), así el alta y la
    edición eligen a la misma persona. ``None`` si el legajo no tiene responsables vigentes (p. ej.
    los anteriores al Cambio 411): esos conservan el contacto escrito a mano.
    """
    if not dispositivo.pk:
        return None
    miembro = (
        responsables_vigentes(dispositivo)
        .select_related("usuario", "usuario__profile")
        .order_by("usuario__last_name", "usuario__first_name", "usuario__username", "pk")
        .first()
    )
    return miembro.usuario if miembro else None


def contacto_del_equipo(dispositivo, usuario=None):
    """El contacto que el legajo tiene que tener según su responsable, o ``None`` si no hay de quién tomarlo.

    Cada dato sale de la persona; el que su perfil no trae válido conserva el valor guardado en
    el legajo, así un contacto cargado antes no se borra al sincronizar (Cambio 457).
    """
    usuario = usuario or responsable_de_contacto(dispositivo)
    if usuario is None:
        return None
    return {campo: valor or getattr(dispositivo, campo) or "" for campo, valor in datos_de_contacto(usuario).items()}


def sincronizar_contacto(dispositivo):
    """Copia al legajo, sin guardar, el contacto de su responsable.

    Devuelve los cambios con la forma de la traza de edición, ``{campo: {"anterior", "nuevo"}}``.

    La llaman la edición y las transiciones que exigen los datos (enviar a validación y validar),
    así un cambio de perfil o de Equipo llega al legajo antes de chequearlo (Cambio 457).
    """
    contacto = contacto_del_equipo(dispositivo)
    if contacto is None:
        return {}
    cambios = {}
    for campo, nuevo in contacto.items():
        anterior = getattr(dispositivo, campo) or ""
        if nuevo != anterior:
            setattr(dispositivo, campo, nuevo)
            cambios[campo] = {"anterior": anterior, "nuevo": nuevo}
    return cambios


def _filtro_equipo(user, capacidad, programa):
    """Membresías vigentes del Equipo cuyo rol tiene ``capacidad``."""

    return membresias_vigentes(user, programa).filter(rol__permissions__codename=rbac.codename_de(capacidad))


def _del_equipo(user, capacidad, programa):
    """Dispositivos donde el usuario integra el Equipo con un rol que tiene ``capacidad``."""

    from programas.models import Dispositivo

    return Dispositivo.objects.filter(pk__in=_filtro_equipo(user, capacidad, programa).values("dispositivo_id"))


def _ve_todos(user, capacidad, programa):
    """``dispositivo.ver_todos`` da lectura total y **solo** lectura (``CAP_VER``)."""

    return capacidad == CAP_VER and rbac.puede(user, CAP_VER_TODOS, programa=programa)


def puede_operar_dispositivo(user, dispositivo, capacidad):
    """Evalúa capacidad de Programa más el alcance fino del dispositivo.

    Los administradores del programa y los superusuarios conservan alcance total, y
    ``dispositivo.ver_todos`` da lectura de todo. El resto necesita ser parte del Equipo del
    dispositivo con un rol que tenga la capacidad.
    """

    if user is None or not getattr(user, "is_authenticated", False):
        return False

    programa = programa_dispositivos(user)
    if programa is None or not rbac.puede(user, capacidad, programa=programa):
        return False
    if puede_configurar_dispositivos(user) or _ve_todos(user, capacidad, programa):
        return True
    # Una sola consulta: el alcance se pregunta por pantalla.
    return _del_equipo(user, capacidad, programa).filter(pk=dispositivo.pk).exists()


def dispositivos_visibles(user):
    """Queryset de dispositivos que el usuario puede consultar dentro de su alcance."""

    return dispositivos_en_alcance(user, CAP_VER)


def dispositivos_en_alcance(user, capacidad):
    """Dispositivos sobre los que el usuario tiene ``capacidad``, con el alcance fino.

    La misma regla que :func:`puede_operar_dispositivo`, en forma de queryset: la
    capacidad en el programa, y después todo (admin del programa, o ``ver_todos`` para
    leer) o solo los dispositivos donde integra el Equipo con un rol que tiene esa
    capacidad.
    """

    from programas.models import Dispositivo

    programa = programa_dispositivos(user)
    if programa is None or not rbac.puede(user, capacidad, programa=programa):
        return Dispositivo.objects.none()
    if puede_configurar_dispositivos(user) or _ve_todos(user, capacidad, programa):
        return Dispositivo.objects.all()
    return _del_equipo(user, capacidad, programa)


def dispositivos_operados(user, capacidad):
    """Solo el alcance fino: los dispositivos donde integra el Equipo con un rol que tiene ``capacidad``.

    Lo mismo que :func:`dispositivos_en_alcance` **sin** la ampliación a todo del admin del
    programa ni de ``dispositivo.ver_todos``: es «la institución que opera», no «lo que puede
    leer». La usa el relevamiento edilicio (Cambio 422), que no se abre por ver todos los
    dispositivos.
    """

    from programas.models import Dispositivo

    programa = programa_dispositivos(user)
    if programa is None or not rbac.puede(user, capacidad, programa=programa):
        return Dispositivo.objects.none()
    return _del_equipo(user, capacidad, programa)


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


def estados_desde_los_que_se_envia():
    """Estados desde los que se (re)envía a validación: borrador, observado y rechazado.

    El rechazado se corrige y vuelve a enviarse (decisión del PM, 30/10/2026, Cambio 407).
    Una sola fuente para el servicio, el formulario y el botón del detalle.
    """
    from programas.models import Dispositivo

    return (Dispositivo.Estado.BORRADOR, Dispositivo.Estado.OBSERVADO, Dispositivo.Estado.RECHAZADO)


def puede_enviar_desde_formulario(usuario, dispositivo):
    """Una institución nueva todavía no tiene asignaciones: exige alcance total."""

    if dispositivo.estado not in estados_desde_los_que_se_envia():
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
        # Con el nombre de cada campo como lo ve el operador: el aviso genérico lo dejaba buscando.
        nombres = [str(dispositivo._meta.get_field(campo).verbose_name) for campo in faltantes]
        raise ValidationError(
            "Completá los campos obligatorios antes de validar el dispositivo. Falta: " + ", ".join(nombres) + "."
        )


def _sincronizar_contacto(dispositivo, usuario):
    """Antes de exigir los datos, el contacto del legajo se pone al día con su responsable (Cambio 457).

    Si el perfil del responsable o el Equipo cambiaron después del último guardado, el chequeo ve
    lo vigente; lo que se copia queda en la traza como una edición más.
    """

    cambios = sincronizar_contacto(dispositivo)
    if cambios:
        dispositivo.save(update_fields=[*cambios, "modificado"])
        registrar_edicion_dispositivo(dispositivo, usuario, cambios)


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
            _sincronizar_contacto(dispositivo, usuario)
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
        origenes=estados_desde_los_que_se_envia(),
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


def reactivar_dispositivo(dispositivo, usuario):
    """Un dispositivo inactivo vuelve a ACTIVO (decisión del PM, 02/11/2026, Cambio 409).

    Misma capacidad que inactivar (`dispositivo.editar`); queda en el historial como
    «REACTIVADO». El cerrado no vuelve: el cierre es definitivo.
    """
    from programas.models import Dispositivo

    return _transicionar(
        dispositivo,
        usuario,
        origenes=(Dispositivo.Estado.INACTIVO,),
        destino=Dispositivo.Estado.ACTIVO,
        accion="REACTIVADO",
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
