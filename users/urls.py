from django.contrib.auth.views import LogoutView, PasswordResetConfirmView
from django.urls import path, reverse_lazy

from users.views import (
    RolCreateView,
    RolDeleteView,
    RolDetailView,
    RolListView,
    RolToggleActivoView,
    RolUpdateView,
    UserCreateView,
    UserListView,
    UserToggleActivoView,
    UserUpdateView,
    UsuariosLoginView,
    usuario_alta_rapida,
)

app_name = "users"

urlpatterns = [
    path("", UsuariosLoginView.as_view(), name="login"),
    path("login/", UsuariosLoginView.as_view(), name="login_compat"),
    path("logout", (LogoutView.as_view()), name="logout"),
    path(
        "establecer-contrasena/<uidb64>/<token>/",
        PasswordResetConfirmView.as_view(
            template_name="user/establecer_contrasena.html",
            success_url=reverse_lazy("users:login"),
        ),
        name="establecer_contrasena",
    ),
    # --- Usuarios (RBAC por capacidad: usuario.administrar, vía AdminRequiredMixin) ---
    path("usuarios/", UserListView.as_view(), name="usuarios"),
    path("usuarios/crear/", UserCreateView.as_view(), name="usuario_crear"),
    path("usuarios/alta-rapida/", usuario_alta_rapida, name="usuario_alta_rapida"),
    path("usuarios/editar/<int:pk>/", UserUpdateView.as_view(), name="usuario_editar"),
    path("usuarios/<int:pk>/toggle/", UserToggleActivoView.as_view(), name="usuario_toggle"),
    # --- Roles (RBAC por capacidad: rol.administrar) ---
    path("roles/", RolListView.as_view(), name="roles"),
    path("roles/crear/", RolCreateView.as_view(), name="rol_crear"),
    path("roles/<int:pk>/", RolDetailView.as_view(), name="rol_detalle"),
    path("roles/<int:pk>/editar/", RolUpdateView.as_view(), name="rol_editar"),
    path("roles/<int:pk>/eliminar/", RolDeleteView.as_view(), name="rol_eliminar"),
    path("roles/<int:pk>/toggle/", RolToggleActivoView.as_view(), name="rol_toggle"),
]
