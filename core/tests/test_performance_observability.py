import json
from io import StringIO

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.db import connection
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from config.middlewares.query_counter import QueryCountMiddleware
from conversaciones.context_processors import user_groups
from core import rbac


class PerformanceObservabilityTests(TestCase):
    def setUp(self):
        QueryCountMiddleware.session_stats = None
        self.admin = User.objects.create_superuser("performance-admin", "performance@example.test", "test-password")
        self.client.force_login(self.admin)

    def test_performance_api_reports_unavailable_metrics_before_any_instrumented_request(self):
        response = self.client.get(reverse("core:performance_api"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["metrics"]["queries"]["source"], "unavailable")
        self.assertEqual(response.json()["metrics"]["memory"]["source"], "psutil")

    def test_authenticated_user_without_performance_access_is_rejected(self):
        self.client.force_login(User.objects.create_user("regular-user", password="test-password"))

        response = self.client.get(reverse("core:performance_api"))

        self.assertEqual(response.status_code, 403)

    def test_dashboard_explains_when_query_metrics_are_not_measured(self):
        response = self.client.get(reverse("core:performance_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Métricas de consultas no disponibles")

    def test_query_analysis_does_not_report_an_empty_debug_buffer_as_measurement(self):
        response = self.client.get(reverse("core:query_analysis_api"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["metrics"]["queries"]["source"], "unavailable")
        self.assertIsNone(response.json()["query_count"])

    def test_system_metrics_identify_sources_for_dashboard_values(self):
        response = self.client.get(reverse("core:system_metrics_api"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["sources"]["cpu"]["source"], "psutil")
        self.assertEqual(response.json()["sources"]["database_connections"]["source"], "unavailable")


class QueryCountMiddlewareTests(TestCase):
    def setUp(self):
        QueryCountMiddleware.session_stats = None

    @override_settings(DEBUG=False)
    def test_records_real_database_queries_without_debug(self):
        user = User.objects.create_user("observability-user", password="test-password")

        def get_response(_request):
            User.objects.get(pk=user.pk)
            return HttpResponse("ok")

        response = QueryCountMiddleware(get_response)(RequestFactory().get("/observability-test/"))

        self.assertEqual(response.status_code, 200)
        stats = QueryCountMiddleware.get_session_stats()
        self.assertEqual(stats["metrics_source"], "measured")
        self.assertEqual(stats["total_requests"], 1)
        self.assertGreaterEqual(stats["total_queries"], 1)

    def test_excludes_observability_routes_from_measurement(self):
        response = QueryCountMiddleware(lambda _request: HttpResponse("ok"))(
            RequestFactory().get(reverse("core:performance_api"))
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(QueryCountMiddleware.get_session_stats()["metrics_source"], "unavailable")


class QueryObservabilityIntegrationTests(TestCase):
    def setUp(self):
        QueryCountMiddleware.session_stats = None
        self.admin = User.objects.create_superuser("instrumented-admin", "instrumented@example.test", "test-password")
        self.client.force_login(self.admin)

    @override_settings(MIDDLEWARE=[*settings.MIDDLEWARE, "config.middlewares.query_counter.QueryCountMiddleware"])
    def test_api_exposes_measured_queries_after_an_instrumented_request(self):
        def get_response(_request):
            User.objects.count()
            return HttpResponse("ok")

        QueryCountMiddleware(get_response)(RequestFactory().get("/inicio/"))

        response = self.client.get(reverse("core:performance_api"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["metrics"]["queries"]["source"], "measured")
        self.assertGreaterEqual(response.json()["total_requests"], 1)

    @override_settings(DEBUG=False)
    def test_api_uses_instrumented_aggregate_when_debug_is_disabled(self):
        QueryCountMiddleware.session_stats = {
            "total_requests": 2,
            "total_queries": 12,
            "slow_requests": 0,
            "slow_queries_count": 1,
            "n1_affected_requests": 1,
            "metrics_source": "measured",
            "last_reset": timezone.now(),
        }

        response = self.client.get(reverse("core:performance_api"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total_queries"], 12)
        self.assertEqual(response.json()["n1_affected_requests"], 1)
        self.assertEqual(response.json()["slow_queries"], None)
        self.assertEqual(response.json()["metrics"]["queries"]["details_source"], "unavailable")


class AnalyzePerformanceCommandTests(TestCase):
    def setUp(self):
        QueryCountMiddleware.session_stats = None

    def test_json_report_marks_query_metrics_unavailable_without_instrumented_activity(self):
        output = StringIO()

        call_command("analyze_performance", "--output", "json", stdout=output)

        report = json.loads(output.getvalue())
        self.assertEqual(report["metrics"]["queries"]["source"], "unavailable")
        self.assertIsNone(report["total_queries"])
        self.assertIsNone(report["performance_score"])

    @override_settings(DEBUG=False)
    def test_json_report_uses_measured_aggregate_when_debug_is_disabled(self):
        QueryCountMiddleware.session_stats = {
            "total_requests": 2,
            "total_queries": 12,
            "slow_requests": 0,
            "slow_queries_count": 1,
            "n1_affected_requests": 1,
            "metrics_source": "measured",
            "last_reset": timezone.now(),
        }
        output = StringIO()

        call_command("analyze_performance", "--output", "json", stdout=output)

        report = json.loads(output.getvalue())
        self.assertEqual(report["total_queries"], 12)
        self.assertEqual(report["n1_affected_requests"], 1)
        self.assertIsNone(report["slow_queries"])


class GroupLookupReuseTests(TestCase):
    def test_portal_identity_and_template_context_share_one_group_lookup(self):
        group = Group.objects.create(name="Operadores")
        user = User.objects.create_superuser("grouped-user", "grouped@example.test", "test-password")
        user.groups.add(group)
        user = User.objects.get(pk=user.pk)
        request = RequestFactory().get("/inicio/")
        request.user = user

        with CaptureQueriesContext(connection) as queries:
            self.assertFalse(rbac.es_ciudadano_portal(user))
            context = user_groups(request)

        self.assertEqual(context["user_groups_list"], ["Operadores"])
        self.assertEqual(len(queries), 1)
