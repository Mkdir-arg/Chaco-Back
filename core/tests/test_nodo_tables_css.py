"""Tabla densa (.nodo-th/.nodo-td) y botón de ícono (.nodo-icon-btn).

Las piezas viven en ``nodo-tables.css`` y al final de ``nodo-buttons.css``; se leen
como el navegador (sin comentarios) para no dar por buena una regla que un
comentario roto dejó muerta. El consumidor de prueba es la bandeja de revisión
(``becas:revision``, ``personas_list.html``).
"""

import re
from datetime import date
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from legajos.models import Ciudadano
from programas.models import Convocatoria, Formulario, Relevamiento, Segmento

CSS_DIR = Path(settings.BASE_DIR) / "static" / "custom" / "css"
BASE_HTML = Path(settings.BASE_DIR) / "templates" / "includes" / "base.html"
PERSONAS_LIST = (
    Path(settings.BASE_DIR) / "programas" / "templates" / "programas" / "becas" / "revision" / "personas_list.html"
)
COMENTARIO = re.compile(r"/\*.*?\*/", re.DOTALL)
REGLA = re.compile(r"([^{}]+)\{([^{}]*)\}")


def _reglas(nombre):
    css = (CSS_DIR / nombre).read_text(encoding="utf-8")
    sin_comentarios = COMENTARIO.sub("", css)
    reglas = {}
    for sel, cuerpo in REGLA.findall(sin_comentarios):
        for parte in sel.split(","):
            reglas.setdefault(" ".join(parte.split()), []).append(cuerpo)
    return reglas


def _cuerpo(reglas, selector):
    return " ".join(" ".join(c.split()) for c in reglas.get(selector, []))


class NodoTablesCssTests(SimpleTestCase):
    def setUp(self):
        self.reglas = _reglas("nodo-tables.css")

    def test_comentarios_balanceados(self):
        css = (CSS_DIR / "nodo-tables.css").read_text(encoding="utf-8")
        self.assertEqual(css.count("/*"), css.count("*/"))
        self.assertNotIn("*/", COMENTARIO.sub("", css))

    def test_th_con_el_canon_de_la_tabla_densa(self):
        cuerpo = _cuerpo(self.reglas, ".nodo-th")
        for decl in (
            "padding: 11px 16px",
            "font-size: 11px",
            "font-weight: 700",
            "text-transform: uppercase",
            "letter-spacing: 0.05em",
            "color: var(--text-body-subtle)",
        ):
            self.assertIn(decl, cuerpo)

    def test_alineacion_del_th_cede_a_las_utilidades(self):
        # text-left en :where() (especificidad cero): text-center/text-right la pisan.
        self.assertIn("text-align: left", _cuerpo(self.reglas, ":where(.nodo-th)"))
        self.assertNotIn("text-align", _cuerpo(self.reglas, ".nodo-th"))

    def test_td_y_fila_de_encabezado(self):
        td = _cuerpo(self.reglas, ".nodo-td")
        self.assertIn("padding: 13px 16px", td)
        self.assertIn("font-size: var(--font-size-sm)", td)
        self.assertIn("border-top: 1px solid var(--border-light)", td)
        fila = _cuerpo(self.reglas, ".nodo-thead-row")
        self.assertIn("background: var(--bg-secondary)", fila)
        self.assertIn("border-bottom: 1px solid var(--border-base)", fila)

    def test_base_carga_nodo_tables(self):
        self.assertIn("{% static 'custom/css/nodo-tables.css' %}", BASE_HTML.read_text(encoding="utf-8"))


class NodoIconBtnCssTests(SimpleTestCase):
    def setUp(self):
        self.reglas = _reglas("nodo-buttons.css")

    def test_reposo_gris_y_caja_compacta(self):
        cuerpo = _cuerpo(self.reglas, ".nodo-icon-btn")
        for decl in (
            "--nodo-icon-btn-color: var(--text-body-subtle)",
            "display: inline-flex",
            "padding: 6px",
            "border-radius: var(--rounded-lg)",
            "color: var(--nodo-icon-btn-color) !important",
        ):
            self.assertIn(decl, cuerpo)

    def test_gana_al_color_de_link_de_nodo_brand(self):
        # nodo-brand.css pinta todo <a> con !important; la regla del color tiene que
        # igualar su selector para que el <a class="nodo-icon-btn"> quede gris.
        selector = 'a.nodo-icon-btn:not(.btn):not(.btn-nodo):not(.btn-brand):not([class*="bg-"])'
        self.assertIn("color: var(--nodo-icon-btn-color) !important", _cuerpo(self.reglas, selector))

    def test_hover_marca_y_foco_con_anillo_de_marca(self):
        hover = _cuerpo(self.reglas, ".nodo-icon-btn:hover")
        self.assertIn("--nodo-icon-btn-color: var(--text-fg-brand)", hover)
        self.assertIn("background: var(--bg-secondary)", hover)
        foco = _cuerpo(self.reglas, ".nodo-icon-btn:focus-visible")
        self.assertIn("outline: 2px solid var(--border-brand)", foco)
        self.assertIn("outline-offset: 2px", foco)

    def test_variante_danger(self):
        self.assertIn(
            "--nodo-icon-btn-color: var(--text-fg-danger)", _cuerpo(self.reglas, ".nodo-icon-btn--danger:hover")
        )

    def test_lo_existente_de_nodo_buttons_sigue_vivo(self):
        self.assertIn("btn-nodo", " ".join(self.reglas))
        self.assertTrue(self.reglas.get(".btn-tertiary.btn-back-circle"))


class PersonasListUsaLasPiezasTests(TestCase):
    def setUp(self):
        cache.clear()
        segmento = Segmento.objects.create(nombre="Seg Tabla", cupo_maximo=100)
        convocatoria = Convocatoria.objects.create(
            nombre="Conv Tabla", segmento=segmento, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )
        territorial = User.objects.create_user("terri_tabla", password="x")
        relevamiento = Relevamiento.objects.create(
            convocatoria=convocatoria,
            territorial=territorial,
            fecha_asignada=date(2026, 6, 1),
            zona="Z",
            estado=Relevamiento.Estado.FINALIZADO,
        )
        ciudadano = Ciudadano.objects.create(
            dni="41000001", nombre="Lucía", apellido="Benítez", fecha_nacimiento=date(2000, 1, 1)
        )
        self.con_ciudadano = Formulario.objects.create(relevamiento=relevamiento, ciudadano=ciudadano, celular="1")
        self.offline = Formulario.objects.create(
            relevamiento=relevamiento, celular="2", datos_identificacion={"nombre": "Ana", "apellido": "Gómez"}
        )
        self.sin_identificar = Formulario.objects.create(relevamiento=relevamiento, celular="3")
        self.client.force_login(User.objects.create_superuser("super_tabla", password="x"))

    def test_tabla_usa_las_clases_comunes(self):
        html = self.client.get(reverse("becas:revision")).content.decode()
        self.assertIn('<tr class="nodo-thead-row">', html)
        self.assertEqual(len(re.findall(r'<th class="nodo-th[ "]', html)), 7)
        self.assertIn('class="nodo-td', html)
        self.assertNotIn("font-size:11px", html)

    def test_ojo_es_boton_de_icono_con_nombre_accesible(self):
        html = self.client.get(reverse("becas:revision")).content.decode()
        for formulario, etiqueta in (
            (self.con_ciudadano, "Ver caso de Lucía Benítez"),
            (self.offline, "Ver caso de Ana Gómez"),
            (self.sin_identificar, "Ver caso de persona sin identificar"),
        ):
            url = reverse("becas:formulario_detalle", args=[formulario.pk])
            self.assertInHTML(
                f'<a href="{url}" class="nodo-icon-btn" aria-label="{etiqueta}">'
                '<i class="fas fa-eye" aria-hidden="true"></i></a>',
                html,
            )
        self.assertNotIn('aria-label="Ver formulario"', html)

    def test_sin_focus_ring_brand(self):
        # focus:ring-brand no está en el build de Tailwind (TWBUILD): no hacía nada.
        self.assertNotIn("focus:ring-brand", PERSONAS_LIST.read_text(encoding="utf-8"))
        html = self.client.get(reverse("becas:revision")).content.decode()
        self.assertNotIn("focus:ring-brand", html)
        self.assertIn('class="nodo-field max-w-xs"', html)
