from django.urls import include, path

from core.api_routers import RouterBackoffice

from ..api_views import (
    AlertasViewSet,
    CiudadanoViewSet,
)

router = RouterBackoffice()
router.register(r"ciudadanos", CiudadanoViewSet)
router.register(r"alertas", AlertasViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
