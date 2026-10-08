"""Router de DRF para la API del backoffice (SEC-01).

``DefaultRouter`` publica una vista raíz —el índice de endpoints— que usa los
permisos **por defecto** de ``REST_FRAMEWORK``. Los ViewSets que cuelgan de él
declaran los suyos y por eso no heredan ese default (Cambio 109), pero la raíz
quedaba con ``IsAuthenticated`` pelado: la única superficie de ``/api/legajos/`` y
``/api/core/`` a la que un ciudadano del portal podía llegar si alguna vez se
saltara ``PortalCiudadanoMiddleware``.

No es explotable hoy —la sesión viaja por cookie y el middleware frena al
ciudadano antes de la vista—, y por eso esto es defensa en profundidad: la regla
«toda vista DRF del backoffice declara ``BackofficeAutenticado``» vale también
para las que publica una biblioteca, que son las que nadie escribe y nadie mira.
Lo verifica ``core.tests.test_api_backoffice_permiso``.
"""

from rest_framework.routers import APIRootView, DefaultRouter

from core.api_permissions import BackofficeAutenticado


class RaizApiBackoffice(APIRootView):
    """Índice de endpoints, solo para una sesión de backoffice."""

    permission_classes = [BackofficeAutenticado]


class RouterBackoffice(DefaultRouter):
    APIRootView = RaizApiBackoffice
