"""URLs de la API de campo de Becas (#82). Namespace ``becas_api``."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from programas.api.views import (
    FormularioViewSet,
    ObtainCampoToken,
    RelevamientoViewSet,
    consultar_renaper_becas,
)

app_name = "becas_api"

router = DefaultRouter()
router.register("relevamientos", RelevamientoViewSet, basename="relevamiento")
router.register("formularios", FormularioViewSet, basename="formulario")

urlpatterns = [
    path("auth/token/", ObtainCampoToken.as_view(), name="token"),
    path("renaper/consultar/", consultar_renaper_becas, name="renaper-consultar"),
    path("", include(router.urls)),
]
