"""Ola 5 · PR 4 — FE-06 (clases que el build no genera) y FE-01 (`mobile-enhancements.js`).

Las dos fichas son del mismo síntoma: un control que *parece* estar pero el navegador
no lo dibuja, o lo dibuja distinto de lo que dice el template.

- **FE-06**: `tailwind.config.js` declara `extend.backgroundColor.gray` como string, lo
  que pisa la escala `gray` entera para `bg-*`. Un `bg-gray-300` no genera ninguna regla:
  el «Cancelar» queda sin caja y el backdrop del sidebar, transparente. Igual con
  `bg-white/78`, que no se genera porque `white` es `var(--bg-white)` sin `<alpha-value>`.
  La escala **no** se agrega al build (va contra los tokens): cada uso se reemplaza por
  la pieza canónica.
- **FE-01**: `static/custom/js/mobile-enhancements.js` se cargaba en **todo** el
  backoffice y reescribía estilos en línea sobre cualquier `button`/`a` más chico que
  44 px —también en escritorio—, ocultaba cualquier `[class*="modal"]` con un
  `touchstart` sin resolver su promesa ni devolver el foco, y abría el sidebar con
  cualquier swipe horizontal de más de 100 px, incluido el de una tabla con scroll.
  El área táctil se rescata en CSS y solo en táctil (`@media (pointer: coarse)`).
"""

import importlib.util
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

_SPEC = importlib.util.spec_from_file_location(
    "design_audit", Path(__file__).resolve().parents[2] / "scripts" / "design_audit.py"
)
design_audit = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(design_audit)

REPO = Path(settings.BASE_DIR)

#: Las pantallas y parciales que lista la ficha FE-06 (más el anexo
#: `anexo-front-clases-inexistentes.md`, lista A) como «vivos y en alcance».
#: Conversaciones y el portal quedan afuera a propósito: la lista D del anexo los
#: deja para el apagado de conversaciones (G1-01 fase 2) y para el portal.
PANTALLAS_FE06 = (
    "templates/includes/base.html",
    "templates/includes/sidebar/base.html",
    "templates/legajos/alertas_dashboard.html",
    "legajos/templates/legajos/ciudadano_confirmar_form.html",
    "legajos/templates/legajos/ciudadano_edit_form.html",
    "legajos/templates/legajos/ciudadano_manual_form.html",
    "legajos/templates/legajos/dashboard_contactos_simple.html",
    "legajos/templates/legajos/derivar_programa.html",
    "legajos/templates/legajos/historial_contactos_simple.html",
    "legajos/templates/legajos/programas/programa_detail.html",
    "legajos/templates/legajos/red_contactos_simple.html",
    "legajos/templates/legajos/reportes.html",
    "users/templates/rol/rol_form.html",
    "configuracion/templates/configuracion/localidad_form.html",
    "configuracion/templates/configuracion/localidad_confirm_delete.html",
    "configuracion/templates/configuracion/municipio_form.html",
    "configuracion/templates/configuracion/municipio_confirm_delete.html",
    "configuracion/templates/configuracion/provincia_form.html",
    "configuracion/templates/configuracion/provincia_confirm_delete.html",
    "configuracion/templates/configuracion/secretaria_form.html",
    "configuracion/templates/configuracion/secretaria_confirm_delete.html",
    "configuracion/templates/configuracion/subsecretaria_form.html",
    "configuracion/templates/configuracion/subsecretaria_confirm_delete.html",
    "configuracion/templates/configuracion/programa_wizard_paso1.html",
    "configuracion/templates/configuracion/programa_wizard_paso2.html",
    "configuracion/templates/configuracion/programa_wizard_paso3.html",
    "configuracion/templates/configuracion/programa_wizard_paso4.html",
    "programas/templates/programas/dispositivos/config/_tipo_detail_content.html",
    "programas/templates/programas/dispositivos/config/tipo_list.html",
    "programas/templates/programas/dispositivos/legajo/list.html",
    "programas/templates/programas/dispositivos/legajo/detail.html",
)


def _hallazgos(ruta_relativa, regla):
    """`audit_file` devuelve (severidad, línea, regla, mensaje, extracto)."""
    path = REPO / ruta_relativa
    return [
        f"{ruta_relativa}:{linea}: {mensaje}"
        for severidad, linea, r, mensaje, _ in design_audit.audit_file(path)
        if r == regla and severidad != "WARN"
    ]


class ClasesQueElBuildNoGeneraTests(SimpleTestCase):
    """FE-06: ninguna de las pantallas de la ficha nombra una clase inexistente."""

    def test_las_pantallas_de_la_ficha_no_usan_clases_fuera_del_build(self):
        hallazgos = [h for ruta in PANTALLAS_FE06 for h in _hallazgos(ruta, "CLASSDEF")]

        self.assertEqual(hallazgos, [], "clases que ningún CSS cargable define (controles invisibles)")

    def test_el_backdrop_del_sidebar_tiene_fondo_real(self):
        """A 390 px el backdrop quedaba transparente: `bg-gray-900/80` no existe."""
        sidebar = (REPO / "templates/includes/sidebar/base.html").read_text(encoding="utf-8")
        build = design_audit._clases_del_build()

        self.assertIn("bg-black/50", sidebar)
        self.assertNotIn("bg-gray-900/80", sidebar)
        self.assertIn("bg-black/50", build, "el backdrop canónico tiene que estar compilado")

    def test_el_html_no_pinta_un_fondo_que_no_existe(self):
        """El fondo de la página lo da `--fondo-principal` del shell, no una utilidad."""
        base = (REPO / "templates/includes/base.html").read_text(encoding="utf-8")
        linea_html = next(ln for ln in base.splitlines() if ln.lstrip().startswith("<html"))

        self.assertNotIn("bg-gray-50", linea_html)

    def test_los_cancelar_de_configuracion_son_botones_del_sistema(self):
        """Sin `btn-nodo` + variante + tamaño el «Cancelar» se renderiza sin caja."""
        sin_boton = []
        for ruta in PANTALLAS_FE06:
            if "/configuracion/" not in ruta and not ruta.endswith("rol/rol_form.html"):
                continue
            texto = (REPO / ruta).read_text(encoding="utf-8")
            if "Cancelar" in texto and "btn-nodo btn-tertiary btn-base" not in texto:
                sin_boton.append(ruta)

        self.assertEqual(sin_boton, [])


class MobileEnhancementsRetiradoTests(SimpleTestCase):
    """FE-01: el script global se fue y el área táctil la da el CSS, solo en táctil."""

    def test_el_shell_del_backoffice_no_carga_el_script(self):
        base = (REPO / "templates/includes/base.html").read_text(encoding="utf-8")

        self.assertNotIn("mobile-enhancements", base)

    def test_el_script_no_existe_en_el_repo(self):
        """Dejarlo escrito es dejar la trampa armada para el próximo template."""
        self.assertFalse((REPO / "static/custom/js/mobile-enhancements.js").exists())

    def test_ningun_template_ni_js_lo_referencia(self):
        fuentes = list((REPO / "templates").rglob("*.html"))
        fuentes += [
            f
            for app in ("configuracion", "core", "legajos", "portal", "programas", "users")
            for f in (REPO / app).rglob("templates/**/*.html")
        ]
        fuentes += list((REPO / "static/custom/js").glob("*.js"))
        culpables = [
            f.relative_to(REPO).as_posix()
            for f in fuentes
            if "custom/js/mobile-enhancements" in f.read_text(encoding="utf-8", errors="replace")
        ]

        self.assertEqual(culpables, [])

    def test_el_area_tactil_de_44px_la_da_el_css_y_solo_en_tactil(self):
        """En escritorio los botones conservan su alto de token (40 px en `btn-base`)."""
        css = (REPO / "static/custom/css/nodo-buttons.css").read_text(encoding="utf-8")

        self.assertIn("@media (pointer: coarse)", css)
        bloque = css.split("@media (pointer: coarse)", 1)[1]
        self.assertIn(".btn-nodo", bloque)
        self.assertIn(".nodo-icon-btn", bloque)
        self.assertIn("min-height: 44px", bloque)

    def test_un_boton_del_sistema_con_hidden_queda_oculto(self):
        """El «Cancelar» de un `ModernModal` de aviso se veía igual.

        No lo causaba el script: `nodo-buttons.css` se carga **después** de
        `tailwind.css` y `.btn-nodo { display: inline-flex }` tiene la misma
        especificidad que `.hidden`, así que ganaba por orden. El criterio de
        verificación de FE-01 (`ModernModal.show({type:'success'})` deja
        `#modal-cancel` en `display:none`) no se cumplía por este motivo.
        """
        css = (REPO / "static/custom/css/nodo-buttons.css").read_text(encoding="utf-8")

        self.assertRegex(css, r"\.btn-nodo\.hidden,\s*\n\s*\.nodo-icon-btn\.hidden\s*\{\s*\n\s*display: none;")

    def test_el_sidebar_da_area_tactil_en_tactil(self):
        sidebar = (REPO / "templates/includes/sidebar/base.html").read_text(encoding="utf-8")

        self.assertIn("@media (pointer: coarse)", sidebar)
        bloque = sidebar.split("@media (pointer: coarse)", 1)[1]
        self.assertIn(".ds-snav a", bloque)
        self.assertIn("min-height: 44px", bloque)

    def test_el_navbar_no_esconde_el_boton_mobile_con_important(self):
        """El workaround culpaba a «Tailwind CDN»; la causa era el script global.

        `lg:hidden` del propio botón alcanza: el shell carga Tailwind compilado, no CDN.
        """
        navbar = (REPO / "templates/includes/navbar.html").read_text(encoding="utf-8")

        self.assertNotIn("mobile-menu-btn", navbar)
        self.assertNotIn("mobile-menu-sep", navbar)
        self.assertNotIn("display: none !important", navbar)
        self.assertIn('class="-m-2.5 p-2.5 lg:hidden"', navbar)
