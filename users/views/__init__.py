"""Paquete de vistas para la app de usuarios."""

from .admin import (  # noqa: F401
    AdminRequiredMixin,
    UserCreateView,
    UserListView,
    UserToggleActivoView,
    UserUpdateView,
)
from .auth import UsuariosLoginView  # noqa: F401
from .roles import (  # noqa: F401
    RolCreateView,
    RolDeleteView,
    RolDetailView,
    RolListView,
    RolToggleActivoView,
    RolUpdateView,
)
