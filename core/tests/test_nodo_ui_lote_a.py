"""Piezas de diseño de la etapa 0 del MVP de Dispositivos (lote A): eyebrow del
encabezado de página, filtro rápido en píldora, chips de selección múltiple y switch."""

from django import forms
from django.template import Context, Template
from django.test import SimpleTestCase

from core.widgets import ChipsSelectMultiple, SwitchInput


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
            '<p class="text-xs font-semibold uppercase tracking-wide text-fg-brand mb-1">Programa Dispositivos</p>',
            html,
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


PILDORA = "components/_filtro_pildora.html"


def _pildoras(valor="2"):
    return [
        {"nombre": "area", "etiqueta": "Área", "opciones": [(1, "Abordaje"), (2, "Alojamiento")], "valor": valor},
        {"nombre": "tipo", "etiqueta": "Tipo", "opciones": [("a", "A")], "valor": "", "todos": "Todos los tipos"},
    ]


class FiltroPildoraTests(SimpleTestCase):
    def _html(self, **extra):
        from django.template.loader import render_to_string

        return render_to_string(PILDORA, {"pildoras": _pildoras(), **extra})

    def test_cada_pildora_es_un_select_con_etiqueta_y_aria_label(self):
        html = self._html()
        self.assertEqual(html.count('class="nodo-pildora"'), 2)
        self.assertIn("<span>Área:</span>", html)
        self.assertIn('name="area" class="nodo-pildora__control" aria-label="Área"', html)

    def test_la_opcion_vacia_dice_todos_o_el_texto_pedido(self):
        html = self._html()
        self.assertIn('<option value="">Todos</option>', html)
        self.assertIn('<option value="">Todos los tipos</option>', html)

    def test_marca_la_opcion_elegida_aunque_el_valor_sea_numerico(self):
        html = self._html()
        self.assertIn('<option value="2" selected>Alojamiento</option>', html)
        self.assertNotIn('<option value="1" selected>', html)

    def test_sin_valor_elegido_no_marca_ninguna(self):
        from django.template.loader import render_to_string

        html = render_to_string(PILDORA, {"pildoras": _pildoras(valor="")})
        self.assertNotIn("selected", html)

    def test_conserva_los_parametros_ocultos_y_no_la_pagina(self):
        html = self._html(ocultos=[("q", "pérez")])
        self.assertIn('<input type="hidden" name="q" value="pérez">', html)
        self.assertNotIn('name="page"', html)

    def test_envia_el_form_al_cambiar_y_deja_boton_sin_js(self):
        html = self._html()
        self.assertIn('method="get"', html)
        self.assertIn('@change="$el.requestSubmit()"', html)
        self.assertIn("<noscript>", html)

    def test_escapa_textos_y_valores(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            PILDORA,
            {"pildoras": [{"nombre": "x", "etiqueta": "<b>E</b>", "opciones": [("<i>", "<u>t</u>")], "valor": ""}]},
        )
        for crudo in ("<b>E</b>", "<i>", "<u>t</u>"):
            self.assertNotIn(crudo, html)

    def test_el_css_de_la_pildora_esta_en_nodo_forms(self):
        from pathlib import Path

        css = (Path(__file__).resolve().parents[2] / "static/custom/css/nodo-forms.css").read_text(encoding="utf-8")
        for clase in (".nodo-pildora {", ".nodo-pildora__control {"):
            self.assertIn(clase, css)
        self.assertIn("height: 36px", css)


class _FormPiezas(forms.Form):
    servicios = forms.MultipleChoiceField(
        label="Servicios que brinda",
        choices=[("alo", "Alojamiento"), ("des", "Desayuno"), ("cen", "Cena")],
        widget=ChipsSelectMultiple,
        required=False,
        help_text="Marcá los que presta.",
    )
    autoriza = forms.BooleanField(label="Exige autorización", widget=SwitchInput, required=False)


def _campo(form, nombre):
    from django.template.loader import render_to_string

    return render_to_string("components/_field.html", {"field": form[nombre]})


class ChipsYSwitchTests(SimpleTestCase):
    def test_chips_son_checkboxes_reales_dentro_de_un_contenedor_nodo_chips(self):
        html = str(_FormPiezas()["servicios"])
        self.assertIn('class="nodo-chips"', html)
        self.assertEqual(html.count('type="checkbox"'), 3)
        self.assertIn("Alojamiento", html)

    def test_chips_marcan_lo_elegido_y_el_form_valida_como_siempre(self):
        form = _FormPiezas(data={"servicios": ["alo", "cen"]})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["servicios"], ["alo", "cen"])
        html = str(form["servicios"])
        self.assertEqual(html.count("checked"), 2)

    def test_chips_rechazan_una_opcion_inexistente(self):
        form = _FormPiezas(data={"servicios": ["inventada"]})
        self.assertFalse(form.is_valid())
        self.assertIn("servicios", form.errors)

    def test_switch_es_un_checkbox_con_role_switch(self):
        html = str(_FormPiezas()["autoriza"])
        self.assertIn('type="checkbox"', html)
        self.assertIn('class="nodo-switch"', html)
        self.assertIn('role="switch"', html)

    def test_switch_se_marca_con_el_dato_y_se_lee_como_booleano(self):
        encendido = _FormPiezas(data={"autoriza": "on"})
        apagado = _FormPiezas(data={})
        self.assertTrue(encendido.is_valid() and encendido.cleaned_data["autoriza"])
        self.assertTrue(apagado.is_valid() and not apagado.cleaned_data["autoriza"])
        self.assertIn("checked", str(encendido["autoriza"]))

    def test_los_widgets_respetan_attrs_propios_sin_perder_la_clase(self):
        self.assertEqual(
            SwitchInput(attrs={"data-x": "1"}).attrs, {"class": "nodo-switch", "role": "switch", "data-x": "1"}
        )
        self.assertEqual(ChipsSelectMultiple(attrs={"data-x": "1"}).attrs["class"], "nodo-chips")

    def test_conviven_con_field_html_label_ayuda_y_error(self):
        chips = _campo(_FormPiezas(), "servicios")
        self.assertIn('class="nodo-chips"', chips)
        self.assertIn("Servicios que brinda", chips)
        self.assertIn('data-error="servicios"', chips)
        self.assertIn("Marcá los que presta.", chips)
        switch = _campo(_FormPiezas(), "autoriza")
        self.assertIn('class="nodo-switch"', switch)
        self.assertIn('data-error="autoriza"', switch)

    def test_el_css_define_las_tres_clases(self):
        from pathlib import Path

        css = (Path(__file__).resolve().parents[2] / "static/custom/css/nodo-forms.css").read_text(encoding="utf-8")
        for pieza in (".nodo-chips label:has(input:checked)", 'input[type="checkbox"].nodo-switch:checked'):
            self.assertIn(pieza, css)
