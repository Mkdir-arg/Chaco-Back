"""Listas de revisión de Becas (ola 3): badge de espera, ``next``, clases compiladas, vacíos."""

from urllib.parse import quote

from django.urls import reverse

from programas.models import Formulario, ListaEspera
from programas.tests.test_becas_revision import _BaseRevisionTest


class ListasRevisionTests(_BaseRevisionTest):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def _en_espera(self, formulario, promovido=False):
        return ListaEspera.objects.create(
            formulario=formulario, segmento=formulario.relevamiento.segmento, posicion=1, promovido=promovido
        )

    def _urls(self):
        return {
            "personas": reverse("becas:revision"),
            "casos": reverse("becas:revision_formularios", args=[self.rel_a.pk]),
        }

    def test_badge_lista_de_espera_solo_si_hay_entrada_activa(self):
        for url in self._urls().values():
            self.assertNotContains(self.client.get(url), "Lista de espera")
        self._en_espera(self.form_a)
        for url in self._urls().values():
            self.assertContains(self.client.get(url), "Lista de espera")

    def test_promovido_no_muestra_badge(self):
        self._en_espera(self.form_a, promovido=True)
        for url in self._urls().values():
            self.assertNotContains(self.client.get(url), "Lista de espera")

    def _contar(self, url):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as ctx:
            self.client.get(url)
        return len(ctx)

    def test_consultas_iguales_con_1_y_10_filas(self):
        for nombre, url in self._urls().items():
            self._en_espera(self.form_a)
            self.client.get(url)
            una = self._contar(url)
            for i in range(10):
                f = Formulario.objects.create(relevamiento=self.rel_a, celular=f"36241000{i:02d}")
                self._en_espera(f)
            self.assertEqual(self._contar(url), una, nombre)
            ListaEspera.objects.all().delete()

    def test_links_al_caso_llevan_next(self):
        for url in self._urls().values():
            resp = self.client.get(url, {"estado": "ENVIADO"})
            esperado = f"?next={quote(url + '?estado=ENVIADO', safe='/')}"
            self.assertContains(resp, reverse("becas:formulario_detalle", args=[self.form_a.pk]) + esperado)

    def test_sin_clases_no_compiladas_ni_aria_faltante(self):
        for url in self._urls().values():
            html = self.client.get(url).content.decode()
            self.assertNotIn("focus:ring-brand", html)
            self.assertIn("nodo-icon-btn", html)
            self.assertIn('aria-label="Ver caso de ', html)
            self.assertIn("nodo-thead-row", html)

    def test_estado_vacio_con_y_sin_filtros(self):
        vacio = reverse("becas:revision_formularios", args=[self.rel_b.pk])
        Formulario.objects.filter(relevamiento=self.rel_b).delete()
        sin = self.client.get(vacio)
        self.assertContains(sin, "Sin casos")
        self.assertNotContains(sin, "Ningún caso coincide")
        self.assertNotContains(sin, "Sin formularios")
        con = self.client.get(vacio, {"estado": "APROBADO"})
        self.assertContains(con, "Ningún caso coincide con el filtro")
        self.assertContains(con, "Ningún caso coincide con el filtro")
        con = self.client.get(reverse("becas:revision"), {"estado": "BAJA"})
        self.assertContains(con, "Ningún caso coincide con el filtro")

    def test_renaper_pendientes_next_y_vacio(self):
        url = reverse("becas:renaper_pendientes")
        resp = self.client.get(url)
        self.assertContains(resp, "?next=" + quote(url, safe="/"))
        self.assertNotContains(resp, "px-4 py-[13px]")
        Formulario.objects.all().update(validado_renaper=True)
        self.assertContains(self.client.get(url), "No hay casos pendientes")
        self.assertContains(self.client.get(url, {"fecha": "2001-01-01"}), "coincide con los filtros")
