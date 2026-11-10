"""Contratos del modelo base de Dispositivos (#173).

Las relaciones de **estadía** y sus invariantes de la versión 1 se fueron con
los modelos que las sostenían (MVP v2, release A). Las repone la E1/E2 sobre
`Sector`, `Plaza` y `Estadia`, con sus propios contratos.
"""

from django.db import IntegrityError, transaction
from django.test import TestCase

from legajos.models import Ciudadano
from programas.models import Programa


class TipoProgramaDispositivosTests(TestCase):
    def test_incluye_dispositivos_sin_quitar_choices_existentes(self):
        valores_originales = {
            "ACOMPANAMIENTO_SOCIAL",
            "ECONOMICO",
            "FAMILIAR",
            "REDUCCION_DANOS",
            "REINSERCION_SOCIAL",
            "CAPACITACION_COMUNITARIA",
            "BECAS",
        }

        valores = {valor for valor, _etiqueta in Programa.TipoPrograma.choices}

        self.assertTrue(valores_originales.issubset(valores))
        self.assertIn("DISPOSITIVOS", valores)
        self.assertNotIn("MERENDEROS", valores)


class ModelosDispositivosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.programa_dispositivos, _ = Programa.objects.get_or_create(
            codigo="DISPOSITIVOS",
            defaults={"nombre": "Dispositivos", "tipo": Programa.TipoPrograma.DISPOSITIVOS},
        )

    def test_choices_de_estado_coinciden_con_el_analisis(self):
        from programas.models import Dispositivo

        self.assertEqual(
            {etiqueta for _valor, etiqueta in Dispositivo.Estado.choices},
            {"Borrador", "Pendiente de validación", "Activo", "Observado", "Rechazado", "Inactivo", "Cerrado"},
        )

    def test_membresia_conserva_unicidad_por_ciudadano_y_programa(self):
        from programas.models import InscripcionPrograma

        ciudadano = Ciudadano.objects.create(dni="30111222", nombre="Ana", apellido="Demo")
        InscripcionPrograma.objects.create(ciudadano=ciudadano, programa=self.programa_dispositivos)

        with self.assertRaises(IntegrityError), transaction.atomic():
            InscripcionPrograma.objects.create(ciudadano=ciudadano, programa=self.programa_dispositivos)
