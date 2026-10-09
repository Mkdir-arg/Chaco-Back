"""Piezas reutilizables del backoffice: paginación, tarjeta de número, estado vacío,
alerta inline, errores no de campo y el filtro ``hay_filtros``
(W2-C9b, CMP-11/22/23, ALR-14/15, FE-08)."""

import re
from io import StringIO
from pathlib import Path

from django import forms
from django.contrib.auth.models import AnonymousUser, User
from django.core.management import call_command
from django.core.paginator import Paginator
from django.http import QueryDict
from django.template import Context, Template
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from core.templatetags.nodo_ui import hay_filtros, sin_parametros

PAGINACION = "components/_paginacion.html"
STAT = "components/_stat_card.html"
VACIO = "components/_estado_vacio.html"
ALERTA = "components/_alerta.html"
FORM_ERRORES = "components/_form_errores.html"


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

    def test_escapa(self):
        html = render_to_string(ALERTA, {"tono": "danger", "titulo": "<script>", "texto": "<img src=x>"})

        self.assertNotIn("<script>", html)
        self.assertNotIn("<img", html)


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
