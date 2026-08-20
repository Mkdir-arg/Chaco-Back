from django.contrib.auth.views import LogoutView, PasswordResetConfirmView, PasswordResetDoneView, PasswordResetView
from django.urls import path, reverse_lazy

from users.services.correo import contexto_pie
from users.views import (
    CambioContrasenaObligatorioView,
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
        "recuperar-contrasena/",
        PasswordResetView.as_view(
            template_name="user/recuperar_contrasena.html",
            email_template_name="user/email/recupero_contrasena.txt",
            html_email_template_name="user/email/recupero_contrasena.html",
            subject_template_name="user/email/recupero_contrasena_asunto.txt",
            # El pie y el prefijo del asunto salen de variables de entorno: fijas
            # para el proceso, así que alcanza con resolverlas al cargar el URLconf.
            extra_email_context=contexto_pie(),
            success_url=reverse_lazy("users:recuperar_contrasena_enviada"),
        ),
        name="recuperar_contrasena",
    ),
    path(
        "cambiar-contrasena/",
        CambioContrasenaObligatorioView.as_view(),
        name="cambiar_contrasena_obligatorio",
    ),
    path(
        "recuperar-contrasena/enviada/",
        PasswordResetDoneView.as_view(template_name="user/recuperar_contrasena_enviada.html"),
        name="recuperar_contrasena_enviada",
    ),
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
