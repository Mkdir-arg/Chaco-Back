"""Un territorial con varios segmentos: alta y reasignación de relevamientos.

Las filas múltiples se crean directo en el ORM: en este PR el ABM todavía ofrece un
solo segmento, así que en producción nadie las crea con este código solo.
"""

from datetime import date

from django.contrib.auth.models import Group, User
from django.urls import reverse

from programas.forms import RelevamientoForm
from programas.management.commands.seed_becas import ROL_TERRITORIAL
from programas.models import AsignacionTerritorial, Convocatoria, Segmento
from programas.services.autorizacion import (
    segmento_dueno_id,
    segmentos_duenos_en_lote,
    usuarios_territoriales_becas,
)
from programas.tests.test_becas_relevamientos import _BaseRelevTest


class TerritorialConVariosSegmentosTests(_BaseRelevTest):
    def setUp(self):
        super().setUp()
        self.seg_c = Segmento.objects.create(nombre="Segmento C", cupo_maximo=100)
        self.conv_c = Convocatoria.objects.create(
            nombre="Conv C", segmento=self.seg_c, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )
        # `self.territorial` ya tiene A; se le suma B (A es el dueño: la más antigua).
        AsignacionTerritorial.objects.create(segmento=self.seg_b, territorial=self.territorial)

    def _form(self, convocatoria):
        return RelevamientoForm(
            {
                "convocatoria": convocatoria.pk,
                "territorial": self.territorial.pk,
                "fecha_asignada": "2026-07-01",
                "municipio": self.municipio.pk,
                "zona": self.localidad.pk,
            }
        )

    def test_se_acepta_en_las_convocatorias_de_sus_dos_segmentos_y_se_rechaza_en_la_tercera(self):
        self.assertTrue(self._form(self.conv_a).is_valid())
        self.assertTrue(self._form(self.conv_b).is_valid())
        rechazado = self._form(self.conv_c)
        self.assertFalse(rechazado.is_valid())
        self.assertIn("territorial", rechazado.errors)

    def test_reasignar_lo_ofrece_en_los_dos_segmentos_y_no_en_el_tercero(self):
        self.assertIn(self.territorial, usuarios_territoriales_becas(segmento=self.seg_a))
        self.assertIn(self.territorial, usuarios_territoriales_becas(segmento=self.seg_b))
        self.assertNotIn(self.territorial, usuarios_territoriales_becas(segmento=self.seg_c))
        self.assertEqual(usuarios_territoriales_becas(segmento=self.seg_b).filter(pk=self.territorial.pk).count(), 1)

    def test_reasignar_por_la_vista_en_el_segmento_secundario(self):
        self.client.force_login(self.admin)
        otro = User.objects.create_user("terri_otro", password="x")
        otro.groups.add(Group.objects.get(name=ROL_TERRITORIAL))
        AsignacionTerritorial.objects.create(segmento=self.seg_b, territorial=otro)
        resp = self.client.post(reverse("becas:relevamiento_reasignar", args=[self.rel_b.pk]), {"territorial": otro.pk})
        self.assertEqual(resp.status_code, 302)
        self.rel_b.refresh_from_db()
        self.assertEqual(self.rel_b.territorial, otro)

    def test_data_segmentos_trae_los_dos_ids(self):
        html = str(RelevamientoForm()["territorial"])
        self.assertIn(f'data-segmentos="{self.seg_a.pk} {self.seg_b.pk}"', html)
        self.assertNotIn("data-segmento=", html)
        self.assertIn(f'data-segmento="{self.seg_a.pk}"', str(RelevamientoForm()["convocatoria"]))

    def test_dueno_es_la_asignacion_mas_antigua(self):
        self.assertEqual(segmento_dueno_id(self.territorial), self.seg_a.pk)
        self.assertEqual(segmentos_duenos_en_lote([self.territorial.pk])[self.territorial.pk], self.seg_a.pk)
        AsignacionTerritorial.objects.filter(segmento=self.seg_a, territorial=self.territorial).delete()
        self.assertEqual(segmento_dueno_id(self.territorial), self.seg_b.pk)
        self.assertIsNone(segmento_dueno_id(User.objects.create_user("sin_seg", password="x")))
