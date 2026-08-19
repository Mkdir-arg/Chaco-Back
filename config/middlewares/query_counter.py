import logging
import time
from collections import Counter

from django.db import connection

from core.performance.query_observability import (
    _MEASUREMENT,
    QueryObservabilityStore,
    RequestMeasurement,
    query_observability_report,
    route_name,
    sql_fingerprint,
)

logger = logging.getLogger(__name__)


class QueryCollector:
    """Cuenta y fingerprinta consultas de una request, sin retener SQL crudo."""

    def __init__(self):
        self.count = 0
        self.slow_queries_count = 0
        self.fingerprints = Counter()

    def __call__(self, execute, sql, params, many, context):
        started = time.monotonic()
        try:
            return execute(sql, params, many, context)
        finally:
            duration = time.monotonic() - started
            self.count += 1
            self.slow_queries_count += int(duration > 0.1)
            self.fingerprints[sql_fingerprint(sql)] += 1

    @property
    def n1_detected(self):
        return any(count > 3 for count in self.fingerprints.values())

    @property
    def duplicate_query_count(self):
        return sum(count - 1 for count in self.fingerprints.values() if count > 1)


class QueryCountMiddleware:
    """Mide requests de negocio y las agrega sin datos sensibles."""

    excluded_paths = frozenset(
        {
            "/health/",
            "/performance-dashboard/",
            "/performance-api/",
            "/query-analysis-api/",
            "/optimization-suggestions-api/",
            "/system-metrics-api/",
            "/alerts-api/",
            "/realtime-metrics-api/",
            "/phase2-metrics-api/",
            "/run-phase2-tests-api/",
        }
    )

    def __init__(self, get_response):
        self.get_response = get_response
        self.store = QueryObservabilityStore()

    def __call__(self, request):
        if request.path in self.excluded_paths:
            return self.get_response(request)
        route = route_name(request.path_info)
        measurement = RequestMeasurement(route)
        token = _MEASUREMENT.set(measurement)
        collector = QueryCollector()
        started = time.monotonic()
        try:
            with connection.execute_wrapper(collector):
                response = self.get_response(request)
        finally:
            _MEASUREMENT.reset(token)
        duration_ms = (time.monotonic() - started) * 1000
        self.store.record(
            route,
            collector.count,
            collector.slow_queries_count,
            collector.n1_detected,
            duration_ms,
            measurement.dependencies,
            duplicate_query_count=collector.duplicate_query_count,
        )
        if collector.n1_detected:
            logger.warning(
                "Performance Alert: route=%s query_count=%s duration_ms=%.0f", route, collector.count, duration_ms
            )
        return response

    @classmethod
    def get_session_stats(cls):
        """Compatibilidad temporal para consumidores existentes."""
        report = query_observability_report()
        return {
            "total_requests": report["total_requests"] or 0,
            "total_queries": report["total_queries"] or 0,
            "slow_requests": report["slow_requests"] or 0,
            "slow_queries_count": report["slow_queries_count"] or 0,
            "n1_affected_requests": report["n1_affected_requests"] or 0,
            "metrics_source": report["metrics"]["queries"]["source"],
        }
