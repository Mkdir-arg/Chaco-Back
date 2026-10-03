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

    Exige además `is_active`: `SessionAuthentication` no vuelve a mirar ese campo,
    así que la sesión abierta antes de dar de baja a un usuario seguiría entrando a
    `/api/` hasta vencer.

    **Un superusuario dentro del grupo `Ciudadanos` queda denegado a propósito**
    (fail-closed): acá no hay bypass de `is_superuser` como en `rbac.puede`. Una
    cuenta en las dos superficies a la vez es un error de datos —el portal y el
    backoffice son excluyentes, es lo que asume `PortalCiudadanoMiddleware`— y
    frente a la duda la API del backoffice se cierra. Se corrige sacando la cuenta
    del grupo del portal, no relajando este permiso.
    """

    message = "Esta API es del backoffice."

    def has_permission(self, request, view):
        usuario = request.user
        return usuario.is_authenticated and usuario.is_active and not rbac.es_ciudadano_portal(usuario)


def RequiereCapacidad(*codigos):
    """Factory de permission class: exige al menos una de las capacidades."""

    class _RequiereCapacidad(BasePermission):
        message = "No tiene la capacidad requerida para esta operación."

        def has_permission(self, request, view):
            return rbac.puede_alguna(request.user, codigos)

    return _RequiereCapacidad
