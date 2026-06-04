"""Servicio de administración de Roles (Group + RolMeta + capacidades)."""
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from core import rbac
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
            activo=True,
            protegido=False,
        )
        _set_capacidades(group, cd.get("capacidades", []))
        return group

    @staticmethod
    @transaction.atomic
    def actualizar(form, group):
        if _meta(group).protegido:
            raise RolProtegidoError("El rol está protegido y no puede editarse.")
        cd = form.cleaned_data
        group.name = cd["name"]
        group.save()
        meta = _meta(group)
        meta.descripcion = cd.get("descripcion", "")
        meta.categoria = cd["categoria"]
        meta.save()
        _set_capacidades(group, cd.get("capacidades", []))
        # Si la edición quitó usuario.administrar/rol.administrar y dejaría al
        # sistema sin admins, revierte la transacción.
        rbac.asegurar_admin_restante()
        return group

    @staticmethod
    @transaction.atomic
    def eliminar(group):
        if _meta(group).protegido:
            raise RolProtegidoError("El rol está protegido y no puede eliminarse.")
        # Al borrar el Group, Django desvincula a los usuarios (tabla intermedia)
        # y borra RolMeta por CASCADE.
        group.delete()
        rbac.asegurar_admin_restante()

    @staticmethod
    @transaction.atomic
    def toggle_activo(group):
        meta = _meta(group)
        if meta.protegido:
            raise RolProtegidoError("El rol está protegido y no puede desactivarse.")
        meta.activo = not meta.activo
        meta.save(update_fields=["activo"])
        # Desactivar un rol NO lo quita a quienes ya lo tienen (solo deja de ser
        # asignable), por eso no afecta a los administradores actuales.
        return meta.activo

    @staticmethod
    def usuarios_afectados(group):
        """Cantidad de usuarios que tienen asignado el rol (para la confirmación)."""
        return group.user_set.count()
