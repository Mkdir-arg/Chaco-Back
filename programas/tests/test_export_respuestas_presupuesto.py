"""Presupuesto del Excel «respuestas por persona» (G2-01, ronda 2 de la revisión).

El export es O(casos) en filas —no hay forma de que no lo sea— pero tiene que ser
**O(1) en consultas por caso** y, sobre todo, no puede volver a pedir la foto de la
definición (`Formulario.definicion`) fila por fila: con 20.000 casos y una foto de
15 KB eso llevó el export de 1,5 s a 14 s contra `mariadb:10.11` (08/10/2026), y
hacer que el motor la mire aunque sea para hashearla cuesta 3 s porque InnoDB tiene
que leer igual las páginas externas.

Estos dos tests son la guarda que impide que vuelva. El presupuesto vive en
`scripts/perf_budgets.json` (sección `servicios`), fuera de `budgets`, que tiene que
coincidir exactamente con el manifiesto de rutas de `scripts/perf_audit.py`.
"""

import json
from datetime import date

from django.conf import settings
from django.db import connection
from django.test import TestCase, tag
from django.test.utils import CaptureQueriesContext

from programas.models import (
    Convocatoria,
    DisenoFormulario,
    Formulario,
    ItemDiseno,
    ProgramaSiis,
    Relevamiento,
    Segmento,
    TipoCampo,
)
from programas.services.dashboard_becas import LOTE_RESPUESTAS, respuestas_por_persona
from programas.services.respuestas import foto_definicion

PRESUPUESTOS = settings.BASE_DIR / "scripts" / "perf_budgets.json"
CLAVE = "becas_respuestas_por_persona"


@tag("performance")
class ExportRespuestasPorPersonaPresupuestoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        programa = ProgramaSiis.objects.create(nombre="Presupuesto export", siis_programa_id=9401)
        segmento = Segmento.objects.create(programa=programa, nombre="Seg", cupo_maximo=9999)
        cls.convocatoria = Convocatoria.objects.create(
            nombre="Conv presupuesto",
            segmento=segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        relevamiento = Relevamiento.objects.create(
            convocatoria=cls.convocatoria,
            tipo=Relevamiento.Tipo.PUBLICO,
            fecha_asignada=date(2026, 1, 2),
            fecha_hasta=date(2026, 12, 30),
            zona="",
            estado=Relevamiento.Estado.EN_CURSO,
        )
        diseno = DisenoFormulario.objects.create(convocatoria=cls.convocatoria, version=1)
        grupo = ItemDiseno.objects.create(diseno=diseno, tipo=ItemDiseno.Tipo.GRUPO, clave="g-1", orden=0)
        ItemDiseno.objects.create(
            diseno=diseno,
            tipo=ItemDiseno.Tipo.CAMPO,
            clave="cp-presup01",
            padre=grupo,
            orden=1,
            propio={"texto": "Campo propio", "tipo": TipoCampo.SELECTOR, "opciones": ["Sí", "No"]},
        )
        foto = foto_definicion(relevamiento)
        Formulario.objects.bulk_create(
            Formulario(
                relevamiento=relevamiento,
                numero=n + 1,
                estado=Formulario.Estado.ENVIADO,
                celular="3624000000",
                datos_identificacion={"dni": str(30000000 + n), "nombre": "N", "apellido": "A"},
                data={"globales": {}, "requisitos": {}},
                respuestas={"cp-presup01": "Sí" if n % 2 else "No"},
                definicion=foto,
            )
            for n in range(60)
        )

    def _presupuesto(self):
        return json.loads(PRESUPUESTOS.read_text(encoding="utf-8"))["servicios"][CLAVE]

    def test_las_consultas_no_crecen_con_cada_caso(self):
        presupuesto = self._presupuesto()
        casos = Formulario.objects.filter(relevamiento__convocatoria=self.convocatoria).count()
        techo = presupuesto["consultas_fijas"] + -(-casos // presupuesto["casos_por_consulta"])

        with CaptureQueriesContext(connection) as capturadas:
            reporte, _alcance = respuestas_por_persona(self.convocatoria)

        self.assertEqual(len(reporte.filas), casos)
        self.assertLessEqual(
            len(capturadas),
            techo,
            f"{len(capturadas)} consultas para {casos} casos; el presupuesto de «{CLAVE}» en "
            f"scripts/perf_budgets.json es {techo}. Subirlo exige justificarlo en el mismo PR.",
        )
        self.assertEqual(presupuesto["casos_por_consulta"], LOTE_RESPUESTAS)

    def test_la_foto_de_la_definicion_no_viaja_por_fila(self):
        """El MAJOR de la ronda 2: `values_list("pk", "respuestas", "definicion")`.

        La foto es **la misma** para todos los casos que respondieron el mismo diseño y
        pesa 15 KB: ninguna consulta sobre `programas_formulario` puede nombrarla.
        """
        with CaptureQueriesContext(connection) as capturadas:
            respuestas_por_persona(self.convocatoria)

        culpables = [q["sql"] for q in capturadas if "programas_formulario" in q["sql"] and "definicion" in q["sql"]]

        self.assertEqual(
            culpables,
            [],
            "la foto volvió a leerse por fila: con 20.000 casos eso son 12 s de export "
            "(mariadb:10.11, 08/10/2026). Ni siquiera hashearla sirve: InnoDB lee igual las páginas externas.",
        )
