"""Piezas reutilizables del backoffice: indicador de pasos, paginación, tarjeta de número, estado vacío,
alerta inline, errores no de campo y el filtro ``hay_filtros``
(W2-C9b, CMP-11/22/23, ALR-14/15, FE-08)."""

import importlib.util
import json
import os
import re
from decimal import Decimal
from io import StringIO
from pathlib import Path
from unittest import skipUnless

from django import forms, template
from django.contrib.auth.models import AnonymousUser, User
from django.core.management import call_command
from django.core.paginator import Paginator
from django.http import QueryDict
from django.template import Context, Template
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from core.templatetags.nodo_ui import hay_filtros, sin_parametros


@skipUnless(os.environ.get("CHACO_PLAYWRIGHT") == "1", "Requiere Playwright y Chromium en el entorno de prueba")
class TablaResponsiveTest(SimpleTestCase):
    """Mide el overflow real, incluido el rótulo accesible absoluto de Acciones."""

    def test_el_scroll_de_la_tabla_no_amplia_la_pagina(self):
        from playwright.sync_api import sync_playwright

        raiz = Path(__file__).resolve().parents[2]
        css = "\n".join(
            (raiz / "static/custom/css" / nombre).read_text(encoding="utf-8")
            for nombre in ("tailwind.css", "nodo-tables.css")
        )
        with sync_playwright() as motor:
            navegador = motor.chromium.launch()
            pagina = navegador.new_page(viewport={"width": 390, "height": 700})
            pagina.set_content(
                '<!DOCTYPE html><html class="overflow-x-hidden"><head><style>' + css + "</style></head>"
                '<body class="overflow-x-hidden"><div class="p-4"><div class="overflow-x-auto">'
                '<table class="w-full border-collapse"><thead><tr class="nodo-thead-row">'
                '<th class="nodo-th">Persona</th><th class="nodo-th text-right">'
                '<span class="sr-only">Acciones</span></th></tr></thead><tbody><tr>'
                '<td class="nodo-td">' + "DocumentoSinEspacios" * 8 + '</td><td class="nodo-td">Ver</td>'
                "</tr></tbody></table></div></div></body></html>"
            )
            self.assertEqual(pagina.evaluate("document.documentElement.scrollWidth"), 390)
            wrapper = pagina.locator(".overflow-x-auto")
            self.assertEqual(wrapper.evaluate("e => getComputedStyle(e).position"), "relative")
            self.assertTrue(wrapper.evaluate("e => e.scrollWidth > e.clientWidth"))
            wrapper.evaluate("e => e.scrollLeft = e.scrollWidth")
            self.assertGreater(wrapper.evaluate("e => e.scrollLeft"), 0)
            self.assertEqual(pagina.locator("th").last.text_content().strip(), "Acciones")
            self.assertEqual(pagina.evaluate("document.documentElement.scrollWidth"), 390)
            pagina.locator("th").first.evaluate("e => e.classList.add('sticky')")
            self.assertEqual(pagina.locator("th").first.evaluate("e => getComputedStyle(e).position"), "sticky")
            navegador.close()


PAGINACION = "components/_paginacion.html"
STAT = "components/_stat_card.html"
VACIO = "components/_estado_vacio.html"
ALERTA = "components/_alerta.html"
FORM_ERRORES = "components/_form_errores.html"
UBICACION = "components/_ubicacion.html"
STEPPER = "components/_stepper.html"
LINEA_TIEMPO = "components/_linea_tiempo.html"
FICHA_SECCION = "components/_ficha_seccion.html"
REVISION = "programas/dispositivos/estadia/revision_referencia.html"


def _pagina(total, numero=1, por_pagina=10):
    return Paginator(list(range(total)), por_pagina).get_page(numero)


RAIZ = Path(__file__).resolve().parents[2]
_INCLUDE_STAT = re.compile(r"\{%\s*include\s+\"components/_stat_card\.html\".*?%\}")


def _includes_de_stat_card():
    """Cada llamada real a la pieza en el repo (sin la del propio comentario ni docs/)."""
    invocaciones = []
    for ruta in sorted(RAIZ.glob("**/templates/**/*.html")):
        partes = ruta.parts
        if "node_modules" in partes or "docs" in partes or ruta.name == "_stat_card.html":
            continue
        invocaciones.extend(_INCLUDE_STAT.findall(ruta.read_text(encoding="utf-8")))
    return invocaciones


_INCLUDES_DE_STAT_CARD = _includes_de_stat_card()


class EntradasBitacoraAccionTest(SimpleTestCase):
    def setUp(self):
        self.entradas = [
            {
                "hora": "16:10",
                "categoria": "Incidente",
                "tono": "danger",
                "texto": "Acta <sin HTML>\nSegunda línea",
                "autor": "Lucía Méndez",
            },
            {
                "hora": "16:05",
                "categoria": "Ingreso",
                "tono": "success",
                "automatica": True,
                "autor": "Operador",
                "version": 2,
            },
            {"hora": "16:00", "categoria": "General"},
        ]

    def _render(self):
        return render_to_string("components/_entradas_bitacora.html", {"entradas": self.entradas})

    def test_sin_accion_conserva_exactamente_el_html_anterior(self):
        esperado = json.loads(
            (RAIZ / "core/tests/snapshots/entradas_bitacora_sin_accion.json").read_text(encoding="utf-8")
        )
        self.assertEqual(self._render(), esperado)
        for entrada in self.entradas:
            entrada["url_corregir"] = ""
        self.assertEqual(self._render(), esperado)

    def test_accion_opcional_en_la_linea_de_autoria_y_texto_escapado(self):
        sin_accion = self._render()
        self.entradas[0]["url_corregir"] = "/bitacora/?turno=2&corregir=7"
        html = self._render()
        accion = ' · <a href="/bitacora/?turno=2&amp;corregir=7" class="text-fg-brand hover:underline">corregir</a> (crea versión)'
        self.assertIn("Lucía Méndez" + accion + "</p>", html)
        self.assertEqual(html.replace(accion, ""), sin_accion)
        self.assertIn("Acta &lt;sin HTML&gt;<br>Segunda línea", html)

    def test_accion_sin_autor_tambien_se_dibuja_sin_separador_suelto(self):
        self.entradas[2]["url_corregir"] = "/bitacora/?corregir=8"
        self.assertIn('<p class="mt-1 text-xs text-body-subtle"><a href="/bitacora/?corregir=8"', self._render())


class PaginacionTest(SimpleTestCase):
    def _render(self, query="", **contexto):
        request = RequestFactory().get("/lista/" + (f"?{query}" if query else ""))
        request.user = AnonymousUser()
        return render_to_string(PAGINACION, contexto, request=request)

    def test_con_una_sola_pagina_no_se_muestra(self):
        html = self._render(page_obj=_pagina(4), entidad="programa")

        self.assertEqual(html.strip(), "")

    def test_sin_page_obj_no_se_muestra(self):
        self.assertEqual(self._render(page_obj=None).strip(), "")

    def test_primera_pagina_solo_tiene_siguiente(self):
        html = self._render(page_obj=_pagina(51, 1, 50), entidad="caso")

        self.assertIn("Página 1 de 2 · 51 casos", html)
        self.assertIn('href="?page=2"', html)
        self.assertIn('aria-label="Página siguiente"', html)
        self.assertNotIn('aria-label="Página anterior"', html)
        self.assertIn("px-4 py-3 border-t border-light bg-secondary", html)
        self.assertIn('class="btn-nodo btn-tertiary btn-sm"', html)
        self.assertIn('<i class="fas fa-chevron-right" aria-hidden="true"></i>', html)

    def test_ultima_pagina_solo_tiene_anterior(self):
        html = self._render("page=3", page_obj=_pagina(25, 3), entidad="caso")

        self.assertIn("Página 3 de 3 · 25 casos", html)
        self.assertIn('href="?page=2"', html)
        self.assertNotIn('aria-label="Página siguiente"', html)

    def test_conserva_los_filtros_y_saca_page(self):
        html = self._render("fecha=2026-09-30&page=2&segmento=7", page_obj=_pagina(40, 2), entidad="caso")

        self.assertIn('href="?page=1&amp;fecha=2026-09-30&amp;segmento=7"', html)
        self.assertIn('href="?page=3&amp;fecha=2026-09-30&amp;segmento=7"', html)
        self.assertNotIn("page=2&amp;", html)

    def test_escapa_y_codifica_los_parametros(self):
        html = self._render(
            "q=%22%3E%3Cscript%3Ealert(1)%3C%2Fscript%3E&x=a%26b",
            page_obj=_pagina(40, 1),
            entidad="caso",
        )

        self.assertNotIn("<script>", html)
        self.assertNotIn('">', html.split("href=")[1].split(" ")[0])
        self.assertIn("q=%22%3E%3Cscript%3Ealert%281%29%3C%2Fscript%3E", html)
        self.assertIn("&amp;x=a%26b", html)

    def test_filtros_qs_explicito_tiene_precedencia(self):
        html = self._render("otro=1", page_obj=_pagina(40, 1), entidad="caso", filtros_qs="segmento=5")

        self.assertIn('href="?page=2&amp;segmento=5"', html)
        self.assertNotIn("otro=1", html)

    def test_plural_explicito_y_singular(self):
        html = self._render(page_obj=_pagina(30, 1), entidad="localidad", entidad_plural="localidades")
        self.assertIn("30 localidades", html)

        html = self._render(page_obj=_pagina(1, 1, 1), entidad="caso")
        self.assertEqual(html.strip(), "")


class PaginacionPorSolapaTest(SimpleTestCase):
    """FE-17: ``param`` y ``extra_qs`` para más de una lista paginada por pantalla.

    Hasta el Cambio 167 la pieza leía y escribía siempre ``?page=``, así que las tres
    solapas de la golden de detalle (`becas/cupo/segmento_detail.html`) y los dos detalles
    de relevamientos tenían el pie copiado a mano.
    """

    def _render(self, query="", **contexto):
        request = RequestFactory().get("/detalle/" + (f"?{query}" if query else ""))
        request.user = AnonymousUser()
        return render_to_string(PAGINACION, contexto, request=request)

    def test_param_cambia_el_nombre_del_parametro_de_pagina(self):
        html = self._render(page_obj=_pagina(40, 1), entidad="beneficiario", param="beneficiarios_page")

        self.assertIn('href="?beneficiarios_page=2"', html)
        self.assertNotIn("?page=", html)

    def test_extra_qs_viaja_en_los_dos_enlaces(self):
        html = self._render(
            page_obj=_pagina(40, 2),
            entidad="beneficiario",
            param="beneficiarios_page",
            extra_qs="tab=beneficiarios",
        )

        self.assertIn('href="?beneficiarios_page=1&amp;tab=beneficiarios"', html)
        self.assertIn('href="?beneficiarios_page=3&amp;tab=beneficiarios"', html)

    def test_el_parametro_propio_no_se_duplica_al_conservar_los_filtros(self):
        """Sin esto el enlace salía con el parámetro dos veces y la página no cambiaba."""
        html = self._render(
            "tab=beneficiarios&beneficiarios_page=2&dni=30",
            page_obj=_pagina(40, 2),
            entidad="beneficiario",
            param="beneficiarios_page",
            extra_qs="tab=beneficiarios",
        )

        self.assertIn('href="?beneficiarios_page=1&amp;tab=beneficiarios&amp;dni=30"', html)
        self.assertEqual(html.count("beneficiarios_page="), 2)
        self.assertEqual(html.count("tab=beneficiarios"), 2)

    def test_un_extra_qs_escapado_tampoco_duplica_sus_claves(self):
        """Con dos claves en `extra_qs`, lo natural es escribirlas con `&amp;`."""
        html = self._render(
            "tab=ben&modo=lista&dni=30",
            page_obj=_pagina(40, 2),
            entidad="caso",
            param="casos_page",
            extra_qs="tab=ben&amp;modo=lista",
        )

        self.assertIn('href="?casos_page=1&amp;tab=ben&amp;modo=lista&amp;dni=30"', html)
        self.assertEqual(html.count("modo=lista"), 2, "una vez por enlace, no dos")

    def test_dos_listas_en_la_misma_pantalla_no_se_pisan(self):
        contexto = {"page_obj": _pagina(40, 1)}
        beneficiarios = self._render(
            "lista_espera_page=3", entidad="beneficiario", param="beneficiarios_page", **contexto
        )
        espera = self._render("lista_espera_page=3", entidad="persona", param="lista_espera_page", **contexto)

        self.assertIn('href="?beneficiarios_page=2&amp;lista_espera_page=3"', beneficiarios)
        self.assertIn('href="?lista_espera_page=2"', espera)
        self.assertNotIn("lista_espera_page=3", espera)

    def test_filtros_qs_explicito_tambien_manda_con_param(self):
        html = self._render(
            "otro=1",
            page_obj=_pagina(40, 1),
            entidad="pendiente",
            param="pendientes_page",
            extra_qs="tab=pendientes",
            filtros_qs="dni=30",
        )

        self.assertIn('href="?pendientes_page=2&amp;tab=pendientes&amp;dni=30"', html)
        self.assertNotIn("otro=1", html)


class SinParametrosFiltroTest(SimpleTestCase):
    """El filtro que sostiene ``param``/``extra_qs``: ``{% load %}``-able y sin «?»."""

    def test_saca_las_claves_pedidas_y_conserva_el_orden(self):
        qs = QueryDict("fecha=2026-09-30&beneficiarios_page=2&segmento=7")

        self.assertEqual(sin_parametros(qs, "beneficiarios_page"), "fecha=2026-09-30&segmento=7")

    def test_acepta_un_querystring_y_usa_solo_la_clave_de_cada_par(self):
        qs = QueryDict("tab=beneficiarios&dni=30")

        self.assertEqual(sin_parametros(qs, "tab=beneficiarios"), "dni=30")

    def test_acepta_varias_claves_separadas_por_coma_o_ampersand(self):
        qs = QueryDict("a=1&b=2&c=3")

        self.assertEqual(sin_parametros(qs, "a,b"), "c=3")
        self.assertEqual(sin_parametros(qs, "a=1&b=2"), "c=3")

    def test_encadenable_sobre_su_propia_salida(self):
        qs = QueryDict("a=1&b=2&c=3")

        self.assertEqual(sin_parametros(sin_parametros(qs, "a"), "b"), "c=3")

    def test_sin_excluidos_ni_parametros_no_rompe(self):
        self.assertEqual(sin_parametros(QueryDict("a=1"), ""), "a=1")
        self.assertEqual(sin_parametros(None, "a"), "")

    def test_conserva_los_valores_repetidos(self):
        qs = QueryDict("estado=A&estado=B&page=2")

        self.assertEqual(sin_parametros(qs, "page"), "estado=A&estado=B")

    def test_tolera_un_extra_qs_ya_escapado(self):
        """La pieza escribe sus enlaces con ``&amp;``, así que un consumidor que pasa
        ``extra_qs`` escapado está siendo coherente con lo que ve. Partiendo en ``&`` a
        secas, la segunda clave quedaba como ``amp;modo`` y no se sacaba nunca."""
        qs = QueryDict("tab=ben&modo=lista&dni=30")

        self.assertEqual(sin_parametros(qs, "tab=ben&amp;modo=lista"), "dni=30")

    def test_tolera_un_querystring_de_entrada_ya_escapado(self):
        self.assertEqual(sin_parametros("a=1&amp;b=2", "a"), "b=2")


class StatCardTest(SimpleTestCase):
    def test_estructura_canonica(self):
        html = render_to_string(
            STAT, {"etiqueta": "Aprobados", "valor": 12, "icono": "fa-circle-check", "tono": "success"}
        )

        self.assertIn('class="bg-white rounded-xl border border-base p-4"', html)
        self.assertIn('<p class="text-xs font-semibold text-body-subtle">Aprobados</p>', html)
        self.assertIn(
            "w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 bg-success-soft text-fg-success", html
        )
        self.assertIn('<i class="fas fa-circle-check text-sm" aria-hidden="true"></i>', html)
        self.assertIn('<p class="text-2xl font-bold text-heading mt-2">12</p>', html)
        self.assertNotIn("shadow-sm", html)
        self.assertNotIn("gradient", html)

    def test_tonos(self):
        for tono in ("warning", "danger", "brand"):
            html = render_to_string(STAT, {"etiqueta": "X", "valor": 1, "icono": "fa-users", "tono": tono})
            self.assertIn(f"bg-{tono}-soft text-fg-{tono}", html)

        html = render_to_string(STAT, {"etiqueta": "X", "valor": 1, "icono": "fa-users"})
        self.assertIn("bg-brand-soft text-fg-brand", html)

    def test_escapa_etiqueta_y_valor(self):
        html = render_to_string(STAT, {"etiqueta": "<b>x</b>", "valor": "<i>1</i>", "icono": "fa-users"})

        self.assertNotIn("<b>", html)
        self.assertIn("&lt;b&gt;x&lt;/b&gt;", html)
        self.assertIn("&lt;i&gt;1&lt;/i&gt;", html)

    def test_sin_los_parametros_opcionales_el_render_es_el_de_siempre(self):
        """FE-22 / V5A-NEW-07 (b): los opcionales no pueden mover a los 20 consumidores.

        El HTML de abajo es, carácter por carácter, el que la pieza daba antes de
        aprender `kpi_id`, `sufijo`, `sufijo_id`, `nota` y `nota_id`.
        """
        html = render_to_string(
            STAT, {"etiqueta": "Aprobados", "valor": 12, "icono": "fa-circle-check", "tono": "success"}
        )

        self.assertEqual(
            html,
            "\n"
            '<div class="bg-white rounded-xl border border-base p-4">\n'
            '  <div class="flex items-center justify-between gap-2">\n'
            '    <p class="text-xs font-semibold text-body-subtle">Aprobados</p>\n'
            '    <div class="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 '
            'bg-success-soft text-fg-success"><i class="fas fa-circle-check text-sm" aria-hidden="true">'
            "</i></div>\n"
            "  </div>\n"
            '  <p class="text-2xl font-bold text-heading mt-2">12</p>\n'
            "</div>\n",
        )

    def test_variante_tablero_es_la_franja_grande(self):
        """#582 / C-2: caja de 52 px con gradiente y valor de 32 px / 800 (reglas en nodo-stat-card.css)."""
        html = render_to_string(
            STAT, {"etiqueta": "Plazas", "valor": 40, "icono": "fa-bed", "tono": "danger", "variante": "tablero"}
        )

        self.assertIn('class="bg-white rounded-xl border border-base p-4 nodo-stat-tablero shadow-sm"', html)
        self.assertIn('class="nodo-stat-tablero-ico flex items-center justify-center flex-shrink-0"', html)
        self.assertIn('<i class="fas fa-bed" aria-hidden="true"></i>', html)
        self.assertIn('class="text-2xl font-bold text-heading mt-2 nodo-stat-tablero-valor">40</p>', html)
        self.assertNotIn("w-8 h-8", html)
        self.assertNotIn("bg-danger-soft", html)  # el tono no pinta la caja grande
        css = (RAIZ / "static/custom/css/nodo-stat-card.css").read_text(encoding="utf-8")
        for regla in ("width: 52px", "height: 52px", "var(--gradient-brand)", "font-size: 32px", "font-weight: 800"):
            self.assertIn(regla, css)

    def test_una_variante_desconocida_es_la_chica(self):
        chica = render_to_string(STAT, {"etiqueta": "X", "valor": 1, "icono": "fa-users"})
        otra = render_to_string(STAT, {"etiqueta": "X", "valor": 1, "icono": "fa-users", "variante": "grande"})

        self.assertEqual(chica, otra)

    def test_los_consumidores_que_no_los_piden_no_estrenan_data_kpi_ni_pie(self):
        """Ninguna de las llamadas que ya existían pasa un opcional: el render no se mueve."""
        for invocacion in _INCLUDES_DE_STAT_CARD:
            if any(f"{nombre}=" in invocacion for nombre in ("kpi_id", "sufijo", "nota")):
                continue
            with self.subTest(invocacion=invocacion):
                html = Template("{% load nodo_ui %}" + invocacion).render(Context({}))
                self.assertNotIn("data-kpi", html)
                self.assertNotIn("text-xs text-body-subtle mt-1", html)
                self.assertNotIn("text-sm text-body-subtle font-semibold", html)

    def test_kpi_id_marca_el_valor_para_que_el_js_lo_refresque(self):
        html = render_to_string(STAT, {"etiqueta": "Aprobados", "valor": "—", "kpi_id": "aprobados"})

        self.assertIn('<p class="text-2xl font-bold text-heading mt-2" data-kpi="aprobados">—</p>', html)

    def test_nota_es_el_pie_de_la_tarjeta(self):
        html = render_to_string(STAT, {"etiqueta": "X", "valor": 3, "nota": "2 cerradas por vencimiento"})

        self.assertIn('<p class="text-xs text-body-subtle mt-1">2 cerradas por vencimiento</p>', html)

    def test_nota_id_deja_el_pie_vacio_para_el_js(self):
        html = render_to_string(STAT, {"etiqueta": "X", "valor": "—", "nota_id": "aprobados_nota"})

        self.assertIn('<p class="text-xs text-body-subtle mt-1" data-kpi="aprobados_nota"></p>', html)

    def test_sufijo_va_pegado_al_valor_en_tamano_secundario(self):
        html = render_to_string(STAT, {"etiqueta": "Cupo", "valor": 80, "sufijo": " %"})

        self.assertIn(
            '<p class="text-2xl font-bold text-heading mt-2">80'
            '<span class="text-sm text-body-subtle font-semibold"> %</span></p>',
            html,
        )

    def test_valor_compuesto_marca_los_dos_numeros_y_el_sufijo_sobrevive_al_js(self):
        """El JS asigna `textContent`: con `data-kpi` en el `<p>` borraría el « / M»."""
        html = render_to_string(
            STAT,
            {
                "etiqueta": "Convocatorias activas",
                "valor": "—",
                "kpi_id": "convocatorias_activas",
                "sufijo": " / ",
                "sufijo_id": "convocatorias_total",
            },
        )

        self.assertIn(
            '<p class="text-2xl font-bold text-heading mt-2">'
            '<span data-kpi="convocatorias_activas">—</span>'
            '<span class="text-sm text-body-subtle font-semibold"> / '
            '<span data-kpi="convocatorias_total">—</span></span></p>',
            html,
        )
        self.assertNotIn('mt-2" data-kpi', html)

    def test_escapa_los_opcionales(self):
        html = render_to_string(
            STAT,
            {"etiqueta": "X", "valor": 1, "nota": "<b>n</b>", "sufijo": "<i>s</i>", "kpi_id": '"><script>'},
        )

        self.assertNotIn("<b>", html)
        self.assertNotIn("<i>s", html)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;b&gt;n&lt;/b&gt;", html)


class EstadoVacioTest(SimpleTestCase):
    def test_sin_filtros_con_accion_primaria(self):
        html = render_to_string(
            VACIO,
            {
                "icono": "fa-clipboard-check",
                "titulo": "No hay relevamientos",
                "texto": "Creá el primero.",
                "accion_url": "/nuevo/",
                "accion_texto": "Nuevo relevamiento",
                "accion_icono": "fa-plus",
            },
        )

        self.assertIn('class="py-14 px-6 text-center flex flex-col items-center gap-3"', html)
        self.assertIn('<i class="fas fa-clipboard-check text-5xl" aria-hidden="true"></i>', html)
        self.assertIn('<p class="text-[17px] font-bold text-heading">No hay relevamientos</p>', html)
        self.assertIn('<p class="text-sm text-body max-w-xs">Creá el primero.</p>', html)
        self.assertIn('href="/nuevo/" class="btn-nodo btn-brand btn-base mt-2"', html)
        self.assertIn('<i class="fas fa-plus" aria-hidden="true"></i> Nuevo relevamiento', html)

    def test_con_filtros_ofrece_limpiar(self):
        html = render_to_string(
            VACIO, {"con_filtros": True, "titulo": "Ningún caso coincide con los filtros", "accion_url": "/lista/"}
        )

        self.assertIn("fa-magnifying-glass text-5xl", html)
        self.assertIn('href="/lista/" class="btn-nodo btn-tertiary btn-base mt-2"', html)
        self.assertIn("Limpiar filtros", html)
        self.assertNotIn("btn-brand", html)

    def test_sin_accion_ni_texto(self):
        html = render_to_string(VACIO, {"titulo": "Vacío"})

        self.assertNotIn("<a ", html)
        self.assertNotIn("max-w-xs", html)

    def test_escapa_titulo_texto_y_url(self):
        html = render_to_string(
            VACIO,
            {
                "titulo": "<script>x</script>",
                "texto": "<b>t</b>",
                "accion_url": '/a/"onmouseover="x',
                "accion_texto": "y",
            },
        )

        self.assertNotIn("<script>", html)
        self.assertNotIn("<b>", html)
        self.assertNotIn('"onmouseover="', html)


class AlertaTest(SimpleTestCase):
    def test_warning_es_alert_con_titulo_y_texto(self):
        html = render_to_string(ALERTA, {"tono": "warning", "titulo": "Sin padrón", "texto": "Link abierto."})

        self.assertIn('class="rounded-lg bg-warning-soft border border-warning-subtle p-4 text-sm" role="alert"', html)
        self.assertIn('<strong class="text-heading">Sin padrón</strong>', html)
        self.assertIn('<p class="text-body mt-1">Link abierto.</p>', html)

    def test_danger_es_alert(self):
        html = render_to_string(ALERTA, {"tono": "danger", "titulo": "Bloqueo"})

        self.assertIn("bg-danger-soft border border-danger-subtle", html)
        self.assertIn('role="alert"', html)

    def test_success_es_status(self):
        html = render_to_string(ALERTA, {"tono": "success", "texto": "Listo."})

        self.assertIn("bg-success-soft border border-success-subtle", html)
        self.assertIn('role="status"', html)
        self.assertIn('<p class="text-body">Listo.</p>', html)

    def test_info_reusa_la_nota_informativa_canonica(self):
        html = render_to_string(ALERTA, {"tono": "info", "texto": "Después de guardar."})

        self.assertIn("background:var(--bg-info-soft); border:1px solid var(--color-brand-200)", html)
        self.assertIn('role="status"', html)
        self.assertIn("fa-circle-info", html)
        self.assertNotIn("border-info-subtle", html)

    def test_role_explicito(self):
        html = render_to_string(ALERTA, {"tono": "warning", "texto": "x", "role": "status"})

        self.assertIn('role="status"', html)

    def test_sin_parametros_nuevos_el_markup_no_cambia(self):
        html = render_to_string(ALERTA, {"tono": "warning", "titulo": "T", "texto": "x"})

        self.assertNotIn("<i ", html)
        self.assertNotIn("<a ", html)
        self.assertNotIn("flex items-start", html)

    def test_icono_va_a_18px_y_aria_hidden(self):
        html = render_to_string(ALERTA, {"tono": "danger", "icono": "triangle-exclamation", "titulo": "T"})

        self.assertIn(
            '<i class="fas fa-triangle-exclamation text-lg flex-shrink-0 text-fg-danger" aria-hidden="true"></i>', html
        )
        self.assertIn('role="alert"', html)
        self.assertIn("bg-danger-soft border border-danger-subtle", html)

    def test_accion_con_url_y_texto_dibuja_el_link(self):
        html = render_to_string(
            ALERTA, {"tono": "warning", "titulo": "T", "accion_url": "/x/", "accion_texto": "Resolver"}
        )

        self.assertIn('<a href="/x/" class="flex-shrink-0 font-medium underline text-fg-warning">Resolver</a>', html)

    def test_accion_incompleta_no_deja_link_ni_cambia_el_markup(self):
        solo_url = render_to_string(ALERTA, {"tono": "warning", "texto": "x", "accion_url": "/x/"})
        solo_texto = render_to_string(ALERTA, {"tono": "warning", "texto": "x", "accion_texto": "Resolver"})
        base = render_to_string(ALERTA, {"tono": "warning", "texto": "x"})

        self.assertEqual(solo_url, base)
        self.assertEqual(solo_texto, base)

    def test_info_con_icono_y_accion(self):
        html = render_to_string(
            ALERTA, {"tono": "info", "icono": "circle-check", "texto": "x", "accion_url": "/x/", "accion_texto": "Ver"}
        )

        self.assertIn("fa-circle-check text-lg", html)
        self.assertNotIn("fa-circle-info", html)
        self.assertIn('<a href="/x/" class="flex-shrink-0 text-sm font-medium underline text-fg-info">Ver</a>', html)

    def test_escapa_la_accion(self):
        html = render_to_string(
            ALERTA,
            {"tono": "danger", "accion_url": '/x/"onclick="y', "accion_texto": "<b>"},
        )

        # No alcanza con que el marcado no aparezca: eso pasaria tambien si el
        # texto se descartara. Hay que ver que aparece escapado, y que la comilla
        # de la URL no cierra el atributo.
        self.assertNotIn("<b>", html)
        self.assertIn("&lt;b&gt;", html)
        self.assertNotIn('onclick="y"', html)
        self.assertIn("&quot;onclick=&quot;y", html)

    def test_escapa(self):
        html = render_to_string(ALERTA, {"tono": "danger", "titulo": "<script>", "texto": "<img src=x>"})

        self.assertNotIn("<script>", html)
        self.assertNotIn("<img", html)


class UbicacionTest(SimpleTestCase):
    def test_con_coordenadas_muestra_valores_y_enlace_externo_seguro(self):
        html = render_to_string(UBICACION, {"latitud": Decimal("-27.451234"), "longitud": Decimal("-58.986543")})

        self.assertIn("-27,451234", html)
        self.assertIn("-58,986543", html)
        self.assertIn("mlat=-27.451234&amp;mlon=-58.986543", html)
        self.assertIn('target="_blank" rel="noopener noreferrer"', html)
        self.assertNotIn("Sin ubicación cargada", html)
        self.assertNotIn("<script", html)
        self.assertNotIn("<iframe", html)

    def test_sin_coordenadas_muestra_el_vacio_y_ningun_enlace(self):
        for contexto in ({}, {"latitud": None, "longitud": None}, {"latitud": Decimal("-27.4"), "longitud": None}):
            html = render_to_string(UBICACION, contexto)

            self.assertIn("Sin ubicación cargada", html)
            self.assertNotIn("<a ", html)

    def test_plano_adjunto_es_opcional(self):
        base = {"latitud": Decimal("-27.45"), "longitud": Decimal("-58.98")}

        self.assertNotIn("Plano del edificio", render_to_string(UBICACION, base))
        html = render_to_string(UBICACION, {**base, "plano_url": "/media/plano.pdf"})
        self.assertIn('href="/media/plano.pdf" target="_blank" rel="noopener noreferrer"', html)
        self.assertIn("Plano del edificio", html)

    def test_escapa_el_nombre_del_plano(self):
        html = render_to_string(
            UBICACION,
            {
                "latitud": Decimal("-27.45"),
                "longitud": Decimal("-58.98"),
                "plano_url": "/p",
                "plano_nombre": "<b>x</b>",
            },
        )

        # No alcanza con que el marcado no aparezca: eso pasaria igual si el nombre
        # se descartara. Hay que ver que aparece escapado.
        self.assertNotIn("<b>x", html)
        self.assertIn("&lt;b&gt;x", html)

    def test_el_plano_se_muestra_aunque_no_haya_coordenadas(self):
        # Son dos datos independientes: un plano cargado no puede desaparecer
        # porque todavia nadie tomo las coordenadas del edificio.
        html = render_to_string(UBICACION, {"plano_url": "/p.pdf", "plano_nombre": "Plano PB"})

        self.assertIn("/p.pdf", html)
        self.assertIn("Plano PB", html)
        self.assertIn("Sin ubicacion cargada".replace("ubicacion", "ubicación"), html)
        self.assertNotIn("openstreetmap", html)

    def test_el_enlace_del_plano_avisa_que_abre_pestana_nueva(self):
        html = render_to_string(UBICACION, {"plano_url": "/p.pdf"})

        enlace = html[html.index("/p.pdf") :]
        self.assertIn("se abre en una pestaña nueva", enlace)


class LineaTiempoTest(SimpleTestCase):
    def test_dibuja_cada_evento_con_su_cuando_y_su_titulo(self):
        eventos = [
            {"cuando": "08/09 · 16:48", "titulo": "Ficha actualizada", "detalle": "sección A"},
            {"cuando": "03/09 · 19:40", "titulo": "Ingreso", "tono": "success"},
        ]
        html = render_to_string(LINEA_TIEMPO, {"eventos": eventos})

        self.assertEqual(html.count("<li "), 2)
        self.assertIn("08/09 · 16:48", html)
        self.assertIn("Ficha actualizada</strong> · sección A", html)
        self.assertIn("border-success", html)
        self.assertIn("border-brand", html)

    def test_tono_y_badge_son_opcionales(self):
        html = render_to_string(
            LINEA_TIEMPO,
            {"eventos": [{"cuando": "x", "titulo": "Novedad", "tono": "danger", "badge": "sensible"}]},
        )

        self.assertIn("border-danger", html)
        self.assertIn('badge badge-warning">sensible', html)
        self.assertNotIn("border-brand", html)

    def test_sin_eventos_muestra_el_estado_vacio(self):
        html = render_to_string(LINEA_TIEMPO, {"eventos": []})

        self.assertIn("Sin movimientos todavía", html)
        self.assertNotIn("<ol", html)

    def test_escapa_los_textos(self):
        html = render_to_string(LINEA_TIEMPO, {"eventos": [{"cuando": "<i>", "titulo": "<b>x</b>"}]})

        self.assertNotIn("<b>x", html)
        self.assertIn("&lt;b&gt;x", html)

    def test_las_fotos_van_dentro_del_evento_con_la_galeria(self):
        fotos = [{"url": "/media/x/1.jpg", "alt": "Fachada del predio", "rotulo": "fachada"}]
        eventos = [
            {"cuando": "02/02", "titulo": "8 fotos", "fotos": fotos, "total_fotos": 8},
            {"cuando": "14/08", "titulo": "Sin fotos"},
        ]
        html = render_to_string(LINEA_TIEMPO, {"eventos": eventos})

        self.assertEqual(html.count("<ol "), 1)
        primero, segundo = html.split('<li class="relative pl-5 text-sm">')[1:]
        self.assertRegex(primero, r'<div class="mt-3">\s*<ul class="grid')
        self.assertIn('src="/media/x/1.jpg"', primero)
        self.assertIn('loading="lazy"', primero)
        self.assertIn("Mostrando 1 de 8 fotos.", primero)
        self.assertNotIn("<figure", segundo)

    def test_sin_fotos_el_html_es_el_de_siempre(self):
        """`fotos` vacío o ausente no cambia ni un carácter: ni galería ni estado vacío de fotos."""

        base = [{"cuando": "x", "titulo": "Ingreso", "detalle": "plaza B-03", "badge": "nuevo", "tono": "success"}]
        sin_clave = render_to_string(LINEA_TIEMPO, {"eventos": base})
        vacia = render_to_string(LINEA_TIEMPO, {"eventos": [{**base[0], "fotos": [], "total_fotos": 0}]})

        self.assertEqual(sin_clave, vacia)
        self.assertNotIn("mt-3", sin_clave)

    def test_el_enlace_del_evento_se_dibuja_al_final_de_su_linea(self):
        """La ranura que convierte la línea de tiempo en el «historial» con acción por fila (P19)."""

        eventos = [
            {"cuando": "02/02/2026 · C. Ríos", "titulo": "8 fotos", "enlace": "/x/1/", "enlace_texto": "Ver informe"},
            {"cuando": "14/08/2025", "titulo": "6 fotos", "enlace": "/x/2/"},
        ]
        html = render_to_string(LINEA_TIEMPO, {"eventos": eventos})

        primero, segundo = html.split('<li class="relative pl-5 text-sm">')[1:]
        self.assertIn('<a href="/x/1/"', primero)
        self.assertIn("Ver informe", primero)
        # El nombre accesible no es diez veces «Ver»: le suma el metadato del evento.
        self.assertIn('<span class="sr-only"> · 02/02/2026 · C. Ríos</span>', primero)
        self.assertIn(">Ver<", segundo)

    def test_sin_enlace_el_html_es_el_de_siempre(self):
        """`enlace` ausente o vacío no cambia ni un carácter del evento."""

        base = [{"cuando": "x", "titulo": "Ingreso", "detalle": "plaza B-03", "badge": "nuevo", "tono": "success"}]
        sin_clave = render_to_string(LINEA_TIEMPO, {"eventos": base})
        vacio = render_to_string(LINEA_TIEMPO, {"eventos": [{**base[0], "enlace": "", "enlace_texto": "Ver"}]})

        self.assertEqual(sin_clave, vacio)
        self.assertNotIn("<a ", sin_clave)
        self.assertNotIn("Sin fotos", sin_clave)
        self.assertIn("</p>\n  </li>", sin_clave)

    def test_las_fotos_no_abren_el_escape_del_texto(self):
        fotos = [{"url": "", "rotulo": "<b>techo</b>"}]
        html = render_to_string(LINEA_TIEMPO, {"eventos": [{"cuando": "x", "titulo": "<i>t</i>", "fotos": fotos}]})

        self.assertNotIn("<b>techo", html)
        self.assertNotIn("<i>t", html)
        self.assertIn("&lt;b&gt;techo", html)


class FichaSeccionTest(SimpleTestCase):
    def test_formatea_el_dni_y_conserva_los_otros_valores_y_el_contexto(self):
        campos = [
            {"etiqueta": "Documento", "valor": "12345678", "formato": "dni"},
            {"etiqueta": "DNI", "valor": "12345678"},
        ]
        html = render_to_string("components/_ficha_seccion.html", {"codigo": "persona", "campos": campos})
        self.assertInHTML(
            '<div><dt class="text-xs font-semibold uppercase text-body-subtle">Documento</dt>'
            '<dd class="mt-1 text-sm text-body">12.345.678</dd></div>',
            html,
        )
        self.assertInHTML(
            '<div><dt class="text-xs font-semibold uppercase text-body-subtle">DNI</dt>'
            '<dd class="mt-1 text-sm text-body">12345678</dd></div>',
            html,
        )
        self.assertEqual(campos[0]["valor"], "12345678")

    def test_sin_formato_el_html_no_cambia_con_formato_vacio_o_desconocido(self):
        campo = {"etiqueta": "DNI", "valor": "12345678"}
        html = self._render(campos=[campo])
        for formato in ("", "otro"):
            with self.subTest(formato=formato):
                self.assertEqual(self._render(campos=[{**campo, "formato": formato}]), html)

    def _render(self, **contexto):
        return render_to_string(FICHA_SECCION, {"codigo": "salud", "titulo": "9 · Salud", **contexto})

    def test_seccion_legible_muestra_campos_avance_y_es_plegable(self):
        campos = [
            {"etiqueta": "Cobertura", "valor": "No"},
            {"etiqueta": "Ingreso mensual", "valor": "falta", "estado": "falta"},
            {"etiqueta": "Total egresos", "valor": "se calcula", "estado": "calculado"},
        ]
        html = self._render(avance=60, sensibilidad="Sensible · salud", campos=campos)

        self.assertIn("Cobertura", html)
        self.assertIn("60 %", html)
        self.assertIn('aria-valuenow="60"', html)
        self.assertIn("--avance:60%", html)
        self.assertIn("badge badge-warning", html)
        self.assertIn('aria-controls="ficha-salud"', html)
        self.assertIn('id="ficha-salud"', html)
        self.assertIn("text-fg-danger font-semibold", html)
        self.assertIn('text-body-subtle">se calcula', html)
        self.assertNotIn("nodo-ficha-bloqueada", html)

    def test_por_defecto_abierta_y_con_abierta_false_plegada(self):
        self.assertIn("{ abierta: true }", self._render())
        self.assertIn("{ abierta: false }", self._render(abierta=False))

    def test_sin_avance_no_hay_medidor_y_el_tono_warning_cambia_el_color(self):
        self.assertNotIn("progressbar", self._render())
        html = self._render(avance=20, avance_tono="warning")
        self.assertIn("bg-warning", html)
        self.assertNotIn("block h-full bg-brand", html)

    def test_sin_campos_muestra_el_texto_de_vacio(self):
        self.assertIn("Sin datos todavía.", self._render())
        self.assertIn("Plazo de 15 días", self._render(vacio_texto="Plazo de 15 días"))

    def test_completar_nombra_la_seccion(self):
        html = self._render(avance=0, completar_url="/c/")

        self.assertIn('href="/c/"', html)
        self.assertIn('completar<span class="sr-only"> 9 · Salud</span>', html)

    def test_bloqueada_no_se_oculta_y_no_muestra_datos(self):
        html = self._render(
            bloqueada=True,
            avance=80,
            sensibilidad="Sensible · psicosocial",
            sensibilidad_tono="danger",
            completa="el equipo de psicología",
            campos=[{"etiqueta": "Secreto", "valor": "no se ve"}],
        )

        self.assertIn("nodo-ficha-bloqueada", html)
        self.assertIn("9 · Salud", html)
        self.assertIn("80 %", html)
        self.assertIn("badge badge-danger", html)
        self.assertIn("Tu rol no accede a esta sección.", html)
        self.assertIn("La completa el equipo de psicología.", html)
        self.assertIn("fa-lock", html)
        self.assertNotIn("Secreto", html)
        self.assertNotIn("no se ve", html)
        self.assertNotIn("<button", html)
        self.assertNotIn("\U0001f512", html)


class RevisionReferenciaTest(TestCase):
    """La golden del arquetipo Revisión se renderiza con los datos de ejemplo del mockup P7."""

    def _contexto(self):
        return {
            "persona": {"nombre_completo": "Ramírez, Jorge Daniel", "dni": "28.556.001", "edad": 45},
            "ubicacion": "CIS N.º 3 · Pabellón A · plaza A-02",
            "estadia": {"estado": "Alojado", "reingreso": True, "ingreso": "03/09/2026 19:40", "dias": 5},
            "ficha": {
                "pendiente": True,
                "titulo": "Ficha al 45 %.",
                "texto": "Faltan Situación laboral, Red de sostén y Salud.",
                "url_completar": "/completar/",
            },
            "secciones": [
                {
                    "codigo": "a",
                    "titulo": "A · Datos personales",
                    "avance": 100,
                    "campos": [
                        {"etiqueta": "DNI", "valor": "28556001", "formato": "dni"},
                        {"etiqueta": "Oficio", "valor": "Albañilería"},
                    ],
                },
                {"codigo": "b", "titulo": "B · Situación laboral", "avance": 20, "avance_tono": "warning"},
                {
                    "codigo": "c12",
                    "titulo": "12 · Consumos y situaciones de crisis",
                    "bloqueada": True,
                    "avance": 80,
                    "sensibilidad": "Sensible · psicosocial",
                    "sensibilidad_tono": "danger",
                    "completa": "el equipo de psicología",
                },
            ],
            "eventos": [{"cuando": "08/09 · 16:48", "titulo": "Ficha actualizada"}],
            "puede_cambiar_plaza": True,
            "url_cambiar_plaza": "/plaza/",
            "puede_egresar": True,
            "url_egresar": "/egresar/",
            "puede_cargar_novedad": True,
            "url_novedad": "/novedad/",
            "n_movimientos": 6,
            "n_novedades": 3,
            "n_adjuntos": 2,
            "adjuntos": [{"nombre": "DNI frente y dorso.pdf", "url": "/a/1", "fecha": "03/09"}],
            "otras_estadias": [{"estado": "En seguimiento", "detalle": "Mírame/Vedia desde 20/03/2026"}],
        }

    def _html(self, **cambios):
        contexto = {**self._contexto(), **cambios}
        request = RequestFactory().get("/")
        request.user = User.objects.create_user(username="u", password="x", is_superuser=True)
        return render_to_string(REVISION, contexto, request=request)

    def test_dibuja_identidad_secciones_linea_de_tiempo_y_acciones(self):
        html = self._html()

        self.assertIn("Ramírez, Jorge Daniel", html)
        self.assertIn("CIS N.º 3 · Pabellón A · plaza A-02", html)
        self.assertIn("Reingreso", html)
        self.assertIn("Ficha al 45 %.", html)
        self.assertIn("Completar ahora", html)
        self.assertIn("A · Datos personales", html)
        self.assertIn("nodo-ficha-bloqueada", html)
        self.assertIn("Ficha actualizada", html)
        self.assertIn("Cambiar plaza", html)
        self.assertIn("Egresar", html)

    def test_las_acciones_dependen_de_las_capacidades_que_trae_la_vista(self):
        html = self._html(puede_egresar=False, puede_cargar_novedad=False)

        self.assertNotIn("Egresar", html)
        self.assertNotIn("/novedad/", html)
        self.assertIn("Cambiar plaza", html)

    def test_sin_ficha_pendiente_no_hay_alerta(self):
        self.assertNotIn("Completar ahora", self._html(ficha={"pendiente": False}))

    def test_la_seccion_bloqueada_sigue_estando_y_muestra_quien_la_completa(self):
        html = self._html()

        self.assertIn("12 · Consumos y situaciones de crisis", html)
        self.assertIn("La completa el equipo de psicología.", html)

    def test_solapas_con_aria_y_contadores(self):
        html = self._html()

        for tab in ("ficha", "movimientos", "novedades", "adjuntos", "historial"):
            self.assertIn(f'id="tab-{tab}" aria-controls="panel-{tab}"', html)
            self.assertIn(f'id="panel-{tab}" aria-labelledby="tab-{tab}"', html)
        self.assertIn('role="tablist" aria-label="Secciones de la estadía"', html)

    def test_sin_emoji(self):
        html = self._html()

        self.assertNotIn("\U0001f512", html)
        self.assertNotIn("\U0001f4ce", html)


class FormErroresTest(SimpleTestCase):
    """FE-08: los errores no de campo dejan de ser invisibles.

    `unique_together` y los `clean()` de form rechazan el conjunto, no un control:
    sin esta pieza la pantalla vuelve igual, con todos los `field.errors` vacíos.
    """

    class _Duplicado(forms.Form):
        nombre = forms.CharField()

        def clean(self):
            raise forms.ValidationError("Ya existe una localidad con ese nombre en ese municipio.")

    def _render(self, form, **contexto):
        return render_to_string(FORM_ERRORES, {"form": form, **contexto})

    def test_sin_errores_no_se_muestra(self):
        self.assertEqual(self._render(self._Duplicado()).strip(), "")

    def test_sin_form_no_se_muestra(self):
        self.assertEqual(self._render(None).strip(), "")

    def test_solo_errores_de_campo_no_se_muestra(self):
        form = forms.Form({}, initial={})
        form.fields["nombre"] = forms.CharField()
        form.is_valid()

        self.assertEqual(self._render(form).strip(), "")

    def test_muestra_cada_error_con_role_alert(self):
        form = self._Duplicado({"nombre": "Barranqueras"})
        form.is_valid()

        html = self._render(form)

        self.assertIn(
            'class="mb-4 rounded-lg bg-danger-soft border border-danger-subtle p-4 text-sm" role="alert"', html
        )
        self.assertIn('<strong class="text-heading">Revisá el formulario</strong>', html)
        self.assertIn(
            '<p class="text-body mt-1">Ya existe una localidad con ese nombre en ese municipio.</p>',
            html,
        )
        # El `<ul class="errorlist">` de Django no tiene estilo en el backoffice.
        self.assertNotIn("errorlist", html)

    def test_titulo_propio(self):
        form = self._Duplicado({"nombre": "x"})
        form.is_valid()

        self.assertIn("Revisá el domicilio", self._render(form, titulo="Revisá el domicilio"))

    def test_escapa(self):
        class Inyectado(forms.Form):
            def clean(self):
                raise forms.ValidationError("<img src=x onerror=alert(1)>")

        form = Inyectado({})
        form.is_valid()

        html = self._render(form)

        self.assertNotIn("<img", html)
        self.assertIn("&lt;img", html)


class HayFiltrosTest(SimpleTestCase):
    def test_querydict(self):
        self.assertFalse(hay_filtros(QueryDict("")))
        self.assertFalse(hay_filtros(QueryDict("page=2")))
        self.assertFalse(hay_filtros(QueryDict("page=2&tab=casos"), "page,tab"))
        self.assertFalse(hay_filtros(QueryDict("fecha=&segmento=%20")))
        self.assertTrue(hay_filtros(QueryDict("segmento=3")))
        self.assertTrue(hay_filtros(QueryDict("page=2&tab=casos"), "page"))
        self.assertTrue(hay_filtros(QueryDict("estado=&estado=activas")))

    def test_dict_y_none(self):
        self.assertFalse(hay_filtros(None))
        self.assertFalse(hay_filtros({"page": "2", "q": ""}))
        self.assertTrue(hay_filtros({"q": "ana"}))
        self.assertTrue(hay_filtros({"q": ["", "ana"]}))

    def test_desde_plantilla(self):
        plantilla = Template('{% load nodo_ui %}{% if request.GET|hay_filtros:"page,tab" %}SI{% else %}NO{% endif %}')

        def render(query):
            return plantilla.render(Context({"request": RequestFactory().get(f"/?{query}")}))

        self.assertEqual(render("page=2&tab=x"), "NO")
        self.assertEqual(render("page=2&segmento=1"), "SI")


class ReporteEstadoVacioTest(TestCase):
    """Consumidor: el estado vacío del reporte distingue «sin datos» de «los filtros no traen nada»."""

    def setUp(self):
        # RED-56: los guards de Becas fallan cerrados sin el Programa BECAS
        # sembrado; el escenario lo incluye, como en producción.
        call_command("seed_becas", stdout=StringIO())
        self.client.force_login(User.objects.create_superuser("admin-piezas", password="x"))
        self.url = reverse("becas:reporte_detalle", args=["avance"])

    def test_sin_filtros(self):
        resp = self.client.get(self.url)

        self.assertContains(resp, "Sin resultados")
        self.assertContains(resp, "fa-chart-column text-5xl")
        self.assertNotContains(resp, "btn-nodo btn-tertiary btn-base mt-2")

    def test_con_filtros_ofrece_limpiarlos(self):
        resp = self.client.get(self.url, {"estado": "activas"})

        self.assertContains(resp, "Ningún dato coincide con los filtros")
        self.assertContains(resp, f'href="{self.url}" class="btn-nodo btn-tertiary btn-base mt-2"')


class BtnFitTest(SimpleTestCase):
    """C-15: btn-fit anula solo el min-width y los tamaños del sistema no cambian."""

    def setUp(self):
        crudo = (RAIZ / "static/custom/css/nodo-buttons.css").read_text(encoding="utf-8")
        # Sin los comentarios: los de esta hoja citan selectores y reglas para explicar
        # por que estan donde estan, y una busqueda por texto los encuentra antes que al
        # codigo real. Ya paso: `@media (pointer: coarse)` y `.btn-nodo.btn-fit` aparecen
        # los dos en el comentario de `btn-fit`.
        self.css = re.sub(r"/\*.*?\*/", "", crudo, flags=re.S)

    def test_los_min_width_por_tamano_siguen_intactos(self):
        esperado = {"xs": 128, "sm": 143, "base": 151, "lg": 170, "xl": 186}
        for tam, ancho in esperado.items():
            bloque = re.search(r"\.btn-%s \{([^}]*)\}" % tam, self.css).group(1)
            self.assertIn(f"min-width: {ancho}px;", bloque)

    def test_btn_fit_solo_anula_el_min_width_y_va_despues_de_todos_los_tamanos(self):
        bloque = re.search(r"\.btn-fit \{([^}]*)\}", self.css).group(1)
        # `auto`, no `0`: el boton no lleva `nowrap` ni `flex-shrink: 0`, asi que un 0 lo
        # dejaria comprimirse por debajo de su texto en un header flex sin `flex-wrap`.
        self.assertEqual([d.strip() for d in bloque.split(";") if d.strip()], ["min-width: auto"])

        # Contra TODOS los tamanos, no solo contra .btn-xl: si manana se agrega uno
        # despues de btn-fit, la variante deja de ganarle y el test tiene que avisar.
        ultimo = max(self.css.index(".btn-%s {" % t) for t in ("xs", "sm", "base", "lg", "xl"))
        self.assertGreater(self.css.index(".btn-fit {"), ultimo)

    def test_btn_fit_no_le_gana_al_area_tactil(self):
        # El bloque `pointer: coarse` impone 44 px a proposito (WCAG 2.5.8) y va despues:
        # por eso btn-fit no sube su especificidad a `.btn-nodo.btn-fit`.
        self.assertGreater(self.css.index("@media (pointer: coarse)"), self.css.index(".btn-fit {"))
        self.assertNotIn(".btn-nodo.btn-fit", self.css)


class StepperTest(SimpleTestCase):
    """Indicador de pasos del arquetipo Wizard (``components/_stepper.html``)."""

    PASOS = [
        {"etiqueta": "Identidad", "url": "/paso/1/"},
        {"etiqueta": "Naturaleza", "url": "/paso/2/"},
        {"etiqueta": "Capacidades", "url": "/paso/3/"},
        {"etiqueta": "Confirmación", "url": "/paso/4/"},
    ]

    def _render(self, paso_actual, pasos=None):
        return render_to_string(STEPPER, {"pasos": self.PASOS if pasos is None else pasos, "paso_actual": paso_actual})

    def test_marca_hecho_actual_y_pendiente_segun_el_paso(self):
        html = self._render(3)
        self.assertEqual(html.count("nodo-step--hecho"), 2)
        self.assertEqual(html.count("nodo-step--actual"), 1)
        self.assertEqual(html.count("nodo-step--pendiente"), 1)

    def test_el_paso_actual_se_anuncia_y_no_depende_del_color(self):
        html = self._render(2)
        self.assertEqual(html.count('aria-current="step"'), 1)
        self.assertIn('<span class="sr-only">Paso actual: </span>Naturaleza', html)
        self.assertIn('<span class="sr-only">Paso completado: </span>Identidad', html)
        self.assertIn('<span class="sr-only">Paso pendiente: </span>Capacidades', html)
        # El hecho lleva tilde y el resto el numero: el estado se ve sin distinguir colores.
        self.assertIn("fa-check", html)
        self.assertIn(">3</span>", html)

    def test_solo_los_pasos_hechos_son_links(self):
        html = self._render(3)
        self.assertIn('href="/paso/1/"', html)
        self.assertIn('href="/paso/2/"', html)
        self.assertNotIn('href="/paso/3/"', html)
        self.assertNotIn('href="/paso/4/"', html)

    def test_un_paso_hecho_sin_url_no_es_link(self):
        html = self._render(2, pasos=[{"etiqueta": "Uno"}, {"etiqueta": "Dos"}])
        self.assertNotIn("<a ", html)
        self.assertIn("Uno", html)

    def test_es_una_lista_ordenada_con_nombre_accesible(self):
        html = self._render(1)
        self.assertIn('<nav aria-label="Pasos del asistente">', html)
        self.assertIn('<ol class="nodo-stepper">', html)

    def test_el_shell_carga_la_hoja_y_define_el_circulo_y_el_conector(self):
        base = (RAIZ / "templates/includes/base.html").read_text(encoding="utf-8")
        self.assertIn("custom/css/nodo-stepper.css", base)
        css = re.sub(
            r"/\*.*?\*/", "", (RAIZ / "static/custom/css/nodo-stepper.css").read_text(encoding="utf-8"), flags=re.S
        )
        self.assertIn("width: 28px;", re.search(r"\.nodo-step__circle \{([^}]*)\}", css).group(1))
        self.assertIn("width: 56px;", re.search(r"\.nodo-step \+ \.nodo-step::before \{([^}]*)\}", css).group(1))


class MenuFilaTest(SimpleTestCase):
    """C-9: el menu de fila anuncia que controla, nace cerrado y explica lo deshabilitado."""

    ITEM = '{% include "components/_menu_fila_item.html" with '

    def _render(self, cuerpo, argumentos='id="cis-3" etiqueta="Acciones de CIS N.º 3"', **contexto):
        plantilla = "{% load nodo_ui %}{% menu_fila " + argumentos + " %}" + cuerpo + "{% endmenu_fila %}"
        return Template(plantilla).render(Context(contexto))

    def test_el_boton_nombra_el_registro_y_apunta_al_menu(self):
        html = self._render(self.ITEM + 'texto="Ver ficha" url="/ficha/" only %}')

        self.assertIn('aria-label="Acciones de CIS N.º 3"', html)
        self.assertIn('aria-haspopup="menu"', html)
        self.assertIn('aria-expanded="false"', html)
        self.assertIn('aria-controls="menu-fila-cis-3"', html)
        self.assertIn('id="menu-fila-cis-3" role="menu"', html)
        self.assertIn("data-menu-fila-trigger", html)
        self.assertIn('class="nodo-icon-btn nodo-menu-fila__trigger"', html)

    def test_el_menu_nace_cerrado(self):
        html = self._render(self.ITEM + 'texto="Ver ficha" url="/ficha/" only %}')

        self.assertRegex(html, r'role="menu" aria-label="[^"]*" hidden>')

    def test_el_icono_es_decorativo_y_no_hay_estilos_en_linea(self):
        html = self._render(self.ITEM + 'texto="Ver ficha" icono="fa-eye" url="/ficha/" only %}')

        self.assertIn('<i class="fas fa-ellipsis-vertical" aria-hidden="true"></i>', html)
        self.assertIn('<i class="fas fa-eye nodo-menu-fila__icono" aria-hidden="true"></i>', html)
        self.assertNotIn("style=", html)

    def test_item_con_url_es_un_enlace_menuitem(self):
        html = self._render(self.ITEM + 'texto="Ver ficha" url=url only %}', url="/ficha/?a=1&b=2")

        self.assertIn('<a href="/ficha/?a=1&amp;b=2" role="menuitem" class="nodo-menu-fila__item">', html)

    def test_item_deshabilitado_se_ve_con_su_motivo_y_no_lleva_destino(self):
        html = self._render(
            self.ITEM
            + 'texto="Reasignar" url="/reasignar/" confirm_url="/x/" motivo="Solo con relevamiento vencido" only %}'
        )

        self.assertIn('role="menuitem" class="nodo-menu-fila__item" aria-disabled="true"', html)
        self.assertIn('Reasignar<span class="nodo-menu-fila__motivo">Solo con relevamiento vencido</span>', html)
        self.assertNotIn("/reasignar/", html)
        self.assertNotIn("data-confirm-url", html)
        # aria-disabled, no disabled: tiene que seguir enfocable para que se anuncie el motivo.
        self.assertNotRegex(html, r"<button[^>]*\sdisabled[\s>]")

    def test_item_que_confirma_usa_data_confirm_url(self):
        html = self._render(
            self.ITEM + 'texto="Dar de baja" peligro=True confirm_url="/baja/" confirm_title="¿Dar de baja?" '
            'confirm_text="Se puede revertir." confirm_ok="Sí, dar de baja" only %}'
        )

        self.assertIn('data-confirm-url="/baja/"', html)
        self.assertIn('data-confirm-title="¿Dar de baja?"', html)
        self.assertIn('data-confirm-ok="Sí, dar de baja"', html)
        self.assertIn('data-confirm-danger="true"', html)
        self.assertIn("nodo-menu-fila__item--danger", html)

    def test_item_sin_destino_ni_motivo_no_se_dibuja(self):
        html = self._render(self.ITEM + 'texto="Nada" only %}')

        self.assertEqual(html.strip(), "")

    def test_sin_items_no_se_dibuja_ni_el_boton(self):
        self.assertEqual(self._render("   {% if False %}x{% endif %}  ").strip(), "")

    def test_el_id_se_sanea_para_aria_controls(self):
        html = self._render(self.ITEM + 'texto="Ver" url="/x/" only %}', argumentos='id="cama 5/a" etiqueta="Acciones"')

        self.assertIn('aria-controls="menu-fila-cama-5-a"', html)
        self.assertIn('id="menu-fila-cama-5-a"', html)

    def test_escapa_la_etiqueta_y_los_textos(self):
        html = self._render(
            self.ITEM + "texto=texto motivo=motivo only %}",
            argumentos="id=1 etiqueta=etiqueta",
            etiqueta='<b>"x"</b>',
            texto="<i>t</i>",
            motivo="<u>m</u>",
        )

        self.assertNotIn("<b>", html)
        self.assertNotIn("<i>t", html)
        self.assertNotIn("<u>", html)
        self.assertIn("&lt;b&gt;&quot;x&quot;&lt;/b&gt;", html)

    def test_exige_id_y_etiqueta_y_rechaza_el_resto(self):
        for argumentos in ('etiqueta="a"', 'id="a"', 'id="a" etiqueta="b" extra="c"', 'id="a" etiqueta="b" suelto'):
            with self.subTest(argumentos=argumentos), self.assertRaises(template.TemplateSyntaxError):
                self._render("x", argumentos=argumentos)

    def test_el_shell_carga_la_hoja_y_el_script(self):
        base = (RAIZ / "templates/includes/base.html").read_text(encoding="utf-8")

        self.assertIn("custom/css/nodo-menu-fila.css", base)
        self.assertIn("custom/js/nodo-menu-fila.js", base)

    def test_el_script_cubre_el_contrato_de_teclado(self):
        js = (RAIZ / "static/custom/js/nodo-menu-fila.js").read_text(encoding="utf-8")

        for clave in ("'Escape'", "'Tab'", "'ArrowDown'", "'ArrowUp'", "'Home'", "'End'", "aria-expanded"):
            self.assertIn(clave, js)
        self.assertNotIn("confirm(", js)

    def test_el_menu_no_lo_recorta_el_contenedor_de_la_tabla(self):
        css = re.sub(
            r"/\*.*?\*/", "", (RAIZ / "static/custom/css/nodo-menu-fila.css").read_text(encoding="utf-8"), flags=re.S
        )
        bloque = re.search(r"\.nodo-menu-fila__menu \{([^}]*)\}", css).group(1)

        self.assertIn("position: fixed;", bloque)
        self.assertIn(".nodo-menu-fila__menu[hidden]", css)


# Pantallas autorizadas a usar el hero: SOLO la de inicio y los tableros de programa (C-3). Hoy
# ninguna lo usa (el Inicio lo retiró FE-22); la primera en incorporarlo se agrega acá, y esa línea
# es lo que un revisor tiene que ver: usarlo en otra pantalla es rechazable citando el agente.
PANTALLAS_CON_HERO = frozenset()
# Pantallas autorizadas a usar el hero: la lista vive en scripts/design_audit.py (HERO_PANTALLAS), que
# la hace cumplir como regla P1 HEROFUERA. Esta prueba la contrasta contra los templates reales.
_SPEC_AUDIT = importlib.util.spec_from_file_location("design_audit_hero", RAIZ / "scripts" / "design_audit.py")
_design_audit = importlib.util.module_from_spec(_SPEC_AUDIT)
_SPEC_AUDIT.loader.exec_module(_design_audit)
PANTALLAS_CON_HERO = _design_audit.HERO_PANTALLAS


class HeroInicioTest(SimpleTestCase):
    """C-3: el hero es de inicio de programa y de ningun otro lado."""

    def _render(self, argumentos, cuerpo="", **contexto):
        plantilla = "{% load nodo_ui %}{% hero_inicio " + argumentos + " %}" + cuerpo + "{% endhero_inicio %}"
        return Template(plantilla).render(Context(contexto))

    def test_dibuja_titulo_eyebrow_bajada_y_accion(self):
        html = self._render(
            'titulo="Red de dispositivos" eyebrow="Programa Dispositivos" accion_url="/instituciones/" '
            'accion_texto="Ver instituciones" accion_icono="fa-building"',
            "{% bajada %}18 instituciones, <strong>3</strong> críticas.{% endbajada %}",
        )

        self.assertIn('<div class="nodo-hero">', html)
        self.assertIn('<div class="nodo-hero__eyebrow">Programa Dispositivos</div>', html)
        self.assertIn('<h1 class="nodo-hero__titulo">Red de dispositivos</h1>', html)
        self.assertIn('<p class="nodo-hero__bajada">18 instituciones, <strong>3</strong> críticas.</p>', html)
        self.assertIn('<a href="/instituciones/" class="nodo-hero__accion">', html)
        self.assertIn('<i class="fas fa-building" aria-hidden="true"></i> Ver instituciones', html)

    def test_solo_el_titulo_es_obligatorio(self):
        html = self._render('titulo="Inicio"')

        self.assertIn('<h1 class="nodo-hero__titulo">Inicio</h1>', html)
        for ausente in ("eyebrow", "bajada", "nodo-hero__accion"):
            self.assertNotIn(ausente, html.replace("nodo-hero__titulo", ""))

    def test_la_accion_pide_url_y_texto(self):
        self.assertNotIn("nodo-hero__accion", self._render('titulo="x" accion_url="/a/"'))
        self.assertNotIn("nodo-hero__accion", self._render('titulo="x" accion_texto="Ir"'))

    def test_la_bajada_como_argumento_se_escapa_y_el_bloque_manda(self):
        html = self._render("titulo=t bajada=b", t="<i>t</i>", b="<u>b</u>")
        self.assertIn("&lt;u&gt;b&lt;/u&gt;", html)
        self.assertIn("&lt;i&gt;t&lt;/i&gt;", html)

        html = self._render('titulo="x" bajada="no"', "{% bajada %}gana{% endbajada %}")
        self.assertIn(">gana</p>", html)
        self.assertNotIn("no</p>", html)

    def test_el_bloque_bajada_escapa_las_variables(self):
        html = self._render('titulo="x"', "{% bajada %}{{ nombre }}{% endbajada %}", nombre="<script>")

        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>", html)

    def test_un_bloque_bajada_en_blanco_no_deja_parrafo(self):
        self.assertNotIn("nodo-hero__bajada", self._render('titulo="x"', "{% bajada %}   {% endbajada %}"))

    def test_sintaxis_estricta(self):
        casos = {
            "sin titulo": ('eyebrow="a"', ""),
            "argumento desconocido": ('titulo="a" color="rojo"', ""),
            "argumento suelto": ('titulo="a" suelto', ""),
            "cuerpo que no es bajada": ('titulo="a"', "<p>otro</p>"),
            "dos bajadas": ('titulo="a"', "{% bajada %}1{% endbajada %}{% bajada %}2{% endbajada %}"),
        }
        for nombre, (argumentos, cuerpo) in casos.items():
            with self.subTest(nombre), self.assertRaises(template.TemplateSyntaxError):
                self._render(argumentos, cuerpo)

    def test_sin_estilos_en_linea_ni_hex(self):
        html = self._render('titulo="x" accion_url="/a/" accion_texto="Ir"')
        css = (RAIZ / "static/custom/css/nodo-hero.css").read_text(encoding="utf-8")

        self.assertNotIn("style=", html)
        self.assertNotRegex(css, r"#[0-9a-fA-F]{3,8}\b")

    def test_el_gradiente_sale_del_token_y_la_hoja_esta_en_el_shell(self):
        css = (RAIZ / "static/custom/css/nodo-hero.css").read_text(encoding="utf-8")
        base = (RAIZ / "templates/includes/base.html").read_text(encoding="utf-8")

        self.assertIn("background: var(--gradient-brand);", css)
        self.assertIn("custom/css/nodo-hero.css", base)

    def test_solo_las_pantallas_autorizadas_lo_usan(self):
        """El alcance escrito en el agente, hecho prueba: ni el tag ni las clases fuera de la lista."""
        usos = {}
        for ruta in sorted(RAIZ.glob("**/templates/**/*.html")):
            rel = ruta.relative_to(RAIZ)
            if {"node_modules", "docs", ".claude", "worktrees"} & set(rel.parts) or ruta.name == "_hero_inicio.html":
                continue
            if _design_audit.HERO_RE.search(ruta.read_text(encoding="utf-8")):
                usos[rel.as_posix()] = True

        self.assertEqual(
            set(usos) - PANTALLAS_CON_HERO,
            set(),
            "El hero es solo de la pantalla de inicio y de los tableros de programa "
            "(.claude/design/componentes/hero_inicio.md). Otra pantalla usa {% page_header %}.",
        )
        self.assertEqual(PANTALLAS_CON_HERO - set(usos), set(), "pantalla autorizada que ya no usa el hero")

    def test_el_inicio_de_hoy_sigue_sin_hero(self):
        """FE-22 retiró el hero del Inicio; esta pieza no lo devuelve sola."""
        inicio = (RAIZ / "templates/inicio.html").read_text(encoding="utf-8")

        self.assertNotIn("hero_inicio", inicio)
        self.assertIn("{% page_header", inicio)
