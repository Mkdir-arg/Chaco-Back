"""Las 8 reglas estructurales de `design_audit.py`, el ratchet y los marcadores.

Corre en Backend CI (igual que `test_design_audit_confirm.py`): el script es solo
stdlib, pero sus reglas son el gate de UI de todo el repo y no pueden quedar sin
red adentro de la suite.
"""

import contextlib
import importlib.util
import io
import re
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

    GOLDENS = dict(design_audit.GOLDENS)

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

    def test_el_step_de_goldens_corre_y_bloquea(self):
        """Ola 6 paso 3: con las goldens saneadas el step deja de ser tolerante."""
        gate = self.workflow
        self.assertIn("design_audit.py --goldens", gate)
        bloque = gate.split("- name: Design audit goldens", 1)[1].split("design_audit.py --goldens", 1)[0]

        self.assertNotIn("continue-on-error", bloque)


class GoldensSaneadasTests(SimpleTestCase):
    """Las goldens del anexo §3, en 0 (Ola 6 paso 3, V5A-NEW-07 parte (a)).

    Son las cuatro pantallas que `chaco-frontend` clona: lo que tengan encima se
    reproduce en cada pantalla nueva. Por eso el contrato es más duro que el del
    resto del repo (ratchet): acá el piso es cero, no «no empeorar».
    """

    def contenido(self, ruta):
        return Path(design_audit.REPO, ruta).read_text(encoding="utf-8")

    def test_goldens_mode_sale_en_cero(self):
        with contextlib.redirect_stdout(io.StringIO()) as salida:
            codigo = design_audit.goldens_mode()

        self.assertEqual(codigo, 0, salida.getvalue())

    def test_hay_una_golden_por_arquetipo(self):
        self.assertEqual(sorted(dict(design_audit.GOLDENS)), sorted(design_audit.ARQUETIPOS))

    def test_ninguna_golden_tiene_hallazgos_p1(self):
        for arquetipo, ruta in design_audit.GOLDENS:
            with self.subTest(arquetipo=arquetipo):
                hallazgos = [
                    f"{f[1]}: [{f[2]}] {f[3]}"
                    for f in design_audit.audit_file(Path(design_audit.REPO, ruta))
                    if f[0] in design_audit.SEVERIDADES_BLOQUEANTES
                ]

                self.assertEqual(hallazgos, [], f"{ruta} no puede ser molde con deuda encima")

    def test_el_listado_nombra_la_columna_de_acciones(self):
        """WCAG 1.3.1: el `<th>` de acciones estaba vacío y la columna no tenía nombre."""
        listado = self.contenido(dict(design_audit.GOLDENS)["listado"])
        th = '<th class="nodo-th text-right"><span class="sr-only">Acciones</span></th>'

        self.assertEqual(listado.count(th), 1, "el <th> de acciones tiene que nombrar la columna")

    def test_los_filtros_del_listado_nombran_sus_controles_con_aria_label(self):
        """`dynamic_list_filters.js` vacía el form y le pisa la clase al montar.

        Con un `<label>` suelto el control se queda sin nombre accesible apenas
        corre el JS, y la `class` del `<form>` no llega nunca.
        """
        listado = self.contenido(dict(design_audit.GOLDENS)["listado"])
        form = listado.split("data-dynamic-list-filters", 1)[1].split("</form>", 1)[0]

        self.assertEqual(form.count('aria-label="Estado"'), 1, "el control va con aria-label")
        self.assertEqual(form.count("<label"), 0, "sin <label> suelto: el JS lo borra al montar")
        self.assertEqual(listado.count('<form method="get" data-dynamic-list-filters>'), 1, "el form va sin class")

    def test_el_detalle_no_pinta_las_iniciales_con_el_gradiente(self):
        """D5: un solo acento por bloque, y saca los 3 `style=` de la golden."""
        detalle = self.contenido(dict(design_audit.GOLDENS)["detalle"])

        self.assertEqual(detalle.count("--gradient-brand"), 0, "las iniciales no llevan el gradiente (D5)")
        self.assertEqual(detalle.count("rounded-full bg-brand-soft text-fg-brand"), 3)

    def test_el_modal_usa_las_piezas_canonicas(self):
        """Labels canónicos, ayuda que no parece error, backdrop por clase y nota con `_alerta`."""
        modal = self.contenido(dict(design_audit.GOLDENS)["modal"])

        self.assertEqual(modal.count("text-[13px]"), 0, "labels con valor arbitrario")
        self.assertEqual(modal.count('class="block text-sm font-medium text-heading mb-1"'), 3)
        self.assertEqual(modal.count("bg-black/50 backdrop-blur-sm"), 1, "backdrop por clase, no por style=")
        self.assertEqual(modal.count('components/_alerta.html" with tono="info"'), 1, "la nota es _alerta")
        self.assertEqual(modal.count("<svg"), 0, "D3: Font Awesome en el contenido, no SVG inline")

    def test_el_modal_tiene_donde_mostrar_el_error_general(self):
        """`_ajax_js.html` escribe los errores en `[data-error="<campo>"]`.

        Sin caja para `__all__`, un error de formulario que no es de campo solo
        aparecía en el toast y el modal no decía nada.
        """
        modal = self.contenido(dict(design_audit.GOLDENS)["modal"])

        self.assertEqual(modal.count('data-error="__all__"'), 1, "falta la caja del error general")

    def test_ninguna_golden_declara_x_cloak_local(self):
        """`[x-cloak]` ya es global en `static/custom/css/override.css`."""
        for arquetipo, ruta in design_audit.GOLDENS:
            with self.subTest(arquetipo=arquetipo):
                self.assertEqual(self.contenido(ruta).count("[x-cloak]{display:none"), 0)


def _config_tailwind() -> str:
    return Path(design_audit.REPO, "tailwind.config.js").read_text(encoding="utf-8")


def _apps_del_content() -> list[str]:
    """Las apps que `tailwind.config.js` enumera en su constante `APPS`."""
    m = re.search(r"^const APPS = '\{([^}]+)\}'", _config_tailwind(), re.M)
    assert m, "tailwind.config.js tiene que declarar `const APPS = '{app,app,...}'`"
    return m.group(1).split(",")


def _patrones_del_content() -> list[str]:
    """Los patrones del array `content`, con `${APPS}` ya resuelto."""
    bloque = re.search(r"content: \[(.*?)^  \],", _config_tailwind(), re.S | re.M)
    assert bloque, "no se encontró el array `content` en tailwind.config.js"
    apps = "{" + ",".join(_apps_del_content()) + "}"
    crudos = re.findall(r"^\s*[`'\"](.+?)[`'\"],\s*$", bloque.group(1), re.M)
    return [p.replace("${APPS}", apps) for p in crudos]


class ContentDeTailwindTests(SimpleTestCase):
    """`tailwind.config.js` tiene que escanear todo lo que nombra una clase, y nada más.

    Lo que el escáner no ve, no se genera: la pantalla sale mal y no falla nada. Y
    lo que ve de más —los templates de Django admin adentro de un virtualenv del
    checkout, `node_modules`— hace que el CSS dependa de la máquina donde se corrió
    el build, con lo cual el gate obligatorio rechaza al que lo corrió en la suya.

    El seguro contra lo primero es `CssCompiladoAlDiaTests`, que mide el resultado.
    El seguro contra lo segundo es estructural y se verifica acá: ningún patrón
    positivo puede empezar con un comodín de primer nivel.
    """

    #: Dirs de primer nivel que no son apps y no aportan markup. Lo que no esté acá
    #: ni en `APPS` hace fallar `test_apps_lista_todas_las_apps_del_repo`.
    NO_SON_APPS = {"config", "docs", "documentos", "scripts", "static", "media", "certs", "docker", "templates"}

    def test_ningun_patron_positivo_usa_comodin_de_primer_nivel(self):
        """`./**/templates/…` y `./*/templates/…` alcanzan un venv dentro del checkout.

        Es el modo de falla que rompe el gate obligatorio: el CSS sale distinto
        según qué tenga instalado el que buildea. Las negaciones no alcanzan —se
        pueden out-globear—; lo que lo cierra es que no haya comodín que escape.
        """
        culpables = [p for p in _patrones_del_content() if not p.startswith("!") and re.match(r"^\./(\*\*|\*)/", p)]

        self.assertEqual(
            culpables,
            [],
            "estos patrones alcanzan .venv/, venv/ o node_modules dentro del checkout: anclalos a la constante APPS",
        )

    def test_apps_lista_todas_las_apps_del_repo(self):
        """Si alguien agrega una app, su markup tiene que entrar al build con ella."""
        repo = design_audit.REPO
        con_markup = {
            d.name
            for d in repo.iterdir()
            if d.is_dir()
            and not d.name.startswith((".", "_", "node_modules"))
            and d.name not in self.NO_SON_APPS
            and ((d / "templates").is_dir() or (d / "forms.py").is_file() or (d / "forms").is_dir())
        }

        self.assertEqual(
            sorted(con_markup - set(_apps_del_content())),
            [],
            "apps con templates o forms que `APPS` de tailwind.config.js no cubre: sus clases no se van a generar",
        )

    def test_escanea_los_py_que_arman_clases(self):
        """Los widgets de los forms traen sus clases desde Python, no desde el template."""
        patrones = _patrones_del_content()

        for sufijo in ("/forms.py", "/{forms,models,templatetags}/**/*.py"):
            self.assertTrue(
                any(p.endswith(sufijo) for p in patrones),
                f"falta el patrón terminado en `{sufijo}`: las clases de los widgets no se generan",
            )

    def test_excluye_los_tests(self):
        """Los casos negativos de CLASSDEF usan clases mal escritas a propósito."""
        patrones = _patrones_del_content()
        for negacion in ("!./**/tests/**", "!./**/test_*.py"):
            self.assertIn(negacion, patrones)


class CssCompiladoAlDiaTests(SimpleTestCase):
    """Toda clase usada tiene que existir en el CSS compilado, o estar en la deuda.

    Barato y local: es el mismo hallazgo que levanta el gate del CI, pero sin
    esperar al runner, y además cubre lo que el gate no puede ver (si una clase
    desaparece porque el `content` dejó de cubrir su archivo, acá se nota).

    Mira **todas** las apps: los templates, el JS propio y *todo* `.py` de la app,
    no solo los que `content` escanea. La asimetría es a propósito: `content` se
    mantiene corto para no generar basura, y este test es el que avisa cuando quedó
    corto de más. Por eso lee los `.py` con `ast` y no con una regex — ve las
    cadenas literales y nada más, así que un slice (`xs[desde:hasta]`) no le parece
    una clase.
    """

    #: Clases usadas que el build **no** genera. Es deuda congelada: puede bajar,
    #: nunca subir. Casi todas son markup heredado que se va con FE-06, FE-12 y
    #: FE-20; ninguna es una utilidad válida que falte por un build viejo (eso es
    #: justo lo que este test impide que vuelva a pasar).
    DEUDA = {
        # Paleta cruda de Tailwind: la escala `gray` está pisada a propósito en
        # `tailwind.config.js` (no se agrega al build; se migra a color semántico).
        # Las gobierna la regla P1 RAWPALETTE y su ratchet. FE-06 las sacó de **todos
        # los templates del backoffice**; estos cinco usos son los que quedan, cada uno
        # con su dueño:
        #
        #   bg-gray-50, bg-gray-600  Conversaciones (`configurar_cola.html`, `lista.html`),
        #                            que se apaga entera con G1-01 fase 2.
        #   bg-gray-200, bg-gray-900 `static/custom/js/portal-effects.js` (portal ciudadano;
        #                            el tooltip queda texto blanco sobre transparente).
        #   hover:bg-gray-50         JS de Conversaciones: FE-14
        #                            (`alertas_conversaciones_simple.js`). FE-25 ya la sacó de
        #                            `alertas_websocket.js`.
        #   bg-gray-100              `legajos/forms/ciudadanos.py` y `legajos/models/base.py`.
        #                            **No** se tocaron en FE-06 a propósito: el primero es el
        #                            bloque `_FLOWBITE_*_CSS` entero del formulario del
        #                            ciudadano (su reemplazo es `nodo-field`, FE-11/FE-12) y el
        #                            segundo es un mapa estado→clase dentro del modelo, que por
        #                            el inventario va en el parcial de badges del módulo (FE-12).
        #                            Cambiarles la clase sola los deja igual de fuera de canon.
        "bg-gray-50",
        "bg-gray-100",
        "bg-gray-200",
        "bg-gray-600",
        "bg-gray-900",
        "hover:bg-gray-50",
        # Bootstrap/AdminLTE heredado, con la forma justa para parecer utilidad.
        # FE-20 (Cambio 167) se llevó `text-warning`, que solo vivía en `404.html`.
        # FE-14 y OPS-10 (Cambio 195) se llevaron `bg-info`, `text-danger` y
        # `text-info`: sus últimos consumidores eran los 29 JS huérfanos y el bloque
        # de «Pruebas de Fase 2» de `core/performance_dashboard.html`.
        "content-header",
        "text-success",
        # Definidas a mano en el `<style>` de un shell o en CSS propio, no por Tailwind.
        "animate-fadeInUp",
        # `font-lora` salió de la deuda con FE-22: su único consumidor era el `<h1>`
        # propio de `legajos/reportes.html`, que pasó a `{% page_header %}`.
        "touch-target",
        # `ring-brand` no es un color del tema (el foco de marca es la custom
        # property `--ring-brand`, un box-shadow). O sea que el checkbox canónico
        # de `programas/forms.py` CHECKBOX_CLASS **no tiene indicador de foco**:
        # hallazgo nuevo, WCAG 2.4.7, anotado para la Ola 5 (no se arregla acá
        # porque cambia el render de todos los checkboxes del backoffice).
        "focus:ring-brand",
    }

    def usadas_fuera_del_build(self):
        build = design_audit._clases_del_build()
        self.assertTrue(build, "falta static/custom/css/tailwind.css")
        fuera = {}
        for ruta in self.fuentes():
            texto = ruta.read_text(encoding="utf-8", errors="replace")
            if ruta.suffix == ".html":
                pares = design_audit.tokens_de_clase(texto) + design_audit.tokens_de_clase_dinamicos(texto)
            elif ruta.suffix == ".js":
                pares = design_audit.tokens_de_clase_dinamicos(texto)
            else:
                pares = design_audit.clases_en_python(texto)
            for _, token in pares:
                if (
                    design_audit._TOKEN_VALIDO_RE.match(token)
                    and design_audit._es_utilidad_tailwind(token)
                    and token not in build
                ):
                    fuera.setdefault(token, ruta.relative_to(design_audit.REPO).as_posix())
        return fuera

    @staticmethod
    def fuentes():
        """Templates y JS propio del repo, y **todo** `.py` de las apps de `APPS`.

        Se recorren las apps y no el repo entero para no entrar a un virtualenv o a
        `node_modules` del checkout, que son decenas de miles de archivos y además
        no son superficie nuestra.
        """
        repo = design_audit.REPO
        excluidos = {"tests", "migrations", "__pycache__"}
        patrones = [(repo, "templates/**/*.html"), (repo, "static/custom/js/*.js")]
        patrones += [(repo / app, p) for app in _apps_del_content() for p in ("templates/**/*.html", "**/*.py")]
        vistos = set()
        for base, patron in patrones:
            for f in sorted(base.glob(patron)):
                if f in vistos or set(f.relative_to(repo).parts) & excluidos or f.name.startswith("test_"):
                    continue
                vistos.add(f)
                yield f

    def test_ninguna_clase_usada_quedo_fuera_del_build(self):
        nuevas = {t: f for t, f in self.usadas_fuera_del_build().items() if t not in self.DEUDA}

        self.assertEqual(
            nuevas,
            {},
            "Clases usadas que el CSS compilado no tiene. Si son válidas, correr "
            "`npm run build:tailwind` y commitear static/custom/css/tailwind.css; si vienen de un "
            "archivo nuevo, revisar que `content` de tailwind.config.js lo cubra.",
        )

    def test_la_deuda_no_tiene_entradas_resueltas(self):
        """El ratchet solo baja: una clase que ya está en el build sale de DEUDA."""
        resueltas = self.DEUDA - set(self.usadas_fuera_del_build())

        self.assertEqual(resueltas, set(), "ya no faltan en el build: borralas de DEUDA")

    def test_las_clases_que_vienen_de_un_widget_estan_en_el_build(self):
        """Regresión del blocker: `content` no escaneaba Python y el build las borraba.

        `cursor-not-allowed` lo usa el campo deshabilitado del legajo y
        `file:bg-blue-600` su input de archivo (`legajos/forms/ciudadanos.py`): si el
        `content` deja de escanear Python, el build las borra y el control queda sin
        estado visible.

        Las dos anclas originales —`focus:ring-1` y `focus:ring-indigo-500`, de los cinco
        campos del wizard de programas— **ya no existen**: FE-20 (Cambio 167) pasó esos
        widgets a `nodo-field`, que trae su propio foco de marca. Exigirlas acá haría
        fallar el test por una clase que nadie usa, no por el `content`.
        """
        build = design_audit._clases_del_build()
        esperadas = ("cursor-not-allowed", "file:bg-blue-600")

        # `assertTrue` y no `assertIn`: el set del build tiene ~1.400 clases y
        # unittest lo volcaría entero en el mensaje de error.
        faltan = sorted(c for c in esperadas if c not in build)
        self.assertTrue(
            not faltan,
            f"se usan desde un .py y el build no las tiene: {faltan}. "
            "Revisar que `content` de tailwind.config.js cubra los .py y rebuildear.",
        )
