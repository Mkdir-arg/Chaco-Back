from django.urls import include, path
from rest_framework.routers import DefaultRouter

from ..api_views import (
    AlertasViewSet,
    CiudadanoViewSet,
)

router = DefaultRouter()
router.register(r"ciudadanos", CiudadanoViewSet)
router.register(r"alertas", AlertasViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
