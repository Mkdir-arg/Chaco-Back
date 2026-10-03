from django.urls import path

from .api_views import UsuarioActualView

urlpatterns = [
    path("me/", UsuarioActualView.as_view(), name="usuario-actual"),
]
