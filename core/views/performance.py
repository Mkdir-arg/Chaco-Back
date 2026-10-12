import logging

from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from core import rbac

from ..performance.query_observability import query_observability_report

logger = logging.getLogger(__name__)

#: SEC-36 · Lo único que sale al cliente cuando una de estas APIs explota.
ERROR_GENERICO = "No se pudieron obtener las métricas. El detalle quedó en el log del servidor."


def is_admin(user):
    return rbac.puede(user, "config.administrar")


@login_required
@user_passes_test(is_admin)
def performance_dashboard(request):
    """Performance monitoring dashboard"""
    return render(request, "core/performance_dashboard.html")


from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import BasePermission

from core.api_permissions import BackofficeAutenticado

# RED-37 punto 3 (Ola 7). Las tres APIs de acá declaraban `responses={200: "<una
# frase>"}`: Spectacular no sabe resolver una cadena suelta, avisaba
# («could not resolve … Defaulting to generic free-form object») y publicaba un
# objeto sin una sola propiedad. Ahora declaran sus claves de primer nivel, que
# son las mismas en las dos ramas de `query_observability_report()` —la medida y
# la que devuelve todo en `null` cuando la instrumentación está apagada—.
#
# Los bloques anidados quedan como objetos libres **a propósito**: `metrics`,
# `routes` y `real_time` cambian de forma con la instrumentación y declararlos
# campo por campo sería fijar un contrato que la vista no sostiene. Son APIs de
# diagnóstico para `config.administrar`, no superficie de integración.


def _opcional(campo):
    """Las métricas vienen en `null` enteras cuando no hay medición."""
    return campo(allow_null=True, required=True)


class IsPerformanceAdmin(BasePermission):
    message = "No tiene permiso para consultar métricas de performance."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and is_admin(request.user))


@extend_schema(
    summary="Métricas de performance del sistema",
    description="Observabilidad de consultas del proceso. Solo para `config.administrar`.",
    responses={
        200: inline_serializer(
            name="MetricasPerformance",
            fields={
                "total_queries": _opcional(serializers.IntegerField),
                "total_duplicate_queries": _opcional(serializers.IntegerField),
                "total_requests": _opcional(serializers.IntegerField),
                "slow_requests": _opcional(serializers.IntegerField),
                "slow_queries_count": _opcional(serializers.IntegerField),
                "slow_queries": _opcional(serializers.IntegerField),
                "n1_detected": _opcional(serializers.IntegerField),
                "n1_affected_requests": _opcional(serializers.IntegerField),
                "performance_score": _opcional(serializers.FloatField),
                "recommendations": serializers.ListField(child=serializers.DictField()),
                "routes": serializers.ListField(child=serializers.DictField()),
                "window": _opcional(serializers.IntegerField),
                "sampling_rate": _opcional(serializers.FloatField),
                "metrics": serializers.DictField(help_text="Una entrada por métrica, con `source`, `scope` y `value`."),
                "real_time": serializers.DictField(help_text="Foto del proceso al momento de la consulta."),
            },
        )
    },
)
@api_view(["GET"])
@permission_classes([BackofficeAutenticado, IsPerformanceAdmin])
def performance_api(request):
    """API endpoint for performance data"""
    report = query_observability_report()
    query_metric = report["metrics"]["queries"]
    memory_usage = _get_memory_usage()

    report.update(
        {
            "metrics": {
                "queries": query_metric,
                "requests": {
                    "source": query_metric["source"],
                    "scope": query_metric["scope"],
                    "value": report["total_requests"],
                },
                "n_plus_one": {
                    "source": query_metric["source"],
                    "scope": query_metric["scope"],
                    "value": report["n1_affected_requests"],
                },
                "memory": {"source": "psutil", "scope": "current_process", "value": memory_usage},
                "database_connections": {"source": "unavailable", "scope": None, "value": None},
            },
            "real_time": {
                "active_connections": None,
                "observed_requests": report["total_requests"],
                "timestamp": timezone.now().isoformat(),
                "memory_usage": memory_usage,
                "window": report["window"],
            },
        }
    )

    return JsonResponse(report)


@extend_schema(
    summary="Análisis de patrones de consultas",
    description=(
        "Mismas claves con o sin medición: sin ella todos los números vienen en `null` y "
        "`recommendations` vacío, para que el tablero no tenga que distinguir dos formas."
    ),
    responses={
        200: inline_serializer(
            name="AnalisisDeConsultas",
            fields={
                "query_count": _opcional(serializers.IntegerField),
                "patterns": serializers.DictField(
                    help_text="`total_queries`, `n1_detected` y `affected_requests`, cada uno anulable."
                ),
                "slow_queries": _opcional(serializers.IntegerField),
                "slow_queries_count": _opcional(serializers.IntegerField),
                "recommendations": serializers.ListField(child=serializers.DictField()),
                "metrics": serializers.DictField(),
            },
        )
    },
)
@api_view(["GET"])
@permission_classes([BackofficeAutenticado, IsPerformanceAdmin])
def query_analysis_api(request):
    """Detailed query analysis API"""
    report = query_observability_report()
    query_metric = report["metrics"]["queries"]
    if query_metric["source"] != "measured":
        return JsonResponse(
            {
                "query_count": None,
                "patterns": {"total_queries": None, "n1_detected": None, "affected_requests": None},
                "slow_queries": None,
                "slow_queries_count": None,
                "recommendations": [],
                "metrics": {"queries": query_metric},
            }
        )

    analysis = {
        "query_count": report["total_queries"],
        "patterns": {
            "total_queries": report["total_queries"],
            "n1_detected": report["n1_detected"],
            "affected_requests": report["n1_affected_requests"],
        },
        "slow_queries": None,
        "slow_queries_count": report["slow_queries_count"],
        "recommendations": report["recommendations"],
        "metrics": {"queries": query_metric},
    }

    return JsonResponse(analysis)


@extend_schema(
    summary="Sugerencias de optimización",
    description="Texto fijo parametrizado con `?model=`; no mira el estado del sistema.",
    responses={
        200: inline_serializer(
            name="SugerenciasDeOptimizacion",
            fields={
                "suggestions": inline_serializer(
                    name="SugerenciaDeOptimizacion",
                    many=True,
                    fields={
                        "category": serializers.CharField(),
                        "items": serializers.ListField(
                            child=serializers.DictField(
                                help_text="`title`, `description`, `example` e `impact`.",
                            )
                        ),
                    },
                )
            },
        )
    },
)
@api_view(["GET"])
@permission_classes([BackofficeAutenticado, IsPerformanceAdmin])
def optimization_suggestions_api(request):
    """API for optimization suggestions"""
    model_name = request.GET.get("model", "")

    suggestions = [
        {
            "category": "Query Optimization",
            "items": [
                {
                    "title": "Use select_related()",
                    "description": "For ForeignKey relationships to reduce queries",
                    "example": f'{model_name}.objects.select_related("foreign_key_field")',
                    "impact": "High",
                },
                {
                    "title": "Use prefetch_related()",
                    "description": "For reverse relationships and ManyToMany fields",
                    "example": f'{model_name}.objects.prefetch_related("reverse_field")',
                    "impact": "High",
                },
                {
                    "title": "Use only() for field limitation",
                    "description": "When you only need specific fields",
                    "example": f'{model_name}.objects.only("field1", "field2")',
                    "impact": "Medium",
                },
            ],
        }
    ]

    return JsonResponse({"suggestions": suggestions})


def _get_memory_usage():
    """Get current memory usage (simplified)"""
    try:
        import psutil

        process = psutil.Process()
        return {"memory_percent": process.memory_percent(), "memory_mb": process.memory_info().rss / 1024 / 1024}
    except ImportError:
        return {"memory_percent": 0, "memory_mb": 0}
