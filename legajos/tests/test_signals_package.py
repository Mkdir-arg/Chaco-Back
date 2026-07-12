from django.test import SimpleTestCase


class LegajosSignalsPackageTests(SimpleTestCase):
    def test_signals_package_exports_receivers(self):
        # Los signals de historial se removieron con SEDRONAR; quedan los vigentes.
        from legajos.signals import invalidate_legajo_cache

        self.assertTrue(callable(invalidate_legajo_cache))
