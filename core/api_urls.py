from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api_views import (
    DiaViewSet,
    LocalidadViewSet,
    MesViewSet,
    MunicipioViewSet,
    ProvinciaViewSet,
    SexoViewSet,
)

router = DefaultRouter()
router.register(r"provincias", ProvinciaViewSet)
router.register(r"municipios", MunicipioViewSet)
router.register(r"localidades", LocalidadViewSet)
router.register(r"sexos", SexoViewSet)
router.register(r"meses", MesViewSet)
router.register(r"dias", DiaViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
