from django.test import SimpleTestCase


class ConfiguracionPackageExportsTests(SimpleTestCase):
    def test_views_package_exports_public_symbols(self):
        from configuracion.views import (
            ProvinciaListView,
        )

        self.assertIsNotNone(ProvinciaListView)

    def test_forms_services_and_selectors_packages_export_public_symbols(self):
        from configuracion.forms import ProvinciaForm
        from configuracion.selectors import build_institucion_detail_context

        self.assertIsNotNone(ProvinciaForm)
        self.assertTrue(callable(build_institucion_detail_context))
