from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import path

from .views import (
    alerts_api,
    inicio_view,
    load_localidad,
    load_municipios,
    load_subsecretarias,
    optimization_suggestions_api,
    performance_api,
    performance_dashboard,
    phase2_metrics_api,
    query_analysis_api,
    realtime_metrics_api,
    relevamiento_detail_view,
    relevamientos_view,
    run_phase2_tests_api,
    system_metrics_api,
)

app_name = "core"


def dashboard_redirect(request):
    return redirect("dashboard:inicio")


urlpatterns = [
    path("inicio/", login_required(inicio_view), name="inicio"),
    path("dashboard/", login_required(dashboard_redirect), name="dashboard"),
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
    # Performance Dashboard URLs
    path("performance-dashboard/", performance_dashboard, name="performance_dashboard"),
    path("performance-api/", performance_api, name="performance_api"),
    path("query-analysis-api/", query_analysis_api, name="query_analysis_api"),
    path("optimization-suggestions-api/", optimization_suggestions_api, name="optimization_suggestions_api"),
    # Monitoring APIs
    path("system-metrics-api/", system_metrics_api, name="system_metrics_api"),
    path("alerts-api/", alerts_api, name="alerts_api"),
    path("realtime-metrics-api/", realtime_metrics_api, name="realtime_metrics_api"),
    path("phase2-metrics-api/", phase2_metrics_api, name="phase2_metrics_api"),
    path("run-phase2-tests-api/", run_phase2_tests_api, name="run_phase2_tests_api"),
]
