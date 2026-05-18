import importlib

from django.test import SimpleTestCase


class LegajosInstitucionalPackageTests(SimpleTestCase):
    def test_views_institucionales_legacy_retiradas(self):
        with self.assertRaises(ModuleNotFoundError):
            importlib.import_module("legajos.views.institucional")
