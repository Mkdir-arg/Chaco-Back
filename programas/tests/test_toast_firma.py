"""Los avisos llaman a ``window.toast(tipo, mensaje)`` en el orden correcto (W1-C2).

``static/custom/js/nodo-toast.js`` expone ``window.toast(tipo, mensaje, opts)``. Varios
lugares lo llamaban al revés, ``window.toast(mensaje, tipo)``: el usuario veía un toast
gris «Información» con el texto literal «success» o «error» y el mensaje real se perdía.
Se ejecuta el ``nodo-toast.js`` real con ``node`` y se verifica qué toast se arma.
"""

import json
import re
import subprocess
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase
from django.urls import reverse

from core.tests.js_harness import NODE, requiere_node
from programas.tests import test_becas_revision as base

JS = Path(settings.BASE_DIR) / "static" / "custom" / "js"
TEMPLATE = (
    Path(settings.BASE_DIR) / "programas" / "templates" / "programas" / "becas" / "revision" / "formulario_detalle.html"
)
ARCHIVOS = [JS / "nodo-constructor.js", JS / "nodo-catalogo-grupos.js", TEMPLATE]

# Toma solo la función ``aviso`` del archivo real (sin correr el resto del IIFE).
_AVISO = re.compile(r"function aviso\(mensaje, tipo\) \{.*?\n  \}", re.S)

# DOM mínimo que conserva lo que nodo-toast.js le asigna a cada elemento.
_DOM = r"""
var window = globalThis;
var __creados = [];
var requestAnimationFrame = function () {};
function __el(tag) {
  var e = {tag: tag, className: '', textContent: '', children: [], style: {}, dataset: {},
           setAttribute: function () {}, addEventListener: function () {},
           appendChild: function (h) { this.children.push(h); return h; },
           insertBefore: function (h) { this.children.push(h); return h; },
           classList: {add: function () {}, remove: function () {}}};
  __creados.push(e);
  return e;
}
var document = {readyState: 'complete', addEventListener: function () {}, getElementById: function () { return null; },
                createElement: __el, body: __el('body')};
"""


def _aviso_de(archivo):
    return _AVISO.search(archivo.read_text(encoding="utf-8")).group(0)


def _toasts_armados(archivo, llamada):
    """Carga el nodo-toast.js real y la función ``aviso`` real; devuelve ``[(clase, texto)]``."""
    motor = (JS / "nodo-toast.js").read_text(encoding="utf-8")
    programa = (
        _DOM
        + motor
        + "\n"
        + _aviso_de(archivo)
        + "\n"
        + llamada
        + "\nconsole.log(JSON.stringify(__creados.filter(function (e) { return /^toast /.test(e.className); })"
        ".map(function (t) { return [t.className, __creados.filter(function (e) {"
        " return e.className === 'toast__message'; }).map(function (e) { return e.textContent; })]; })));"
    )
    proceso = subprocess.run([NODE, "-"], input=programa, capture_output=True, text=True, encoding="utf-8", timeout=30)
    if proceso.returncode != 0:
        raise AssertionError(f"node falló:\n{proceso.stderr}")
    return json.loads(proceso.stdout.strip().splitlines()[-1])


@requiere_node
class AvisoMuestraElMensajeRealTests(SimpleTestCase):
    def _assert_toast(self, archivo, llamada, clase, mensaje):
        toasts = _toasts_armados(archivo, llamada)
        self.assertEqual(len(toasts), 1, toasts)
        self.assertEqual(toasts[0][0], f"toast {clase}")
        self.assertEqual(toasts[0][1], [mensaje])

    def test_constructor_por_defecto_es_success_con_el_mensaje(self):
        self._assert_toast(JS / "nodo-constructor.js", "aviso('Listo');", "toast--success", "Listo")

    def test_constructor_error_lleva_el_mensaje_y_no_la_palabra_error(self):
        self._assert_toast(JS / "nodo-constructor.js", "aviso('No se pudo', 'error');", "toast--error", "No se pudo")

    def test_catalogo_por_defecto_es_success_con_el_mensaje(self):
        self._assert_toast(JS / "nodo-catalogo-grupos.js", "aviso('Listo');", "toast--success", "Listo")

    def test_catalogo_error_lleva_el_mensaje_y_no_la_palabra_error(self):
        self._assert_toast(JS / "nodo-catalogo-grupos.js", "aviso('Falló', 'error');", "toast--error", "Falló")


class SinFirmaInvertidaTests(SimpleTestCase):
    INVERTIDA = re.compile(
        r"window\.toast\(\s*(?!['\"](?:success|error|warning|info)['\"]|tipo\b)[^,]+,\s*['\"]?(?:success|error|warning|info|tipo)"
    )

    def test_no_quedan_llamadas_con_el_orden_invertido(self):
        for archivo in ARCHIVOS:
            with self.subTest(archivo=archivo.name):
                self.assertIsNone(self.INVERTIDA.search(archivo.read_text(encoding="utf-8")))


class DetalleDelCasoAvisaConElOrdenCorrectoTests(base._BaseAprobacionTest):
    def setUp(self):
        super().setUp()
        patch("programas.forms.catalogo", side_effect=base._catalogo_siis_falso).start()
        patch("programas.forms.listar_programas", side_effect=base._programas_siis_falsos).start()
        self.addCleanup(patch.stopall)

    def test_render_usa_tipo_primero(self):
        resp = self.client.get(reverse("becas:formulario_detalle", args=[self.form_a.pk]))
        html = resp.content.decode()
        self.assertEqual(html.count("window.toast('error',"), 4)
        self.assertNotRegex(html, r"window\.toast\([^)]*,\s*'error'\)")
