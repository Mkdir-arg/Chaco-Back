"""Equipo de un dispositivo: quién trabaja ahí, con qué rol y quién lo arma (Cambio 410).

Reglas (decisiones del PM, 02-nov-2026):

* El Equipo es por **persona** (``MiembroEquipoDispositivo``): el alcance fino de quien opera
  un dispositivo sin ser admin del programa.
* Hay **varios responsables** por dispositivo; si ya tenía alguno, no se lo deja sin ninguno.
* Arman el Equipo el admin de Dispositivos y los responsables **de ese** dispositivo.
* El rol tiene que ser de un rol del programa Dispositivos y la persona tiene que tenerlo.
* Quien además administra los usuarios del programa Dispositivos puede **crear a la persona** que no
  está (Cambio 420), con un rol que la regla del ABM de Usuarios le deje dar, y sumarla en la misma
  transacción.

Las escrituras toman ``select_for_update`` sobre el dispositivo: dos altas o bajas
simultáneas no pueden dejarlo sin responsables.
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import BooleanField, Case, When

from core import rbac
from programas.services.dispositivos import (
    membresias_vigentes,
    programa_dispositivos,
    puede_configurar_dispositivos,
    q_membresia_vigente,
)
from programas.services.inspecciones import CLAVE_ROL_AGENTE


def puede_gestionar_equipo(user, dispositivo):
    """Admin del programa Dispositivos o responsable activo de ese dispositivo."""

    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if puede_configurar_dispositivos(user):
        return True
    return (
        membresias_vigentes(user, programa_dispositivos(user))
        .filter(dispositivo=dispositivo, es_responsable=True)
        .exists()
    )


def puede_administrar_usuarios_dispositivos(user):
    """Superusuario, ``usuario.administrar`` o ``programa.usuario.administrar`` **acotado a Dispositivos**.

    Es el alcance del ABM de Usuarios (``programas_administrables_usuarios``): la misma definición que
    acota los roles que se pueden dar, así que quien pasa esta puerta no queda con el combo vacío por otra regla.
    """

    if user is None or not getattr(user, "is_authenticated", False) or not user.is_active:
        return False
    if rbac.puede(user, "usuario.administrar"):
        return True
    programa = programa_dispositivos(user)
    return programa is not None and rbac.puede(user, "programa.usuario.administrar", programa=programa)


def puede_crear_persona(user, dispositivo):
    """«Crear persona» desde el Equipo: gestiona **este** Equipo y administra los usuarios de Dispositivos."""

    return puede_gestionar_equipo(user, dispositivo) and puede_administrar_usuarios_dispositivos(user)


def roles_para_crear_persona(actor):
    """Roles con los que el ``actor`` puede dar de alta a una persona nueva en el Equipo.

    Parte de la regla del ABM de Usuarios (``roles_asignables``: no se da un rol con capacidades que el
    actor no puede asignar) y la acota al programa Dispositivos, sin el rol de agente de relevamiento.
    """

    from django.contrib.auth.models import Group

    from users.selectors.usuarios import roles_asignables

    programa = programa_dispositivos()
    if programa is None:
        return Group.objects.none()
    return roles_asignables(actor).filter(meta__programa=programa).exclude(meta__clave=CLAVE_ROL_AGENTE)


def _exigir_gestion(actor, dispositivo):
    if not puede_gestionar_equipo(actor, dispositivo):
        raise PermissionDenied("Solo el admin de Dispositivos o un responsable del dispositivo arma el Equipo.")


def _bloquear(dispositivo):
    from programas.models import Dispositivo

    return Dispositivo.objects.select_for_update().get(pk=dispositivo.pk)


def _exigir_pares_sumables(programa, pares):
    """Todos los ``(usuario, rol)`` son opciones de ``pares_persona_rol`` (Cambio 414).

    Es el único validador de quién se puede sumar al Equipo: usuario activo, rol activo del
    programa Dispositivos que la persona tiene y que no es el de agente de relevamiento. Mira solo
    las personas y roles elegidos, no todo el padrón.
    """

    pares = list(pares)
    if programa is None or not pares:
        raise ValidationError("Elegí personas y roles del listado.")
    validos = set(
        get_user_model()
        .groups.through.objects.filter(
            user__is_active=True,
            group__meta__activo=True,
            group__meta__programa=programa,
            user_id__in={usuario.pk for usuario, _ in pares},
            group_id__in={rol.pk for _, rol in pares},
        )
        .exclude(group__meta__clave=CLAVE_ROL_AGENTE)
        .values_list("user_id", "group_id")
    )
    if any((usuario.pk, rol.pk) not in validos for usuario, rol in pares):
        raise ValidationError("Elegí personas y roles del listado.")


def exigir_par_sumable(usuario, rol):
    """Falla con ``ValidationError`` si ``(usuario, rol)`` no es una opción de ``pares_persona_rol``."""

    _exigir_pares_sumables(programa_dispositivos(), [(usuario, rol)])


def _responsables_activos(dispositivo):
    from programas.models import MiembroEquipoDispositivo

    return MiembroEquipoDispositivo.objects.filter(
        q_membresia_vigente(programa_dispositivos()), dispositivo=dispositivo, es_responsable=True
    )


def _exigir_otro_responsable(dispositivo, miembro):
    """No dejar sin responsables a un dispositivo que tenía: queda al menos otro activo."""

    es_responsable_activo = miembro.activo and miembro.es_responsable
    if es_responsable_activo and not _responsables_activos(dispositivo).exclude(pk=miembro.pk).exists():
        raise ValidationError("El dispositivo no puede quedar sin responsables: marcá a otra persona antes.")


def sumar_miembro(*, actor, dispositivo, usuario, rol, es_responsable=False):
    """Suma a ``usuario`` con ``rol``; si la fila existía de baja, la reactiva."""

    from programas.models import MiembroEquipoDispositivo

    with transaction.atomic():
        dispositivo = _bloquear(dispositivo)
        _exigir_gestion(actor, dispositivo)
        _exigir_pares_sumables(programa_dispositivos(), [(usuario, rol)])
        miembro, creado = MiembroEquipoDispositivo.objects.get_or_create(
            dispositivo=dispositivo, usuario=usuario, rol=rol, defaults={"es_responsable": es_responsable}
        )
        if not creado:
            estaba_de_baja = not miembro.activo
            miembro.activo = True
            # De baja vuelve como se pide; si ya estaba activa (dos altas a la vez) no se le saca la marca.
            miembro.es_responsable = es_responsable if estaba_de_baja else miembro.es_responsable or es_responsable
            miembro.save(update_fields=["activo", "es_responsable", "modificado"])
        return miembro


def datos_de_alta_de_persona(*, actor, dni, nombre, apellido, correo, rol):
    """El ``UserCreationForm`` del ABM de Usuarios armado para el alta de una persona del Equipo.

    No hay una regla paralela: es el formulario del ABM, con los roles acotados a ``roles_para_crear_persona``
    (el rol elegido tiene que estar ahí) y el operador, que valida DNI, correo y que el rol no se pise.
    La clave la genera el sistema y llega por enlace al correo: no se pide ni se muestra una provisoria.
    El usuario se llama como el DNI (o ``<dni>-<n>`` si ese nombre ya lo tiene otra cuenta).
    """

    from django.http import QueryDict

    from users.forms import UserCreationForm

    username = str(dni)
    ocupado = get_user_model().objects.filter(username__iexact=username).exists()
    numero = 1
    while ocupado:
        numero += 1
        username = f"{dni}-{numero}"
        ocupado = get_user_model().objects.filter(username__iexact=username).exists()
    datos = QueryDict(mutable=True)
    datos.update({"username": username, "email": correo, "first_name": nombre, "last_name": apellido, "dni": dni})
    datos.setlist("groups", [str(rol.pk)])
    return UserCreationForm(data=datos, operador=actor, roles_acotados=roles_para_crear_persona(actor))


def crear_persona_y_sumar(*, actor, dispositivo, alta, rol, es_responsable=False):
    """Crea el usuario de ``alta`` (``UserCreationForm`` válido) y lo suma al Equipo, **todo o nada**.

    Una sola transacción: si sumar al Equipo falla, no queda ni el usuario. La escritura del usuario es la
    de las altas rápidas (``UsuariosAdminService.create_user_from_form``). El correo con la clave no viaja
    acá: lo manda la vista cuando la transacción ya cerró.
    """

    from users.selectors.usuarios import alcance_roles_ids
    from users.services.admin import UsuariosAdminService

    with transaction.atomic():
        if not puede_crear_persona(actor, dispositivo):
            raise PermissionDenied("Solo quien administra los usuarios de Dispositivos da de alta personas.")
        if not roles_para_crear_persona(actor).filter(pk=rol.pk).exists():
            raise ValidationError({"rol": "Ese rol no se puede dar al crear una persona."})
        usuario = UsuariosAdminService.create_user_from_form(alta, alcance_group_ids=alcance_roles_ids(actor))
        sumar_miembro(actor=actor, dispositivo=dispositivo, usuario=usuario, rol=rol, es_responsable=es_responsable)
    return usuario


def sumar_responsables_al_crear(*, actor, dispositivo, pares):
    """Deja a ``pares`` (``[(usuario, rol)]``) como responsables de un dispositivo recién creado.

    Va dentro de la transacción del alta. Valida todo con ``_exigir_pares_sumables``, la misma definición que ofrece el
    formulario (``pares_persona_rol``) y escribe en una sola consulta, así que sumar a varios no
    cuesta más consultas por persona.
    """

    from programas.models import MiembroEquipoDispositivo

    with transaction.atomic():
        dispositivo = _bloquear(dispositivo)
        _exigir_gestion(actor, dispositivo)
        _exigir_pares_sumables(programa_dispositivos(), pares)
        MiembroEquipoDispositivo.objects.bulk_create(
            [
                MiembroEquipoDispositivo(dispositivo=dispositivo, usuario=usuario, rol=rol, es_responsable=True)
                for usuario, rol in dict.fromkeys(pares)
            ]
        )


def cambiar_rol(*, actor, miembro, rol_nuevo):
    """Pasa a la persona a otro rol del mismo dispositivo (conserva la marca de responsable)."""

    from programas.models import MiembroEquipoDispositivo

    with transaction.atomic():
        dispositivo = _bloquear(miembro.dispositivo)
        _exigir_gestion(actor, dispositivo)
        miembro = MiembroEquipoDispositivo.objects.select_for_update().get(pk=miembro.pk)
        _exigir_pares_sumables(programa_dispositivos(), [(miembro.usuario, rol_nuevo)])
        if miembro.rol_id == rol_nuevo.pk:
            return miembro
        if MiembroEquipoDispositivo.objects.filter(
            dispositivo=dispositivo, usuario=miembro.usuario, rol=rol_nuevo
        ).exists():
            raise ValidationError("La persona ya está en el Equipo con ese rol.")
        miembro.rol = rol_nuevo
        miembro.save(update_fields=["rol", "modificado"])
        return miembro


def dar_de_baja(*, actor, miembro):
    from programas.models import MiembroEquipoDispositivo

    with transaction.atomic():
        dispositivo = _bloquear(miembro.dispositivo)
        _exigir_gestion(actor, dispositivo)
        miembro = MiembroEquipoDispositivo.objects.select_for_update().get(pk=miembro.pk)
        if not miembro.activo:
            return miembro
        _exigir_otro_responsable(dispositivo, miembro)
        miembro.activo = False
        miembro.save(update_fields=["activo", "modificado"])
        return miembro


def marcar_responsable(*, actor, miembro):
    from programas.models import MiembroEquipoDispositivo

    with transaction.atomic():
        dispositivo = _bloquear(miembro.dispositivo)
        _exigir_gestion(actor, dispositivo)
        miembro = MiembroEquipoDispositivo.objects.select_for_update().get(pk=miembro.pk)
        if not miembro.activo:
            raise ValidationError("La persona está de baja en el Equipo.")
        if not miembro.es_responsable:
            miembro.es_responsable = True
            miembro.save(update_fields=["es_responsable", "modificado"])
        return miembro


def desmarcar_responsable(*, actor, miembro):
    from programas.models import MiembroEquipoDispositivo

    with transaction.atomic():
        dispositivo = _bloquear(miembro.dispositivo)
        _exigir_gestion(actor, dispositivo)
        miembro = MiembroEquipoDispositivo.objects.select_for_update().get(pk=miembro.pk)
        if not miembro.es_responsable:
            return miembro
        _exigir_otro_responsable(dispositivo, miembro)
        miembro.es_responsable = False
        miembro.save(update_fields=["es_responsable", "modificado"])
        return miembro


def nombre_de_persona(usuario):
    return usuario.get_full_name().strip() or usuario.get_username()


def datos_de_contacto(usuario):
    """Responsable y contacto del legajo tomados de la persona (alta, Cambio 448).

    El alta ya no los pide a mano: salen del primer responsable elegido. Se copian una vez; la
    edición los sigue mostrando para corregirlos. Sin perfil, documento y teléfono quedan vacíos.
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


def pares_persona_rol(dispositivo=None):
    """Las opciones «Persona — Rol» que se pueden sumar al Equipo.

    Una por usuario activo × rol activo del programa Dispositivos que la persona **tiene**, sin
    el rol de agente de relevamiento (los agentes no integran el Equipo, decisión 5 del 410).
    Con ``dispositivo`` salen las que ya están activas ahí. Devuelve diccionarios
    ``{valor, usuario, rol, etiqueta}``; ``valor`` es ``"<usuario_pk>:<rol_pk>"``.
    """

    programa = programa_dispositivos()
    if programa is None:
        return []
    enlaces = (
        get_user_model()
        .groups.through.objects.filter(
            user__is_active=True,
            group__meta__activo=True,
            group__meta__programa=programa,
        )
        .exclude(group__meta__clave=CLAVE_ROL_AGENTE)
        .select_related("user", "user__profile", "group")
        .order_by("user__last_name", "user__first_name", "user__username", "group__name")
    )
    ocupadas = set()
    if dispositivo is not None:
        from programas.models import MiembroEquipoDispositivo

        ocupadas = set(
            MiembroEquipoDispositivo.objects.filter(dispositivo=dispositivo, activo=True).values_list(
                "usuario_id", "rol_id"
            )
        )
    pares = []
    for enlace in enlaces:
        if (enlace.user_id, enlace.group_id) in ocupadas:
            continue
        pares.append(
            {
                "valor": f"{enlace.user_id}:{enlace.group_id}",
                "usuario": enlace.user,
                "rol": enlace.group,
                "etiqueta": f"{nombre_de_persona(enlace.user)} — {enlace.group.name}",
            }
        )
    return pares


def equipo_del_dispositivo(dispositivo):
    """Los miembros activos del Equipo para la solapa, con ``vigente`` (el rol todavía vale).

    Una sola consulta: «vigente» es ``q_membresia_vigente``, la misma definición que usan el
    alcance y la gestión del Equipo, anotada sobre cada fila.
    """

    from programas.models import MiembroEquipoDispositivo

    vigente = Case(
        When(q_membresia_vigente(programa_dispositivos()), then=True),
        default=False,
        output_field=BooleanField(),
    )
    miembros = list(
        MiembroEquipoDispositivo.objects.filter(dispositivo=dispositivo, activo=True)
        .select_related("usuario", "rol__meta")
        .annotate(vigente=vigente)
        .order_by("-es_responsable", "usuario__last_name", "usuario__first_name", "usuario__username", "rol__name")
    )
    for miembro in miembros:
        miembro.persona = nombre_de_persona(miembro.usuario)
    return miembros
