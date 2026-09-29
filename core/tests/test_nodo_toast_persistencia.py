"""Persistencia de los toasts de error (nodo-toast.js real, sobre un DOM mínimo simulado)."""

import json
import subprocess
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from core.tests.js_harness import NODE, requiere_node

TOAST_JS = Path(settings.BASE_DIR) / "static" / "custom" / "js" / "nodo-toast.js"

_DOM = r"""
var __timers = [];
var __docListeners = {};
function El(tag) {
  var self = this;
  this.tag = tag; this.children = []; this.attrs = {}; this.listeners = {}; this.parentNode = null;
  this.style = {}; this.id = ''; this.textContent = ''; this.innerHTML = ''; this._cls = new Set();
  this.classList = {
    add: function (c) { self._cls.add(c); }, remove: function (c) { self._cls.delete(c); },
    contains: function (c) { return self._cls.has(c); }
  };
}
Object.defineProperty(El.prototype, 'className', {
  get: function () { return Array.from(this._cls).join(' '); },
  set: function (v) { this._cls = new Set(String(v).split(/\s+/).filter(Boolean)); }
});
El.prototype.setAttribute = function (k, v) { this.attrs[k] = String(v); };
El.prototype.getAttribute = function (k) { return k in this.attrs ? this.attrs[k] : null; };
El.prototype.appendChild = function (c) { c.parentNode = this; this.children.push(c); return c; };
El.prototype.removeChild = function (c) {
  this.children = this.children.filter(function (x) { return x !== c; }); c.parentNode = null;
};
El.prototype.addEventListener = function (t, fn) { (this.listeners[t] = this.listeners[t] || []).push(fn); };
El.prototype.fire = function (t, ev) { (this.listeners[t] || []).forEach(function (fn) { fn(ev || {}); }); };
El.prototype.getBoundingClientRect = function () { return {height: this._alto || 0, top: 0, bottom: 0}; };
El.prototype.focus = function () { document.activeElement = this; };
El.prototype.all = function () {
  return this.children.reduce(function (a, c) { return a.concat([c], c.all()); }, []);
};
El.prototype.contains = function (o) { return o === this || this.all().indexOf(o) !== -1; };
El.prototype.querySelectorAll = function (sel) {
  var m = sel.match(/^\.([\w-]+)(?:\[([\w-]+)="(\w+)"\])?$/);
  return this.all().filter(function (e) {
    return e.classList.contains(m[1]) && (!m[2] || e.getAttribute(m[2]) === m[3]);
  });
};
El.prototype.querySelector = function (sel) { return this.querySelectorAll(sel)[0] || null; };
var body = new El('body');
var __modales = [];
var document = {
  querySelectorAll: function () { return __modales; },
  readyState: 'complete', activeElement: null, body: body,
  addEventListener: function (t, fn) { (__docListeners[t] = __docListeners[t] || []).push(fn); },
  getElementById: function (id) { return body.all().filter(function (e) { return e.id === id; })[0] || null; },
  createElement: function (t) { return new El(t); }
};
var window = globalThis;
var requestAnimationFrame = function (fn) { fn(); };
setTimeout = function (fn, ms) { __timers.push({fn: fn, ms: ms}); return __timers.length; };
function __keydown(key, prevented) {
  (__docListeners.keydown || []).forEach(function (fn) { fn({key: key, defaultPrevented: !!prevented}); });
}
function __toasts() { return document.getElementById('toast-container').children; }
function __vivos() { return __toasts().filter(function (t) { return !t.classList.contains('toast--leaving'); }); }
function __terminarBarras() {
  __toasts().slice().forEach(function (t) {
    t.children.forEach(function (c) { if (c.classList.contains('toast__progress')) c.fire('animationend'); });
  });
}
function __remover() { __timers.splice(0).forEach(function (x) { x.fn(); }); }
function __botones(t) { return t.children.filter(function (c) { return c.classList.contains('toast__close'); }); }
"""


def _correr(cuerpo):
    programa = _DOM + TOAST_JS.read_text(encoding="utf-8") + "\n" + cuerpo + "\nconsole.log(JSON.stringify(R));"
    p = subprocess.run([NODE, "-"], input=programa, capture_output=True, text=True, encoding="utf-8", timeout=30)
    if p.returncode != 0:
        raise AssertionError(f"node falló:\n{p.stderr}")
    return json.loads(p.stdout.strip().splitlines()[-1])


@requiere_node
class ToastErrorPersistenteTest(SimpleTestCase):
    def test_error_no_lleva_barra_ni_temporizador(self):
        r = _correr(
            """
var t = toast.error('Boom');
var R = {barra: t.querySelector('.toast__progress') !== null,
         largos: __timers.filter(function (x) { return x.ms > 500; }).length,
         role: t.getAttribute('role'), live: t.getAttribute('aria-live')};
__terminarBarras(); __remover();
R.vivos = __vivos().length;"""
        )
        self.assertFalse(r["barra"])
        self.assertEqual(r["largos"], 0)
        self.assertEqual(r["vivos"], 1)
        self.assertEqual((r["role"], r["live"]), ("alert", "assertive"))

    def test_success_info_warning_siguen_con_barra_y_se_cierran(self):
        r = _correr(
            """
var R = {};
['success', 'info', 'warning'].forEach(function (tipo) {
  var t = toast(tipo, 'Msg ' + tipo);
  R[tipo] = t.querySelector('.toast__progress').style.animationDuration;
});
__terminarBarras(); __remover();
R.vivos = __vivos().length;"""
        )
        for tipo in ("success", "info", "warning"):
            self.assertEqual(r[tipo], "7000ms")
        self.assertEqual(r["vivos"], 0)

    def test_duration_explicita_en_error_si_cierra(self):
        r = _correr(
            """
var t = toast.error('Temporal', {duration: 3000});
var R = {barra: t.querySelector('.toast__progress').style.animationDuration};
__terminarBarras(); __remover();
R.vivos = __vivos().length;"""
        )
        self.assertEqual(r["barra"], "3000ms")
        self.assertEqual(r["vivos"], 0)

    def test_boton_cierra_el_error(self):
        r = _correr(
            """
var t = toast.error('Cerrame');
__botones(t)[0].fire('click'); __remover();
var R = {vivos: __vivos().length, total: __toasts().length};"""
        )
        self.assertEqual((r["vivos"], r["total"]), (0, 0))

    def test_escape_cierra_el_ultimo_error_visible(self):
        r = _correr(
            """
toast.error('Uno'); toast.error('Dos'); toast.success('Ok');
__keydown('Escape'); __remover();
var R = {vivos: __vivos().length,
         errores: __vivos().filter(function (t) { return t.classList.contains('toast--error'); }).length,
         queda: __vivos()[0]._msg};"""
        )
        self.assertEqual(r["vivos"], 2)
        self.assertEqual(r["errores"], 1)
        self.assertEqual(r["queda"], "Uno")

    def test_escape_cierra_el_error_con_foco(self):
        r = _correr(
            """
var a = toast.error('Uno'); var b = toast.error('Dos');
document.activeElement = __botones(a)[0];
__keydown('Escape'); __remover();
var R = {vivos: __vivos().length, queda: __vivos()[0]._msg};"""
        )
        self.assertEqual(r["vivos"], 1)
        self.assertEqual(r["queda"], "Dos")

    def test_error_repetido_no_se_apila(self):
        r = _correr(
            """
var a = toast.error('Igual'); var b = toast.error('Igual'); toast.error('Otro');
var R = {mismo: a === b, total: __toasts().length};"""
        )
        self.assertTrue(r["mismo"])
        self.assertEqual(r["total"], 2)

    def test_escape_con_modal_abierto_no_cierra_el_error(self):
        r = _correr(
            """
toast.error('Persistente');
__modales.push({getClientRects: function () { return [1]; }});
__keydown('Escape'); __remover();
var R = {con_modal: __vivos().length};
__modales.length = 0;
__keydown('Escape'); __remover();
R.sin_modal = __vivos().length;"""
        )
        self.assertEqual(r["con_modal"], 1)
        self.assertEqual(r["sin_modal"], 0)

    def test_modal_oculto_no_bloquea_escape_y_defaultprevented_lo_respeta(self):
        r = _correr(
            """
toast.error('A');
__modales.push({getClientRects: function () { return []; }});
__keydown('Escape', true); __remover();
var R = {prevenido: __vivos().length};
__keydown('Escape'); __remover();
R.oculto = __vivos().length;"""
        )
        self.assertEqual(r["prevenido"], 1)
        self.assertEqual(r["oculto"], 0)

    def test_maximo_tres_errores_visibles(self):
        r = _correr(
            """
for (var i = 1; i <= 5; i++) toast.error('E' + i);
__remover();
var R = {vivos: __vivos().map(function (t) { return t._msg; })};"""
        )
        self.assertEqual(r["vivos"], ["E3", "E4", "E5"])

    def test_cerrar_con_teclado_mueve_el_foco_al_siguiente_toast(self):
        r = _correr(
            """
var a = toast.error('Uno'); var b = toast.error('Dos');
__botones(b)[0].focus();
__keydown('Escape');
var R = {enA: document.activeElement === __botones(a)[0]};
__keydown('Escape');
var origen = document.createElement('button'); origen.focus();
var c = toast.error('Tres'); __botones(c)[0].focus();
__keydown('Escape');
R.vuelve = document.activeElement === origen;"""
        )
        self.assertTrue(r["enA"])
        self.assertTrue(r["vuelve"])

    def test_pila_sube_arriba_con_modal_abierto(self):
        r = _correr(
            """
var a = toast.error('Uno');
var box = document.getElementById('toast-container');
var R = {sin: box.classList.contains('toast-container--sobre-modal')};
__modales.push({getClientRects: function () { return [1]; }});
toast.error('Dos');
R.con = box.classList.contains('toast-container--sobre-modal');
__modales.length = 0;
toast.error('Tres');
R.cerrado = box.classList.contains('toast-container--sobre-modal');"""
        )
        self.assertFalse(r["sin"])
        self.assertTrue(r["con"])
        self.assertFalse(r["cerrado"])

    def test_pila_movil_queda_bajo_el_encabezado_y_sobre_el_pie(self):
        r = _correr(
            """
window.innerWidth = 390;
var cabecera = {getBoundingClientRect: function () { return {bottom: 66, top: 0}; }};
var pie = {getBoundingClientRect: function () { return {top: 634, bottom: 700}; }};
__modales.push({getClientRects: function () { return [1]; }, getAttribute: function () { return null; },
  querySelector: function (s) { return s === '.border-b' ? cabecera : null; },
  querySelectorAll: function () { return [pie]; }});
toast.error('Uno'); toast.error('Dos'); toast.error('Tres');
var box = document.getElementById('toast-container');
var R = {top: box.style.top, max: box.style.maxHeight, bottom: box.style.bottom};
window.innerWidth = 1440; toast.error('Cuatro');
R.desktop = [box.style.top, box.style.maxHeight];
window.innerWidth = 390; toast.error('Cinco');
__modales.length = 0; toast.error('Seis');
R.cerrado = [box.style.top, box.style.maxHeight];"""
        )
        self.assertEqual(r["top"], "74px")
        self.assertEqual(r["max"], "552px")
        self.assertEqual(r["bottom"], "auto")
        self.assertEqual(r["desktop"], ["", ""])
        self.assertEqual(r["cerrado"], ["", ""])

    def test_movil_modal_sin_encabezado_el_error_es_temporal_y_unico(self):
        r = _correr(
            """
window.innerWidth = 390;
__modales.push({getClientRects: function () { return [1]; }, getAttribute: function () { return null; },
  querySelector: function () { return null; }, querySelectorAll: function () { return []; }});
var a = toast.error('Uno'); var b = toast.error('Dos');
var R = {barraA: a.querySelector('.toast__progress') !== null, barraB: b.querySelector('.toast__progress') !== null,
         vivos: __vivos().map(function (t) { return t._msg || 'temporal'; }).length};
R.tempVivos = __vivos().length;
b.querySelector('.toast__progress').fire('animationend'); __remover();
R.tras7s = __vivos().length;
__modales.length = 0;
var c = toast.error('Tres');
R.persistente = c.querySelector('.toast__progress') === null;"""
        )
        self.assertTrue(r["barraB"])
        self.assertEqual(r["tempVivos"], 1)
        self.assertEqual(r["tras7s"], 0)
        self.assertTrue(r["persistente"])

    def test_movil_modal_con_poco_espacio_entre_encabezado_y_pie_es_temporal(self):
        r = _correr(
            """
window.innerWidth = 390;
var cab = {getBoundingClientRect: function () { return {bottom: 60, top: 0}; }};
var pie = {getBoundingClientRect: function () { return {top: 150, bottom: 200}; }};
__modales.push({getClientRects: function () { return [1]; }, getAttribute: function () { return null; },
  querySelector: function (s) { return s === '.border-b' ? cab : null; }, querySelectorAll: function () { return [pie]; }});
var a = toast.error('Uno'); var b = toast.error('Dos');
var box = document.getElementById('toast-container');
var R = {barra: b.querySelector('.toast__progress') !== null, vivos: __vivos().length,
         clase: box.classList.contains('toast-container--sobre-modal')};"""
        )
        self.assertTrue(r["barra"])
        self.assertEqual(r["vivos"], 1)
        self.assertFalse(r["clase"])

    def test_error_ya_visible_pasa_a_temporal_al_abrirse_un_modal_sin_lugar(self):
        r = _correr(
            """
window.innerWidth = 390;
var a = toast.error('Antes');
var R = {barraAntes: a.querySelector('.toast__progress') !== null};
__modales.push({getClientRects: function () { return [1]; }, getAttribute: function () { return null; },
  querySelector: function () { return null; }, querySelectorAll: function () { return []; }});
toast.success('x');
R.barraDespues = a.querySelector('.toast__progress') !== null;"""
        )
        self.assertFalse(r["barraAntes"])
        self.assertTrue(r["barraDespues"])

    def test_movil_sin_modal_maximo_un_error_visible(self):
        r = _correr(
            """
window.innerWidth = 390;
toast.error('Uno'); toast.error('Dos'); var c = toast.error('Tres');
var R = {vivos: __vivos().length, ultimo: __vivos()[0]._msg, barra: c.querySelector('.toast__progress') !== null};
window.innerWidth = 1440;
toast.error('Cuatro'); toast.error('Cinco');
R.escritorio = __vivos().length;"""
        )
        self.assertEqual(r["vivos"], 1)
        self.assertEqual(r["ultimo"], "Tres")
        self.assertFalse(r["barra"])
        self.assertEqual(r["escritorio"], 3)

    def test_movil_sin_modal_reserva_espacio_abajo_y_lo_restaura(self):
        r = _correr(
            """
window.innerWidth = 390;
window.getComputedStyle = function () { return {paddingBottom: '10px'}; };
body.style.paddingBottom = '4px';
var a = toast.error('Uno');
document.getElementById('toast-container')._alto = 76;
toast.info('recalcula');
var R = {con: body.style.paddingBottom};
__botones(a)[0].fire('click'); __remover();
R.tras = body.style.paddingBottom;
R.sinErrorNoAplica = (function () { toast.success('ok'); return body.style.paddingBottom; })();
window.innerWidth = 1440;
var b = toast.error('Otro');
R.escritorio = body.style.paddingBottom;"""
        )
        self.assertEqual(r["con"], "98px")
        self.assertEqual(r["tras"], "4px")
        self.assertEqual(r["sinErrorNoAplica"], "4px")
        self.assertEqual(r["escritorio"], "4px")

    def test_reserva_se_limpia_al_abrirse_un_modal(self):
        r = _correr(
            """
window.innerWidth = 390;
window.getComputedStyle = function () { return {paddingBottom: '0px'}; };
var a = toast.error('Uno');
document.getElementById('toast-container')._alto = 50;
toast.info('x');
var R = {antes: body.style.paddingBottom};
__modales.push({getClientRects: function () { return [1]; }, getAttribute: function () { return null; },
  querySelector: function () { return null; }, querySelectorAll: function () { return []; }});
toast.info('y');
R.conModal = body.style.paddingBottom;"""
        )
        self.assertEqual(r["antes"], "62px")
        self.assertEqual(r["conModal"], "")
