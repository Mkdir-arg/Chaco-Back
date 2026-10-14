"""El separador de miles es presentación; no normaliza documentos ni entradas."""

from django.template import Context, Template
from django.test import SimpleTestCase

from core.templatetags.nodo_ui import dni


class DniPresentacionTests(SimpleTestCase):
    def test_agrupa_siete_y_ocho_digitos_con_puntos_independientes_del_locale(self):
        for valor, esperado in (("1234567", "1.234.567"), ("12345678", "12.345.678"), (12345678, "12.345.678")):
            with self.subTest(valor=valor):
                self.assertEqual(dni(valor), esperado)

    def test_preserva_ceros_iniciales(self):
        self.assertEqual(dni("01234567"), "01.234.567")

    def test_devuelve_vacios_y_no_numericos_tal_cual(self):
        for valor in (
            None,
            "",
            "sin documento",
            "12.345.678",
            " 12345678 ",
            "1234567A",
            "١٢٣٤٥٦٧٨",
            "１２３４５６７８",
        ):
            with self.subTest(valor=valor):
                self.assertEqual(dni(valor), valor)

    def test_el_filtro_no_marca_como_seguro_el_texto_no_numerico(self):
        html = Template("{% load nodo_ui %}{{ valor|dni }}").render(Context({"valor": "<script>"}))
        self.assertEqual(html, "&lt;script&gt;")

    def test_el_template_presenta_el_dni_y_conserva_el_valor_original(self):
        contexto = Context({"valor": "12345678"})
        html = Template('{% load nodo_ui %}<p>{{ valor|dni }}</p><input name="dni" value="{{ valor }}">').render(
            contexto
        )
        self.assertInHTML("<p>12.345.678</p>", html)
        self.assertInHTML('<input name="dni" value="12345678">', html)
        self.assertEqual(contexto["valor"], "12345678")
