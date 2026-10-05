"""Las 8 reglas estructurales de `design_audit.py`, el ratchet y los marcadores.

Corre en Backend CI (igual que `test_design_audit_confirm.py`): el script es solo
stdlib, pero sus reglas son el gate de UI de todo el repo y no pueden quedar sin
red adentro de la suite.
"""

import contextlib
import importlib.util
import io
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

_SPEC = importlib.util.spec_from_file_location(
    "design_audit", Path(__file__).resolve().parents[2] / "scripts" / "design_audit.py"
)
design_audit = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(design_audit)

SHELL = '{% extends "includes/base.html" %}\n{% block main-content %}\n'


def reglas(contenido, suffix=".html"):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / f"x{suffix}"
        p.write_text(contenido, encoding="utf-8")
        return [f[2] for f in design_audit.audit_file(p)]


class ReglasP1Tests(SimpleTestCase):
    """Un positivo y un negativo por regla."""

    def test_rawpalette(self):
        self.assertIn("RAWPALETTE", reglas('<div class="bg-gray-200 text-red-500">x</div>'))
        self.assertNotIn("RAWPALETTE", reglas('<div class="bg-secondary text-body">x</div>'))

    def test_rawpalette_solo_adentro_de_class(self):
        # Un nombre de variable o un comentario que diga `text-gray-900` no es markup.
        self.assertNotIn("RAWPALETTE", reglas("{# el legacy usaba text-gray-900 #}\n<div>x</div>"))

    def test_inlinestyle(self):
        self.assertIn("INLINESTYLE", reglas('<div style="margin:16px">x</div>'))
        self.assertNotIn("INLINESTYLE", reglas('<div class="m-4">x</div>'))

    def test_inlinestyle_exime_custom_properties_y_display_none(self):
        for exento in (
            '<div style="--barra: 40%;">x</div>',
            '<div style="--barra: {{ pct }}%;">x</div>',
            '<div style="display:none">x</div>',
        ):
            self.assertNotIn("INLINESTYLE", reglas(exento), exento)

    def test_inlinestyle_marca_la_declaracion_con_valor_dinamico(self):
        # Una barra de progreso se escribe `style="--barra: {{ pct }}%"` y la
        # utilidad lee esa custom property: `width:{{ pct }}%` sigue siendo una
        # declaración escrita a mano, y cuenta.
        self.assertIn("INLINESTYLE", reglas('<div style="width: {{ pct }}%">x</div>'))

    def test_styleblock(self):
        self.assertIn("STYLEBLOCK", reglas("<style>[x-cloak]{display:none!important}</style>"))
        self.assertNotIn("STYLEBLOCK", reglas("<div>sin estilos locales</div>"))

    def test_styleblock_exime_los_shells(self):
        # El `<style>` global vive en los cuatro shells; ahí no es deuda.
        self.assertEqual(design_audit._p1_styleblock("templates/includes/base.html", "<style>a{}</style>"), [])
        self.assertEqual(len(design_audit._p1_styleblock("legajos/templates/legajos/x.html", "<style>a{}</style>")), 1)

    def test_shelllegacy(self):
        self.assertIn("SHELLLEGACY", reglas('{% extends "includes/main.html" %}'))
        self.assertNotIn("SHELLLEGACY", reglas('{% extends "includes/base.html" %}'))

    def test_pageheader(self):
        self.assertIn("PAGEHEADER", reglas(SHELL + '<h1 class="text-2xl">Título</h1>'))
        self.assertNotIn("PAGEHEADER", reglas(SHELL + '{% page_header titulo="Título" %}{% endpage_header %}'))

    def test_pageheader_no_aplica_al_portal(self):
        self.assertEqual(design_audit._p1_pageheader("portal/templates/portal/x.html", SHELL + "<h1>T</h1>"), [])
        self.assertEqual(len(design_audit._p1_pageheader("legajos/templates/x.html", SHELL + "<h1>T</h1>")), 1)

    def test_tablecanon(self):
        self.assertIn("TABLECANON", reglas("<table><thead><tr><th>Nombre</th></tr></thead></table>"))
        self.assertNotIn(
            "TABLECANON",
            reglas('<table><thead><tr class="nodo-thead-row"><th class="nodo-th">Nombre</th></tr></thead></table>'),
        )

    def test_tablecanon_marca_el_thead_con_style(self):
        self.assertIn("TABLECANON", reglas('<table><thead style="background:#eee"><tr></tr></thead></table>'))

    def test_iconaria(self):
        self.assertIn("ICONARIA", reglas('<i class="fas fa-eye"></i>'))
        self.assertNotIn("ICONARIA", reglas('<i class="fas fa-eye" aria-hidden="true"></i>'))

    def test_classdef_marca_la_utilidad_que_no_existe_en_el_build(self):
        hallazgos = reglas('<div class="bg-gray-200">x</div>')
        self.assertIn("CLASSDEF", hallazgos)

    def test_classdef_no_marca_una_clase_canonica(self):
        self.assertNotIn("CLASSDEF", reglas('<div class="nodo-td badge badge-success">x</div>'))

    def test_classdef_acepta_la_clase_definida_en_el_style_del_propio_template(self):
        self.assertNotIn("CLASSDEF", reglas('<style>.mi-hoja{color:red}</style><div class="mi-hoja">x</div>'))

    def test_classdef_hereda_el_css_del_shell_que_extiende(self):
        # `.animate-fadeInUp` la define el <style> de portal/base.html y la usan
        # sus 17 hijos sin declararla: heredar el CSS del shell evita 17 falsos.
        hallazgos = reglas('{% extends "portal/base.html" %}<div class="animate-fadeInUp">x</div>')
        self.assertNotIn("CLASSDEF", hallazgos)

    def test_classdef_respeta_la_allowlist_de_hooks(self):
        self.assertNotIn("CLASSDEF", reglas('<div class="js-cerrar-panel">x</div>'))

    def test_pragma_allow_saltea_la_linea(self):
        self.assertNotIn("RAWPALETTE", reglas('<div class="bg-gray-200">x</div>{# design-audit: allow #}'))


class DecodificadorCssTests(SimpleTestCase):
    """FE-13: el parser de identificadores CSS, con los tres escapes que importan."""

    def test_escape_hexadecimal_consume_un_solo_espacio(self):
        css = r".h-\[clamp\(12rem\2c calc\(100dvh-31rem\)\2c 28rem\)\]{height:1rem}"
        self.assertIn("h-[clamp(12rem,calc(100dvh-31rem),28rem)]", design_audit.clases_css(css))

    def test_escape_literal_de_dos_puntos(self):
        self.assertIn("xl:top-6", design_audit.clases_css(r".xl\:top-6{top:1.5rem}"))

    def test_escape_literal_de_barra(self):
        self.assertIn("w-1/2", design_audit.clases_css(r".w-1\/2{width:50%}"))

    def test_no_lee_puntos_dentro_de_declaraciones(self):
        # `.5rem` adentro del bloque no es una clase.
        self.assertNotIn("5rem", design_audit.clases_css(".p-2{padding:.5rem}"))

    def test_twbuild_reconoce_valores_arbitrarios_con_coma(self):
        """RS-R6-08: los dos TWBUILD falsos que enseñaban a ignorar la regla."""
        css = r".h-\[clamp\(1rem\2c 2rem\)\]{height:1rem}.xl\:grid-cols-\[minmax\(0\2c 1fr\)_auto\]{}"
        declaradas = design_audit.clases_css(css)
        for clase in ("h-[clamp(1rem,2rem)]", "xl:grid-cols-[minmax(0,1fr)_auto]"):
            self.assertIn(clase, declaradas)


class RatchetTests(SimpleTestCase):
    """`nuevos(base, actual)`: la deuda vieja no bloquea, lo que se suma sí."""

    RUTA = "legajos/templates/legajos/x.html"

    def test_archivo_sin_cambios_no_reporta_nada(self):
        texto = '<div class="bg-gray-200">x</div>'
        self.assertEqual(design_audit.nuevos(texto, texto, self.RUTA), [])

    def test_deuda_preexistente_no_bloquea_al_editar_otra_cosa(self):
        base = '<div class="bg-gray-200">viejo</div>'
        actual = '<div class="bg-gray-200">viejo</div>\n<p class="text-body">nuevo</p>'
        self.assertEqual(design_audit.nuevos(base, actual, self.RUTA), [])

    def test_sumar_un_hallazgo_sobre_deuda_preexistente_bloquea(self):
        base = '<div class="bg-gray-200">viejo</div>'
        actual = '<div class="bg-gray-200">viejo</div>\n<p class="text-gray-900">nuevo</p>'
        hallazgos = design_audit.nuevos(base, actual, self.RUTA)
        self.assertTrue(any(f[2] == "RAWPALETTE" for f in hallazgos))
        self.assertEqual(hallazgos[0][1], 2, "tiene que señalar la línea que lo agregó, no la vieja")

    def test_bajar_la_deuda_no_reporta(self):
        base = '<div class="bg-gray-200 text-red-500">viejo</div>'
        actual = '<div class="bg-secondary text-body">migrado</div>'
        self.assertEqual(design_audit.nuevos(base, actual, self.RUTA), [])

    def test_archivo_nuevo_se_mide_entero(self):
        actual = SHELL + "<h1>Título a mano</h1>"
        reglas_nuevas = {f[2] for f in design_audit.nuevos(None, actual, self.RUTA)}
        self.assertIn("PAGEHEADER", reglas_nuevas)

    def test_el_ratchet_usa_la_ruta_real_no_la_del_temporal(self):
        # Un `<style>` en un shell no es deuda; en cualquier otra pantalla sí.
        style = "<style>a{color:red}</style>"
        self.assertEqual(design_audit.nuevos(None, style, "templates/includes/base.html"), [])
        self.assertTrue(design_audit.nuevos(None, style, self.RUTA))


class MarcadoresDeArquetipoTests(SimpleTestCase):
    """Un caso por arquetipo, medido sobre la golden real que el anexo nombra."""

    GOLDENS = {
        "listado": "programas/templates/programas/becas/revision/personas_list.html",
        "formulario": "programas/templates/programas/becas/config/segmento_form.html",
    }

    def marcadores(self, arquetipo, rutas):
        """Código de salida de `--arquetipo`, sin ensuciar la salida de la suite."""
        with contextlib.redirect_stdout(io.StringIO()) as salida:
            codigo = design_audit.arquetipo_mode(arquetipo, rutas)
        return codigo, salida.getvalue()

    def test_las_goldens_limpias_cumplen_sus_marcadores(self):
        for arquetipo, ruta in self.GOLDENS.items():
            with self.subTest(arquetipo=arquetipo):
                codigo, salida = self.marcadores(arquetipo, [ruta])
                self.assertEqual(codigo, 0, salida)

    def test_falta_un_marcador(self):
        sin_tabla = SHELL + '<div class="space-y-6">{% page_header titulo="x" %}{% endpage_header %}</div>'
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "list.html"
            p.write_text(sin_tabla, encoding="utf-8")
            codigo, salida = self.marcadores("listado", [str(p)])
        self.assertEqual(codigo, 1)
        self.assertIn("tabla canónica", salida)

    def test_marcadores_fuera_de_orden(self):
        # La tabla antes del encabezado: están todos los marcadores, mal ordenados.
        desordenado = (
            SHELL + '<div class="space-y-6"><table class="w-full border-collapse">'
            '<tr class="nodo-thead-row"><th class="nodo-th">x</th></tr>'
            '<td class="nodo-td">y</td></table>'
            '{% page_header titulo="x" %}{% endpage_header %}</div>'
        )
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "list.html"
            p.write_text(desordenado, encoding="utf-8")
            codigo, salida = self.marcadores("listado", [str(p)])
        self.assertEqual(codigo, 1)
        self.assertIn("fuera de orden", salida)

    def test_marcador_prohibido(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "detail.html"
            p.write_text("<style>a{}</style>", encoding="utf-8")
            codigo, salida = self.marcadores("detalle", [str(p)])
        self.assertEqual(codigo, 1)
        self.assertIn("<style> local", salida)

    def test_arquetipo_desconocido_falla(self):
        codigo, _ = self.marcadores("wizard", [])
        self.assertEqual(codigo, 1)

    def test_hay_ficha_de_marcadores_para_los_cuatro_arquetipos(self):
        self.assertEqual(sorted(design_audit.ARQUETIPOS), ["detalle", "formulario", "listado", "modal"])


class GateDeCiTests(SimpleTestCase):
    """El check «Design Agent Contract» tiene que correr lo que el anexo pide.

    Las aserciones son de texto a propósito: el contrato que importa es que los
    tres comandos estén en el workflow, y así no hace falta un parser de YAML.
    """

    @property
    def workflow(self):
        ruta = Path(design_audit.REPO, ".github", "workflows", "design-agent-contract.yml")
        return ruta.read_text(encoding="utf-8")

    def test_corre_el_ratchet_contra_la_base_del_pr(self):
        self.assertIn("design_audit.py --ratchet --base", self.workflow)

    def test_corre_el_gate_de_build_de_tailwind(self):
        """V5A-NEW-01: es lo único que distingue «utilidad válida sin build» de «inválida»."""
        gate = self.workflow
        self.assertIn("npm run build:tailwind", gate)
        self.assertIn("git diff --exit-code -- static/custom/css/tailwind.css", gate)

    def test_el_filtro_de_rutas_cubre_las_herramientas(self):
        gate = self.workflow
        for ruta in ("scripts/design_audit.py", "scripts/design_audit_hooks.txt", ".claude/design/**"):
            self.assertIn(f"'{ruta}'", gate)

    def test_el_css_de_tailwind_esta_al_dia(self):
        """Barata y local: las clases que el markup usa con variante tienen que estar en el build.

        Si falla, correr `npm run build:tailwind` y commitear el CSS; es el mismo
        hallazgo que levanta el gate del CI, pero sin esperar al runner.
        """
        faltantes = sorted(
            {
                f"{f.relative_to(design_audit.REPO).as_posix()}: {clase}"
                for f in design_audit.iter_files([design_audit.REPO / "programas" / "templates"])
                if f.suffix == ".html"
                for _, clase in design_audit.clases_sin_build(f.read_text(encoding="utf-8", errors="replace"))
            }
        )
        self.assertEqual(faltantes, [], "correr `npm run build:tailwind` y commitear static/custom/css/tailwind.css")
