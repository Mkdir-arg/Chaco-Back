"""Ola 5, PR 6c — FE-22, FE-23, FE-24 y V5A-NEW-07 (b): lo que cierra la ola.

Tres hilos:

- **FE-22 / V5A-NEW-07 (b):** los KPIs del inicio y del tablero de Becas estaban
  escritos a mano porque `components/_stat_card.html` no sabía marcar el valor para el
  JS ni poner un pie. Ahora sí, y ocho de los diez salen de la pieza única.
- **FE-23:** había dos `_field.html` —uno en Becas y otro en Dispositivos, con otro
  dialecto de label—, y media docena de pantallas se escribían el campo a mano. Queda
  uno solo, en `templates/components/`, con `data-error` y el ARIA que enlaza el error
  con el control.
- **FE-24:** las solapas de cuatro pantallas no declaraban nada de ARIA. (El teclado
  vive en `core.tests.test_nodo_tabs`.)

Más los tres MINOR de la revisión del PR 6b (#615).
"""

import re
from pathlib import Path
from types import SimpleNamespace

from django import forms
from django.conf import settings
from django.template.loader import render_to_string
from django.test import SimpleTestCase

from core.tests.js_harness import sin_comentarios

RAIZ = Path(settings.BASE_DIR)

INICIO = RAIZ / "templates" / "inicio.html"
VISTA_INICIO = RAIZ / "core" / "views" / "public.py"
PANEL = RAIZ / "programas" / "templates" / "programas" / "becas" / "config" / "_dashboard_panel.html"
DASHBOARD_JS = RAIZ / "static" / "custom" / "js" / "becas-dashboard.js"
CAMPO = "components/_field.html"
NODO_FORMS = RAIZ / "static" / "custom" / "css" / "nodo-forms.css"

TABS_CON_ARIA = {
    "programas/templates/programas/becas/config/programa_detail.html": "Secciones del programa",
    "programas/templates/programas/becas/relevamientos/convocatoria_detail.html": "Secciones de la convocatoria",
    "programas/templates/programas/becas/relevamientos/relevamiento_detail.html": "Secciones del relevamiento",
    "users/templates/rol/rol_form.html": "Categorías de capacidades",
}


def texto(ruta):
    return (RAIZ / ruta).read_text(encoding="utf-8")


def _panel_renderizado():
    """El panel del tablero con lo mínimo que piden sus `{% url %}`."""
    return render_to_string(
        "programas/becas/config/_dashboard_panel.html",
        {"programa": SimpleNamespace(pk=1), "puede_exportar_dashboard": True},
    )


_TAG = re.compile(r"<[a-zA-Z][^<>]*>")
_ATRIBUTO = re.compile(r'([a-zA-Z:@-]+)="([^"]*)"')


def _solapas_y_paneles(contenido):
    """(id → aria-controls) de cada solapa y (id → aria-labelledby) de cada panel."""
    solapas, paneles = {}, {}
    for tag in _TAG.findall(contenido):
        attrs = dict(_ATRIBUTO.findall(tag))
        if attrs.get("role") == "tab":
            solapas[attrs.get("id")] = attrs.get("aria-controls")
        elif attrs.get("role") == "tabpanel":
            paneles[attrs.get("id")] = attrs.get("aria-labelledby")
    return solapas, paneles


class FormularioDePrueba(forms.Form):
    nombre = forms.CharField(label="Nombre", widget=forms.TextInput(attrs={"class": "nodo-field"}))
    alias = forms.CharField(label="Alias", required=False, help_text="Como lo conoce la gente")


# ---------------------------------------------------------------- FE-22 / V5A-NEW-07 (b)


class StatCardsDelInicioTests(SimpleTestCase):
    """Las cuatro tarjetas del inicio salen de la pieza única (FE-22, lo que faltaba)."""

    def setUp(self):
        self.html = texto("templates/inicio.html")

    def test_las_cuatro_salen_del_include(self):
        self.assertEqual(self.html.count('{% include "components/_stat_card.html"'), 4)

    def test_no_queda_el_dialecto_propio_de_tarjeta(self):
        for clase in ("stat-card-top", "stat-card-label", "stat-card-icon", "stat-card-value", "stat-card-footnote"):
            self.assertNotIn(clase, self.html, f"`{clase}` tenía que irse con la migración")
        self.assertNotIn('class="stat-card"', self.html)

    def test_se_fueron_el_gradiente_y_la_caja_de_52_px(self):
        """Los dos están prohibidos por la ficha del componente.

        El gradiente que queda en la pantalla es el de las barras de progreso de «Mi
        trabajo de hoy», que no es una stat card y es de otra ficha.
        """
        tarjetas = self.html.split("{# ── Stat cards (4 col) ── #}", 1)[1].split("{# ── Búsqueda rápida", 1)[0]

        self.assertNotIn("var(--gradient-brand)", tarjetas)
        self.assertNotIn("52px", self.html)
        self.assertNotIn("<svg", tarjetas, "los íconos de contenido son Font Awesome (D3)")

    def test_los_pies_se_arman_en_la_vista(self):
        vista = VISTA_INICIO.read_text(encoding="utf-8")

        for clave in ("pie_ciudadanos", "pie_legajos", "pie_alertas"):
            self.assertIn(f'context["{clave}"]', vista)
            self.assertIn(clave, self.html)

    def test_el_pie_concuerda_en_numero(self):
        """Con uno solo decía «1 inscripciones»: la concordancia la hace la vista."""
        vista = VISTA_INICIO.read_text(encoding="utf-8")

        self.assertIn("'ón' if context['registros_mes'] == 1 else 'ones'", vista)
        self.assertIn("'' if context['ingresos_24h'] == 1 else 's'", vista)


class KpisDelTableroDeBecasTests(SimpleTestCase):
    """V5A-NEW-07 (b): los seis KPIs del tablero, lo último que quedaba a mano."""

    def setUp(self):
        self.html = PANEL.read_text(encoding="utf-8")

    def test_cuatro_de_los_seis_salen_del_include(self):
        self.assertEqual(self.html.count('{% include "components/_stat_card.html"'), 4)

    def test_los_dos_que_quedan_a_mano_son_los_que_llevan_grafico_o_barra(self):
        """La pieza no tiene ranura de cuerpo y el arquetipo Dashboard no está definido."""
        bloque = self.html.split('data-dash="kpis"', 1)[1].split("{# Bloques #}", 1)[0]
        a_mano = re.findall(r'<div class="bg-white rounded-xl border border-base p-4">', bloque)

        self.assertEqual(len(a_mano), 2)
        self.assertIn('data-kpi="sparkline"', bloque)
        self.assertIn('data-kpi="cupo_barra"', bloque)

    def test_los_dos_que_quedan_usan_el_esqueleto_de_la_pieza(self):
        """Mezclados en la misma franja, tienen que leerse como una sola cosa."""
        bloque = self.html.split('data-dash="kpis"', 1)[1].split("{# Bloques #}", 1)[0]

        self.assertNotIn("shadow-sm", bloque)
        self.assertNotIn("text-xs text-body-subtle font-medium", bloque)
        self.assertNotIn("var(--gradient-brand)", bloque)

    def test_cada_dato_que_el_js_escribe_tiene_dónde_caer(self):
        """Contrato con `becas-dashboard.js`: migrar las tarjetas no puede perder un id."""
        js = DASHBOARD_JS.read_text(encoding="utf-8")
        pedidos = set(re.findall(r"kpi\('([a-z_]+)'", js)) | set(re.findall(r"\[data-kpi=\"([a-z_]+)\"\]", js))
        panel = _panel_renderizado()

        self.assertGreaterEqual(len(pedidos), 14)
        for nombre in sorted(pedidos):
            self.assertIn(f'data-kpi="{nombre}"', panel, f"el JS escribe «{nombre}» y nadie lo recibe")

    def test_el_valor_compuesto_conserva_los_dos_numeros(self):
        panel = _panel_renderizado()

        self.assertIn(
            '<span data-kpi="convocatorias_activas">—</span>'
            '<span class="text-sm text-body-subtle font-semibold"> / '
            '<span data-kpi="convocatorias_total">—</span></span>',
            panel,
        )


# ------------------------------------------------------------------------------- FE-23


class UnSoloFieldTests(SimpleTestCase):
    """FE-23: un único include de campo, en `templates/components/`."""

    def test_los_dos_includes_viejos_no_existen(self):
        self.assertFalse((RAIZ / "programas/templates/programas/becas/_field.html").exists())
        self.assertFalse((RAIZ / "programas/templates/programas/dispositivos/config/_field.html").exists())

    def test_nadie_los_incluye(self):
        """Sin los comentarios: el include nuevo cuenta de dónde viene, y eso vale."""
        for ruta in RAIZ.glob("**/templates/**/*.html"):
            if "node_modules" in ruta.parts or "docs" in ruta.parts:
                continue
            contenido = sin_comentarios(ruta.read_text(encoding="utf-8"))
            with self.subTest(ruta=ruta.name):
                self.assertNotIn("programas/becas/_field.html", contenido)
                self.assertNotIn("programas/dispositivos/config/_field.html", contenido)

    def test_las_pantallas_de_la_ficha_dejaron_de_escribir_el_campo_a_mano(self):
        # Las cinco de admisiones y camas se fueron con sus modelos (MVP v2, release A);
        # las tres que quedan son las mismas pantallas de la ficha que siguen vivas.
        pantallas = [
            "programas/templates/programas/dispositivos/legajo/form.html",
            "programas/templates/programas/merenderos/entrega_form.html",
            "programas/templates/programas/merenderos/solicitud_form.html",
        ]
        for ruta in pantallas:
            contenido = texto(ruta)
            with self.subTest(ruta=ruta):
                self.assertIn(CAMPO, contenido)
                # El label con `mb-1.5`/`font-semibold` era el dialecto que FE-23 unifica.
                self.assertNotIn("mb-1.5 block text-sm font-semibold", contenido)
                self.assertNotIn("field.errors|join", contenido)

    def test_el_render_es_el_canonico(self):
        form = FormularioDePrueba()
        html = render_to_string(CAMPO, {"field": form["nombre"]})

        self.assertIn('<div class="mb-4">', html)
        self.assertIn('class="block text-sm font-medium text-heading mb-1" for="id_nombre"', html)
        self.assertIn('<span class="text-fg-danger">*</span>', html)
        self.assertIn('class="nodo-field"', html)

    def test_el_hueco_del_error_existe_siempre_y_lo_encuentra_el_guardado_ajax(self):
        """`_ajax_js.html` busca `[data-error="<campo>"]` dentro del form."""
        html = render_to_string(CAMPO, {"field": FormularioDePrueba()["nombre"]})

        self.assertIn('data-error="nombre"', html)
        self.assertIn("text-fg-danger hidden", html)

    def test_con_error_se_muestra_y_el_control_queda_marcado(self):
        form = FormularioDePrueba({"nombre": ""})
        form.is_valid()
        html = render_to_string(CAMPO, {"field": form["nombre"]})

        self.assertIn('aria-invalid="true"', html)
        self.assertIn('aria-describedby="id_nombre-error"', html)
        self.assertIn('id="id_nombre-error"', html)
        self.assertNotIn("text-fg-danger hidden", html)

    def test_la_ayuda_queda_enlazada_al_control(self):
        html = render_to_string(CAMPO, {"field": FormularioDePrueba()["alias"]})

        self.assertIn('aria-describedby="id_alias-ayuda"', html)
        self.assertIn('id="id_alias-ayuda"', html)

    def test_sin_ayuda_ni_error_el_control_no_estrena_atributos(self):
        html = render_to_string(CAMPO, {"field": FormularioDePrueba()["nombre"]})

        self.assertNotIn("aria-describedby", html)
        self.assertNotIn("aria-invalid", html)

    def test_el_contenedor_se_puede_dejar_sin_margen(self):
        """Lo piden los formularios cuya grilla ya separa con `space-y`/`gap`."""
        campo = {"field": FormularioDePrueba()["nombre"]}

        self.assertIn('<div class="mb-4">', render_to_string(CAMPO, campo))
        self.assertIn('<div class="">', render_to_string(CAMPO, dict(campo, wrapper_class="")))
        self.assertIn('<div class="mt-4">', render_to_string(CAMPO, dict(campo, wrapper_class="mt-4")))

    def test_la_clase_del_control_sigue_viniendo_del_widget(self):
        """El ARIA pasa por `as_widget`, que no puede pisar los `attrs` del form."""
        form = FormularioDePrueba({"nombre": ""})
        form.is_valid()
        html = render_to_string(CAMPO, {"field": form["nombre"]})

        self.assertIn('class="nodo-field"', html)


# ------------------------------------------------------------------------------- FE-24


class SolapasConAriaTests(SimpleTestCase):
    """Las cuatro pantallas de la ficha declaran el ARIA completo de la golden."""

    def test_cada_barra_es_un_tablist_con_nombre(self):
        for ruta, etiqueta in TABS_CON_ARIA.items():
            with self.subTest(ruta=ruta):
                contenido = texto(ruta)
                self.assertIn('role="tablist"', contenido)
                self.assertIn(f'aria-label="{etiqueta}"', contenido)

    def test_cada_solapa_apunta_a_su_panel_y_el_panel_a_su_solapa(self):
        for ruta in TABS_CON_ARIA:
            solapas, paneles = _solapas_y_paneles(texto(ruta))
            with self.subTest(ruta=ruta):
                self.assertTrue(solapas, "la pantalla tiene que declarar sus solapas")
                self.assertEqual(len(solapas), len(paneles), "una solapa, un panel")
                self.assertEqual(sorted(solapas.values()), sorted(paneles))
                for panel, etiqueta in paneles.items():
                    self.assertIn(etiqueta, solapas, f"«{panel}» dice llamarse «{etiqueta}», que no es una solapa")
                    self.assertEqual(solapas[etiqueta], panel, "la ida y la vuelta tienen que coincidir")

    def test_las_tres_de_becas_declaran_la_solapa_activa_con_alpine(self):
        for ruta in list(TABS_CON_ARIA)[:3]:
            with self.subTest(ruta=ruta):
                contenido = texto(ruta)
                self.assertEqual(contenido.count('role="tab"'), contenido.count(":aria-selected="))

    def test_el_abm_de_roles_mantiene_aria_selected_desde_su_js(self):
        """No usa Alpine: el `aria-selected` lo escribe `activarTab`."""
        contenido = texto("users/templates/rol/rol_form.html")

        self.assertIn("btn.setAttribute('aria-selected', activo ? 'true' : 'false');", contenido)
        self.assertIn('aria-label="Buscar en todas las categorías"', contenido)

    def test_las_tres_de_becas_dejaron_su_estilo_local(self):
        """`[x-cloak]` ya es global en `override.css`: con él afuera, `programa_detail`
        pasa entero los marcadores del arquetipo Detalle."""
        for ruta in list(TABS_CON_ARIA)[:3]:
            with self.subTest(ruta=ruta):
                self.assertNotIn("[x-cloak]{display:none", texto(ruta))

    def test_dispositivos_queda_afuera(self):
        """D-V1 = No: el detalle del legajo de Dispositivos lo reemplaza la v2."""
        contenido = texto("programas/templates/programas/dispositivos/legajo/detail.html")

        self.assertNotIn('role="tabpanel"', contenido)


# ------------------------------------------------- MINOR de la revisión del PR 6b (#615)


class CampoDeColorTests(SimpleTestCase):
    """El `input[type=color]` con `nodo-field` salía como una barra de borde a borde."""

    def test_el_selector_de_color_tiene_el_tamano_de_una_muestra(self):
        css = NODO_FORMS.read_text(encoding="utf-8")

        self.assertIn('input[type="color"].nodo-field', css)
        regla = css.split('input[type="color"].nodo-field', 1)[1].split("}", 1)[0]
        self.assertIn("width: 64px", regla)
        self.assertIn("padding: 4px", regla)
        self.assertIn("cursor: pointer", regla)

    def test_el_unico_campo_de_color_del_repo_sigue_siendo_un_campo_nodo(self):
        forms_py = (RAIZ / "configuracion" / "forms" / "programas.py").read_text(encoding="utf-8")

        self.assertIn('attrs={"type": "color", "class": _FIELD_CLASS}', forms_py)
