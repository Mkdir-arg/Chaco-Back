"""URLs de la API de campo de Becas (#82). Namespace ``becas_api``."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from programas.api.views import (
    FormularioViewSet,
    ObtainCampoToken,
    RaizApiCampo,
    RelevamientoViewSet,
    consultar_persona_becas,
)

app_name = "becas_api"


class RouterApiCampo(DefaultRouter):
    """R0-04: la raíz del router autentica igual que el resto del namespace."""

    APIRootView = RaizApiCampo


router = RouterApiCampo()
router.register("relevamientos", RelevamientoViewSet, basename="relevamiento")
router.register("formularios", FormularioViewSet, basename="formulario")

urlpatterns = [
    path("auth/token/", ObtainCampoToken.as_view(), name="token"),
    path("personas/consultar/", consultar_persona_becas, name="personas-consultar"),
    path("renaper/consultar/", consultar_persona_becas, name="renaper-consultar"),
    path("", include(router.urls)),
]
