from io import StringIO
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import TestCase

from programas.management.commands.seed_aceptacion_reportes import _es_base_aceptacion
from programas.models import Admision, Dispositivo, EntregaMercaderia, Merendero
from programas.services.indicadores import indicadores_dispositivo


class SeedAceptacionReportesTests(TestCase):
    def test_requiere_habilitacion_explicita_del_entorno_de_aceptacion(self):
        with patch.dict("os.environ", {"CHACO_ACCEPTANCE_SEED": "1"}, clear=True):
            with self.assertRaisesMessage(CommandError, "entorno de aceptación aislado"):
                call_command("seed_aceptacion_reportes")

    @patch("programas.management.commands.seed_aceptacion_reportes.connection")
    def test_verifica_la_base_mysql_de_aceptacion(self, conexion):
        conexion.vendor = "mysql"
        cursor = conexion.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = ("chaco_acceptance",)

        self.assertTrue(_es_base_aceptacion())
        cursor.execute.assert_called_once_with("SELECT DATABASE()")

        cursor.fetchone.return_value = ("chaco",)
        self.assertFalse(_es_base_aceptacion())

    def test_es_idempotente_y_prepara_los_escenarios_de_reportes(self):
        salida = StringIO()

        with patch.dict("os.environ", {"CHACO_ACCEPTANCE_SEED": "1"}):
            with patch("programas.management.commands.seed_aceptacion_reportes._es_base_aceptacion", return_value=True):
                call_command("seed_aceptacion_reportes", stdout=salida)
                call_command("seed_aceptacion_reportes", stdout=salida)

        dispositivo = Dispositivo.objects.get(codigo="ACEP-183-DIS")
        self.assertEqual(Dispositivo.objects.filter(codigo="ACEP-183-DIS").count(), 1)
        self.assertEqual(Merendero.objects.filter(codigo="ACEP-183-MER").count(), 1)
        self.assertEqual(EntregaMercaderia.objects.filter(merendero__codigo="ACEP-183-MER").count(), 1)
        self.assertEqual(Admision.objects.filter(dispositivo=dispositivo, estado=Admision.Estado.ALOJADO).count(), 1)
        self.assertEqual(indicadores_dispositivo(dispositivo)["ocupacion"]["porcentaje"], 50)
