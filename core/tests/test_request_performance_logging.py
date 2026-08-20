from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from core.middleware import RequestLoggingMiddleware


class RequestPerformanceLoggingTests(SimpleTestCase):
    @override_settings(SLOW_REQUEST_MS=3000)
    @patch("core.middleware.time.monotonic", side_effect=[100.0, 103.001])
    def test_slow_request_is_logged_as_warning(self, _monotonic):
        request = RequestFactory().get("/ruta-lenta/")
        request.user = AnonymousUser()
        middleware = RequestLoggingMiddleware(lambda _request: HttpResponse(status=200))

        with self.assertLogs("core.requests", level="WARNING") as captured:
            middleware(request)

        self.assertIn("GET /ruta-lenta/ user=anon", captured.output[0])
        self.assertIn("status=200 duration=3001ms", captured.output[0])

    @override_settings(SLOW_REQUEST_MS=3000)
    @patch("core.middleware.time.monotonic", side_effect=[100.0, 103.0])
    def test_request_at_threshold_remains_info(self, _monotonic):
        request = RequestFactory().get("/ruta-en-umbral/")
        request.user = AnonymousUser()
        middleware = RequestLoggingMiddleware(lambda _request: HttpResponse(status=200))

        with self.assertLogs("core.requests", level="INFO") as captured:
            middleware(request)

        self.assertTrue(captured.output[0].startswith("INFO:core.requests:"))
        self.assertIn("duration=3000ms", captured.output[0])
