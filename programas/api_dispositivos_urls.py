"""URLs de la API de campo del relevamiento edilicio (MVP v2, tasks 38 y 39).

Namespace ``dispositivos_api``. El login es el de la app de campo,
``/api/becas/auth/token/``: un solo token por usuario, y cada recurso con su permiso.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from programas.api.views_inspecciones import InspeccionViewSet, RaizApiInspecciones

app_name = "dispositivos_api"


class RouterApiInspecciones(DefaultRouter):
    """La raíz del router autentica igual que el resto del namespace (R0-04)."""

    APIRootView = RaizApiInspecciones


router = RouterApiInspecciones()
router.register("inspecciones", InspeccionViewSet, basename="inspeccion")

urlpatterns = [
    path("", include(router.urls)),
]
