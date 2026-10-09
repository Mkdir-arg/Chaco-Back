from importlib import import_module

from django.test import SimpleTestCase


class DashboardPackageExportsTests(SimpleTestCase):
    def test_api_views_and_signals_packages_are_importable(self):
        # RED-78: acá también se importaba `dashboard.views.DashboardView`. Esa vista
        # era una copia vieja del inicio del backoffice que el orden de `config/urls.py`
        # dejaba tapada; se borró con su template y su `path`. Lo que queda de la app
        # son las cinco APIs y las señales de cache.
        from dashboard.api_views import metricas_dashboard

        self.assertTrue(callable(metricas_dashboard))
        self.assertIsNotNone(import_module("dashboard.signals"))
