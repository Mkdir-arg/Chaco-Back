"""FE-24 · Teclado de las solapas del backoffice (`static/custom/js/nodo-tabs.js`).

Hasta este PR la navegación por flechas existía en **una** pantalla —escrita a mano en
el `<script>` de `legajos/ciudadano_detail.html`— y las solapas de Becas y del ABM de
roles no tenían ni ARIA ni teclado. Ahora el shell carga un único archivo que cubre
cualquier `[role="tablist"]`.

No hay harness de navegador (D-RED-06 = No), así que el archivo real se ejecuta con
`node` sobre un DOM mínimo escrito acá: elementos con atributos, `closest`,
`querySelectorAll` por rol y un despachador de `keydown`. Alcanza, porque lo que el
script hace es exactamente eso: mover el foco, disparar el `click` que la pantalla ya
escucha y repartir el `tabindex`.
"""

import json
import subprocess
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from core.tests.js_harness import NODE, requiere_node

JS = Path(settings.BASE_DIR) / "static" / "custom" / "js" / "nodo-tabs.js"

_DOM = r"""
var __log = {focos: [], clicks: []};
var __handlers = {};

function Element(tagName, attrs) {
  this.tagName = tagName;
  this._attrs = Object.assign({}, attrs || {});
  this.disabled = false;
  this.hijos = [];
  this.padre = null;
}
Element.prototype.getAttribute = function (n) { return n in this._attrs ? this._attrs[n] : null; };
Element.prototype.setAttribute = function (n, v) { this._attrs[n] = String(v); };
Element.prototype.hasAttribute = function (n) { return n in this._attrs; };
Element.prototype.focus = function () { __log.focos.push(this._attrs.id); };
Element.prototype.click = function () { __log.clicks.push(this._attrs.id); };
Element.prototype.querySelectorAll = function (selector) {
  var rol = /^\[role="([^"]+)"\]$/.exec(selector)[1];
  var encontrados = [];
  (function bajar(nodo) {
    nodo.hijos.forEach(function (hijo) {
      if (hijo.getAttribute('role') === rol) encontrados.push(hijo);
      bajar(hijo);
    });
  })(this);
  return encontrados;
};
Element.prototype.closest = function (selector) {
  var rol = /^\[role="([^"]+)"\]$/.exec(selector)[1];
  var nodo = this;
  while (nodo) {
    if (nodo.getAttribute && nodo.getAttribute('role') === rol) return nodo;
    nodo = nodo.padre;
  }
  return null;
};

var __raiz = new Element('BODY', {});
function __agregar(padre, hijo) { hijo.padre = padre; padre.hijos.push(hijo); return hijo; }

// Una barra con `n` solapas; la de índice `activa` lleva aria-selected="true".
function __barra(n, activa, extras) {
  var lista = __agregar(__raiz, new Element('DIV', {role: 'tablist', id: 'lista'}));
  for (var i = 0; i < n; i++) {
    var attrs = {role: 'tab', id: 't' + i, 'aria-selected': i === activa ? 'true' : 'false'};
    Object.assign(attrs, (extras || {})[i] || {});
    var tab = __agregar(lista, new Element('BUTTON', attrs));
    if (attrs.disabled) tab.disabled = true;
  }
  return lista;
}

var document = {
  readyState: 'complete',
  addEventListener: function (tipo, fn) { (__handlers[tipo] = __handlers[tipo] || []).push(fn); },
  querySelectorAll: function (selector) { return __raiz.querySelectorAll(selector); }
};
var window = globalThis;
var MutationObserver = function (fn) { this.fn = fn; };
MutationObserver.prototype.observe = function () {};

function __tecla(tab, key) {
  var ev = {
    target: tab, key: key, altKey: false, ctrlKey: false, metaKey: false,
    defaultPrevented: false, preventDefault: function () { this.defaultPrevented = true; }
  };
  (__handlers.keydown || []).forEach(function (fn) { fn(ev); });
  return ev;
}

function __tabindex(lista) {
  return lista.querySelectorAll('[role="tab"]').map(function (t) { return t.getAttribute('tabindex'); });
}
"""

_VOLCADO = "\nconsole.log(JSON.stringify(__log));\n"


def _correr(acciones):
    programa = _DOM + "\n" + JS.read_text(encoding="utf-8") + "\n" + acciones + _VOLCADO
    proceso = subprocess.run([NODE, "-"], input=programa, capture_output=True, text=True, encoding="utf-8", timeout=30)
    if proceso.returncode != 0:
        raise AssertionError(f"node falló:\n{proceso.stderr}")
    return json.loads(proceso.stdout.strip().splitlines()[-1])


@requiere_node
class TecladoDeSolapasTests(SimpleTestCase):
    def test_la_flecha_derecha_mueve_el_foco_y_activa_la_siguiente(self):
        log = _correr("var l = __barra(3, 0);\n__tecla(l.hijos[0], 'ArrowRight');\n")

        self.assertEqual(log["focos"], ["t1"])
        self.assertEqual(log["clicks"], ["t1"], "activación automática: la solapa enfocada se abre")

    def test_la_flecha_izquierda_vuelve_y_da_la_vuelta(self):
        log = _correr("var l = __barra(3, 0);\n__tecla(l.hijos[0], 'ArrowLeft');\n")

        self.assertEqual(log["focos"], ["t2"], "desde la primera, la izquierda lleva a la última")

    def test_home_y_end_van_a_los_extremos(self):
        log = _correr("var l = __barra(4, 1);\n__tecla(l.hijos[1], 'End');\n__tecla(l.hijos[3], 'Home');\n")

        self.assertEqual(log["focos"], ["t3", "t0"])
        self.assertEqual(log["clicks"], ["t3", "t0"])

    def test_otras_teclas_no_hacen_nada(self):
        log = _correr(
            "var l = __barra(3, 0);\n"
            "__log.tab = __tecla(l.hijos[0], 'Tab').defaultPrevented;\n"
            "__log.enter = __tecla(l.hijos[0], 'Enter').defaultPrevented;\n"
        )

        self.assertFalse(log["tab"], "Tab tiene que seguir saliendo de la barra")
        self.assertFalse(log["enter"])
        self.assertEqual(log["focos"], [])

    def test_con_una_tecla_modificadora_no_interviene(self):
        """Ctrl/Alt/Cmd + flecha son atajos del navegador (historial, escritorio)."""
        log = _correr(
            "var l = __barra(3, 0);\n"
            "var ev = {target: l.hijos[0], key: 'ArrowRight', ctrlKey: true, altKey: false, metaKey: false,"
            " preventDefault: function () {}};\n"
            "(__handlers.keydown || []).forEach(function (fn) { fn(ev); });\n"
        )

        self.assertEqual(log["focos"], [])

    def test_una_tecla_fuera_de_una_barra_de_solapas_no_la_mueve(self):
        log = _correr(
            "var suelto = __agregar(__raiz, new Element('BUTTON', {id: 'suelto'}));\n"
            "__barra(3, 0);\n__tecla(suelto, 'ArrowRight');\n"
        )

        self.assertEqual(log["focos"], [])

    def test_el_tabindex_itinerante_deja_tabulable_solo_la_activa(self):
        log = _correr("var l = __barra(3, 1);\nwindow.NodoTabs.montar();\n__log.tabindex = __tabindex(l);\n")

        self.assertEqual(log["tabindex"], ["-1", "0", "-1"])

    def test_sin_ninguna_marcada_la_tabulable_es_la_primera(self):
        log = _correr(
            "var l = __barra(3, 0, {0: {'aria-selected': 'false'}});\n"
            "window.NodoTabs.montar();\n__log.tabindex = __tabindex(l);\n"
        )

        self.assertEqual(log["tabindex"], ["0", "-1", "-1"])

    def test_el_tabindex_sigue_a_aria_selected_cuando_cambia_la_solapa(self):
        """Alpine escribe `:aria-selected` después del click; el reparto lo vuelve a leer."""
        log = _correr(
            "var l = __barra(3, 0);\nwindow.NodoTabs.montar();\n"
            "l.hijos[0].setAttribute('aria-selected', 'false');\n"
            "l.hijos[2].setAttribute('aria-selected', 'true');\n"
            "window.NodoTabs.repartirTabindex(l);\n__log.tabindex = __tabindex(l);\n"
        )

        self.assertEqual(log["tabindex"], ["-1", "-1", "0"])

    def test_una_solapa_deshabilitada_u_oculta_se_saltea(self):
        log = _correr(
            "var l = __barra(3, 0, {1: {disabled: 'disabled'}, 2: {hidden: ''}});\n__tecla(l.hijos[0], 'ArrowRight');\n"
        )

        self.assertEqual(log["focos"], [], "queda una sola activable: no hay a dónde moverse")
        self.assertEqual(log["clicks"], [], "y no se la re-activa de gusto")

    def test_una_barra_con_una_sola_solapa_no_se_mueve(self):
        log = _correr("var l = __barra(1, 0);\n__tecla(l.hijos[0], 'ArrowRight');\n")

        self.assertEqual(log["clicks"], [])


class CargaEnElShellTests(SimpleTestCase):
    def test_el_shell_carga_el_script_una_sola_vez(self):
        shell = (Path(settings.BASE_DIR) / "templates" / "includes" / "base.html").read_text(encoding="utf-8")

        self.assertEqual(shell.count("custom/js/nodo-tabs.js"), 1)

    def test_el_detalle_del_ciudadano_ya_no_trae_su_propio_handler(self):
        """Era la única implementación del repo y valía para una sola pantalla."""
        detalle = (Path(settings.BASE_DIR) / "legajos" / "templates" / "legajos" / "ciudadano_detail.html").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("ArrowRight", detalle)
        self.assertNotIn("ArrowLeft", detalle)
