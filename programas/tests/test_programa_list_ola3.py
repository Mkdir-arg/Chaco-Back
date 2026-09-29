"""Listado de programas de Becas con las piezas comunes (W3-P-A1: TIT-13/14/18, CMP-1/11/13..15)."""

from html.parser import HTMLParser
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from programas.management.commands.seed_becas import ROL_ADMIN
from programas.models import ProgramaSiis

VOID = {"meta", "link", "br", "hr", "img", "input", "source", "col", "area", "base", "embed", "wbr"}


class ProgramaListadoOla3Tests(TestCase):
    def setUp(self):
        call_command("seed_becas", stdout=StringIO())
        admin = User.objects.create_user("admin_prog_list", password="x")
        admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        catalogo = patch("programas.forms.listar_programas", return_value=[{"id": 38, "nombre": "Producción"}])
        catalogo.start()
        self.addCleanup(catalogo.stop)
        self.programa = ProgramaSiis.objects.create(
            siis_programa_id=38, nombre="Producción", pausado=True, pausa_motivo="Sin fondos"
        )
        self.client.force_login(admin)
        self.html = self.client.get(reverse("becas:programas")).content.decode()

    def test_sin_paginacion_falsa(self):
        self.assertNotIn("1 de 1", self.html)
        self.assertNotIn("Anterior", self.html)
        self.assertNotIn("Siguiente", self.html)
        self.assertIn("1 programa<", self.html)

    def test_h1_canonico_sin_style_inline(self):
        self.assertIn('<h1 class="text-3xl font-extrabold text-heading tracking-tight">Programas</h1>', self.html)
        self.assertNotIn("font-size:28px", self.html)

    def test_accion_nuevo_programa_con_font_awesome(self):
        self.assertIn('<i class="fas fa-plus"', self.html)

    def test_accion_ver_nombra_el_programa(self):
        self.assertIn('aria-label="Ver programa Producción"', self.html)
        self.assertIn("nodo-icon-btn", self.html)

    def test_tabla_con_clases_nodo(self):
        self.assertIn('<tr class="nodo-thead-row">', self.html)
        self.assertIn('<th class="nodo-th">Nombre</th>', self.html)
        self.assertIn('class="nodo-td', self.html)

    def test_pausado_es_warning(self):
        self.assertIn('class="badge badge-warning badge-dot" title="Sin fondos">Pausado', self.html)
        self.assertNotIn("badge-danger", self.html)

    def test_overlays_fuera_del_contenedor_con_espaciado(self):
        # space-y-5 le da margin-top a los overlays fixed: el backdrop queda a 20 px del borde
        # y el clic en esa franja no cierra el modal.
        class Padres(HTMLParser):
            def __init__(self):
                super().__init__()
                self.pila, self.ancestros_de_overlay = [], []

            def handle_starttag(self, tag, attrs):
                clases = dict(attrs).get("class") or ""
                if "fixed inset-0" in clases:
                    self.ancestros_de_overlay.append(list(self.pila))
                if tag not in VOID:
                    self.pila.append(clases)

            def handle_endtag(self, tag):
                if tag not in VOID and self.pila:
                    self.pila.pop()

        parser = Padres()
        parser.feed(self.html)
        self.assertTrue(parser.ancestros_de_overlay)
        for ancestros in parser.ancestros_de_overlay:
            self.assertFalse([c for c in ancestros if "space-y-" in c.split() or "space-y-5" in c.split()], ancestros)
