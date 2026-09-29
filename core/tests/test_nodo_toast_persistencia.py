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
var document = {
  readyState: 'complete', activeElement: null, body: body,
  addEventListener: function (t, fn) { (__docListeners[t] = __docListeners[t] || []).push(fn); },
  getElementById: function (id) { return body.all().filter(function (e) { return e.id === id; })[0] || null; },
  createElement: function (t) { return new El(t); }
};
var window = globalThis;
var requestAnimationFrame = function (fn) { fn(); };
setTimeout = function (fn, ms) { __timers.push({fn: fn, ms: ms}); return __timers.length; };
function __keydown(key) { (__docListeners.keydown || []).forEach(function (fn) { fn({key: key}); }); }
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
         queda: __vivos()[0].getAttribute('data-msg')};"""
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
var R = {vivos: __vivos().length, queda: __vivos()[0].getAttribute('data-msg')};"""
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
