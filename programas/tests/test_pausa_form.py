from datetime import date

from django.contrib.auth.models import User
from django.urls import reverse

from programas.models import Convocatoria, ProgramaSiis, Relevamiento, Segmento, Subsegmento
from programas.tests.base_becas import BecasPantallaTestCase


class PausaFormEncabezadoTests(BecasPantallaTestCase):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_user("admin-pausa-form", password="x", is_superuser=True)
        self.programa = ProgramaSiis.objects.create(nombre="Programa P", siis_programa_id=9001)
        self.segmento = Segmento.objects.create(nombre="Segmento S", cupo_maximo=10, programa=self.programa)
        self.subsegmento = Subsegmento.objects.create(segmento=self.segmento, nombre="Sub S", cupo_maximo=10)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Convocatoria C",
            segmento=self.segmento,
            subsegmento=self.subsegmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            territorial=self.admin,
            fecha_asignada=date(2026, 8, 7),
            fecha_hasta=date(2026, 8, 8),
            zona="Centro",
        )
        self.client.force_login(self.admin)

    def _casos(self):
        return [
            ("programa", self.programa, "becas:programa_detalle"),
            ("segmento", self.segmento, "becas:segmento_detalle"),
            ("subsegmento", self.subsegmento, "becas:subsegmento_detalle"),
            ("convocatoria", self.convocatoria, "becas:convocatoria_detalle"),
            ("relevamiento", self.relevamiento, "becas:relevamiento_detalle"),
        ]

    def test_get_usa_encabezado_comun_y_cancelar_vuelve_a_la_entidad(self):
        for tipo, objeto, detalle in self._casos():
            with self.subTest(tipo=tipo):
                url_entidad = reverse(detalle, args=[objeto.pk])
                html = self.client.get(reverse("becas:gestionar_pausa", args=[tipo, objeto.pk])).content.decode()
                self.assertIn("<h1", html)
                self.assertIn(f"Pausar · {objeto}", html)
                self.assertRegex(html, r"<title>[^<]*Becas · Pausar")
                self.assertIn('aria-label="Volver a', html)
                self.assertNotIn("history.back", html)
                self.assertIn(f'href="{url_entidad}" class="btn-nodo btn-tertiary btn-base">Cancelar', html)
                self.assertIn('id="motivo" name="motivo" rows="4" required class="nodo-field"', html)
                self.assertNotIn("max-w-3xl", html)

    def test_post_invalido_mantiene_cancelar_hacia_la_entidad(self):
        url = reverse("becas:gestionar_pausa", args=["convocatoria", self.convocatoria.pk])
        html = self.client.post(url, {"accion": "pausar", "motivo": ""}).content.decode()
        self.assertIn(
            f'href="{reverse("becas:convocatoria_detalle", args=[self.convocatoria.pk])}" class="btn-nodo', html
        )
        self.assertNotIn("history.back", html)
