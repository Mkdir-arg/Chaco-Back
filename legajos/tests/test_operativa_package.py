import importlib

from django.test import SimpleTestCase


class LegajosOperativaPackageTests(SimpleTestCase):
    def test_views_operativas_legacy_retiradas(self):
        with self.assertRaises(ModuleNotFoundError):
            importlib.import_module("legajos.views.operativa")
