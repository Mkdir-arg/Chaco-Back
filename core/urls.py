from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import path

from .views import (
    inicio_view,
    latido_de_sesion,
    load_localidad,
    load_municipios,
    load_subsecretarias,
    optimization_suggestions_api,
    performance_api,
    performance_dashboard,
    query_analysis_api,
    relevamiento_detail_view,
    relevamientos_view,
)

app_name = "core"


def dashboard_redirect(request):
    # `/dashboard/` es un alias histórico del inicio del backoffice. Apuntar a
    # `dashboard:inicio` era ambiguo: esa vista está montada en la raíz, así que
    # reverseaba a `/` —la misma URL que el login— y el usuario autenticado
    # rebotaba por la pantalla de login en vez de ir derecho al inicio.
    return redirect("core:inicio")


urlpatterns = [
    path("inicio/", login_required(inicio_view), name="inicio"),
    path("dashboard/", login_required(dashboard_redirect), name="dashboard"),
    # SEC-35: el latido del cierre por inactividad. POST, para que no lo dispare
    # una etiqueta ajena con la cookie del usuario.
    path("sesion/latido/", latido_de_sesion, name="sesion_latido"),
    path("relevamientos/", login_required(relevamientos_view), name="relevamientos"),
    path("relevamientos/<uuid:relevamiento_id>/", login_required(relevamiento_detail_view), name="relevamiento_detail"),
    path(
        "ajax/load-municipios/",
        login_required(load_municipios),
        name="ajax_load_municipios",
    ),
    path(
        "ajax/load-localidades/",
        login_required(load_localidad),
        name="ajax_load_localidades",
    ),
    path(
        "ajax/load-subsecretarias/",
        login_required(load_subsecretarias),
        name="ajax_load_subsecretarias",
    ),
    # Observabilidad de consultas (OPS-10: lo que quedó del dashboard de performance;
    # las APIs de monitoreo de la «fase 2» se fueron con los módulos que las
    # alimentaban, y el candado está en `core/tests/test_performance_observability.py`).
    path("performance-dashboard/", performance_dashboard, name="performance_dashboard"),
    path("performance-api/", performance_api, name="performance_api"),
    path("query-analysis-api/", query_analysis_api, name="query_analysis_api"),
    path("optimization-suggestions-api/", optimization_suggestions_api, name="optimization_suggestions_api"),
]
