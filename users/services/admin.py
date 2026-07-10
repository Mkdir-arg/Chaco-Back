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
        else:
            # Admin de programa: solo toca los roles dentro de su alcance; los roles
            # fuera de alcance (otros programas, globales) del usuario quedan intactos.
            fuera_de_alcance = list(user.groups.exclude(id__in=alcance_group_ids))
            en_alcance_seleccionados = [g for g in seleccionados if g.id in alcance_group_ids]
            user.groups.set(fuera_de_alcance + en_alcance_seleccionados)
        UsuariosAdminService._sync_asignacion_territorial(user, cleaned_data)

    @staticmethod
    def _sync_asignacion_territorial(user, cleaned_data):
        """Mantiene la asignación de segmento del territorial de Becas.

        Regla: un territorial → un segmento, obligatorio mientras tenga un rol
        con ``becas.campo``. Se decide sobre los grupos FINALES del usuario
        (post-sync): si perdió el rol se borra la asignación; si lo tiene y el
        form trajo segmento se crea/actualiza; si lo tiene pero el form no
        trajo segmento (p. ej. un admin de otro programa que no ve el campo),
        se conserva la existente.
        """
        from programas.models import AsignacionTerritorial
        from programas.services.autorizacion import grupos_territoriales_becas

        es_territorial = user.groups.filter(id__in=grupos_territoriales_becas()).exists()
        segmento = cleaned_data.get("segmento_territorial")
        if not es_territorial:
            AsignacionTerritorial.objects.filter(territorial=user).delete()
        elif segmento is not None:
            AsignacionTerritorial.objects.update_or_create(territorial=user, defaults={"segmento": segmento})
