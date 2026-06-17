from django.urls import path, include
from rest_framework.routers import DefaultRouter
from ..api_views.contactos import (
    HistorialContactoViewSet,
    VinculoFamiliarViewSet,
)

router = DefaultRouter()
router.register(r'historial-contactos', HistorialContactoViewSet)
router.register(r'vinculos-familiares', VinculoFamiliarViewSet)

urlpatterns = [
    path('contactos/', include(router.urls)),
]
