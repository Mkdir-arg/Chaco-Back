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

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from programas.services.dispositivos import (
    programa_dispositivos,
    puede_configurar_dispositivos,
)


def puede_gestionar_equipo(user, dispositivo):
    """Admin del programa Dispositivos o responsable activo de ese dispositivo."""

    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if puede_configurar_dispositivos(user):
        return True
    from programas.models import MiembroEquipoDispositivo

    return MiembroEquipoDispositivo.objects.filter(
        dispositivo=dispositivo, usuario=user, activo=True, es_responsable=True
    ).exists()


def _exigir_gestion(actor, dispositivo):
    if not puede_gestionar_equipo(actor, dispositivo):
        raise PermissionDenied("Solo el admin de Dispositivos o un responsable del dispositivo arma el Equipo.")


def _bloquear(dispositivo):
    from programas.models import Dispositivo

    return Dispositivo.objects.select_for_update().get(pk=dispositivo.pk)


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

    return MiembroEquipoDispositivo.objects.filter(dispositivo=dispositivo, activo=True, es_responsable=True)


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
        _validar_rol(usuario, rol)
        miembro, creado = MiembroEquipoDispositivo.objects.get_or_create(
            dispositivo=dispositivo, usuario=usuario, rol=rol, defaults={"es_responsable": es_responsable}
        )
        if not creado:
            miembro.activo = True
            miembro.es_responsable = miembro.es_responsable or es_responsable
            miembro.save(update_fields=["activo", "es_responsable", "modificado"])
        return miembro


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


def validar_responsables_al_crear(responsables):
    """Al crear un dispositivo hace falta al menos un responsable (la UI llega en el PR siguiente).

    ``responsables``: iterable de usuarios. Devuelve la lista sin repetidos o levanta
    ``ValidationError``.
    """

    unicos = list(dict.fromkeys(responsables or []))
    if not unicos:
        raise ValidationError("Indicá al menos un responsable del dispositivo.")
    return unicos
