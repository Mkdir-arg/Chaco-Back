from datetime import date, timedelta

from django.test import TestCase

from legajos.models import Ciudadano
from legajos.selectors.ciudadanos import _build_ciudadanos_dashboard_metrics
from programas.models import InscripcionPrograma, Programa


class CiudadanosDashboardMetricsTests(TestCase):
    def test_consolida_metricas_de_inscripciones_sin_cambiar_valores(self):
        ciudadano = Ciudadano.objects.create(dni="39000200", nombre="Ana", apellido="Métricas")
        inscripciones = []
        for indice, estado in enumerate(
            [
                InscripcionPrograma.Estado.ACTIVO,
                InscripcionPrograma.Estado.EN_SEGUIMIENTO,
                InscripcionPrograma.Estado.CERRADO,
            ]
        ):
            programa = Programa.objects.create(codigo=f"METRICAS-{indice}", nombre=f"Métricas {indice}")
            inscripciones.append(
                InscripcionPrograma.objects.create(ciudadano=ciudadano, programa=programa, estado=estado)
            )

        InscripcionPrograma.objects.filter(pk=inscripciones[1].pk).update(fecha_inscripcion=date.today() - timedelta(1))

        with self.assertNumQueries(3):
            metricas = _build_ciudadanos_dashboard_metrics(total_ciudadanos=17)

        self.assertEqual(
            metricas,
            {
                "total_ciudadanos": 17,
                "legajos_activos": 2,
                "alertas_criticas": 0,
                "seguimientos_hoy": 2,
                "tasa_adherencia": 67,
                "casos_alto_riesgo": 0,
            },
        )

    def test_sin_inscripciones_la_tasa_de_adherencia_es_cero(self):
        metricas = _build_ciudadanos_dashboard_metrics(total_ciudadanos=0)

        self.assertEqual(metricas["legajos_activos"], 0)
        self.assertEqual(metricas["seguimientos_hoy"], 0)
        self.assertEqual(metricas["tasa_adherencia"], 0)
