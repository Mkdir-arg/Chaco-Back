import logging

from django.contrib import messages
from django.contrib.auth.models import User
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from core import rbac
from core.mixins import TimestampedSuccessUrlMixin
from core.rbac import CapacidadRequeridaMixin

from ..forms import CustomUserChangeForm, UserCreationForm
from ..selectors.usuarios import (
    alcance_roles_ids,
    puede_gestionar_usuario,
)
from ..services import UsuariosService
from ..services.admin import UsuariosAdminService
from ..services.correo import entregar_credenciales_provisorias

logger = logging.getLogger(__name__)


class _ScopeDenied(Exception):
    """El operador (admin de programa) intentó acceder a un usuario fuera de alcance."""


class AdminRequiredMixin(CapacidadRequeridaMixin):
    """Acceso al ABM de usuarios.

    Entra el admin global (``usuario.administrar``) y también quien administra los
    usuarios de algún programa (``programa.usuario.administrar``). El alcance fino
    lo aplica cada vista.
    """

    capacidades_requeridas = list(rbac.CAPS_ENTRADA_ABM_USUARIOS)


class UserListView(AdminRequiredMixin, ListView):
    model = User
    template_name = "user/user_list.html"
    context_object_name = "users"
    paginate_by = 25

    def get_queryset(self):
        return UsuariosService.get_filtered_usuarios(self.request, operador=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(UsuariosService.get_usuarios_list_context())
        context["hay_filtros_activos"] = bool(self.request.GET.get("filters"))
        querystring = self.request.GET.copy()
        querystring.pop("page", None)
        context["filtros_qs"] = querystring.urlencode()
        return context


class UserCreateView(TimestampedSuccessUrlMixin, AdminRequiredMixin, CreateView):
    model = User
    form_class = UserCreationForm
    template_name = "user/user_form.html"
    success_url = reverse_lazy("users:usuarios")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["operador"] = self.request.user
        return kwargs

    def form_valid(self, form):
        try:
            self.object = UsuariosAdminService.create_user_from_form(
                form, alcance_group_ids=alcance_roles_ids(self.request.user)
            )
        except Exception as exc:
            logger.exception("Error al crear usuario")
            form.add_error(None, f"Error al guardar el usuario: {exc}")
            return self.form_invalid(form)

        if self.object.email:
            # Con correo, la clave la genera el sistema y viaja en el mensaje: la
            # que tipeó el operador en el formulario no se usa (RN-C1). El primer
            # ingreso obliga a cambiarla (RN-C2).
            try:
                entregar_credenciales_provisorias(self.object, self.request)
                messages.success(self.request, "Usuario creado. Se envió el correo con la clave provisoria.")
            except Exception:
                logger.exception("El usuario fue creado, pero no se pudo enviar la clave provisoria")
                messages.warning(
                    self.request,
                    "El usuario fue creado, pero no se pudo enviar el correo. Revisá la configuración "
                    'de correo; mientras tanto el usuario puede entrar con "Olvidé mi contraseña".',
                )
        else:
            messages.warning(
                self.request,
                "Usuario creado sin correo; no se pudo enviar la clave provisoria.",
            )

        return self.redirect_with_timestamp()


class UserUpdateView(TimestampedSuccessUrlMixin, AdminRequiredMixin, UpdateView):
    model = User
    form_class = CustomUserChangeForm
    template_name = "user/user_form.html"
    success_url = reverse_lazy("users:usuarios")

    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except _ScopeDenied:
            messages.error(request, "No tiene permisos para acceder a esta sección.")
            return redirect("users:usuarios")

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if not puede_gestionar_usuario(self.request.user, obj):
            raise _ScopeDenied
        return obj

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["operador"] = self.request.user
        return kwargs

    def form_valid(self, form):
        try:
            self.object = UsuariosAdminService.update_user_from_form(
                form, alcance_group_ids=alcance_roles_ids(self.request.user)
            )
        except rbac.SinAdministradorError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)
        except Exception as exc:
            logger.exception("Error al actualizar usuario")
            form.add_error(None, f"Error al actualizar el usuario: {exc}")
            return self.form_invalid(form)

        return self.redirect_with_timestamp()


class UserToggleActivoView(AdminRequiredMixin, View):
    """Activa/desactiva un usuario (reemplaza el borrado físico)."""

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        if not puede_gestionar_usuario(request.user, user):
            messages.error(request, "No tiene permisos para acceder a esta sección.")
            return redirect("users:usuarios")
        if user == request.user and user.is_active:
            messages.error(request, "No podés desactivar tu propio usuario.")
            return redirect("users:usuarios")
        try:
            with transaction.atomic():
                # Programas que administra (antes de desactivar): no dejarlos huérfanos.
                programas = UsuariosAdminService._programas_que_administra(user) if user.is_active else set()
                user.is_active = not user.is_active
                user.save(update_fields=["is_active"])
                if not user.is_active:
                    rbac.asegurar_admin_restante()
                    for programa_id in programas:
                        rbac.asegurar_admin_restante(programa=programa_id)
        except rbac.SinAdministradorError as exc:
            messages.error(request, str(exc))
            return redirect("users:usuarios")
        messages.success(request, "Usuario activado." if user.is_active else "Usuario desactivado.")
        return redirect("users:usuarios")
