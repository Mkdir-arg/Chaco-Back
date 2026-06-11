from django.test import SimpleTestCase

# El paquete legajos.views no reexporta símbolos a propósito (evita forzar imports
# de módulos legacy); las vistas se consumen desde su módulo canónico.
from legajos.views.programas import ProgramaDetailView, ProgramaListView


class LegajosProgramasPackageTests(SimpleTestCase):
    def test_views_de_programas_son_cbv(self):
        self.assertTrue(hasattr(ProgramaListView, "as_view"))
        self.assertTrue(hasattr(ProgramaDetailView, "as_view"))
