from django.test import SimpleTestCase

from legajos.views.nachec_dashboard import dashboard_nachec
from legajos.views.nachec_operacion import completar_validacion
from legajos.views.nachec_prestaciones import iniciar_prestacion


class LegajosNachecPackageTests(SimpleTestCase):
    def test_views_nachec_existen(self):
        self.assertTrue(callable(dashboard_nachec))
        self.assertTrue(callable(completar_validacion))
        self.assertTrue(callable(iniciar_prestacion))
