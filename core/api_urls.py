from django.urls import include, path

from core.api_routers import RouterBackoffice

from .api_views import (
    DiaViewSet,
    LocalidadViewSet,
    MesViewSet,
    MunicipioViewSet,
    ProvinciaViewSet,
    SexoViewSet,
)

router = RouterBackoffice()
router.register(r"provincias", ProvinciaViewSet)
router.register(r"municipios", MunicipioViewSet)
router.register(r"localidades", LocalidadViewSet)
router.register(r"sexos", SexoViewSet)
router.register(r"meses", MesViewSet)
router.register(r"dias", DiaViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
