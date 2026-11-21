from django.urls import path

from mapa import views

app_name = "mapa"

urlpatterns = [
    path("", views.mapa, name="inicio"),
    path("api/puntos/", views.puntos, name="api_puntos"),
    path("api/puntos/<int:pk>/", views.punto, name="api_punto"),
]
