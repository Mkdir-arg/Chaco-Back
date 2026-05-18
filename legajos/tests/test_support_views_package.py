import importlib

from django.test import SimpleTestCase


class LegajosSupportViewsPackageTests(SimpleTestCase):
    def test_view_cursos_legacy_retirada(self):
        with self.assertRaises(ModuleNotFoundError):
            importlib.import_module("legajos.views.cursos")
