"""Servicio de administración de Roles (Group + RolMeta + capacidades)."""

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from core import rbac
from programas.models import AsignacionDispositivo
from users.models import Capacidad, RolMeta


class RolProtegidoError(Exception):
    """No se puede editar/eliminar/desactivar un rol protegido."""


def _set_capacidades(group, codigos):
    ct = ContentType.objects.get_for_model(Capacidad)
    codenames = [rbac.codename_de(c) for c in codigos]
    perms = Permission.objects.filter(content_type=ct, codename__in=codenames)
    group.permissions.set(list(perms))


def _meta(group):
    meta, _ = RolMeta.objects.get_or_create(grupo=group)
    return meta


def _sincronizar_alcance_dispositivos(group, dispositivos):
    """Mantiene las asignaciones activas del rol sin borrar su historial."""

    ids = [dispositivo.pk for dispositivo in dispositivos]
    asignaciones = AsignacionDispositivo.objects.filter(rol=group)
    asignaciones.exclude(dispositivo_id__in=ids).update(activo=False)
    for dispositivo_id in ids:
        asignacion, _ = AsignacionDispositivo.objects.get_or_create(
            rol=group,
            dispositivo_id=dispositivo_id,
        )
        if not asignacion.activo:
            asignacion.activo = True
            asignacion.save(update_fields=["activo", "modificado"])


def _programa_que_administra(group):
    """Programa que este rol administra hoy, o ``None``.

    Un rol "administra" un programa si es de categoría 'Programa', tiene
    ``programa`` y la capacidad ``programa.configurar`` tildada. Se usa para el
    check scoped de "programa sin administrador" (RN-8)."""
    meta = getattr(group, "meta", None)
    if (
        meta
        and meta.categoria == rbac.CATEGORIA_PROGRAMA
        and meta.programa_id
        and "programa.configurar" in rbac.capacidades_de_grupo(group)
    ):
        return meta.programa
    return None


class RolesAdminService:
    @staticmethod
    @transaction.atomic
    def crear(form):
        cd = form.cleaned_data
        group = Group.objects.create(name=cd["name"])
        RolMeta.objects.create(
            grupo=group,
            descripcion=cd.get("descripcion", ""),
            categoria=cd["categoria"],
            programa=cd.get("programa"),
            activo=True,
            protegido=False,
        )
        _set_capacidades(group, cd.get("capacidades", []))
        _sincronizar_alcance_dispositivos(group, cd.get("dispositivos_alcance", []))
        return group

    @staticmethod
    @transaction.atomic
    def actualizar(form, group):
        if _meta(group).protegido:
            raise RolProtegidoError("El rol está protegido y no puede editarse.")
        # Programa que este rol administraba ANTES del cambio (puede quedar
        # huérfano si la edición le saca programa.configurar o le cambia el programa).
        programa_previo = _programa_que_administra(group)
        cd = form.cleaned_data
        group.name = cd["name"]
        group.save()
        meta = _meta(group)
        meta.descripcion = cd.get("descripcion", "")
        meta.categoria = cd["categoria"]
        meta.programa = cd.get("programa")
        meta.save()
        _set_capacidades(group, cd.get("capacidades", []))
        _sincronizar_alcance_dispositivos(group, cd.get("dispositivos_alcance", []))
        # Si la edición quitó usuario.administrar/rol.administrar y dejaría al
        # sistema sin admins, revierte la transacción.
        rbac.asegurar_admin_restante()
        if programa_previo is not None:
            rbac.asegurar_admin_restante(programa=programa_previo)
        return group

    @staticmethod
    @transaction.atomic
    def eliminar(group):
        if _meta(group).protegido:
            raise RolProtegidoError("El rol está protegido y no puede eliminarse.")
        programa_previo = _programa_que_administra(group)
        # Al borrar el Group, Django desvincula a los usuarios (tabla intermedia)
        # y borra RolMeta por CASCADE.
        group.delete()
        rbac.asegurar_admin_restante()
        if programa_previo is not None:
            rbac.asegurar_admin_restante(programa=programa_previo)

    @staticmethod
    @transaction.atomic
    def toggle_activo(group):
        meta = _meta(group)
        if meta.protegido:
            raise RolProtegidoError("El rol está protegido y no puede desactivarse.")
        # Capturar antes: si es un rol que administra un programa y se va a
        # desactivar, podría dejar ese programa sin administrador.
        programa_admin = _programa_que_administra(group)
        meta.activo = not meta.activo
        meta.save(update_fields=["activo"])
        # Desactivar un rol de programa SÍ deja de otorgar programa.configurar:
        # si era el último admin de ese programa, revierte.
        if not meta.activo and programa_admin is not None:
            rbac.asegurar_admin_restante(programa=programa_admin)
        return meta.activo

    @staticmethod
    def usuarios_afectados(group):
        """Cantidad de usuarios que tienen asignado el rol (para la confirmación)."""
        return group.user_set.count()
