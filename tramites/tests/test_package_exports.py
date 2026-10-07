"""`tramites` es un stub: está en `INSTALLED_APPS` y no hace nada.

TST-02. El único test del módulo era `self.assertTrue(True)`. Lo que hay que
sostener mientras la app siga instalada es que sigue siendo un stub: sin modelos
(y por lo tanto sin tablas ni migraciones) y sin rutas. La app entera se borra en
OPS-14 (Ola 7); hasta entonces, esto impide que alguien le cuelgue un modelo y se
estrene una tabla en producción sin que nadie lo decida.
"""

from django.apps import apps
from django.test import SimpleTestCase

import tramites.urls


class TramitesSigueSiendoUnStubTests(SimpleTestCase):
    def test_no_tiene_modelos(self):
        """Un modelo acá sería una tabla nueva en PRD por una app que nadie usa."""
        self.assertEqual(list(apps.get_app_config("tramites").get_models()), [])

    def test_no_expone_ninguna_ruta(self):
        self.assertEqual(tramites.urls.urlpatterns, [])

    def test_su_urlconf_no_esta_montado_en_el_proyecto(self):
        """Ni siquiera está incluido: `config/urls.py` no lo nombra (OPS-14)."""
        from django.urls import NoReverseMatch, reverse

        with self.assertRaises(NoReverseMatch):
            reverse("tramites:cualquier-cosa")
