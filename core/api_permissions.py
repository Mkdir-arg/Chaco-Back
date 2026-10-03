"""Permission classes de DRF del backoffice.

Uso::

    permission_classes = [BackofficeAutenticado, RequiereCapacidad("usuario.administrar")]
"""

from rest_framework.permissions import BasePermission

from core import rbac


class BackofficeAutenticado(BasePermission):
    """Exige sesión de backoffice: usuario autenticado que no sea del portal.

    Defensa en profundidad (SEC-01, auditoría oct-2026). El Cambio 100 dejó
    `IsAuthenticated` como `DEFAULT_PERMISSION_CLASSES`, pero las vistas que
    declaran `permission_classes` explícitas **no heredan** ese default: ahí va
    esta clase como primer elemento. No evalúa capacidades —de eso se ocupa
    `RequiereCapacidad`—, solo separa las dos superficies.
    """

    message = "Esta API es del backoffice."

    def has_permission(self, request, view):
        return request.user.is_authenticated and not rbac.es_ciudadano_portal(request.user)


def RequiereCapacidad(*codigos):
    """Factory de permission class: exige al menos una de las capacidades."""

    class _RequiereCapacidad(BasePermission):
        message = "No tiene la capacidad requerida para esta operación."

        def has_permission(self, request, view):
            return rbac.puede_alguna(request.user, codigos)

    return _RequiereCapacidad
