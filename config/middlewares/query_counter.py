import logging
import time
from threading import Lock

from django.db import connection
from django.utils import timezone

from core.performance.performance_analyzer import PerformanceAnalyzer

logger = logging.getLogger(__name__)


class QueryCollector:
    """Captura consultas ejecutadas por una sola solicitud sin depender de DEBUG."""

    def __init__(self):
        self.count = 0
        self.slow_queries_count = 0
        self.queries = []

    def __call__(self, execute, sql, params, many, context):
        start = time.monotonic()
        try:
            return execute(sql, params, many, context)
        finally:
            duration = time.monotonic() - start
            self.count += 1
            if duration > 0.1:
                self.slow_queries_count += 1
            if len(self.queries) < 100:
                self.queries.append({"sql": sql, "time": f"{duration:.6f}"})


class QueryCountMiddleware:
    """Advanced middleware para monitorear queries N+1 y performance"""

    session_stats = None
    session_stats_lock = Lock()
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

    @classmethod
    def _initial_session_stats(cls):
        return {
            "total_requests": 0,
            "total_queries": 0,
            "slow_requests": 0,
            "slow_queries_count": 0,
            "n1_affected_requests": 0,
            "metrics_source": "unavailable",
            "last_reset": timezone.now(),
        }

    @classmethod
    def _ensure_session_stats(cls):
        if cls.session_stats is None:
            cls.session_stats = cls._initial_session_stats()
        return cls.session_stats

    def __init__(self, get_response):
        self.get_response = get_response
        self.analyzer = PerformanceAnalyzer()
        with self.__class__.session_stats_lock:
            self.__class__._ensure_session_stats()

    def __call__(self, request):
        if request.path in self.excluded_paths:
            return self.get_response(request)

        start_time = timezone.now()
        collector = QueryCollector()

        with connection.execute_wrapper(collector):
            response = self.get_response(request)

        end_time = timezone.now()
        response_time = (end_time - start_time).total_seconds()
        session_stats = self.__class__._ensure_session_stats()

        # Thresholds por tipo de vista (Phase 6 optimized)
        thresholds = {
            "/conversaciones/": 6,  # Phase 5 optimized (services improved)
            "/legajos/": 6,  # Phase 4 optimized
            "/dashboard/": 4,  # Phase 4 optimized
            "/core/": 2,  # Phase 5 optimized (audit service improved)
            "/users/": 5,  # Phase 2 optimized
            "/configuracion/": 6,  # Phase 3 optimized
            "/portal/": 4,  # Phase 4 optimized
            "/tramites/": 5,  # Phase 4 optimized
            "/admin/": 3,  # Phase 6 optimized (admin interfaces)
            "/api/": 4,  # Phase 3 optimized
        }

        threshold = 5  # Default (Phase 6 optimized)
        for path, limit in thresholds.items():
            if request.path.startswith(path):
                threshold = limit
                break

        n1_detected = False
        if collector.count > threshold:
            analysis = self.analyzer.analyze_queries(collector.queries)
            n1_detected = analysis["n1_detected"]

            alert_msg = (
                f"Performance Alert: {request.path} executed {collector.count} queries "
                f"(threshold: {threshold}) in {response_time:.3f}s - User: {request.user}"
            )

            logger.warning(alert_msg)

        with self.__class__.session_stats_lock:
            session_stats["total_requests"] += 1
            session_stats["total_queries"] += collector.count
            session_stats["slow_queries_count"] += collector.slow_queries_count
            session_stats["metrics_source"] = "measured"
            if response_time > 1.0:
                session_stats["slow_requests"] += 1
            if n1_detected:
                session_stats["n1_affected_requests"] += 1

        return response

    @classmethod
    def get_session_stats(cls):
        """Get current session statistics"""
        with cls.session_stats_lock:
            return cls._ensure_session_stats().copy()

    def _calculate_request_score(self, query_count, response_time):
        """Calculate performance score for request (0-100)"""
        score = 100

        # Penalize for high query count
        if query_count > 10:
            score -= min(50, (query_count - 10) * 5)

        # Penalize for slow response
        if response_time > 1.0:
            score -= min(30, (response_time - 1.0) * 20)

        return max(0, int(score))
