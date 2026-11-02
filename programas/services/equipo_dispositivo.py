"""Equipo de un dispositivo: quién trabaja ahí, con qué rol y quién lo arma (Cambio 410).

Reglas (decisiones del PM, 02-nov-2026):

* El Equipo es por **persona** (``MiembroEquipoDispositivo``): el alcance fino de quien opera
  un dispositivo sin ser admin del programa.
* Hay **varios responsables** por dispositivo; si ya tenía alguno, no se lo deja sin ninguno.
* Arman el Equipo el admin de Dispositivos y los responsables **de ese** dispositivo.
* El rol tiene que ser de un rol del programa Dispositivos y la persona tiene que tenerlo.

Las escrituras toman ``select_for_update`` sobre el dispositivo: dos altas o bajas
simultáneas no pueden dejarlo sin responsables.
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import BooleanField, Case, When

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


def _validar_rol(usuario, rol):
    """El rol es del programa Dispositivos, está activo y la persona lo tiene."""

    programa = programa_dispositivos()
    meta = getattr(rol, "meta", None)
    if programa is None or meta is None or not meta.activo or meta.programa_id != programa.pk:
        raise ValidationError("El rol no es un rol activo del programa Dispositivos.")
    if not usuario.groups.filter(pk=rol.pk).exists():
        raise ValidationError("La persona no tiene ese rol.")


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
            miembro.activo = True
            miembro.es_responsable = es_responsable
            miembro.save(update_fields=["activo", "es_responsable", "modificado"])
        return miembro


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
        _validar_rol(miembro.usuario, rol_nuevo)
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
        .select_related("user", "group")
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
