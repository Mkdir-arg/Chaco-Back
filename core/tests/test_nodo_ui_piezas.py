"""Piezas reutilizables del backoffice: paginación, tarjeta de número, estado vacío,
alerta inline y el filtro ``hay_filtros`` (W2-C9b, CMP-11/22/23, ALR-14/15)."""

from io import StringIO

from django.contrib.auth.models import AnonymousUser, User
from django.core.management import call_command
from django.core.paginator import Paginator
from django.http import QueryDict
from django.template import Context, Template
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from core.templatetags.nodo_ui import hay_filtros

PAGINACION = "components/_paginacion.html"
STAT = "components/_stat_card.html"
VACIO = "components/_estado_vacio.html"
ALERTA = "components/_alerta.html"


def _pagina(total, numero=1, por_pagina=10):
    return Paginator(list(range(total)), por_pagina).get_page(numero)


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
