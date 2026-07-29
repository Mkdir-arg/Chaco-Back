from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from programas.models import Admision, Dispositivo, EntregaMercaderia, Merendero
from programas.services.indicadores import indicadores_dispositivo


class SeedAceptacionReportesTests(TestCase):
    def test_es_idempotente_y_prepara_los_escenarios_de_reportes(self):
        salida = StringIO()

        call_command("seed_aceptacion_reportes", stdout=salida)
        call_command("seed_aceptacion_reportes", stdout=salida)

        dispositivo = Dispositivo.objects.get(codigo="ACEP-183-DIS")
        self.assertEqual(Dispositivo.objects.filter(codigo="ACEP-183-DIS").count(), 1)
        self.assertEqual(Merendero.objects.filter(codigo="ACEP-183-MER").count(), 1)
        self.assertEqual(EntregaMercaderia.objects.filter(merendero__codigo="ACEP-183-MER").count(), 1)
        self.assertEqual(Admision.objects.filter(dispositivo=dispositivo, estado=Admision.Estado.ALOJADO).count(), 1)
        self.assertEqual(indicadores_dispositivo(dispositivo)["ocupacion"]["porcentaje"], 50)
