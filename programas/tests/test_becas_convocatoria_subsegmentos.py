from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from programas.forms import ConvocatoriaForm
from programas.models import Segmento, Subsegmento


class ConvocatoriaSubsegmentosTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("admin-subsegmentos", password="x")
        self.client.force_login(self.user)
        self.segmento_a = Segmento.objects.create(nombre="Segmento A", cupo_maximo=100)
        self.segmento_b = Segmento.objects.create(nombre="Segmento B", cupo_maximo=100)
        self.sub_a_2 = Subsegmento.objects.create(segmento=self.segmento_a, nombre="Subsegmento A2", cupo_maximo=20)
        self.sub_a_1 = Subsegmento.objects.create(segmento=self.segmento_a, nombre="Subsegmento A1", cupo_maximo=20)
        self.sub_b = Subsegmento.objects.create(segmento=self.segmento_b, nombre="Subsegmento B", cupo_maximo=20)

    def _form_data(self, *, segmento, subsegmento):
        return {
            "nombre": "Convocatoria",
            "segmento": segmento.pk,
            "subsegmento": subsegmento.pk,
            "fecha_inicio": date(2026, 8, 1),
            "fecha_fin": date(2026, 8, 31),
            "descripcion": "",
            "activo": False,
        }

    def test_endpoint_devuelve_solo_subsegmentos_del_segmento_ordenados(self):
        response = self.client.get(reverse("becas:segmento_subsegmentos_json", args=[self.segmento_a.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [
                {"id": self.sub_a_1.pk, "nombre": "Subsegmento A1", "cupo_maximo": 20},
                {"id": self.sub_a_2.pk, "nombre": "Subsegmento A2", "cupo_maximo": 20},
            ],
        )

    def test_form_limita_queryset_al_segmento_elegido(self):
        form = ConvocatoriaForm(data=self._form_data(segmento=self.segmento_a, subsegmento=self.sub_a_1))

        self.assertEqual(list(form.fields["subsegmento"].queryset), [self.sub_a_1, self.sub_a_2])
        self.assertTrue(form.is_valid(), form.errors)

    def test_form_rechaza_subsegmento_de_otro_segmento(self):
        form = ConvocatoriaForm(data=self._form_data(segmento=self.segmento_a, subsegmento=self.sub_b))

        self.assertFalse(form.is_valid())
        self.assertIn("subsegmento", form.errors)

    def test_formulario_anuncia_carga_y_error_de_subsegmentos(self):
        response = self.client.get(reverse("becas:convocatoria_crear"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-live="polite"')
        self.assertContains(response, 'role="alert"')
        self.assertContains(response, ':aria-busy="loadingSubsegmentos.toString()"')
