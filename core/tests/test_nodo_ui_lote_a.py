"""Piezas de diseño de la etapa 0 del MVP de Dispositivos (lote A): eyebrow del
encabezado de página, filtro rápido en píldora, chips de selección múltiple y switch."""

from django.template import Context, Template
from django.test import SimpleTestCase


def _render(plantilla, **contexto):
    return Template(plantilla).render(Context(contexto))


class EyebrowPageHeaderTests(SimpleTestCase):
    def test_sin_eyebrow_no_dibuja_la_linea(self):
        html = _render('{% load nodo_ui %}{% page_header titulo="Instituciones" %}{% endpage_header %}')
        self.assertNotIn("uppercase", html)
        self.assertIn("Instituciones</h1>", html)

    def test_eyebrow_va_antes_del_titulo_con_las_clases_de_la_ficha(self):
        html = _render(
            '{% load nodo_ui %}{% page_header titulo="Instituciones" eyebrow="Programa Dispositivos" %}{% endpage_header %}'
        )
        self.assertIn(
            '<p class="text-xs font-semibold uppercase tracking-wide text-fg-brand mb-1">Programa Dispositivos</p>', html
        )
        self.assertLess(html.index("Programa Dispositivos"), html.index("<h1"))

    def test_eyebrow_se_escapa(self):
        html = _render(
            '{% load nodo_ui %}{% page_header titulo="X" eyebrow=texto %}{% endpage_header %}',
            texto="<script>alert(1)</script>",
        )
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_eyebrow_acepta_una_variable_de_contexto(self):
        html = _render(
            '{% load nodo_ui %}{% page_header titulo="X" eyebrow=ubicacion %}{% endpage_header %}',
            ubicacion="CIS N.º 3",
        )
        self.assertIn(">CIS N.º 3</p>", html)
