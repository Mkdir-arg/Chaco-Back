from django.urls import path

from programas.views import merenderos

app_name = "merenderos"

urlpatterns = [
    path("", merenderos.MerenderoListView.as_view(), name="lista"),
    path("solicitudes/", merenderos.SolicitudMerenderoListView.as_view(), name="solicitudes"),
    path("solicitudes/nueva/", merenderos.SolicitudMerenderoCreateView.as_view(), name="solicitud_crear"),
    path("solicitudes/<int:pk>/editar/", merenderos.SolicitudMerenderoUpdateView.as_view(), name="solicitud_editar"),
    path(
        "solicitudes/<int:pk>/<str:accion>/",
        merenderos.SolicitudMerenderoResolverView.as_view(),
        name="solicitud_resolver",
    ),
    path("<int:pk>/", merenderos.MerenderoDetailView.as_view(), name="detalle"),
    path("<int:pk>/entregas/nueva/", merenderos.EntregaMercaderiaCreateView.as_view(), name="entrega_crear"),
    path("<int:pk>/prestacion/", merenderos.PrestacionMensualView.as_view(), name="prestacion"),
    path("<int:pk>/<str:estado>/", merenderos.MerenderoEstadoView.as_view(), name="estado"),
]
