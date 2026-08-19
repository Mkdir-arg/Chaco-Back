"""Métricas HTTP agregadas, sin SQL ni datos personales."""

import hashlib
import logging
import time
from collections import defaultdict
from contextvars import ContextVar
from threading import Lock

from django.conf import settings
from django.urls import Resolver404, resolve

METRICS_VERSION = "v1"
logger = logging.getLogger(__name__)
_LOCAL_LOCK = Lock()
_LOCAL_BUCKETS = defaultdict(lambda: defaultdict(int))
_MEASUREMENT = ContextVar("performance_measurement", default=None)
_REDIS_STATE_LOCK = Lock()
_REDIS_DEGRADED = False
_REDIS_LAST_WARNING = 0.0
_REDIS_WARNING_INTERVAL_SECONDS = 60.0
_UPDATE_MAXIMA_SCRIPT = """
for index = 1, #ARGV, 2 do
    local field = ARGV[index]
    local candidate = tonumber(ARGV[index + 1])
    local current = tonumber(redis.call('HGET', KEYS[1], field) or '0')
    if candidate > current then
        redis.call('HSET', KEYS[1], field, candidate)
    end
end
return 1
"""


def reset_local_metrics_for_tests():
    """Aísla tests; nunca se invoca en un entorno servido."""
    global _REDIS_DEGRADED, _REDIS_LAST_WARNING
    with _LOCAL_LOCK:
        _LOCAL_BUCKETS.clear()
    with _REDIS_STATE_LOCK:
        _REDIS_DEGRADED = False
        _REDIS_LAST_WARNING = 0.0


def _mark_redis_degraded(operation, error):
    """Informa la degradación sin registrar endpoints, payloads ni credenciales."""
    global _REDIS_DEGRADED, _REDIS_LAST_WARNING
    now = time.monotonic()
    with _REDIS_STATE_LOCK:
        _REDIS_DEGRADED = True
        should_warn = now - _REDIS_LAST_WARNING >= _REDIS_WARNING_INTERVAL_SECONDS
        if should_warn:
            _REDIS_LAST_WARNING = now
    if should_warn:
        logger.warning(
            "Redis de métricas no disponible durante %s; se informarán métricas no disponibles hasta una escritura exitosa (%s).",
            operation,
            type(error).__name__,
        )


def _mark_redis_healthy():
    global _REDIS_DEGRADED
    with _REDIS_STATE_LOCK:
        _REDIS_DEGRADED = False


def _redis_is_degraded():
    with _REDIS_STATE_LOCK:
        return _REDIS_DEGRADED


def route_name(path):
    """Devuelve una ruta estable, sin IDs ni query strings."""
    try:
        return resolve(path).view_name or "unresolved"
    except Resolver404:
        return "unresolved"


def sql_fingerprint(sql):
    """Normaliza SQL sólo para detectar repeticiones durante una request."""
    import re

    sql = re.sub(r"'(?:''|\\.|[^'])*'", "?", sql)
    return re.sub(r"(?<![\w])[-+]?\d+(?:\.\d+)?(?![\w])", "?", sql)


def _duration_bucket(milliseconds):
    for limit in (50, 100, 250, 500, 1000, 3000):
        if milliseconds <= limit:
            return str(limit)
    return "inf"


class RequestMeasurement:
    def __init__(self, route):
        self.route = route
        self.dependencies = defaultdict(lambda: {"calls": 0, "errors": 0, "duration_ms": 0})

    def record_dependency(self, dependency, duration_ms, failed):
        item = self.dependencies[dependency]
        item["calls"] += 1
        item["errors"] += int(failed)
        item["duration_ms"] += round(duration_ms)


def instrument_external_call(dependency, call, *args, **kwargs):
    """Mide un cliente externo en el contexto de la request actual.

    No registra URL, payload, credenciales ni respuesta.
    """
    measurement = _MEASUREMENT.get()
    started = time.monotonic()
    try:
        result = call(*args, **kwargs)
    except Exception:
        if measurement:
            measurement.record_dependency(dependency, (time.monotonic() - started) * 1000, True)
        raise
    if measurement:
        failed = getattr(result, "status_code", 200) >= 400
        measurement.record_dependency(dependency, (time.monotonic() - started) * 1000, failed)
    return result


class QueryObservabilityStore:
    """Escritura atómica por ventana sobre Redis, con fallback sólo local."""

    def __init__(self):
        self.window_seconds = int(getattr(settings, "PERFORMANCE_METRICS_WINDOW_SECONDS", 3600))
        self.retention_seconds = int(getattr(settings, "PERFORMANCE_METRICS_RETENTION_SECONDS", 86400))
        self.namespace = str(getattr(settings, "PERFORMANCE_METRICS_NAMESPACE", "")).strip()

    def _bucket_key(self):
        if self.namespace:
            bucket = hashlib.sha256(self.namespace.encode()).hexdigest()[:16]
            return f"performance:observability:{METRICS_VERSION}:{settings.ENVIRONMENT}:run:{bucket}", bucket
        bucket = int(time.time() // self.window_seconds)
        return f"performance:observability:{METRICS_VERSION}:{settings.ENVIRONMENT}:{bucket}", bucket

    def _redis(self):
        if "performance" not in settings.CACHES:
            return None
        try:
            from django_redis import get_redis_connection

            return get_redis_connection("performance")
        except Exception as exc:
            _mark_redis_degraded("conexión", exc)
            return None

    def _local_allowed(self):
        return bool(getattr(settings, "PYTEST_RUNNING", False) or settings.ENVIRONMENT == "dev")

    def record(self, route, query_count, slow_queries, n1_detected, duration_ms, dependencies, duplicate_query_count=0):
        key, _bucket = self._bucket_key()
        route_id = hashlib.sha256(route.encode()).hexdigest()[:16]
        increments = {
            "total_requests": 1,
            "total_queries": query_count,
            "total_duplicate_queries": duplicate_query_count,
            "slow_queries_count": slow_queries,
            "slow_requests": int(duration_ms > 1000),
            "n1_affected_requests": int(n1_detected),
            f"route:{route_id}:requests": 1,
            f"route:{route_id}:queries": query_count,
            f"route:{route_id}:duplicate_queries": duplicate_query_count,
            f"route:{route_id}:slow_queries": slow_queries,
            f"route:{route_id}:n1": int(n1_detected),
            f"route:{route_id}:latency:{_duration_bucket(duration_ms)}": 1,
        }
        for dependency, values in dependencies.items():
            increments[f"route:{route_id}:dependency:{dependency}:calls"] = values["calls"]
            increments[f"route:{route_id}:dependency:{dependency}:errors"] = values["errors"]
            increments[f"route:{route_id}:dependency:{dependency}:duration_ms"] = values["duration_ms"]

        redis = self._redis()
        if redis:
            try:
                pipeline = redis.pipeline()
                for field, value in increments.items():
                    pipeline.hincrby(key, field, value)
                pipeline.hsetnx(key, f"route:{route_id}:name", route)
                pipeline.eval(
                    _UPDATE_MAXIMA_SCRIPT,
                    1,
                    key,
                    f"route:{route_id}:max_queries",
                    query_count,
                    f"route:{route_id}:max_duplicate_queries",
                    duplicate_query_count,
                )
                pipeline.expire(key, self.retention_seconds)
                pipeline.execute()
            except Exception as exc:
                _mark_redis_degraded("escritura", exc)
                return
            _mark_redis_healthy()
            return
        if self._local_allowed():
            with _LOCAL_LOCK:
                for field, value in increments.items():
                    _LOCAL_BUCKETS[key][field] += value
                _LOCAL_BUCKETS[key][f"route:{route_id}:name"] = route
                for field, value in (
                    (f"route:{route_id}:max_queries", query_count),
                    (f"route:{route_id}:max_duplicate_queries", duplicate_query_count),
                ):
                    _LOCAL_BUCKETS[key][field] = max(_LOCAL_BUCKETS[key][field], value)

    def snapshot(self):
        key, bucket = self._bucket_key()
        redis = self._redis()
        shared = redis is not None
        if redis:
            try:
                raw = {k.decode() if isinstance(k, bytes) else k: v for k, v in redis.hgetall(key).items()}
            except Exception as exc:
                _mark_redis_degraded("lectura", exc)
                raw = {}
            if _redis_is_degraded():
                raw = {}
        elif self._local_allowed():
            with _LOCAL_LOCK:
                raw = dict(_LOCAL_BUCKETS[key])
        else:
            raw = {}
        if not raw:
            return {"metrics_source": "unavailable", "scope": None, "window": None, "routes": []}

        def number(name):
            value = raw.get(name, 0)
            return int(value.decode() if isinstance(value, bytes) else value)

        routes = []
        for field, value in raw.items():
            if not field.endswith(":name"):
                continue
            route_id = field.split(":")[1]
            name = value.decode() if isinstance(value, bytes) else value
            histogram = {
                limit: number(f"route:{route_id}:latency:{limit}")
                for limit in ("50", "100", "250", "500", "1000", "3000", "inf")
            }
            dependencies = defaultdict(dict)
            prefix = f"route:{route_id}:dependency:"
            for dependency_field, dependency_value in raw.items():
                if not dependency_field.startswith(prefix):
                    continue
                _, metric = dependency_field.rsplit(":", 1)
                dependency = dependency_field[len(prefix) :].rsplit(":", 1)[0]
                dependencies[dependency][metric] = int(
                    dependency_value.decode() if isinstance(dependency_value, bytes) else dependency_value
                )
            target = number(f"route:{route_id}:requests") * 0.95
            cumulative = 0
            p95_bucket = "inf"
            for limit, count in histogram.items():
                cumulative += count
                if cumulative >= target:
                    p95_bucket = limit
                    break
            routes.append(
                {
                    "route": name,
                    "requests": number(f"route:{route_id}:requests"),
                    "queries": number(f"route:{route_id}:queries"),
                    "duplicate_queries": number(f"route:{route_id}:duplicate_queries"),
                    "max_queries": number(f"route:{route_id}:max_queries"),
                    "max_duplicate_queries": number(f"route:{route_id}:max_duplicate_queries"),
                    "n1_affected_requests": number(f"route:{route_id}:n1"),
                    "latency_histogram": histogram,
                    "p95_upper_bound_ms": None if p95_bucket == "inf" else int(p95_bucket),
                    "dependencies": dict(dependencies),
                }
            )
        return {
            "metrics_source": "measured",
            "scope": (
                "shared_ci_run"
                if shared and self.namespace
                else "shared_fixed_window"
                if shared
                else "local_fixed_window"
            ),
            "window": {
                "kind": "ci_run" if self.namespace else "fixed",
                "bucket": bucket,
                "seconds": None if self.namespace else self.window_seconds,
            },
            "total_requests": number("total_requests"),
            "total_queries": number("total_queries"),
            "total_duplicate_queries": number("total_duplicate_queries"),
            "slow_requests": number("slow_requests"),
            "slow_queries_count": number("slow_queries_count"),
            "n1_affected_requests": number("n1_affected_requests"),
            "routes": sorted(routes, key=lambda item: item["route"]),
        }


def query_observability_report(session_stats=None):
    """Contrato único de métricas reales; ``session_stats`` queda por compatibilidad."""
    snapshot = QueryObservabilityStore().snapshot()
    source = snapshot["metrics_source"]
    query_metric = {
        "source": source,
        "scope": snapshot["scope"],
        "value": snapshot.get("total_queries") if source == "measured" else None,
        "details_source": "aggregated_only" if source == "measured" else "unavailable",
        "retention_seconds": int(getattr(settings, "PERFORMANCE_METRICS_RETENTION_SECONDS", 86400)),
    }
    if source != "measured":
        return {
            "total_queries": None,
            "total_duplicate_queries": None,
            "total_requests": None,
            "slow_requests": None,
            "slow_queries_count": None,
            "slow_queries": None,
            "n1_detected": None,
            "n1_affected_requests": None,
            "performance_score": None,
            "recommendations": [],
            "routes": [],
            "window": None,
            "metrics": {"queries": query_metric},
        }
    n1 = snapshot["n1_affected_requests"]
    recommendations = []
    if n1:
        recommendations.append(
            {"type": "N+1 Detection", "suggestion": "Revisar rutas medidas con patrones N+1.", "count": n1}
        )
    if snapshot["slow_queries_count"]:
        recommendations.append(
            {
                "type": "Slow Queries",
                "suggestion": "Revisar rutas medidas con consultas lentas.",
                "count": snapshot["slow_queries_count"],
            }
        )
    return {
        **{
            key: snapshot[key]
            for key in (
                "total_queries",
                "total_duplicate_queries",
                "total_requests",
                "slow_requests",
                "slow_queries_count",
                "n1_affected_requests",
                "routes",
                "window",
            )
        },
        "slow_queries": None,
        "n1_detected": n1 > 0,
        "performance_score": max(20, 100 - min(50, snapshot["slow_requests"] * 5) - min(30, n1 * 3)),
        "recommendations": recommendations,
        "metrics": {"queries": query_metric},
    }
