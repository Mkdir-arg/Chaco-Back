"""Contratos del modelo base de Dispositivos y Merenderos (#173).

Las relaciones de **estadía** —`Admision`, `Cama` y sus invariantes— se fueron con
los modelos que las sostenían (MVP v2, release A). Las repone la E1/E2 sobre
`Sector`, `Plaza` y `Estadia`, con sus propios contratos.
"""

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from legajos.models import Ciudadano
from programas.models import Programa


class TipoProgramaDispositivosTests(TestCase):
    def test_incluye_dispositivos_y_merenderos_sin_quitar_choices_existentes(self):
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
        self.assertIn("MERENDEROS", valores)


class ModelosDispositivosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.programa_dispositivos, _ = Programa.objects.get_or_create(
            codigo="DISPOSITIVOS",
            defaults={"nombre": "Dispositivos", "tipo": Programa.TipoPrograma.DISPOSITIVOS},
        )
        cls.programa_merenderos, _ = Programa.objects.get_or_create(
            codigo="MERENDEROS",
            defaults={"nombre": "Merenderos", "tipo": Programa.TipoPrograma.MERENDEROS},
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


class ModelosMerenderosTests(TestCase):
    def test_solicitud_puede_existir_antes_de_crear_el_legajo(self):
        from programas.models import SolicitudMerendero

        solicitud = SolicitudMerendero.objects.create(
            documentacion="merenderos/solicitudes/respaldo.pdf",
        )

        self.assertIsNone(solicitud.merendero)

    def test_solicitud_entrega_y_prestacion_diaria_son_persistibles(self):
        from programas.models import (
            EntregaMercaderia,
            Merendero,
            PrestacionDiaria,
            PrestacionMensual,
            SolicitudMerendero,
        )

        merendero = Merendero.objects.create(
            codigo="MER-001",
            nombre="Rayito de Sol",
            domicilio="Barrio Demo Mz. 1",
            zona="Norte",
            barrio="Demo",
            telefono="3624111111",
            responsable_nombre="Vecina Demo",
            responsable_documento="30123456",
            responsable_email="demo@example.com",
        )
        solicitud = SolicitudMerendero.objects.create(
            merendero=merendero,
            documentacion="merenderos/solicitudes/respaldo.pdf",
        )
        entrega = EntregaMercaderia.objects.create(
            merendero=merendero,
            fecha=timezone.localdate(),
            cantidad_kits=10,
            servicio="Almuerzo",
        )
        prestacion = PrestacionMensual.objects.create(merendero=merendero, anio=2026, mes=7)
        linea = PrestacionDiaria.objects.create(
            prestacion=prestacion,
            dia=1,
            servicio="ALMUERZO",
            raciones=35,
        )

        self.assertTrue(solicitud.documentacion.name.endswith("respaldo.pdf"))
        self.assertEqual(entrega.merendero, merendero)
        self.assertEqual(linea.prestacion, prestacion)
        self.assertEqual(linea.raciones, 35)

    def test_choices_de_estado_coinciden_con_el_analisis(self):
        from programas.models import Merendero, SolicitudMerendero

        self.assertEqual(
            {etiqueta for _valor, etiqueta in Merendero.Estado.choices},
            {"Activo", "Suspendido", "Cerrado"},
        )
        self.assertEqual(
            {etiqueta for _valor, etiqueta in SolicitudMerendero.Estado.choices},
            {"Borrador", "En revisión", "Observada", "Aprobada", "Rechazada"},
        )
