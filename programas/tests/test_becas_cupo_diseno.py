"""Diseño de Cupo y beneficiarios (TIT-6, DE-2, DE-4, CMP-12/15/16/23/24)."""

from datetime import date
from urllib.parse import quote

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.tests.js_harness import atributos_de
from legajos.models import Ciudadano
from programas.models import Convocatoria, Formulario, ListaEspera, Relevamiento, Segmento


class CupoSegmentoDisenoTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin-cupo-diseno", password="x")
        self.segmento = Segmento.objects.create(nombre="Seg Diseño", cupo_maximo=10)
        convocatoria = Convocatoria.objects.create(
            nombre="Conv D", segmento=self.segmento, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )
        relevamiento = Relevamiento.objects.create(
            convocatoria=convocatoria,
            territorial=self.admin,
            fecha_asignada=date(2026, 6, 1),
            zona="A",
            estado=Relevamiento.Estado.FINALIZADO,
        )
        ciudadano = Ciudadano.objects.create(
            dni="80808080", nombre="Luz", apellido="Paz", fecha_nacimiento=date(1990, 1, 1), genero="F"
        )
        self.aprobado = Formulario.objects.create(
            relevamiento=relevamiento,
            ciudadano=ciudadano,
            celular="1",
            email_contacto="a@b.com",
            estado=Formulario.Estado.APROBADO,
        )
        self.url = reverse("becas:cupo_segmento", args=[self.segmento.pk])

    def _html(self, url=None):
        self.client.force_login(self.admin)
        response = self.client.get(url or self.url)
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_encabezado_comun_sin_exportar_ni_ancho_propio(self):
        html = self._html()
        self.assertIn("Cupo y beneficiarios</h1>", html)
        self.assertNotIn("Exportar", html)
        self.assertNotIn("max-w-6xl", html)
        self.assertIn('aria-label="Migas"', html)
        self.assertIn('aria-current="page"', html)
        self.assertIn(f"Volver a {self.segmento.nombre}", html)

    def test_las_acciones_usan_las_piezas_del_sistema(self):
        html = self._html()
        contenido = html[html.index('role="tablist"') : html.index("</main>")]
        self.assertNotIn("onmouseover", contenido)
        self.assertNotIn("<svg", contenido)
        botones = {
            attrs["data-cupo-accion"]: attrs
            for tag, attrs in atributos_de(html)
            if tag == "button" and "data-cupo-accion" in attrs
        }
        self.assertIn("nodo-icon-btn--danger", botones["baja"]["class"])
        self.assertEqual(botones["baja"]["aria-label"], "Dar de baja a Luz Paz")
        self.assertEqual(botones["baja"]["data-nombre"], "Luz Paz")

    def test_tabs_con_contrato_de_accesibilidad_y_tablas_nodo(self):
        html = self._html()
        self.assertIn('role="tablist"', html)
        self.assertEqual(html.count('role="tab"'), 3)
        self.assertEqual(html.count('role="tabpanel"'), 3)
        self.assertIn("nodo-thead-row", html)
        self.assertIn("nodo-th", html)

    def test_links_al_caso_llevan_next(self):
        ListaEspera.objects.create(formulario=self.aprobado, segmento=self.segmento, posicion=1)
        html = self._html(self.url + "?tab=lista_espera")
        next_ = quote("/becas/cupo/segmento/%d/?tab=lista_espera" % self.segmento.pk, safe="/")
        hrefs = [a["href"] for t, a in atributos_de(html) if t == "a" and "/revision/formulario/" in a.get("href", "")]
        self.assertTrue(hrefs)
        for href in hrefs:
            self.assertIn("?next=", href, href)
        self.assertTrue(any(next_ in h for h in hrefs), hrefs)
