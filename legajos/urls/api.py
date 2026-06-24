from django.urls import path, include
from rest_framework.routers import DefaultRouter
from ..api_views import (
    CiudadanoViewSet,
    AlertasViewSet,
    consultar_renaper_api,
)

router = DefaultRouter()
router.register(r'ciudadanos', CiudadanoViewSet)
router.register(r'alertas', AlertasViewSet)

urlpatterns = [
    path('renaper/consultar/', consultar_renaper_api, name='renaper_consultar'),
    path('', include(router.urls)),
]
