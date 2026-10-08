from django.urls import path
from django.views.generic import RedirectView

from notificaciones.views import campanas

app_name = "notificaciones"

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="notificaciones:campanas", permanent=False)),
    path("campanas/", campanas.CampanaListView.as_view(), name="campanas"),
    path("campanas/nueva/", campanas.campana_crear, name="campana_crear"),
    path("campanas/plantilla.xlsx", campanas.plantilla_excel, name="plantilla_excel"),
    path("campanas/<int:pk>/", campanas.campana_detalle, name="campana_detalle"),
    path("campanas/<int:pk>/editar/", campanas.campana_editar, name="campana_editar"),
    path("campanas/<int:pk>/eliminar/", campanas.campana_eliminar, name="campana_eliminar"),
    path("campanas/<int:pk>/duplicar/", campanas.campana_duplicar, name="campana_duplicar"),
    path("campanas/<int:pk>/vista-previa/", campanas.vista_previa_html, name="campana_vista_previa"),
    path("campanas/<int:pk>/prueba/", campanas.campana_prueba, name="campana_prueba"),
    path("campanas/<int:pk>/enviar/", campanas.campana_enviar, name="campana_enviar"),
    path("campanas/<int:pk>/detener/", campanas.campana_detener, name="campana_detener"),
    path("campanas/<int:pk>/reanudar/", campanas.campana_reanudar, name="campana_reanudar"),
    path("campanas/<int:pk>/resultado.xlsx", campanas.exportar_resultado, name="campana_exportar"),
]
