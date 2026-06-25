"""URLs de la API de campo de Becas (#82). Namespace ``becas_api``."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from programas.api.views import (
    FormularioViewSet,
    ObtainCampoToken,
    RelevamientoViewSet,
)

app_name = "becas_api"

router = DefaultRouter()
router.register("relevamientos", RelevamientoViewSet, basename="relevamiento")
router.register("formularios", FormularioViewSet, basename="formulario")

urlpatterns = [
    path("auth/token/", ObtainCampoToken.as_view(), name="token"),
    path("", include(router.urls)),
]
