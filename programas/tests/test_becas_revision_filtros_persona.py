"""Filtros por persona (nombre, apellido, DNI, fecha de nacimiento) de ``/becas/revision/``."""

from datetime import date

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from legajos.models import Ciudadano
from programas.models import Formulario
from programas.tests.test_becas_revision import _BaseRevisionTest


class FiltrosPersonaRevisionTests(_BaseRevisionTest):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)
        self.url = reverse("becas:revision")
        self.ana = Ciudadano.objects.create(
            dni="30123456", nombre="Ana", apellido="Gomez", fecha_nacimiento=date(1990, 5, 17)
        )
        self.luis = Ciudadano.objects.create(
            dni="28111222", nombre="Luis", apellido="Gonzalez", fecha_nacimiento=date(1985, 1, 2)
        )
        self.form_ana = Formulario.objects.create(relevamiento=self.rel_a, celular="1", ciudadano=self.ana)
        self.form_luis = Formulario.objects.create(relevamiento=self.rel_a, celular="2", ciudadano=self.luis)

    def _pks(self, **params):
        resp = self.client.get(self.url, params)
        self.assertEqual(resp.status_code, 200)
        return {f.pk for f in resp.context["formularios"]}

    def test_sin_filtros_trae_todos(self):
        self.assertEqual(self._pks(), {self.form_a.pk, self.form_b.pk, self.form_ana.pk, self.form_luis.pk})

    def test_por_dni_exacto_y_con_puntos(self):
        self.assertEqual(self._pks(dni="30123456"), {self.form_ana.pk})
        self.assertEqual(self._pks(dni="30.123.456"), {self.form_ana.pk})
        self.assertEqual(self._pks(dni=" 30-123 456 "), {self.form_ana.pk})
        self.assertEqual(self._pks(dni="3012345"), set())

    def test_por_apellido_empieza_con_sin_importar_mayusculas(self):
        self.assertEqual(self._pks(apellido="go"), {self.form_ana.pk, self.form_luis.pk})
        self.assertEqual(self._pks(apellido="GONZ"), {self.form_luis.pk})
        self.assertEqual(self._pks(apellido="onzalez"), set())

    def test_por_nombre_empieza_con(self):
        self.assertEqual(self._pks(nombre="an"), {self.form_ana.pk})
        self.assertEqual(self._pks(nombre="na"), set())

    def test_por_fecha_de_nacimiento(self):
        self.assertEqual(self._pks(fecha_nacimiento="1990-05-17"), {self.form_ana.pk})
        self.assertEqual(self._pks(fecha_nacimiento="1990-05-18"), set())

    def test_fecha_invalida_se_ignora(self):
        resp = self.client.get(self.url, {"fecha_nacimiento": "no-es-fecha"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context["formularios"]), 4)
        self.assertNotContains(resp, 'value="no-es-fecha"')

    def test_combinados_entre_si_y_con_estado(self):
        self.assertEqual(self._pks(apellido="go", nombre="luis"), {self.form_luis.pk})
        self.assertEqual(self._pks(apellido="go", fecha_nacimiento="1990-05-17"), {self.form_ana.pk})
        self.assertEqual(self._pks(apellido="go", dni="28111222", nombre="ana"), set())
        Formulario.objects.filter(pk=self.form_ana.pk).update(estado=Formulario.Estado.APROBADO)
        self.assertEqual(self._pks(apellido="go", estado=Formulario.Estado.APROBADO), {self.form_ana.pk})
        self.assertEqual(self._pks(apellido="go", estado=Formulario.Estado.RECHAZADO), set())

    def test_el_formulario_conserva_los_valores(self):
        resp = self.client.get(
            self.url, {"nombre": "an", "apellido": "go", "dni": "30.123.456", "fecha_nacimiento": "1990-05-17"}
        )
        for esperado in (
            'name="nombre" value="an"',
            'name="apellido" value="go"',
            'name="dni" value="30.123.456"',
            'name="fecha_nacimiento" value="1990-05-17"',
        ):
            self.assertContains(resp, esperado)

    def test_se_conservan_al_paginar(self):
        for i in range(30):
            c = Ciudadano.objects.create(dni=f"4000{i:04d}", nombre="Zeta", apellido="Perez")
            Formulario.objects.create(relevamiento=self.rel_a, celular=f"9{i}", ciudadano=c)
        resp = self.client.get(self.url, {"apellido": "perez"})
        self.assertEqual(resp.context["paginator"].count, 30)
        self.assertContains(resp, "apellido=perez")
        self.assertContains(resp, "page=2")

    def test_alcance_un_dni_de_un_relevamiento_no_visible_no_se_muestra(self):
        otro = Ciudadano.objects.create(dni="20999888", nombre="Otra", apellido="Ajena")
        Formulario.objects.create(relevamiento=self.rel_b, celular="3", ciudadano=otro)
        self.client.force_login(self.coord_a)  # coordina solo el segmento A
        self.assertEqual(self._pks(dni="20999888"), set())
        self.assertEqual(self._pks(apellido="ajena"), set())
        self.assertEqual(self._pks(dni="30123456"), {self.form_ana.pk})
        self.client.force_login(self.admin)
        self.assertEqual(len(self._pks(dni="20999888")), 1)

    def test_sin_filtros_de_persona_la_consulta_no_cambia(self):
        with CaptureQueriesContext(connection) as ctx:
            self.client.get(self.url, {"estado": Formulario.Estado.APROBADO})
        self.assertFalse(any("legajos_ciudadano" in q["sql"].lower() and "in (select" in q["sql"].lower() for q in ctx))

    def test_con_filtros_usa_subquery_y_no_suma_consultas(self):
        self.client.get(self.url)
        with CaptureQueriesContext(connection) as base:
            self.client.get(self.url)
        with CaptureQueriesContext(connection) as con:
            self.client.get(self.url, {"dni": "30123456", "apellido": "go"})
        self.assertEqual(len(con), len(base))
        self.assertTrue(any("in (select" in q["sql"].lower() for q in con))
