"""Permission classes de DRF basadas en capacidades del RBAC.

Uso::

    permission_classes = [RequiereCapacidad("usuario.administrar")]
"""

from rest_framework.permissions import BasePermission

from core import rbac


def RequiereCapacidad(*codigos):
    """Factory de permission class: exige al menos una de las capacidades."""

    class _RequiereCapacidad(BasePermission):
        message = "No tiene la capacidad requerida para esta operación."

        def has_permission(self, request, view):
            return rbac.puede_alguna(request.user, codigos)

    return _RequiereCapacidad
