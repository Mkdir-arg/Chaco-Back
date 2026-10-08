from django.urls import path

from . import api_views

app_name = "dashboard"

# RED-78: acá estaba `path("", DashboardView.as_view(), name="inicio")`. Era una copia
# vieja del inicio del backoffice —contadores globales del organismo, sin el gate por
# capacidad de SEC-14— que nunca se servía: en `config/urls.py` el include de
# `users.urls` va **antes** que este, así que `/` es el login. Lo único que la separaba
# de estar viva era el orden de dos líneas, y el comentario «Root paths last» invitaba
# a moverlas. `core.tests.test_dashboard_redirect.RuteoRaizTests` lo cuida.
urlpatterns = [
    # APIs para el dashboard
    path("api/metricas/", api_views.metricas_dashboard, name="api_metricas"),
    path("api/buscar-ciudadanos/", api_views.buscar_ciudadanos, name="api_buscar_ciudadanos"),
    path("api/alertas-criticas/", api_views.alertas_criticas, name="api_alertas_criticas"),
    path("api/actividad-reciente/", api_views.actividad_reciente, name="api_actividad_reciente"),
    path("api/tendencias/", api_views.tendencias_datos, name="api_tendencias"),
]
