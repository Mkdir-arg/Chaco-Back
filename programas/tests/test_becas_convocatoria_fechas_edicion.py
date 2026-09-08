from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from programas.forms import ConvocatoriaForm
from programas.models import Convocatoria, Segmento


class ConvocatoriaFechasEdicionTests(TestCase):
    def setUp(self):
        self.hoy = timezone.localdate()
        self.fecha_inicio = self.hoy - timedelta(days=30)
        self.fecha_fin = self.hoy + timedelta(days=30)
        self.segmento = Segmento.objects.create(
            nombre="Segmento fechas",
            cupo_maximo=100,
        )
        self.convocatoria = Convocatoria.objects.create(
            nombre="Convocatoria fechas",
            segmento=self.segmento,
            fecha_inicio=self.fecha_inicio,
            fecha_fin=self.fecha_fin,
            activo=True,
        )

    def _data(self, **cambios):
        data = {
            "nombre": self.convocatoria.nombre,
            "segmento": self.segmento.pk,
            "subsegmento": "",
            "fecha_inicio": self.convocatoria.fecha_inicio.isoformat(),
            "fecha_fin": self.convocatoria.fecha_fin.isoformat(),
            "descripcion": "",
            "activo": "on",
        }
        data.update(cambios)
        return data

    def test_edicion_renderiza_las_fechas_en_formato_html_date(self):
        form = ConvocatoriaForm(instance=self.convocatoria)

        self.assertIn(f'value="{self.fecha_inicio.isoformat()}"', str(form["fecha_inicio"]))
        self.assertIn(f'value="{self.fecha_fin.isoformat()}"', str(form["fecha_fin"]))

    def test_edicion_permite_cambiar_solo_fecha_fin(self):
        form = ConvocatoriaForm(
            instance=self.convocatoria,
            data=self._data(fecha_inicio="", fecha_fin=(self.fecha_fin + timedelta(days=15)).isoformat()),
        )

        self.assertTrue(form.is_valid(), form.errors)
        convocatoria = form.save()
        self.assertEqual(convocatoria.fecha_inicio, self.fecha_inicio)
        self.assertEqual(convocatoria.fecha_fin, self.fecha_fin + timedelta(days=15))

    def test_edicion_permite_cambiar_solo_fecha_inicio(self):
        form = ConvocatoriaForm(
            instance=self.convocatoria,
            data=self._data(fecha_inicio=(self.fecha_inicio + timedelta(days=10)).isoformat(), fecha_fin=""),
        )

        self.assertTrue(form.is_valid(), form.errors)
        convocatoria = form.save()
        self.assertEqual(convocatoria.fecha_inicio, self.fecha_inicio + timedelta(days=10))
        self.assertEqual(convocatoria.fecha_fin, self.fecha_fin)

    def test_alta_mantiene_ambas_fechas_obligatorias(self):
        form = ConvocatoriaForm(
            data=self._data(fecha_inicio="", fecha_fin=""),
        )

        self.assertFalse(form.is_valid())
        self.assertIn("fecha_inicio", form.errors)
        self.assertIn("fecha_fin", form.errors)
