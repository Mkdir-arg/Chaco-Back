"""Paquete de vistas para la app de usuarios."""

from .admin import (  # noqa: F401
    AdminRequiredMixin,
    UserCreateView,
    UserListView,
    UserToggleActivoView,
    UserUpdateView,
)
from .auth import CambioContrasenaObligatorioView, UsuariosLoginView  # noqa: F401
from .quick_create import usuario_alta_rapida  # noqa: F401
from .roles import (  # noqa: F401
    RolCreateView,
    RolDeleteView,
    RolDetailView,
    RolListView,
    RolToggleActivoView,
    RolUpdateView,
)
