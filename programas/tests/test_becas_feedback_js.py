"""Un solo sistema de avisos y confirmaciones en los modales de Becas (W2-C7).

- ALR-1/POP-14/DA-6: ``_ajax_js.html`` tenía su propio toast (``becasToast``, 2,6 s);
  ahora todo va por ``window.toast(tipo, mensaje)`` de nodo-toast.
- ALR-6: ``_cascada_localidad.html`` llamaba a ``becasToast`` en pantallas donde no
  existía: el error de red no se veía.
- ALR-7/DA-3: un 400 muestra los errores inline y **un** aviso de resumen; el error
  general va inline si el form tiene su lugar (``data-error="__all__"``).
- ALR-4/POP-1/DA-4: el 409 de solapamiento usaba ``window.confirm``; ahora es
  ``ModernModal`` con «Sí, asignar igual», sin doble envío.
- ALR-M7: el botón queda «Guardando…» con ``aria-busy`` mientras dura el pedido.
- ALR-9/POP-18: copiar link sin ``window.prompt``.
- POP-M4/POP-M5: ``_confirm_js.html`` acepta ``data-confirm-danger`` explícito.

Los scripts reales se renderizan con Django y se ejecutan con ``node`` sobre un DOM
simulado (``core/tests/js_harness.py``). Las promesas de ``fetch``/``clipboard`` son
*thenables* síncronos para que todo el flujo termine antes de leer el log.
"""

import json
import os
import sys
from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from django.test import SimpleTestCase

from core.tests.js_harness import correr_script, requiere_node, script_con

AJAX_JS = "programas/becas/_ajax_js.html"
CONFIRM_JS = "programas/becas/_confirm_js.html"
CASCADA_JS = "programas/becas/relevamientos/_cascada_localidad.html"
COPIAR_JS = "programas/becas/relevamientos/_copiar_link_js.html"

# DOM simulado común: nodos con hijos/atributos, thenables síncronos, toast y confirm
# nativos registrados. Se antepone al script real (redeclara lo del harness).
_DOM = r"""
__log.toasts = []; __log.confirm = []; __log.prompt = []; __log.fetches = [];
__log.eventos = []; __log.requestSubmit = 0; __log.seleccionados = [];
function __sync(valor, fallo) {
  if (!fallo && valor && valor.__sync) return valor;
  return {
    __sync: true,
    then: function (ok, ko) {
      try {
        if (fallo) return ko ? __sync(ko(valor)) : this;
        return ok ? __sync(ok(valor)) : this;
      } catch (err) { return __sync(err, true); }
    },
    catch: function (ko) { return this.then(null, ko); },
    finally: function (fn) { fn(); return this; }
  };
}
function __coincide(n, sel) {
  var m = /^(\w+)?\[([\w-]+)(?:="([^"]*)")?\]$/.exec(sel);
  if (!m || !n.attrs) return false;
  if (m[1] && n.tagName !== m[1].toUpperCase()) return false;
  if (!(m[2] in n.attrs)) return false;
  return m[3] === undefined || n.attrs[m[2]] === m[3];
}
function __buscar(raiz, sel) {
  var out = [];
  (function rec(n) {
    (n.childNodes || []).forEach(function (c) { if (__coincide(c, sel)) out.push(c); rec(c); });
  })(raiz);
  return out;
}
function __texto(n) {
  if (n.nodeType === 3) return n.data;
  return (n.childNodes || []).map(__texto).join('');
}
var __creados = [];
function __nodo(tag) {
  var n = {
    tagName: String(tag).toUpperCase(), nodeType: 1, childNodes: [], attrs: {}, parentNode: null,
    style: {}, dataset: {}, disabled: false, value: '', type: '', className: '', textContent: '',
    classList: {add: function () {}, remove: function () {}, contains: function () { return false; }},
    setAttribute: function (k, v) { this.attrs[k] = String(v); },
    getAttribute: function (k) { return k in this.attrs ? this.attrs[k] : null; },
    hasAttribute: function (k) { return k in this.attrs; },
    removeAttribute: function (k) { delete this.attrs[k]; },
    appendChild: function (c) { c.parentNode = this; this.childNodes.push(c); return c; },
    removeChild: function (c) {
      var i = this.childNodes.indexOf(c); if (i >= 0) this.childNodes.splice(i, 1);
      c.parentNode = null; return c;
    },
    remove: function () { if (this.parentNode) this.parentNode.removeChild(this); },
    querySelector: function (sel) { return __buscar(this, sel)[0] || null; },
    querySelectorAll: function (sel) { return __buscar(this, sel); },
    addEventListener: function () {}, removeEventListener: function () {},
    contains: function (o) { return o === this; },
    focus: function () {}, select: function () { __log.seleccionados.push(this.value); },
    getBoundingClientRect: function () { return {top: 100, bottom: 130, left: 50, right: 150, width: 100}; }
  };
  Object.defineProperty(n, 'firstChild', {get: function () { return this.childNodes[0] || null; }});
  return n;
}
function HTMLFormElement() {}
function HTMLSelectElement() {}
var __docHandlers = {};
var document = {
  cookie: 'csrftoken=tok123',
  body: __nodo('body'),
  addEventListener: function (t, fn) { (__docHandlers[t] = __docHandlers[t] || []).push(fn); },
  removeEventListener: function () {},
  createElement: function (t) { var n = __nodo(t); __creados.push(n); return n; },
  createTextNode: function (t) { return {nodeType: 3, data: String(t), parentNode: null}; },
  querySelector: function () { return null; },
  querySelectorAll: function () { return []; }
};
var addEventListener = function () {};
var dispatchEvent = function (ev) { __log.eventos.push(ev.type); };
function CustomEvent(t) { this.type = t; }
var location = {href: ''};
var innerWidth = 1440, innerHeight = 900, scrollX = 0, scrollY = 0;
function FormData(form) {
  var datos = {};
  __buscar(form, 'input[name]').forEach(function (i) { datos[i.attrs.name || i.name] = i.value; });
  (form.childNodes || []).forEach(function (i) { if (i.name) datos[i.name] = i.value; });
  this.datos = datos;
}
window.toast = function (tipo, mensaje) { __log.toasts.push([tipo, mensaje]); return null; };
window.confirm = function (m) { __log.confirm.push(m); return true; };
window.prompt = function (m, v) { __log.prompt.push(v); return v; };
"""

# Un form data-ajax con un botón «Guardar» y placeholders de error configurables.
_FORM = r"""
var __respuestas = [];
var fetch = function (url, opts) {
  __log.fetches.push({
    url: url, csrf: opts.headers['X-CSRFToken'], datos: opts.body.datos,
    boton: __texto(__boton), busy: __boton.getAttribute('aria-busy'), disabled: __boton.disabled
  });
  var r = __respuestas.shift() || {status: 200, data: {ok: true, message: 'Guardado OK.'}};
  if (r.red) return __sync(new Error('red'), true);
  return __sync({status: r.status, json: function () { return __sync(r.data); }});
};
var __form = __nodo('form');
Object.setPrototypeOf(__form, HTMLFormElement.prototype);
__form.action = '/becas/relevamientos/crear/';
__form.attrs['data-ajax'] = '';
__form.reset = function () {};
__form.requestSubmit = function () { __log.requestSubmit++; __enviar(null); };
var __boton = __nodo('button');
__boton.type = 'submit';
__boton.appendChild(document.createTextNode('Guardar'));
__form.appendChild(__boton);
__form.elements = [__boton];
function __placeholder(campo) {
  var p = __nodo('p'); p.attrs['data-error'] = campo; __form.appendChild(p); return p;
}
function __enviar(submitter) {
  (__docHandlers.submit || []).forEach(function (fn) {
    fn({target: __form, submitter: submitter, preventDefault: function () {}});
  });
}
function __errores() {
  var out = {};
  __buscar(__form, '[data-error]').forEach(function (p) { out[p.attrs['data-error']] = p.textContent; });
  return out;
}
"""


def _render(template):
    return render_to_string(template)


@requiere_node
class AjaxJsFeedbackTests(SimpleTestCase):
    def setUp(self):
        self.script = script_con(_render(AJAX_JS), "data-ajax")

    def _correr(self, acciones):
        return correr_script(_DOM + _FORM + self.script, acciones)

    def test_409_confirma_con_modernmodal_y_no_con_confirm_nativo(self):
        log = self._correr(
            """
            __respuestas.push({status: 409, data: {ok: false, confirm_required: true,
                               message: 'Marcela ya tiene asignado otro relevamiento.'}});
            __enviar(__boton);
            __confirmar();
            __confirmar();  // doble clic en «Sí, asignar igual»: un solo reenvío
            """
        )
        self.assertEqual(log["confirm"], [])
        self.assertEqual(len(log["modal"]), 1)
        modal = log["modal"][0]
        self.assertEqual(modal["type"], "confirm")
        self.assertEqual(modal["icon"], "warning")
        self.assertEqual(modal["title"], "¿Asignar igual?")
        self.assertEqual(modal["confirmText"], "Sí, asignar igual")
        self.assertEqual(modal["message"], "Marcela ya tiene asignado otro relevamiento.")
        self.assertNotIn("danger", modal)
        # Se reenvía una sola vez, por requestSubmit y con confirmar_solapamiento=1.
        self.assertEqual(log["requestSubmit"], 1)
        self.assertEqual(len(log["fetches"]), 2)
        self.assertNotIn("confirmar_solapamiento", log["fetches"][0]["datos"])
        self.assertEqual(log["fetches"][1]["datos"]["confirmar_solapamiento"], "1")
        self.assertEqual(log["fetches"][1]["csrf"], "tok123")
        self.assertEqual(log["toasts"], [["success", "Guardado OK."]])

    def test_confirmacion_de_solapamiento_vale_para_un_solo_envio(self):
        log = self._correr(
            """
            __respuestas.push({status: 409, data: {ok: false, confirm_required: true, message: 'Choca.'}});
            __enviar(__boton);
            __confirmar();
            __enviar(__boton);  // alta siguiente en el mismo modal
            """
        )
        self.assertEqual(len(log["fetches"]), 3)
        self.assertEqual(log["fetches"][1]["datos"].get("confirmar_solapamiento"), "1")
        self.assertNotIn("confirmar_solapamiento", log["fetches"][2]["datos"])

    def test_400_con_placeholder_all_no_duplica_el_error_general(self):
        log = self._correr(
            """
            __placeholder('nombre'); __placeholder('__all__');
            __respuestas.push({status: 400, data: {ok: false, errors: {
              nombre: ['Este campo es obligatorio.'], __all__: ['El cupo supera lo disponible.']}}});
            __enviar(__boton);
            __log.inline = __errores();
            """
        )
        self.assertEqual(log["toasts"], [["error", "Revisá los datos del formulario."]])
        self.assertEqual(
            log["inline"], {"nombre": "Este campo es obligatorio.", "__all__": "El cupo supera lo disponible."}
        )

    def test_400_sin_placeholder_all_lleva_el_error_general_en_el_unico_aviso(self):
        log = self._correr(
            """
            __placeholder('nombre');
            __respuestas.push({status: 400, data: {ok: false, errors: {
              nombre: ['Obligatorio.'], __all__: ['El cupo supera lo disponible.']}}});
            __enviar(__boton);
            """
        )
        self.assertEqual(log["toasts"], [["error", "Revisá los datos del formulario: El cupo supera lo disponible."]])

    def test_boton_guardando_con_aria_busy_mientras_dura_el_pedido(self):
        log = self._correr(
            """
            __enviar(__boton);
            __log.despues = {texto: __texto(__boton), busy: __boton.getAttribute('aria-busy'),
                             disabled: __boton.disabled};
            """
        )
        durante = log["fetches"][0]
        self.assertEqual(durante["boton"].strip(), "Guardando…")
        self.assertEqual(durante["busy"], "true")
        self.assertTrue(durante["disabled"])
        self.assertEqual(log["despues"], {"texto": "Guardar", "busy": None, "disabled": False})

    def test_redirect_deja_el_boton_ocupado_hasta_cambiar_de_pagina(self):
        log = self._correr(
            """
            __respuestas.push({status: 200, data: {ok: true, redirect: '/becas/segmentos/9/', message: 'Listo.'}});
            __enviar(__boton);
            __log.href = location.href; __log.disabled = __boton.disabled;
            """
        )
        self.assertEqual(log["href"], "/becas/segmentos/9/")
        self.assertTrue(log["disabled"])

    def test_errores_de_permiso_y_de_red_van_por_window_toast(self):
        log = self._correr(
            """
            __respuestas.push({status: 403, data: {ok: false}});
            __respuestas.push({red: true});
            __enviar(__boton);
            __enviar(__boton);
            """
        )
        self.assertEqual([t[0] for t in log["toasts"]], ["error", "error"])
        self.assertEqual(log["toasts"][0][1], "No tiene permisos para realizar esta acción.")

    def test_design_audit_sin_errores_en_los_scripts_de_feedback(self):
        sys.path.insert(0, str(Path(settings.BASE_DIR) / "scripts"))
        try:
            import design_audit
        finally:
            sys.path.pop(0)
        base = Path(settings.BASE_DIR) / "programas" / "templates"
        for template in (AJAX_JS, CONFIRM_JS, CASCADA_JS, COPIAR_JS):
            errores = [f for f in design_audit.audit_file(base / template) if f[0] == "ERROR"]
            self.assertEqual(errores, [], template)


class SinToastLocalTests(SimpleTestCase):
    def test_no_queda_becas_toast_en_templates_ni_static(self):
        base = Path(settings.BASE_DIR)
        # docs/ guarda antecedentes y mockups, no código que corra.
        omitir = {"node_modules", "staticfiles", "media", "__pycache__", "docs"}
        encontrados = []
        for raiz, dirs, archivos in os.walk(base):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in omitir]
            for nombre in archivos:
                if nombre.endswith((".html", ".js")):
                    ruta = Path(raiz) / nombre
                    if "becasToast" in ruta.read_text(encoding="utf-8", errors="replace"):
                        encontrados.append(str(ruta.relative_to(base)))
        self.assertEqual(encontrados, [])


@requiere_node
class ConfirmJsTests(SimpleTestCase):
    def setUp(self):
        self.script = script_con(_render(CONFIRM_JS), "data-confirm-url")

    def _modal(self, dataset, acciones=""):
        # DOM mínimo del harness + el listener de pageshow sobre window.
        return correr_script(
            "var addEventListener = function () {};\n" + self.script, f"__click({json.dumps(dataset)});\n{acciones}"
        )

    def test_data_confirm_danger_true_pasa_danger_aunque_el_icono_no_sea_warning(self):
        log = self._modal(
            {"confirmUrl": "/x/", "confirmDanger": "true", "confirmIcon": "info", "confirmOk": "Sí, eliminar"}
        )
        self.assertIs(log["modal"][0]["danger"], True)
        self.assertEqual(log["modal"][0]["confirmText"], "Sí, eliminar")

    def test_data_confirm_danger_false_gana_sobre_el_icono(self):
        log = self._modal({"confirmUrl": "/x/", "confirmDanger": "false"})
        self.assertIs(log["modal"][0]["danger"], False)

    def test_sin_atributo_se_conserva_la_regla_del_icono(self):
        self.assertIs(self._modal({"confirmUrl": "/x/"})["modal"][0]["danger"], True)
        self.assertIs(self._modal({"confirmUrl": "/x/", "confirmIcon": "info"})["modal"][0]["danger"], False)

    def test_doble_confirmacion_envia_un_solo_post(self):
        log = self._modal({"confirmUrl": "/becas/x/eliminar/"}, "__confirmar(); __confirmar();")
        self.assertEqual(log["submits"], ["/becas/x/eliminar/"])

    def test_quitar_reversible_triangulo_y_boton_de_marca(self):
        log = self._modal({"confirmUrl": "/x/", "confirmDanger": "false", "confirmIcon": "warning"})
        self.assertIs(log["modal"][0]["danger"], False)
        self.assertEqual(log["modal"][0]["icon"], "warning")


class QuitarReversibleTests(SimpleTestCase):
    """«¿Quitar coordinador?» y «¿Quitar el padrón propio?» se deshacen: no son destructivas."""

    CASOS = (
        ("programas/becas/config/segmento_detail.html", "becas:coordinador_desasignar"),
        ("programas/becas/relevamientos/relevamiento_detail.html", "becas:relevamiento_padron_quitar"),
    )

    def test_llevan_danger_false_e_icono_warning(self):
        base = Path(settings.BASE_DIR) / "programas" / "templates"
        for template, url in self.CASOS:
            with self.subTest(template=template):
                linea = next(
                    ln
                    for ln in (base / template).read_text(encoding="utf-8").splitlines()
                    if f"data-confirm-url=\"{{% url '{url}'" in ln
                )
                self.assertIn('data-confirm-danger="false"', linea)
                self.assertIn('data-confirm-icon="warning"', linea)


@requiere_node
class CascadaLocalidadTests(SimpleTestCase):
    def test_error_de_red_avisa_con_window_toast(self):
        script = script_con(_render(CASCADA_JS), "data-municipio")
        log = correr_script(
            _DOM + script,
            """
            var fetch = function () { return __sync(new Error('sin red'), true); };
            var __local = __nodo('select'); __local.attrs['data-localidad'] = '';
            Object.defineProperty(__local, 'innerHTML', {set: function () { this.childNodes = []; }});
            var __f = __nodo('form'); __f.appendChild(__local);
            var __muni = __nodo('select'); Object.setPrototypeOf(__muni, HTMLSelectElement.prototype);
            __muni.attrs['data-municipio'] = ''; __muni.value = '7';
            __muni.closest = function () { return __f; };
            __docHandlers.change.forEach(function (fn) { fn({target: __muni}); });
            __log.opcion = __texto(__local.childNodes[0]) || __local.childNodes[0].textContent;
            """,
        )
        self.assertEqual(log["toasts"], [["error", "No se pudieron cargar las localidades. Reintentá."]])
        self.assertEqual(log["opcion"], "No se pudieron cargar las localidades")


@requiere_node
class CopiarLinkTests(SimpleTestCase):
    LINK = "https://datanach.chaco.gob.ar/portal/inscripcion/abc/"

    def _click(self, clipboard):
        script = script_con(_render(COPIAR_JS), "data-copy-link")
        return correr_script(
            _DOM + script,
            f"""
            Object.defineProperty(globalThis, 'navigator', {{value: {{clipboard: {clipboard}}},
                                  configurable: true, writable: true}});
            var __cont = __nodo('td');
            var __btn = __nodo('button'); __btn.attrs['data-copy-link'] = {json.dumps(self.LINK)};
            __cont.appendChild(__btn);
            __btn.closest = function () {{ return __btn; }};
            __docHandlers.click.forEach(function (fn) {{ fn({{target: __btn, preventDefault: function () {{}}}}); }});
            __log.inputs = __creados.filter(function (n) {{ return n.tagName === 'INPUT'; }})
              .map(function (n) {{ return {{value: n.value, readOnly: n.readOnly === true}}; }});
            """,
        )

    def test_sin_permiso_de_portapapeles_muestra_el_link_seleccionado_sin_prompt(self):
        log = self._click("{writeText: function () { return __sync(new Error('denegado'), true); }}")
        self.assertEqual(log["prompt"], [])
        self.assertEqual(log["toasts"], [["warning", "Copialo manualmente: el link quedó seleccionado."]])
        self.assertEqual(log["inputs"], [{"value": self.LINK, "readOnly": True}])
        self.assertEqual(log["seleccionados"], [self.LINK])

    def test_sin_api_de_portapapeles_tampoco_usa_prompt(self):
        log = self._click("undefined")
        self.assertEqual(log["prompt"], [])
        self.assertEqual(log["seleccionados"], [self.LINK])

    def test_copia_ok_avisa_con_la_firma_tipo_primero(self):
        log = self._click("{writeText: function () { return __sync(undefined); }}")
        self.assertEqual(log["toasts"], [["success", "Link copiado al portapapeles."]])
        self.assertEqual(log["inputs"], [])
