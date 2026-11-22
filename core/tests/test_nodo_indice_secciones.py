"""Índice de secciones de un modal largo (`static/custom/js/nodo-indice-secciones.js`).

Lo usa el modal «Registrar egreso» de Dispositivos (P4 y P7) cuando el formulario del tipo trae 2 o más grupos. No hay
harness de navegador (D-RED-06 = No), así que el archivo real se ejecuta con `node` sobre un DOM mínimo escrito acá:
elementos con atributos, clases, `closest`, `querySelectorAll` por atributo, `scrollIntoView`, `focus` y un
`MutationObserver` que se dispara a mano. Alcanza, porque lo que el script hace es exactamente eso: armar botones desde
las secciones, llevar el foco y el scroll a la elegida, seguir el scroll y reflejar lo oculto y lo que tiene errores.
"""

import json
import subprocess
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from core.tests.js_harness import NODE, requiere_node

JS = Path(settings.BASE_DIR) / "static" / "custom" / "js" / "nodo-indice-secciones.js"

_DOM = r"""
var __log = {scrolls: [], focos: [], observadores: 0};
var __observadores = [];

function Clases(el) { this.el = el; this.set = new Set(); }
Clases.prototype.add = function (c) { this.set.add(c); };
Clases.prototype.remove = function (c) { this.set.delete(c); };
Clases.prototype.contains = function (c) { return this.set.has(c); };
Clases.prototype.toggle = function (c, forzar) {
  var poner = forzar === undefined ? !this.set.has(c) : !!forzar;
  if (poner) { this.set.add(c); } else { this.set.delete(c); }
  return poner;
};

function Element(tagName, attrs) {
  this.tagName = tagName;
  this._attrs = Object.assign({}, attrs || {});
  this.hijos = [];
  this.padre = null;
  this.classList = new Clases(this);
  this.textContent = '';
  this.hidden = 'hidden' in this._attrs;
  this.top = 0;
  this.scrollTop = 0;
  this.clientHeight = 100;
  this.scrollHeight = 1000;
  this._oyentes = {};
}
Object.defineProperty(Element.prototype, 'className', {
  set: function (valor) { var self = this; this.classList.set = new Set(); String(valor).split(/\s+/).filter(Boolean).forEach(function (c) { self.classList.add(c); }); },
  get: function () { return Array.from(this.classList.set).join(' '); }
});
Element.prototype.getAttribute = function (n) { return n in this._attrs ? this._attrs[n] : null; };
Element.prototype.setAttribute = function (n, v) { this._attrs[n] = String(v); };
Element.prototype.removeAttribute = function (n) { delete this._attrs[n]; };
Element.prototype.hasAttribute = function (n) { return n === 'hidden' ? this.hidden : n in this._attrs; };
Element.prototype.appendChild = function (hijo) { hijo.padre = this; this.hijos.push(hijo); return hijo; };
Element.prototype.addEventListener = function (tipo, fn) { (this._oyentes[tipo] = this._oyentes[tipo] || []).push(fn); };
Element.prototype.disparar = function (tipo) { (this._oyentes[tipo] || []).forEach(function (fn) { fn({}); }); };
Element.prototype.getBoundingClientRect = function () { return {top: this.top}; };
Element.prototype.scrollIntoView = function (opciones) { __log.scrolls.push({id: this._attrs.id, opciones: opciones}); };
Element.prototype.focus = function (opciones) { __log.focos.push({id: this._attrs.id, opciones: opciones || null}); };
Element.prototype._coincide = function (selector) {
  var m = /^\[([a-z-]+)(?:="([^"]*)")?\]$/.exec(selector);
  if (!m) { throw new Error('selector no soportado: ' + selector); }
  if (!(m[1] in this._attrs)) { return false; }
  return m[2] === undefined || this._attrs[m[1]] === m[2];
};
Element.prototype.querySelectorAll = function (selector) {
  var encontrados = [];
  (function bajar(nodo) {
    nodo.hijos.forEach(function (hijo) { if (hijo._coincide(selector)) { encontrados.push(hijo); } bajar(hijo); });
  })(this);
  return encontrados;
};
Element.prototype.querySelector = function (selector) { return this.querySelectorAll(selector)[0] || null; };
Element.prototype.closest = function (selector) {
  var nodo = this;
  while (nodo) { if (nodo._coincide(selector)) { return nodo; } nodo = nodo.padre; }
  return null;
};

var __raiz = new Element('BODY', {});
var document = {
  readyState: 'complete',
  addEventListener: function () {},
  createElement: function (tag) { return new Element(tag.toUpperCase(), {}); },
  querySelectorAll: function () { return []; }
};
var window = globalThis;
window.matchMedia = function () { return {matches: !!window.__quieto}; };
window.MutationObserver = function (fn) { this.fn = fn; this.observados = []; __observadores.push(this); };
window.MutationObserver.prototype.observe = function (nodo) { this.observados.push(nodo); __log.observadores += 1; };

// Un cuerpo con un <nav> y `n` secciones; `titulos` por posición. Devuelve {cuerpo, nav, secciones}.
function __modal(titulos) {
  var cuerpo = __raiz.appendChild(new Element('DIV', {'data-indice-cuerpo': ''}));
  var nav = cuerpo.appendChild(new Element('NAV', {'data-indice-secciones': '', hidden: ''}));
  var lista = nav.appendChild(new Element('OL', {'data-indice-lista': ''}));
  var secciones = titulos.map(function (titulo, i) {
    return cuerpo.appendChild(new Element('SECTION', {id: 's' + i, 'data-indice-seccion': '', 'data-indice-titulo': titulo}));
  });
  return {cuerpo: cuerpo, nav: nav, lista: lista, secciones: secciones};
}
function __botones(m) { return m.lista.hijos.map(function (li) { return li.hijos[0]; }); }
function __actual(m) {
  return __botones(m).map(function (b) { return b.getAttribute('aria-current') === 'true'; });
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
class IndiceDeSeccionesTests(SimpleTestCase):
    def test_arma_un_boton_por_seccion_con_su_titulo_y_muestra_el_indice(self):
        log = _correr(
            "var m = __modal(['Datos del egreso', 'Datos del ingreso', 'Referentes']);\n"
            "NodoIndiceSecciones.montar(m.nav);\n"
            "var b = __botones(m);\n"
            "__log.textos = b.map(function (x) { return x.hijos[0].textContent; });\n"
            "__log.tipos = b.map(function (x) { return x.tagName + ':' + x.type; });\n"
            "__log.nav_oculto = m.nav.hidden;\n"
        )

        self.assertEqual(log["textos"], ["Datos del egreso", "Datos del ingreso", "Referentes"])
        self.assertEqual(log["tipos"], ["BUTTON:button"] * 3, "botones reales: Tab llega y Enter/Espacio activan")
        self.assertFalse(log["nav_oculto"])

    def test_el_titulo_se_escribe_como_texto_nunca_como_html(self):
        log = _correr(
            "var m = __modal(['<img src=x onerror=alert(1)>', 'Otra']);\n"
            "NodoIndiceSecciones.montar(m.nav);\n"
            "__log.texto = __botones(m)[0].hijos[0].textContent;\n"
            "__log.html_asignado = Object.prototype.hasOwnProperty.call(__botones(m)[0], 'innerHTML');\n"
        )

        self.assertEqual(log["texto"], "<img src=x onerror=alert(1)>")
        self.assertFalse(log["html_asignado"])

    def test_el_clic_lleva_a_la_seccion_le_da_el_foco_y_la_marca_actual(self):
        log = _correr(
            "var m = __modal(['A', 'B', 'C']);\n"
            "NodoIndiceSecciones.montar(m.nav);\n"
            "__botones(m)[2].disparar('click');\n"
            "__log.actual = __actual(m);\n"
        )

        self.assertEqual([s["id"] for s in log["scrolls"]], ["s2"])
        self.assertEqual(log["scrolls"][0]["opciones"], {"block": "start", "behavior": "smooth"})
        self.assertEqual(log["focos"], [{"id": "s2", "opciones": {"preventScroll": True}}])
        self.assertEqual(log["actual"], [False, False, True])

    def test_con_movimiento_reducido_el_scroll_es_inmediato(self):
        log = _correr(
            "window.__quieto = true;\n"
            "var m = __modal(['A', 'B']);\n"
            "NodoIndiceSecciones.montar(m.nav);\n"
            "__botones(m)[1].disparar('click');\n"
        )

        self.assertEqual(log["scrolls"][0]["opciones"]["behavior"], "auto")

    def test_la_entrada_activa_cambia_de_estilo_y_las_otras_no_la_comparten(self):
        log = _correr(
            "var m = __modal(['A', 'B']);\n"
            "NodoIndiceSecciones.montar(m.nav);\n"
            "__botones(m)[1].disparar('click');\n"
            "var b = __botones(m);\n"
            "__log.activa = b[1].className; __log.inactiva = b[0].className;\n"
        )

        self.assertIn("bg-brand-soft", log["activa"])
        self.assertIn("font-bold", log["activa"])
        self.assertNotIn("hover:bg-secondary", log["activa"])
        self.assertIn("hover:bg-secondary", log["inactiva"])
        self.assertNotIn("bg-brand-soft", log["inactiva"])

    def test_el_indice_sigue_al_scroll(self):
        log = _correr(
            "var m = __modal(['A', 'B', 'C']);\n"
            "m.secciones[0].top = -300; m.secciones[1].top = 10; m.secciones[2].top = 400;\n"
            "NodoIndiceSecciones.montar(m.nav);\n"
            "m.cuerpo.scrollTop = 300;\n"
            "m.cuerpo.disparar('scroll');\n"
            "__log.actual = __actual(m);\n"
        )

        self.assertEqual(log["actual"], [False, True, False], "la segunda ya llegó al tope; la tercera todavía no")

    def test_al_final_del_scroll_queda_la_ultima_aunque_no_llegue_al_tope(self):
        log = _correr(
            "var m = __modal(['A', 'B', 'C']);\n"
            "m.secciones[0].top = -900; m.secciones[1].top = -400; m.secciones[2].top = 80;\n"
            "NodoIndiceSecciones.montar(m.nav);\n"
            "m.cuerpo.scrollTop = 900; m.cuerpo.clientHeight = 100; m.cuerpo.scrollHeight = 1000;\n"
            "m.cuerpo.disparar('scroll');\n"
            "__log.actual = __actual(m);\n"
        )

        self.assertEqual(log["actual"], [False, False, True])

    def test_una_seccion_oculta_por_una_condicion_sale_del_indice(self):
        log = _correr(
            "var m = __modal(['A', 'B', 'C']);\n"
            "NodoIndiceSecciones.montar(m.nav);\n"
            "m.secciones[1].hidden = true;\n"
            "__observadores[0].fn();\n"
            "__log.ocultas = m.lista.hijos.map(function (li) { return li.hidden; });\n"
            "__log.nav_oculto = m.nav.hidden;\n"
        )

        self.assertEqual(log["ocultas"], [False, True, False])
        self.assertFalse(log["nav_oculto"])

    def test_con_menos_de_dos_secciones_visibles_el_indice_entero_se_oculta(self):
        log = _correr(
            "var m = __modal(['A', 'B']);\n"
            "NodoIndiceSecciones.montar(m.nav);\n"
            "__log.antes = m.nav.hidden;\n"
            "m.secciones[1].hidden = true;\n"
            "__observadores[0].fn();\n"
            "__log.despues = m.nav.hidden;\n"
        )

        self.assertFalse(log["antes"])
        self.assertTrue(log["despues"])

    def test_una_seccion_con_un_error_visible_marca_su_entrada_en_texto(self):
        log = _correr(
            "var m = __modal(['A', 'B']);\n"
            "var aviso = m.secciones[1].appendChild(new Element('P', {'data-error': 'campo'}));\n"
            "aviso.classList.add('hidden');\n"
            "NodoIndiceSecciones.montar(m.nav);\n"
            "var marcas = function () { return __botones(m).map(function (b) { return b.hijos[1].hidden; }); };\n"
            "__log.sin_error = marcas();\n"
            "aviso.classList.remove('hidden'); aviso.textContent = 'Este dato es obligatorio.';\n"
            "__observadores[0].fn();\n"
            "__log.con_error = marcas();\n"
            "__log.texto_marca = __botones(m)[1].hijos[1].textContent;\n"
        )

        self.assertEqual(log["sin_error"], [True, True])
        self.assertEqual(log["con_error"], [True, False])
        self.assertEqual(log["texto_marca"], "Revisar", "el color solo no alcanza")

    def test_un_control_invalido_tambien_cuenta_como_error(self):
        log = _correr(
            "var m = __modal(['A', 'B']);\n"
            "m.secciones[0].appendChild(new Element('INPUT', {'aria-invalid': 'true'}));\n"
            "NodoIndiceSecciones.montar(m.nav);\n"
            "__log.marcas = __botones(m).map(function (b) { return b.hijos[1].hidden; });\n"
        )

        self.assertEqual(log["marcas"], [False, True])

    def test_sin_nav_o_sin_cuerpo_o_sin_secciones_no_hace_nada(self):
        log = _correr(
            "__log.sin_nav = NodoIndiceSecciones.montar(null);\n"
            "var suelto = __raiz.appendChild(new Element('NAV', {'data-indice-secciones': ''}));\n"
            "__log.sin_cuerpo = NodoIndiceSecciones.montar(suelto);\n"
            "var m = __modal([]);\n"
            "__log.sin_secciones = NodoIndiceSecciones.montar(m.nav);\n"
        )

        self.assertIsNone(log["sin_nav"])
        self.assertIsNone(log["sin_cuerpo"])
        self.assertIsNone(log["sin_secciones"])
