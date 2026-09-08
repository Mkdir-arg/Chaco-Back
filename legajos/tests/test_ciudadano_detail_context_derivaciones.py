from datetime import timedelta

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from legajos.models import Ciudadano
from legajos.selectors.ciudadanos import build_ciudadano_detail_context
from programas.models import DerivacionPrograma, Programa


class CiudadanoDetailContextDerivacionesTests(TestCase):
    def test_conserva_derivaciones_y_limita_linea_de_tiempo_sin_n_plus_one(self):
        ciudadano = Ciudadano.objects.create(dni="39000201", nombre="Ana", apellido="Derivaciones")
        derivaciones = []
        for indice in range(12):
            programa = Programa.objects.create(
                codigo=f"DERIVACION-{indice}",
                nombre=f"Programa destino {indice}",
            )
            derivaciones.append(
                DerivacionPrograma.objects.create(
                    ciudadano=ciudadano,
                    programa_destino=programa,
                    motivo=f"Motivo {indice}",
                    estado=DerivacionPrograma.Estado.PENDIENTE,
                )
            )
            DerivacionPrograma.objects.filter(pk=derivaciones[-1].pk).update(
                creado=timezone.now() + timedelta(minutes=indice)
            )

        with CaptureQueriesContext(connection) as queries:
            context = build_ciudadano_detail_context(ciudadano)

        derivaciones_esperadas = list(reversed(derivaciones))
        self.assertEqual(context["derivaciones_ciudadano"], derivaciones_esperadas)
        self.assertEqual(len(context["derivaciones_ciudadano"]), 12)

        derivaciones_en_linea = [entrada for entrada in context["linea_tiempo"] if entrada["icono"] == "share-nodes"]
        self.assertEqual(len(derivaciones_en_linea), 10)
        self.assertEqual(
            [entrada["titulo"] for entrada in derivaciones_en_linea],
            [f"Derivación a {deriv.programa_destino.nombre}" for deriv in derivaciones_esperadas[:10]],
        )
        self.assertEqual(
            [(entrada["descripcion"], entrada["color_hex"]) for entrada in derivaciones_en_linea],
            [("Pendiente", "#F97316")] * 10,
        )

        consultas_programa_destino = [
            query["sql"] for query in queries.captured_queries if 'FROM "programas_programa"' in query["sql"]
        ]
        self.assertEqual(consultas_programa_destino, [])

    def test_sin_derivaciones_no_agrega_entradas_a_la_linea_de_tiempo(self):
        ciudadano = Ciudadano.objects.create(dni="39000202", nombre="Bruno", apellido="Sin derivaciones")

        context = build_ciudadano_detail_context(ciudadano)

        self.assertEqual(context["derivaciones_ciudadano"], [])
        self.assertFalse(any(entrada["icono"] == "share-nodes" for entrada in context["linea_tiempo"]))
