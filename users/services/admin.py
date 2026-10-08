from django.contrib.auth.models import User
from django.db import transaction

from core import rbac


class UsuariosAdminService:
    @staticmethod
    @transaction.atomic
    def create_user_from_form(form, alcance_group_ids=None):
        user = User()
        clave_tipeada = UsuariosAdminService._apply_user_data(form, user)
        user.save()
        UsuariosAdminService._sync_related_data(
            user, form.cleaned_data, alcance_group_ids, operador=getattr(form, "operador", None)
        )
        UsuariosAdminService._marcar_cambio_obligatorio(form, user, clave_tipeada)
        return user

    @staticmethod
    @transaction.atomic
    def update_user_from_form(form, alcance_group_ids=None):
        user = form.instance
        # Programas que el usuario administraba ANTES del cambio: si la edición le
        # quita el rol de administración de alguno, no puede dejarlo huérfano (RN-8).
        programas_previos = UsuariosAdminService._programas_que_administra(user)
        clave_tipeada = UsuariosAdminService._apply_user_data(form, user)
        user.save()
        UsuariosAdminService._sync_related_data(
            user, form.cleaned_data, alcance_group_ids, operador=getattr(form, "operador", None)
        )
        UsuariosAdminService._marcar_cambio_obligatorio(form, user, clave_tipeada)
        # Si la edición quitó la última capacidad de administración del sistema
        # (p. ej. el admin se sacó su propio rol), revierte la transacción.
        rbac.asegurar_admin_restante()
        for programa_id in programas_previos:
            rbac.asegurar_admin_restante(programa=programa_id)
        return user

    @staticmethod
    def _programas_que_administra(user):
        """IDs de programas que el usuario administra (rol activo programa=X + capacidad
        de admin). La consulta vive en ``core.rbac`` porque el alta masiva por CSV
        necesita exactamente la misma (`import_users_from_csv`)."""
        return rbac.programas_que_administra(user)

    @staticmethod
    def _apply_user_data(form, user):
        cleaned_data = form.cleaned_data
        # SEC-03: un admin de programa no toca las credenciales de quien tiene roles
        # fuera de su alcance. El form ya deshabilita esos campos; acá se ignora el
        # POST igual, para que el servicio no dependa de cómo se armó el formulario.
        credenciales_editables = getattr(form, "credenciales_editables", True)
        if credenciales_editables:
            user.username = cleaned_data["username"]
            user.email = cleaned_data["email"]
        user.first_name = cleaned_data["first_name"]
        user.last_name = cleaned_data["last_name"]

        password = cleaned_data.get("password") if credenciales_editables else None
        if password:
            user.set_password(password)
            return True
        if hasattr(form, "_original_password_hash"):
            user.password = form._original_password_hash
        return False

    @staticmethod
    def _marcar_cambio_obligatorio(form, user, clave_tipeada):
        """G1b-08: una clave que eligió **otro** vale para un solo ingreso.

        Si el operador tipeó la contraseña de otra persona, la conoce. El sistema
        ya trata así a la clave que genera y manda por correo (RN-C2); la tipeada
        a mano se escapaba por la ventana de al lado.

        Se escribe sobre el Profile cacheado y se sincroniza la relación, que es
        lo que esperan `users/services/correo.py` y el middleware (Cambio 37).

        **Dónde no alcanza: el usuario de campo.** La marca la cobra el backoffice,
        y a quien solo tiene `becas.campo` el backoffice nunca le pide nada —el
        login web lo rechaza y `/api/becas/auth/token/` no mira el flag—, así que
        acá queda puesta y no la hace cumplir nadie. Esa puerta se cierra en el
        alta y no en esta función: `_validar_correo_de_entrega` le exige correo a
        un usuario de campo, para que la clave le llegue como link de reseteo
        (D-26 (b)) y el operador no la conozca. La marca igual se escribe: si
        mañana suma un rol de backoffice, el primer ingreso se la cobra.
        """
        from users.models import Profile

        if not clave_tipeada:
            return
        operador = getattr(form, "operador", None)
        if operador is not None and operador.pk == user.pk:
            return  # se la cambió a sí mismo: ya la conoce y no hay que forzar nada
        perfil = user._state.fields_cache.get("profile") or Profile.objects.get_or_create(user=user)[0]
        perfil.debe_cambiar_contrasena = True
        perfil.save(update_fields=["debe_cambiar_contrasena"])
        user._state.fields_cache["profile"] = perfil

    @staticmethod
    def _sync_related_data(user, cleaned_data, alcance_group_ids=None, operador=None):
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
        UsuariosAdminService._sync_profile(user, cleaned_data)
        UsuariosAdminService._sync_asignacion_territorial(user, cleaned_data, operador=operador)
        UsuariosAdminService._sync_jerarquia_becas(user, cleaned_data)

    @staticmethod
    def _sync_profile(user, cleaned_data):
        from users.models import Profile

        perfil, _ = Profile.objects.get_or_create(user=user)
        perfil.dni = cleaned_data.get("dni") or None
        perfil.telefono = cleaned_data.get("telefono", "")
        perfil.institucion = cleaned_data.get("institucion", "")
        perfil.observacion = cleaned_data.get("observacion", "")
        perfil.save(update_fields=["dni", "telefono", "institucion", "observacion"])
        # Si una señal creó el perfil al guardar User, puede haber otra instancia
        # cacheada en la relación OneToOne. Mantener ambas referencias coherentes.
        user._state.fields_cache["profile"] = perfil

    @staticmethod
    def _sync_asignacion_territorial(user, cleaned_data, operador=None):
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

    @staticmethod
    def _sync_jerarquia_becas(user, cleaned_data):
        from programas.models import AsignacionReferente
        from programas.services.autorizacion import grupos_referentes_becas

        es_referente = user.groups.filter(id__in=grupos_referentes_becas()).exists()
        coordinador = cleaned_data.get("coordinador_referente")
        if not es_referente:
            AsignacionReferente.objects.filter(referente=user).delete()
        elif coordinador is not None:
            AsignacionReferente.objects.update_or_create(referente=user, defaults={"coordinador": coordinador})
