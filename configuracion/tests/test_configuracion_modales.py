"""Ola 5 · PR 4 — FE-07: los modales de Configuración vuelven al arquetipo Modal.

Los diez modales (alta y edición de Provincias, Municipios, Localidades, Secretarías
y Subsecretarías) traían el overlay con `x-show` **y** `display:flex` en línea. Alpine
borra el `display` del estilo en línea al mostrar, así que el overlay quedaba `block`
y el panel se dibujaba en la esquina (16, 16) en vez de centrado. El pie, además, con
`btn-nodo btn-tertiary` sin tamaño: sin `btn-base` el botón queda con
`padding-left: 0px` y sin alto.

El arreglo es clonar el modal golden (`programas/becas/config/programa_list.html`), ya
saneado por el paso 3 de la Ola 6: overlay por clase, backdrop `bg-black/50`, panel
`max-h-[90vh] flex flex-col`, `_modal_header.html` / `_modal_footer.html` y
`x-becas-modal`, que es el que da foco inicial, Tab atrapado, Escape y devolución del
foco. La confirmación de borrado pasa de un `Swal.fire` propio a `data-confirm-url` →
`ModernModal`, el motor que el shell ya carga (arquetipo Confirmación).

La estructura la mide `design_audit.py --arquetipo modal`; acá se la corre sobre las
cinco pantallas para que el gate viva también adentro de la suite.
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

PANTALLAS = (
    "provincia_list.html",
    "municipio_list.html",
    "localidad_list.html",
    "secretaria_list.html",
    "subsecretaria_list.html",
)


def _texto(nombre):
    return (REPO / "configuracion/templates/configuracion" / nombre).read_text(encoding="utf-8")


class ModalesDeConfiguracionTests(SimpleTestCase):
    def test_cumplen_el_arquetipo_modal(self):
        """`--arquetipo modal`: marcadores en orden y ningún prohibido."""
        import contextlib
        import io

        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            codigo = design_audit.arquetipo_mode(
                "modal", [f"configuracion/templates/configuracion/{n}" for n in PANTALLAS]
            )

        self.assertEqual(codigo, 0, salida.getvalue())

    def test_el_overlay_se_centra_por_clase_y_no_por_style(self):
        """`display:flex` en línea + `x-show` = panel en la esquina al abrir."""
        for nombre in PANTALLAS:
            with self.subTest(nombre):
                texto = _texto(nombre)
                self.assertNotIn("backdrop-filter", texto)
                self.assertNotIn("position:fixed; inset:0", texto)
                self.assertIn('class="fixed inset-0 z-50 flex items-center justify-center p-4"', texto)

    def test_los_modales_atrapan_el_foco_y_cierran_con_escape(self):
        """`x-becas-modal` en los dos overlays (alta y edición) + el JS cargado."""
        for nombre in PANTALLAS:
            with self.subTest(nombre):
                texto = _texto(nombre)
                self.assertEqual(texto.count("x-becas-modal="), 2, "alta y edición")
                self.assertIn("custom/js/becas-modal.js", texto)

    def test_el_pie_del_modal_usa_la_pieza_canonica(self):
        """Sin `_modal_footer.html` los botones vuelven a quedar sin tamaño."""
        for nombre in PANTALLAS:
            with self.subTest(nombre):
                texto = _texto(nombre)
                self.assertEqual(texto.count("_modal_header.html"), 2)
                self.assertEqual(texto.count("_modal_footer.html"), 2)

    def test_ningun_boton_del_sistema_queda_sin_tamano(self):
        """`btn-nodo` + variante sin tamaño = `padding-left: 0px` y sin alto.

        Es el mismo defecto que FE-07 describe en el pie del modal; en estas
        pantallas también lo tenían «Filtrar» y «Limpiar» de la barra de filtros.
        """
        import re

        for nombre in PANTALLAS:
            with self.subTest(nombre):
                sin_tamano = [m.group(0) for m in re.finditer(r'class="btn-nodo btn-\w+"', _texto(nombre))]
                self.assertEqual(sin_tamano, [])

    def test_la_confirmacion_de_borrado_es_la_canonica(self):
        """`data-confirm-url` → `ModernModal`; sin SweetAlert propio en la pantalla."""
        for nombre in PANTALLAS:
            with self.subTest(nombre):
                texto = _texto(nombre)
                self.assertIn("data-confirm-url=", texto)
                self.assertIn("_confirm_js.html", texto)
                self.assertNotIn("Swal.fire", texto)
                self.assertNotIn("sweetalert2", texto)

    def test_el_titulo_del_dialogo_lo_nombra(self):
        for nombre in PANTALLAS:
            with self.subTest(nombre):
                texto = _texto(nombre)
                self.assertEqual(texto.count('role="dialog"'), 2)
                self.assertEqual(texto.count('aria-modal="true"'), 2)
                self.assertEqual(texto.count('aria-labelledby="'), 2)


class SubitemsDelSidebarTests(SimpleTestCase):
    """FE-07, última línea: los contenedores de subítems iban con `style=`."""

    def test_los_contenedores_de_subitems_van_por_clase(self):
        opciones = (REPO / "templates/includes/sidebar/opciones.html").read_text(encoding="utf-8")

        self.assertNotIn("display: flex; flex-direction: column; gap: 2px;", opciones)
        self.assertEqual(opciones.count('class="mt-0.5 ml-5 flex flex-col gap-0.5"'), 5)
        self.assertIn('<nav class="ds-snav flex flex-col gap-0.5">', opciones)
