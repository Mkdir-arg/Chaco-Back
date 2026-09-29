"""Encabezado de página reutilizable (``{% page_header %}``) y migas de Becas."""

from datetime import date
from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.template import Context, Template, TemplateSyntaxError
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from core import rbac
from programas.management.commands.seed_becas import ROL_ADMIN
from programas.models import Convocatoria, ProgramaSiis, Relevamiento, Segmento, Subsegmento
from programas.templatetags.becas_extras import becas_migas

MIGAS_3 = [
    {"label": "Programas", "url": "/p/"},
    {"label": "Programa X", "url": "/p/1/"},
    {"label": "Segmento Y", "url": None},
]


def render(fuente, **contexto):
    return Template("{% load nodo_ui %}" + fuente).render(Context(contexto))


class PageHeaderTagTests(SimpleTestCase):
    def test_renderiza_h1_bajada_volver_y_acciones_con_el_canon(self):
        html = render(
            '{% page_header titulo=t bajada=b volver_url="/volver/" volver_label="convocatorias" %}'
            '<span class="badge badge-success badge-dot">Activa</span>{% endpage_header %}',
            t="Becas 2026",
            b="Segmento A",
        )
        self.assertInHTML(
            '<h1 class="text-3xl font-extrabold text-heading tracking-tight">Becas 2026</h1>',
            html,
        )
        self.assertInHTML('<p class="text-sm text-body-subtle mt-1">Segmento A</p>', html)
        self.assertInHTML(
            '<a href="/volver/" class="btn-tertiary btn-back-circle" aria-label="Volver a convocatorias">'
            '<i class="fas fa-arrow-left" aria-hidden="true"></i></a>',
            html,
        )
        self.assertInHTML(
            '<div class="flex items-center gap-2 flex-wrap">'
            '<span class="badge badge-success badge-dot">Activa</span></div>',
            html,
        )
        self.assertIn('class="flex items-start justify-between gap-4 flex-wrap"', html)
        self.assertIn('class="flex items-start gap-3 min-w-0"', html)

    def test_sin_volver_bajada_ni_acciones_no_deja_huecos(self):
        html = render("{% page_header titulo='Solo título' %}   {% endpage_header %}")
        self.assertIn("Solo título", html)
        self.assertNotIn("btn-back-circle", html)
        self.assertNotIn("<p", html)
        self.assertNotIn("items-center gap-2 flex-wrap", html)

    def test_migas_solo_con_tres_niveles_o_mas(self):
        con_dos = render("{% page_header titulo='X' migas=m %}{% endpage_header %}", m=MIGAS_3[:2])
        self.assertNotIn("<nav", con_dos)

        html = render("{% page_header titulo='X' migas=m %}{% endpage_header %}", m=MIGAS_3)
        self.assertIn('<nav aria-label="Migas">', html)
        self.assertIn('<ol class="flex items-center gap-1.5 flex-wrap text-xs text-body-subtle">', html)
        self.assertInHTML('<a href="/p/" class="text-fg-brand hover:underline">Programas</a>', html)
        self.assertInHTML('<a href="/p/1/" class="text-fg-brand hover:underline">Programa X</a>', html)
        self.assertInHTML('<li aria-current="page" class="font-semibold text-body">Segmento Y</li>', html)
        self.assertEqual(html.count('<li aria-hidden="true">/</li>'), 2)

    def test_miga_intermedia_sin_url_va_como_texto(self):
        migas = [{"label": "Programas", "url": None}] + MIGAS_3[1:]
        html = render("{% page_header titulo='X' migas=m %}{% endpage_header %}", m=migas)
        self.assertInHTML("<li>Programas</li>", html)

    def test_escapa_titulo_bajada_y_migas(self):
        malo = "<script>alert(1)</script>"
        html = render(
            "{% page_header titulo=t bajada=t volver_url='/v/' volver_label=t migas=m %}{% endpage_header %}",
            t=malo,
            m=[{"label": malo, "url": "/a/"}, {"label": malo, "url": None}, {"label": malo, "url": None}],
        )
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)

    def test_bajada_con_html_solo_si_la_plantilla_la_marca(self):
        fragmento = '<a href="/s/">Segmento</a>'
        escapada = render("{% page_header titulo='X' bajada=b %}{% endpage_header %}", b=fragmento)
        self.assertIn("&lt;a href=", escapada)
        marcada = render("{% page_header titulo='X' bajada=b|safe %}{% endpage_header %}", b=fragmento)
        self.assertInHTML('<p class="text-sm text-body-subtle mt-1"><a href="/s/">Segmento</a></p>', marcada)

    def test_bloque_bajada_escapa_variables_y_conserva_el_html_de_la_plantilla(self):
        html = render(
            "{% page_header titulo='X' bajada='ignorada' %}"
            '{% bajada %}Segmento: <a href="/s/">{{ nombre }}</a>{% endbajada %}'
            "<span>acción</span>"
            "{% endpage_header %}",
            nombre="<b>Seg</b>",
        )
        self.assertInHTML(
            '<p class="text-sm text-body-subtle mt-1">Segmento: <a href="/s/">&lt;b&gt;Seg&lt;/b&gt;</a></p>',
            html,
        )
        self.assertNotIn("ignorada", html)
        # La bajada no se repite entre las acciones.
        self.assertEqual(html.count("Segmento:"), 1)
        self.assertInHTML('<div class="flex items-center gap-2 flex-wrap"><span>acción</span></div>', html)

    def test_errores_de_sintaxis(self):
        for fuente in (
            "{% page_header %}{% endpage_header %}",
            "{% page_header titulo='X' color='rojo' %}{% endpage_header %}",
            "{% page_header 'X' %}{% endpage_header %}",
            "{% page_header titulo='X' %}{% bajada %}a{% endbajada %}{% bajada %}b{% endbajada %}{% endpage_header %}",
        ):
            with self.subTest(fuente=fuente), self.assertRaises(TemplateSyntaxError):
                render(fuente)


class _BecasBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_becas", stdout=StringIO())
        cls.admin = User.objects.create_user("admin_migas", password="x")
        cls.admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        cls.programa = ProgramaSiis.objects.create(nombre="Becas Terciarias", siis_programa_id=4242)
        cls.segmento = Segmento.objects.create(programa=cls.programa, nombre="Terciarios", cupo_maximo=100)
        cls.subsegmento = Subsegmento.objects.create(segmento=cls.segmento, nombre="Resistencia Norte", cupo_maximo=50)
        cls.convocatoria = Convocatoria.objects.create(
            nombre="Convocatoria 2026",
            segmento=cls.segmento,
            subsegmento=cls.subsegmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )

    def contexto(self, user):
        request = RequestFactory().get("/")
        request.user = user
        return {"request": request}


class BecasMigasTests(_BecasBase):
    def test_ruta_completa_de_una_convocatoria(self):
        migas = becas_migas(self.contexto(self.admin), self.convocatoria)
        self.assertEqual(
            migas,
            [
                {"label": "Programas", "url": reverse("becas:programas")},
                {"label": "Becas Terciarias", "url": reverse("becas:programa_detalle", args=[self.programa.pk])},
                {"label": "Terciarios", "url": reverse("becas:segmento_detalle", args=[self.segmento.pk])},
                {
                    "label": "Resistencia Norte",
                    "url": reverse("becas:subsegmento_detalle", args=[self.subsegmento.pk]),
                },
                {"label": "Convocatoria 2026", "url": None},
            ],
        )

    def test_no_consulta_la_base_si_el_objeto_trae_sus_relaciones(self):
        conv = Convocatoria.objects.select_related("segmento__programa", "subsegmento").get(pk=self.convocatoria.pk)
        user = User.objects.get(pk=self.admin.pk)
        rbac.puede(user, "becas.segmento.ver")  # la request ya evaluó capacidades
        contexto = self.contexto(user)
        with self.assertNumQueries(0):
            migas = becas_migas(contexto, conv)
        self.assertEqual(len(migas), 5)

    def test_sin_subsegmento_y_con_relevamiento(self):
        conv = Convocatoria.objects.create(
            nombre="Sin sub", segmento=self.segmento, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )
        rel = Relevamiento.objects.create(
            convocatoria=conv, territorial=self.admin, fecha_asignada=date(2026, 6, 1), zona="Z"
        )
        migas = becas_migas(self.contexto(self.admin), rel)
        self.assertEqual(
            [m["label"] for m in migas], ["Programas", "Becas Terciarias", "Terciarios", "Sin sub", rel.nombre]
        )
        self.assertEqual(migas[3]["url"], reverse("becas:convocatoria_detalle", args=[conv.pk]))
        self.assertIsNone(migas[-1]["url"])

    def test_actual_agrega_la_pantalla_y_enlaza_el_objeto(self):
        migas = becas_migas(self.contexto(self.admin), self.segmento, actual="Cupo y beneficiarios")
        self.assertEqual([m["label"] for m in migas][-2:], ["Terciarios", "Cupo y beneficiarios"])
        self.assertEqual(migas[-2]["url"], reverse("becas:segmento_detalle", args=[self.segmento.pk]))
        self.assertIsNone(migas[-1]["url"])

    def test_segmento_historico_sin_programa(self):
        seg = Segmento.objects.create(nombre="Histórico", cupo_maximo=10)
        self.assertEqual([m["label"] for m in becas_migas(self.contexto(self.admin), seg)], ["Programas", "Histórico"])

    def test_sin_capacidad_no_hay_enlace(self):
        sin_roles = User.objects.create_user("sin_roles", password="x")
        migas = becas_migas(self.contexto(sin_roles), self.convocatoria)
        self.assertEqual([m["url"] for m in migas], [None] * 5)

    def test_objeto_desconocido(self):
        with self.assertRaises(TypeError):
            becas_migas(self.contexto(self.admin), self.admin)


class ConvocatoriaDetailHeaderTests(_BecasBase):
    def test_encabezado_mantiene_titulo_bajada_badges_y_acciones_y_suma_migas(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("becas:convocatoria_detalle", args=[self.convocatoria.pk]))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertEqual(html.count("<h1"), 1)
        self.assertInHTML(
            '<h1 class="text-3xl font-extrabold text-heading tracking-tight">Convocatoria 2026</h1>',
            html,
        )
        self.assertInHTML('<p class="text-sm text-body-subtle mt-1">Terciarios · Resistencia Norte</p>', html)
        self.assertInHTML(
            f'<a href="{reverse("becas:convocatorias")}" class="btn-tertiary btn-back-circle"'
            ' aria-label="Volver a convocatorias"><i class="fas fa-arrow-left" aria-hidden="true"></i></a>',
            html,
        )
        self.assertInHTML('<span class="badge badge-success badge-dot">Activa</span>', html)
        pausa = reverse("becas:gestionar_pausa", args=["convocatoria", self.convocatoria.pk])
        self.assertInHTML(f'<a href="{pausa}" class="btn-nodo btn-danger btn-sm">Pausar</a>', html)
        self.assertIn('<nav aria-label="Migas">', html)
        self.assertInHTML('<li aria-current="page" class="font-semibold text-body">Convocatoria 2026</li>', html)

    def test_convocatoria_pausada_muestra_badge_y_reanudar(self):
        Convocatoria.objects.filter(pk=self.convocatoria.pk).update(pausado=True)
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("becas:convocatoria_detalle", args=[self.convocatoria.pk]))
        self.assertInHTML('<span class="badge badge-warning badge-dot">Pausada</span>', resp.content.decode())
        pausa = reverse("becas:gestionar_pausa", args=["convocatoria", self.convocatoria.pk])
        self.assertInHTML(f'<a href="{pausa}" class="btn-nodo btn-brand btn-sm">Reanudar</a>', resp.content.decode())

    def test_nombre_con_marcado_sale_escapado(self):
        Convocatoria.objects.filter(pk=self.convocatoria.pk).update(nombre="<script>alert(1)</script>")
        self.client.force_login(self.admin)
        html = self.client.get(reverse("becas:convocatoria_detalle", args=[self.convocatoria.pk])).content.decode()
        self.assertNotIn("<script>alert(1)</script>", html)
