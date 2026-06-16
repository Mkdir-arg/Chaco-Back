from django.contrib.auth.models import User
from django.db import transaction

from core import rbac


class UsuariosAdminService:
    @staticmethod
    @transaction.atomic
    def create_user_from_form(form, alcance_group_ids=None):
        user = User()
        UsuariosAdminService._apply_user_data(form, user)
        user.save()
        UsuariosAdminService._sync_related_data(user, form.cleaned_data, alcance_group_ids)
        return user

    @staticmethod
    @transaction.atomic
    def update_user_from_form(form, alcance_group_ids=None):
        user = form.instance
        # Programas que el usuario administraba ANTES del cambio: si la edición le
        # quita el rol de administración de alguno, no puede dejarlo huérfano (RN-8).
        programas_previos = UsuariosAdminService._programas_que_administra(user)
        UsuariosAdminService._apply_user_data(form, user)
        user.save()
        UsuariosAdminService._sync_related_data(user, form.cleaned_data, alcance_group_ids)
        # Si la edición quitó la última capacidad de administración del sistema
        # (p. ej. el admin se sacó su propio rol), revierte la transacción.
        rbac.asegurar_admin_restante()
        for programa_id in programas_previos:
            rbac.asegurar_admin_restante(programa=programa_id)
        return user

    @staticmethod
    def _programas_que_administra(user):
        """IDs de programas que el usuario administra (rol activo programa=X + programa.configurar)."""
        if not user.pk:
            return set()
        return set(
            user.groups.filter(
                meta__activo=True,
                meta__categoria=rbac.CATEGORIA_PROGRAMA,
                meta__programa__isnull=False,
                permissions__codename=rbac.codename_de("programa.configurar"),
            ).values_list("meta__programa_id", flat=True)
        )

    @staticmethod
    def _apply_user_data(form, user):
        cleaned_data = form.cleaned_data
        user.username = cleaned_data["username"]
        user.email = cleaned_data["email"]
        user.first_name = cleaned_data["first_name"]
        user.last_name = cleaned_data["last_name"]

        password = cleaned_data.get("password")
        if password:
            user.set_password(password)
        elif hasattr(form, "_original_password_hash"):
            user.password = form._original_password_hash

    @staticmethod
    def _sync_related_data(user, cleaned_data, alcance_group_ids=None):
        seleccionados = list(cleaned_data.get("groups", []))
        if alcance_group_ids is None:
            # Admin global: reemplaza todos los grupos (comportamiento histórico).
            user.groups.set(seleccionados)
            return
        # Admin de programa: solo toca los roles dentro de su alcance; los roles
        # fuera de alcance (otros programas, globales) del usuario quedan intactos.
        fuera_de_alcance = list(user.groups.exclude(id__in=alcance_group_ids))
        en_alcance_seleccionados = [g for g in seleccionados if g.id in alcance_group_ids]
        user.groups.set(fuera_de_alcance + en_alcance_seleccionados)
