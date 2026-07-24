from datetime import date

from django.test import TestCase

from programas.forms import ConvocatoriaForm
from programas.models import Convocatoria, Segmento


class ConvocatoriaFechasEdicionTests(TestCase):
    def setUp(self):
        self.segmento = Segmento.objects.create(
            nombre="Segmento fechas",
            cupo_maximo=100,
        )
        self.convocatoria = Convocatoria.objects.create(
            nombre="Convocatoria fechas",
            segmento=self.segmento,
            fecha_inicio=date(2026, 7, 1),
            fecha_fin=date(2026, 7, 31),
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

        self.assertIn('value="2026-07-01"', str(form["fecha_inicio"]))
        self.assertIn('value="2026-07-31"', str(form["fecha_fin"]))

    def test_edicion_permite_cambiar_solo_fecha_fin(self):
        form = ConvocatoriaForm(
            instance=self.convocatoria,
            data=self._data(fecha_inicio="", fecha_fin="2026-08-15"),
        )

        self.assertTrue(form.is_valid(), form.errors)
        convocatoria = form.save()
        self.assertEqual(convocatoria.fecha_inicio, date(2026, 7, 1))
        self.assertEqual(convocatoria.fecha_fin, date(2026, 8, 15))

    def test_edicion_permite_cambiar_solo_fecha_inicio(self):
        form = ConvocatoriaForm(
            instance=self.convocatoria,
            data=self._data(fecha_inicio="2026-07-10", fecha_fin=""),
        )

        self.assertTrue(form.is_valid(), form.errors)
        convocatoria = form.save()
        self.assertEqual(convocatoria.fecha_inicio, date(2026, 7, 10))
        self.assertEqual(convocatoria.fecha_fin, date(2026, 7, 31))

    def test_alta_mantiene_ambas_fechas_obligatorias(self):
        form = ConvocatoriaForm(
            data=self._data(fecha_inicio="", fecha_fin=""),
        )

        self.assertFalse(form.is_valid())
        self.assertIn("fecha_inicio", form.errors)
        self.assertIn("fecha_fin", form.errors)
