from django.urls import path

from . import api_views
from .views import DashboardView

app_name = "dashboard"

urlpatterns = [
    path("", DashboardView.as_view(), name="inicio"),
    # APIs para el dashboard
    path("api/metricas/", api_views.metricas_dashboard, name="api_metricas"),
    path("api/buscar-ciudadanos/", api_views.buscar_ciudadanos, name="api_buscar_ciudadanos"),
    path("api/alertas-criticas/", api_views.alertas_criticas, name="api_alertas_criticas"),
    path("api/actividad-reciente/", api_views.actividad_reciente, name="api_actividad_reciente"),
    path("api/tendencias/", api_views.tendencias_datos, name="api_tendencias"),
]
