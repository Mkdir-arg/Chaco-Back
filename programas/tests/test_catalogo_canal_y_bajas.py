"""Hallazgos de QA del constructor y del catálogo de Becas (#338, #339 y #341).

- E2 (#338): las listas de requisitos muestran en qué canal se pide cada uno, sin
  abrir el modal, igual que el catálogo de preguntas (`_pregunta_row.html`).
"""

from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from programas.management.commands.seed_becas import ROL_ADMIN
from programas.models import CanalFormulario, ProgramaSiis, RequisitoNativo, Segmento, Subsegmento, TipoCampo

BADGE_APP = '<span class="badge badge-white">Solo app de campo</span>'
BADGE_LINK = '<span class="badge badge-white">Solo link público</span>'
BADGE_AMBOS = '<span class="badge badge-white">Ambos canales</span>'


class BadgeDeCanalTests(TestCase):
    """E2: el canal se ve en la celda Tipo; «ambos» no lleva badge."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_becas", stdout=StringIO())
        cls.admin = User.objects.create_user("admin_canal", password="x")
        cls.admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        cls.programa = ProgramaSiis.objects.create(siis_programa_id=77, nombre="Becas canal")
        cls.segmento = Segmento.objects.create(nombre="Seg canal", cupo_maximo=10, programa=cls.programa)
        cls.subsegmento = Subsegmento.objects.create(segmento=cls.segmento, nombre="Sub canal", cupo_maximo=5)

        def requisito(texto, canal, **ancla):
            return RequisitoNativo.objects.create(texto=texto, tipo=TipoCampo.STRING, canal=canal, **ancla)

        requisito("Prog solo app", CanalFormulario.APP, programa=cls.programa)
        requisito("Prog ambos", CanalFormulario.AMBOS, programa=cls.programa)
        requisito("Seg solo link", CanalFormulario.LINK, segmento=cls.segmento)
        requisito("Seg ambos", CanalFormulario.AMBOS, segmento=cls.segmento)
        requisito("Sub solo app", CanalFormulario.APP, segmento=cls.segmento, subsegmento=cls.subsegmento)
        requisito("Sub ambos", CanalFormulario.AMBOS, segmento=cls.segmento, subsegmento=cls.subsegmento)

    def setUp(self):
        self.client.force_login(self.admin)

    def _html(self, nombre, *args):
        resp = self.client.get(reverse(f"becas:{nombre}", args=args))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertNotIn(BADGE_AMBOS, html)
        return html

    def test_panel_del_programa(self):
        html = self._html("programa_detalle", self.programa.pk)
        self.assertEqual(html.count(BADGE_APP), 1)
        self.assertNotIn(BADGE_LINK, html)

    def test_panel_del_segmento_y_heredados_del_programa(self):
        html = self._html("segmento_detalle", self.segmento.pk)
        self.assertEqual(html.count(BADGE_LINK), 1)  # el propio del segmento
        self.assertEqual(html.count(BADGE_APP), 1)  # el heredado del programa (solo lectura)

    def test_panel_del_subsegmento_y_heredados(self):
        html = self._html("subsegmento_detalle", self.subsegmento.pk)
        # Propio del subsegmento + heredado del programa; el del segmento es «link».
        self.assertEqual(html.count(BADGE_APP), 2)
        self.assertEqual(html.count(BADGE_LINK), 1)

    def test_pagina_de_requisitos(self):
        html = self._html("requisitos_segmento")
        self.assertIn(BADGE_LINK, html)
        self.assertIn(BADGE_APP, html)
