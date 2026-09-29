"""Modal accesible de Becas (POP-7/8/9, POP-M1..M3; decisión DP-3).

Dos frentes:

- El modal «Nuevo programa» de ``becas/config/programa_list.html`` (primer consumidor)
  se renderiza como diálogo nombrado por su título, con ``x-becas-modal``, alto máximo
  y cuerpo desplazable, y sin perder ningún campo ni el envío por AJAX.
- ``static/custom/js/becas-modal.js`` se ejecuta con ``node`` sobre un DOM simulado:
  al abrir el foco entra al primer campo, Tab y Shift+Tab no se escapan del panel,
  Escape cierra y el foco vuelve al botón que lo abrió.
"""

import json
import re
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from core.tests.js_harness import atributos_de, correr_script, requiere_node
from programas.management.commands.seed_becas import ROL_ADMIN

SCRIPT = Path(settings.BASE_DIR) / "static" / "custom" / "js" / "becas-modal.js"


class ModalNuevoProgramaRenderTests(TestCase):
    def setUp(self):
        call_command("seed_becas", stdout=StringIO())
        admin = User.objects.create_user("admin_modal", password="x")
        admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        catalogo = patch("programas.forms.listar_programas", return_value=[{"id": 38, "nombre": "Producción"}])
        catalogo.start()
        self.addCleanup(catalogo.stop)
        self.client.force_login(admin)
        self.html = self.client.get(reverse("becas:programas")).content.decode()
        self.elementos = atributos_de(self.html)

    def _uno(self, predicado):
        encontrados = [attrs for _, attrs in self.elementos if predicado(attrs)]
        self.assertEqual(len(encontrados), 1, encontrados)
        return encontrados[0]

    def test_panel_es_dialogo_nombrado_por_su_titulo(self):
        panel = self._uno(lambda a: a.get("aria-labelledby") == "modal-crear-titulo")
        self.assertEqual(panel.get("role"), "dialog")
        self.assertEqual(panel.get("aria-modal"), "true")
        titulo = self._uno(lambda a: a.get("id") == "modal-crear-titulo")
        self.assertIsNotNone(titulo)
        self.assertIn(">Nuevo programa</h3>", self.html)

    def test_overlay_usa_la_directiva_y_la_pagina_carga_el_script(self):
        overlay = self._uno(lambda a: "x-becas-modal" in a)
        self.assertEqual(overlay["x-becas-modal"], "modalCrear")
        self.assertEqual(overlay.get("x-show"), "modalCrear")
        self.assertIn("custom/js/becas-modal.js", self.html)

    def test_alto_maximo_y_cuerpo_desplazable(self):
        panel = self._uno(lambda a: a.get("aria-labelledby") == "modal-crear-titulo")
        self.assertIn("max-h-[90vh]", panel["class"].split())
        self.assertIn("flex-col", panel["class"].split())
        self.assertTrue(any("overflow-y-auto" in a.get("class", "").split() for _, a in self.elementos))

    def test_contrato_del_formulario_intacto(self):
        form = self._uno(lambda a: a.get("action") == reverse("becas:programa_crear"))
        self.assertEqual(form.get("method"), "post")
        self.assertIn("data-ajax", form)
        nombres = {a.get("name") for tag, a in self.elementos if tag in ("input", "select", "textarea")}
        for campo in ("csrfmiddlewaretoken", "siis_programa_id", "siis_jurid", "siis_funcion_id"):
            self.assertIn(campo, nombres)
        cierre = [a for tag, a in self.elementos if tag == "button" and a.get("aria-label") == "Cerrar"]
        self.assertTrue(any(a.get("@click") == "modalCrear=false" for a in cierre))
        self.assertRegex(self.html, r'<button type="submit"[^>]*btn-brand[^>]*>Guardar y configurar</button>')


# DOM mínimo con foco real: árbol de elementos, document.activeElement, contains,
# querySelectorAll para los selectores que usa becas-modal.js y un Alpine de juguete
# (directive / evaluateLater / evaluate / effect) sobre un scope reactivo.
DOM = r"""
var __rafs = [];
window.requestAnimationFrame = function (fn) { __rafs.push(fn); };
function __flush() { while (__rafs.length) __rafs.shift()(); }
var __docListeners = {};
function El(tag, props) {
  var el = {tagName: tag, hijos: [], padre: null, attrs: {}, style: {}, listeners: {},
    classList: {set: {}, contains: function (c) { return !!this.set[c]; },
                add: function (c) { this.set[c] = 1; __mutar(el); }, remove: function (c) { delete this.set[c]; __mutar(el); }}};
  Object.assign(el, props || {});
  el.isConnected = true;
  el.getAttribute = function (k) { return k in el.attrs ? el.attrs[k] : null; };
  el.setAttribute = function (k, v) { el.attrs[k] = String(v); };
  el.hasAttribute = function (k) { return k in el.attrs; };
  el.addEventListener = function (t, fn) { (el.listeners[t] = el.listeners[t] || []).push(fn); };
  el.removeEventListener = function () {};
  el.append = function () { Array.prototype.forEach.call(arguments, function (h) { h.padre = el; el.hijos.push(h); }); return el; };
  el.contains = function (o) { while (o) { if (o === el) return true; o = o.padre; } return false; };
  el.focus = function () { document.activeElement = el; };
  el.closest = function (sel) { var o = el; while (o) { if (__coincide(o, sel)) return o; o = o.padre; } return null; };
  el.querySelector = function (sel) { return el.querySelectorAll(sel)[0] || null; };
  el.querySelectorAll = function (sel) {
    var out = [];
    (function rec(n) { n.hijos.forEach(function (h) { if (__coincide(h, sel)) out.push(h); rec(h); }); })(el);
    return out;
  };
  return el;
}
function __coincide(el, sel) {
  if (sel === '[autofocus]') return !!el.autofocus;
  if (sel === '[role="dialog"]') return el.attrs.role === 'dialog';
  if (sel === '[data-becas-modal-cerrar]') return 'data-becas-modal-cerrar' in el.attrs;
  if (sel.indexOf('[role="dialog"], [role="alertdialog"]') === 0) return !!el.attrs.role || el.attrs['aria-modal'] === 'true';
  if (sel.indexOf('input:not') === 0) return !!el.campo && !el.disabled;
  return !!el.foco && !el.disabled;
}
var __observadores = [];
function MutationObserver(fn) { this.fn = fn; __observadores.push(this); }
MutationObserver.prototype.observe = function (el) { this.el = el; };
MutationObserver.prototype.disconnect = function () { this.el = null; };
function __mutar(el) { __observadores.forEach(function (o) { if (o.el === el) o.fn([]); }); }

document = {
  activeElement: null,
  addEventListener: function (t, fn) { (__docListeners[t] = __docListeners[t] || []).push(fn); },
  dispatchEvent: function (ev) { (__docListeners[ev.type] || []).forEach(function (fn) { fn(ev); }); }
};
document.documentElement = El('html');
document.body = El('body');
document.activeElement = document.body;

function __tecla(key, shift) {
  var ev = {key: key, shiftKey: !!shift, defaultPrevented: false,
            preventDefault: function () { this.defaultPrevented = true; }};
  (__docListeners.keydown || []).forEach(function (fn) { fn(ev); });
  return ev;
}
function __nombre(el) { return el ? (el.attrs.id || el.tagName) : null; }

// Página: botón que abre + overlay > panel[role=dialog] > X, select, input, Cancelar, Guardar
var __abrir = El('button', {foco: true}); __abrir.attrs.id = 'abrir';
var __overlay = El('div');
var __panel = El('div'); __panel.attrs.role = 'dialog';
var __x = El('button', {foco: true}); __x.attrs.id = 'x'; __x.attrs['data-becas-modal-cerrar'] = '';
var __sel = El('select', {foco: true, campo: true}); __sel.attrs.id = 'campo1';
var __inp = El('input', {foco: true, campo: true}); __inp.attrs.id = 'campo2';
var __cancelar = El('button', {foco: true}); __cancelar.attrs.id = 'cancelar';
var __guardar = El('button', {foco: true}); __guardar.attrs.id = 'guardar';
__panel.append(__x, __sel, __inp, __cancelar, __guardar);
__overlay.append(__panel);
document.body.append(__abrir, __overlay);

// Alpine de juguete.
var __scope = {modalCrear: false};
var __efectos = [];
var __directivas = {};
window.Alpine = undefined;
var __Alpine = {directive: function (n, fn) { __directivas[n] = fn; }};
function __montar(el, expr) {
  __directivas['becas-modal'](el, {expression: expr}, {
    evaluateLater: function (e) { return function (recibir) { recibir(__scope[e]); }; },
    evaluate: function (e) { var m = /^(\w+) = false$/.exec(e); __scope[m[1]] = false; __efectos.forEach(function (f) { f(); }); },
    effect: function (f) { __efectos.push(f); f(); },
    cleanup: function () {}
  });
}
function __set(v) { __scope.modalCrear = v; __efectos.forEach(function (f) { f(); }); __flush(); }
"""

ALPINE_INIT = r"""
window.Alpine = __Alpine;
document.dispatchEvent({type: 'alpine:init'});
__montar(__overlay, 'modalCrear');
"""


@requiere_node
class BecasModalJsTests(SimpleTestCase):
    def setUp(self):
        self.script = SCRIPT.read_text(encoding="utf-8")

    def _correr(self, acciones):
        return correr_script(DOM + "\n" + self.script, ALPINE_INIT + acciones)["r"]

    def test_al_abrir_el_foco_va_al_primer_campo_y_bloquea_el_scroll(self):
        r = self._correr(
            "__abrir.focus(); __set(true);\n"
            "__log.r = {foco: __nombre(document.activeElement), html: document.documentElement.style.overflow};"
        )
        self.assertEqual(r, {"foco": "campo1", "html": "hidden"})

    def test_autofocus_manda(self):
        r = self._correr("__inp.autofocus = true; __set(true); __log.r = __nombre(document.activeElement);")
        self.assertEqual(r, "campo2")

    def test_tab_no_escapa_del_panel(self):
        r = self._correr(
            "__set(true);\n"
            "__guardar.focus(); var t1 = __tecla('Tab'); var a = __nombre(document.activeElement);\n"
            "__x.focus(); var t2 = __tecla('Tab', true); var b = __nombre(document.activeElement);\n"
            "__abrir.focus(); __tecla('Tab'); var c = __nombre(document.activeElement);\n"
            "__sel.focus(); var t3 = __tecla('Tab');\n"
            "__log.r = {ultimo_a_primero: a, primero_a_ultimo: b, desde_afuera: c,"
            " prevenidos: [t1.defaultPrevented, t2.defaultPrevented], medio_libre: !t3.defaultPrevented};"
        )
        self.assertEqual(
            r,
            {
                "ultimo_a_primero": "x",
                "primero_a_ultimo": "guardar",
                "desde_afuera": "x",
                "prevenidos": [True, True],
                "medio_libre": True,
            },
        )

    def test_escape_cierra_y_devuelve_el_foco(self):
        r = self._correr(
            "__abrir.focus(); __set(true); __inp.focus();\n"
            "var ev = __tecla('Escape'); __flush();\n"
            "__log.r = {abierto: __scope.modalCrear, foco: __nombre(document.activeElement),"
            " html: document.documentElement.style.overflow || '', prevenido: ev.defaultPrevented};"
        )
        self.assertEqual(r, {"abierto": False, "foco": "abrir", "html": "", "prevenido": True})

    def test_cerrado_no_toca_el_teclado(self):
        r = self._correr(
            "__set(true); __set(false); __abrir.focus();\n"
            "var e = __tecla('Escape'); var t = __tecla('Tab');\n"
            "__log.r = [e.defaultPrevented, t.defaultPrevented, __nombre(document.activeElement)];"
        )
        self.assertEqual(r, [False, False, "abrir"])

    def test_api_vanilla_bind(self):
        r = correr_script(
            DOM + "\n" + self.script,
            "var cierres = 0;\n"
            "__overlay.classList.add('hidden');\n"
            "window.becasModal.bind(__overlay, {onClose: function () { cierres++; __overlay.classList.add('hidden'); }});\n"
            "__abrir.focus(); __overlay.classList.remove('hidden'); __flush();\n"
            "var foco = __nombre(document.activeElement);\n"
            "__tecla('Escape');\n"
            "__log.r = {foco: foco, cierres: cierres, vuelve: __nombre(document.activeElement),"
            " oculto: __overlay.classList.contains('hidden')};",
        )["r"]
        self.assertEqual(r, {"foco": "campo1", "cierres": 1, "vuelve": "abrir", "oculto": True})


class ModalPartialsTests(SimpleTestCase):
    """Los parciales rinden el canon A y el pie apunta al form cuando queda fuera."""

    def test_header_y_footer(self):
        from django.template.loader import render_to_string

        header = render_to_string(
            "programas/becas/_modal_header.html",
            {
                "titulo": "Borrar",
                "titulo_id": "t-borrar",
                "icono": "fa-trash",
                "tono": "danger",
                "cerrar": "abierto=false",
            },
        )
        self.assertIn('id="t-borrar"', header)
        self.assertIn("bg-danger-soft text-fg-danger", header)
        self.assertIn('aria-label="Cerrar"', header)
        self.assertIn('@click="abierto=false"', header)

        footer = render_to_string(
            "programas/becas/_modal_footer.html",
            {"accion_texto": "Sí, borrar", "accion_tono": "danger", "form_id": "f-borrar"},
        )
        self.assertIn('form="f-borrar"', footer)
        self.assertIn("btn-danger", footer)
        self.assertIn(">Cancelar</button>", footer)
        self.assertIn("data-becas-modal-cerrar", footer)
        self.assertNotIn("@click", footer)
        self.assertEqual(len(re.findall(r"<button", footer)), 2, json.dumps(footer))
