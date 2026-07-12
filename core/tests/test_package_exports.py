from django.test import SimpleTestCase


class CorePackageExportsTests(SimpleTestCase):
    def test_views_forms_and_selectors_packages_export_public_symbols(self):
        from core.api_views import ProvinciaViewSet
        from core.selectors import get_localidades_values, get_municipios_values
        from core.views import (
            inicio_view,
            load_localidad,
            load_municipios,
            performance_dashboard,
        )

        self.assertIsNotNone(ProvinciaViewSet)
        self.assertTrue(callable(get_municipios_values))
        self.assertTrue(callable(get_localidades_values))
        self.assertTrue(callable(inicio_view))
        self.assertTrue(callable(load_municipios))
        self.assertTrue(callable(load_localidad))
        self.assertTrue(callable(performance_dashboard))
