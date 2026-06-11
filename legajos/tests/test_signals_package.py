from django.test import SimpleTestCase


class LegajosSignalsPackageTests(SimpleTestCase):
    def test_signals_package_exports_receivers(self):
        # Los signals de historial se removieron con SEDRONAR; quedan los vigentes.
        from legajos.signals import (
            crear_caso_nachec_desde_derivacion,
            invalidate_ciudadano_cache,
        )

        self.assertTrue(callable(crear_caso_nachec_desde_derivacion))
        self.assertTrue(callable(invalidate_ciudadano_cache))
