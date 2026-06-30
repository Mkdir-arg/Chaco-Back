from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api_views import GroupViewSet, ProfileViewSet, UserViewSet

router = DefaultRouter()
router.register(r"users", UserViewSet)
router.register(r"groups", GroupViewSet)
router.register(r"profiles", ProfileViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
