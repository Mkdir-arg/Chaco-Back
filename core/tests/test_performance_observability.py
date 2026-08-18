import json
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from config.middlewares.query_counter import QueryCollector, QueryCountMiddleware
from conversaciones.context_processors import user_groups
from core import rbac
from core.performance.query_observability import (
    QueryObservabilityStore,
    instrument_external_call,
    reset_local_metrics_for_tests,
)


class BrokenRedis:
    """Cliente mínimo que reproduce una caída después de obtener la conexión."""

    def pipeline(self):
        return self

    def hincrby(self, *_args):
        return self

    def hsetnx(self, *_args):
        return self

    def eval(self, *_args):
        return self

    def expire(self, *_args):
        return self

    def execute(self):
        raise ConnectionError("redis down")

    def hgetall(self, *_args):
        raise ConnectionError("redis down")


class StaleRedis(BrokenRedis):
    """Simula una escritura fallida seguida por una lectura de datos anteriores."""

    def hgetall(self, *_args):
        return {b"total_requests": b"1"}


class PerformanceObservabilityTests(TestCase):
    def setUp(self):
        reset_local_metrics_for_tests()
        self.admin = User.objects.create_superuser("performance-admin", "performance@example.test", "test-password")
        self.client.force_login(self.admin)

    def test_performance_api_reports_unavailable_metrics_before_any_instrumented_request(self):
        response = self.client.get(reverse("core:performance_api"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["metrics"]["queries"]["source"], "unavailable")

    def test_authenticated_user_without_performance_access_is_rejected(self):
        self.client.force_login(User.objects.create_user("regular-user", password="test-password"))
        self.assertEqual(self.client.get(reverse("core:performance_api")).status_code, 403)

    def test_dashboard_explains_when_query_metrics_are_not_measured(self):
        response = self.client.get(reverse("core:performance_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Métricas de consultas no disponibles")

    def test_dashboard_describes_shared_metric_scope(self):
        response = self.client.get(reverse("core:performance_dashboard"))

        self.assertContains(response, "compartidas entre workers")
        self.assertNotContains(response, "de este proceso")

    def test_query_analysis_does_not_report_missing_telemetry_as_zero(self):
        response = self.client.get(reverse("core:query_analysis_api"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["metrics"]["queries"]["source"], "unavailable")
        self.assertIsNone(response.json()["query_count"])

    def test_performance_api_exposes_measured_aggregate(self):
        QueryObservabilityStore().record("core:inicio", 8, 1, True, 120, {})

        response = self.client.get(reverse("core:performance_api"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["metrics"]["queries"]["source"], "measured")
        self.assertEqual(response.json()["total_queries"], 8)

    def test_system_metrics_do_not_claim_connection_queries(self):
        response = self.client.get(reverse("core:system_metrics_api"))

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["django"]["database"]["queries_count"])
        self.assertEqual(response.json()["sources"]["database_connections"]["source"], "unavailable")


class QueryCountMiddlewareTests(TestCase):
    def setUp(self):
        reset_local_metrics_for_tests()

    @override_settings(DEBUG=False)
    def test_records_route_aggregate_without_debug_or_raw_sql(self):
        user = User.objects.create_user("observability-user", password="test-password")

        def get_response(_request):
            User.objects.get(pk=user.pk)
            return HttpResponse("ok")

        response = QueryCountMiddleware(get_response)(RequestFactory().get("/inicio/"))
        snapshot = QueryObservabilityStore().snapshot()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(snapshot["metrics_source"], "measured")
        self.assertEqual(snapshot["scope"], "local_fixed_window")
        self.assertEqual(snapshot["routes"][0]["route"], "core:inicio")
        self.assertGreaterEqual(snapshot["total_queries"], 1)

    def test_excludes_monitoring_and_health_routes_from_measurement(self):
        middleware = QueryCountMiddleware(lambda _request: HttpResponse("ok"))

        middleware(RequestFactory().get(reverse("core:performance_api")))
        middleware(RequestFactory().get("/health/"))

        self.assertEqual(QueryObservabilityStore().snapshot()["metrics_source"], "unavailable")

    def test_collector_keeps_only_normalized_fingerprints(self):
        collector = QueryCollector()
        collector(lambda *_args: None, "SELECT * FROM person WHERE dni = 30111222 AND nombre = 'Ana'", [], False, {})

        fingerprint = next(iter(collector.fingerprints))
        self.assertNotIn("30111222", fingerprint)
        self.assertNotIn("Ana", fingerprint)

    def test_records_external_dependency_without_url_or_payload(self):
        response = type("Response", (), {"status_code": 200})()

        def get_response(_request):
            instrument_external_call("renaper", lambda: response)
            return HttpResponse("ok")

        QueryCountMiddleware(get_response)(RequestFactory().get("/inicio/"))
        snapshot = QueryObservabilityStore().snapshot()

        self.assertEqual(snapshot["total_requests"], 1)
        self.assertEqual(snapshot["routes"][0]["dependencies"]["renaper"]["calls"], 1)

    def test_records_http_4xx_as_external_dependency_error(self):
        response = type("Response", (), {"status_code": 404})()

        def get_response(_request):
            instrument_external_call("personas", lambda: response)
            return HttpResponse("ok")

        QueryCountMiddleware(get_response)(RequestFactory().get("/inicio/"))
        dependency = QueryObservabilityStore().snapshot()["routes"][0]["dependencies"]["personas"]

        self.assertEqual(dependency["calls"], 1)
        self.assertEqual(dependency["errors"], 1)

    def test_records_duplicate_query_count_without_persisting_sql(self):
        user = User.objects.create_user("duplicate-observability-user", password="test-password")

        def get_response(_request):
            User.objects.get(pk=user.pk)
            User.objects.get(pk=user.pk)
            return HttpResponse("ok")

        QueryCountMiddleware(get_response)(RequestFactory().get("/inicio/"))
        snapshot = QueryObservabilityStore().snapshot()

        self.assertEqual(snapshot["total_duplicate_queries"], 1)
        self.assertEqual(snapshot["routes"][0]["duplicate_queries"], 1)

    def test_keeps_per_request_maxima_for_budget_enforcement(self):
        store = QueryObservabilityStore()

        store.record("core:inicio", 19, 0, False, 100, {}, duplicate_query_count=4)
        store.record("core:inicio", 1, 0, False, 10, {})

        route = store.snapshot()["routes"][0]
        self.assertEqual(route["max_queries"], 19)
        self.assertEqual(route["max_duplicate_queries"], 4)

    def test_redis_failure_does_not_break_the_instrumented_request_or_report(self):
        middleware = QueryCountMiddleware(lambda _request: HttpResponse("ok"))

        with patch.object(QueryObservabilityStore, "_redis", return_value=BrokenRedis()):
            response = middleware(RequestFactory().get("/inicio/"))
            report = QueryObservabilityStore().snapshot()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(report["metrics_source"], "unavailable")

    def test_failed_redis_write_does_not_report_stale_metrics_as_measured(self):
        middleware = QueryCountMiddleware(lambda _request: HttpResponse("ok"))

        with self.assertLogs("core.performance.query_observability", level="WARNING"):
            with patch.object(QueryObservabilityStore, "_redis", return_value=StaleRedis()):
                response = middleware(RequestFactory().get("/inicio/"))
                report = QueryObservabilityStore().snapshot()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(report["metrics_source"], "unavailable")


class GroupLookupReuseTests(TestCase):
    def test_reuse_does_not_corrupt_djangos_related_manager_cache(self):
        group = Group.objects.create(name="Operadores")
        user = User.objects.create_user("grouped-user", password="test-password")
        user.groups.add(group)

        self.assertEqual(rbac.nombres_de_grupos(user), ("Operadores",))
        self.assertEqual(list(user.groups.values_list("name", flat=True)), ["Operadores"])

    def test_portal_identity_and_template_context_share_one_group_lookup(self):
        group = Group.objects.create(name="Operadores")
        user = User.objects.create_superuser("context-user", "context@example.test", "test-password")
        user.groups.add(group)
        user = User.objects.get(pk=user.pk)
        request = RequestFactory().get("/inicio/")
        request.user = user

        with CaptureQueriesContext(connection) as queries:
            self.assertFalse(rbac.es_ciudadano_portal(user))
            context = user_groups(request)

        self.assertEqual(context["user_groups_list"], ["Operadores"])
        self.assertEqual(len(queries), 1)


class AnalyzePerformanceCommandTests(TestCase):
    def setUp(self):
        reset_local_metrics_for_tests()

    def test_json_report_marks_query_metrics_unavailable_without_activity(self):
        output = StringIO()
        call_command("analyze_performance", "--output", "json", stdout=output)
        self.assertEqual(json.loads(output.getvalue())["metrics"]["queries"]["source"], "unavailable")

    def test_json_report_exposes_fixed_window_route_contract(self):
        QueryObservabilityStore().record("core:inicio", 8, 1, True, 120, {})
        output = StringIO()
        call_command("analyze_performance", "--output", "json", stdout=output)

        report = json.loads(output.getvalue())
        self.assertEqual(report["routes"][0]["route"], "core:inicio")
        self.assertEqual(report["metrics"]["queries"]["details_source"], "aggregated_only")


class EphemeralPerformanceCiCommandTests(TestCase):
    def test_ci_probe_refuses_non_ephemeral_database(self):
        with self.assertRaisesMessage(CommandError, "sólo puede correr"):
            call_command("perf_ci_probe", "--worker", "worker-1", "--output", "ignored.json")

    def test_ci_artifact_guard_rejects_sensitive_fields(self):
        from core.management.commands.perf_ci_probe import Command

        with self.assertRaisesMessage(CommandError, "campos sensibles"):
            Command._assert_redacted({"route": "core:inicio", "sql": "SELECT secret"})

    def test_ci_dependency_probe_records_only_named_stub_aggregates(self):
        from core.management.commands.perf_ci_probe import Command

        reset_local_metrics_for_tests()
        Command._record_stubbed_dependencies()

        dependencies = QueryObservabilityStore().snapshot()["routes"][0]["dependencies"]
        self.assertEqual(set(dependencies), {"ci_stub", "siis", "personas", "renaper"})
        for item in dependencies.values():
            self.assertEqual(item["calls"], 1)
            self.assertEqual(item["errors"], 0)
            self.assertGreaterEqual(item["duration_ms"], 0)

    def test_ci_workers_use_distinct_identities_for_single_session_policy(self):
        from core.management.commands.perf_ci_probe import Command
        from legajos.models import Ciudadano
        from users.models import Profile

        group = Group.objects.create(name="PERF CI")
        admin = User.objects.create_user("perf_admin")
        citizen = User.objects.create_user("perf_ciudadano")
        admin.groups.add(group)
        citizen.groups.add(group)
        Ciudadano.objects.create(dni="80000001", nombre="Uno", apellido="PERF")
        Ciudadano.objects.create(dni="80000002", nombre="Dos", apellido="PERF")

        first = Command._build_worker_clients("worker-1", {"backoffice": admin.username, "citizen": citizen.username})
        second = Command._build_worker_clients("worker-2", {"backoffice": admin.username, "citizen": citizen.username})

        first_backoffice = first["backoffice"].session["_auth_user_id"]
        second_backoffice = second["backoffice"].session["_auth_user_id"]
        first_citizen = first["citizen"].session["_auth_user_id"]
        second_citizen = second["citizen"].session["_auth_user_id"]
        self.assertNotEqual(first_backoffice, second_backoffice)
        self.assertNotEqual(first_citizen, second_citizen)
        self.assertEqual(Ciudadano.objects.filter(usuario_id__in=(first_citizen, second_citizen)).count(), 2)

        profile = Profile.objects.get(user_id=first_backoffice)
        profile.backoffice_session_key = "old-run-session"
        profile.save(update_fields=["backoffice_session_key"])
        Command._build_worker_clients("worker-1", {"backoffice": admin.username, "citizen": citizen.username})
        profile.refresh_from_db()
        self.assertIsNone(profile.backoffice_session_key)
