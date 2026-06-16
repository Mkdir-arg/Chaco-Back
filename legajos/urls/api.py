from django.urls import path, include
from rest_framework.routers import DefaultRouter
from ..api_views import (
    CiudadanoViewSet,
    DerivacionViewSet,
    AlertasViewSet,
)

router = DefaultRouter()
router.register(r'ciudadanos', CiudadanoViewSet)
router.register(r'derivaciones', DerivacionViewSet)
router.register(r'alertas', AlertasViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
