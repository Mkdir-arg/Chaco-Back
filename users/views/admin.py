import logging

from django.contrib import messages
from django.contrib.auth.models import User
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from core import rbac
from core.rbac import CapacidadRequeridaMixin
from core.mixins import TimestampedSuccessUrlMixin
from ..forms import CustomUserChangeForm, UserCreationForm
from ..services import UsuariosService
from ..services.admin import UsuariosAdminService

logger = logging.getLogger(__name__)


class AdminRequiredMixin(CapacidadRequeridaMixin):
    """Acceso al ABM de usuarios: requiere la capacidad ``usuario.administrar``."""

    capacidades_requeridas = ["usuario.administrar"]


class UserListView(AdminRequiredMixin, ListView):
    model = User
    template_name = "user/user_list.html"
    context_object_name = "users"

    def get_queryset(self):
        return UsuariosService.get_filtered_usuarios(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(UsuariosService.get_usuarios_list_context())
        return context


class UserCreateView(TimestampedSuccessUrlMixin, AdminRequiredMixin, CreateView):
    model = User
    form_class = UserCreationForm
    template_name = "user/user_form.html"
    success_url = reverse_lazy("users:usuarios")

    def form_valid(self, form):
        try:
            self.object = UsuariosAdminService.create_user_from_form(form)
        except Exception as exc:
            logger.exception("Error al crear usuario")
            form.add_error(None, f"Error al guardar el usuario: {exc}")
            return self.form_invalid(form)

        return self.redirect_with_timestamp()


class UserUpdateView(TimestampedSuccessUrlMixin, AdminRequiredMixin, UpdateView):
    model = User
    form_class = CustomUserChangeForm
    template_name = "user/user_form.html"
    success_url = reverse_lazy("users:usuarios")

    def form_valid(self, form):
        try:
            self.object = UsuariosAdminService.update_user_from_form(form)
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
        if user == request.user and user.is_active:
            messages.error(request, "No podés desactivar tu propio usuario.")
            return redirect("users:usuarios")
        try:
            with transaction.atomic():
                user.is_active = not user.is_active
                user.save(update_fields=["is_active"])
                if not user.is_active:
                    rbac.asegurar_admin_restante()
        except rbac.SinAdministradorError as exc:
            messages.error(request, str(exc))
            return redirect("users:usuarios")
        messages.success(
            request, "Usuario activado." if user.is_active else "Usuario desactivado."
        )
        return redirect("users:usuarios")
