from django.test import SimpleTestCase

from legajos.views.solapas import (
    CiudadanoDetalleConSolapasView,
    ciudadano_detalle_con_solapas,
    derivar_a_programa,
)


class LegajosSolapasPackageTests(SimpleTestCase):
    def test_views_de_solapas_existen(self):
        self.assertTrue(hasattr(CiudadanoDetalleConSolapasView, "as_view"))
        self.assertTrue(callable(ciudadano_detalle_con_solapas))
        self.assertTrue(callable(derivar_a_programa))
