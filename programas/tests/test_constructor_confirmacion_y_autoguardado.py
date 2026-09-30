"""Constructor de formularios, Ola 3 W3-L-E (DA-2, POP-19).

- DA-2: el autoguardado (arrastrar, eliminar, restablecer, condición) no lleva
  toast de éxito; el indicador «Guardando…/Guardado en vivo» del encabezado
  (``aria-live``) ya lo dice. Los errores sí van por ``window.toast('error', …)``.
- POP-19: sin ``ModernModal`` cargado, ``confirmar()`` fallaba abierto (ejecutaba
  la acción destructiva sin preguntar). Ahora falla cerrado: no llama a
  ``onConfirm`` ni, por lo tanto, al ``fetch`` de la mutación.

El script real (``nodo-constructor.js``) se ejecuta con ``node`` sobre un DOM
mínimo (``core/tests/js_harness.py``), disparando ``DOMContentLoaded`` para que
``init()`` enlace el ``document.addEventListener('click', …)`` real y despachando
un clic sintético sobre un botón ``data-accion``, igual que hace el usuario.
"""

import json
import subprocess
from datetime import date
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from core.tests.js_harness import NODE, atributos_de, requiere_node
from programas.management.commands.seed_becas import ROL_ADMIN
from programas.models import Convocatoria, Segmento

JS = Path(settings.BASE_DIR) / "static" / "custom" / "js" / "nodo-constructor.js"

# DOM mínimo: un único nodo `#constructor` con los `data-url-*` que lee `init()`,
# un ítem ya cargado en `#constructor-datos` (para que `eliminar` encuentre su
# `dato`) y un `fetch` con thenables síncronos (igual criterio que
# test_becas_feedback_js.py: sin esto el `.then()` de `post()` no corre antes de
# leer `__log`).
_DOM = r"""
var window = globalThis;
var __log = {toasts: [], fetches: [], modal: []};
window.toast = function (tipo, mensaje) { __log.toasts.push([tipo, mensaje]); };
var __docHandlers = {};
function __sync(valor, fallo) {
  // Si `valor` ya es un thenable síncrono (p. ej. el que devuelve el propio
  // `.then()` anidado de `post()`: `resp.json().then(...)`), no se vuelve a
  // envolver: si no, `.then()` nunca desenvuelve el resultado (como hace una
  // Promise real con `resp.json().catch(...).then(...)`).
  if (!fallo && valor && valor.__sync) { return valor; }
  return {
    __sync: true,
    then: function (ok, ko) {
      try {
        if (fallo) { return ko ? __sync(ko(valor)) : this; }
        return ok ? __sync(ok(valor)) : this;
      } catch (err) { return __sync(err, true); }
    },
    catch: function (ko) { return this.then(null, ko); }
  };
}
function __nodo(tag) {
  return {
    tagName: tag, attrs: {}, childNodes: [],
    getAttribute: function (k) { return k in this.attrs ? this.attrs[k] : null; },
    setAttribute: function (k, v) { this.attrs[k] = String(v); },
    contains: function (o) { return o === this || this.childNodes.indexOf(o) !== -1; },
    closest: function () { return this; },
    classList: {add: function () {}, remove: function () {}, contains: function () { return false; }},
    querySelector: function () { return null; },
    querySelectorAll: function () { return []; },
    addEventListener: function () {}, focus: function () {}
  };
}
var __constructor = __nodo('div');
['mover', 'editar', 'condicion', 'eliminar', 'restablecer', 'grupo', 'texto', 'propio'].forEach(function (n) {
  __constructor.attrs['data-url-' + n] = '/becas/x/' + n + '/';
});
var __datosIniciales = JSON.stringify({version: 1, items: [{clave: 'g-x', tipo: 'grupo', titulo: 'Grupo X'}]});
var document = {
  cookie: 'csrftoken=tok123',
  activeElement: null,
  addEventListener: function (t, fn) { (__docHandlers[t] = __docHandlers[t] || []).push(fn); },
  getElementById: function (id) {
    if (id === 'constructor') { return __constructor; }
    if (id === 'constructor-operadores') {
      return {textContent: '{"por_tipo":{},"etiquetas":{},"sin_valor":[],"con_lista":[]}'};
    }
    if (id === 'constructor-datos') { return {textContent: __datosIniciales}; }
    return null;
  },
  querySelector: function () { return null; },
  querySelectorAll: function () { return []; },
  createElement: __nodo,
  body: {appendChild: function () {}}
};
var __fetchRespuestas = [];
var fetch = function (url, opts) {
  __log.fetches.push({url: url, body: JSON.parse(opts.body)});
  var r = __fetchRespuestas.shift() || {status: 200, data: {ok: true}};
  return __sync({status: r.status, json: function () { return __sync(r.data); }});
};
function CustomEvent(tipo, opciones) { this.type = tipo; this.detail = opciones && opciones.detail; }
window.dispatchEvent = function () {};
window.addEventListener = function () {};
function __arrancar() { (__docHandlers.DOMContentLoaded || []).forEach(function (fn) { fn(); }); }
function __click(accion, clave) {
  var boton = __nodo('button');
  boton.attrs['data-accion'] = accion;
  if (clave) { boton.attrs['data-clave'] = clave; }
  boton.closest = function () { return boton; };
  __constructor.childNodes.push(boton);
  (__docHandlers.click || []).forEach(function (fn) { fn({target: boton, preventDefault: function () {}}); });
}
function __confirmar() { __log.modal.forEach(function (m) { if (m.onConfirm) { m.onConfirm(); } }); }
"""


def _correr(acciones):
    script = JS.read_text(encoding="utf-8")
    programa = _DOM + "\n" + script + "\n__arrancar();\n" + acciones + "\nconsole.log(JSON.stringify(__log));"
    proceso = subprocess.run([NODE, "-"], input=programa, capture_output=True, text=True, encoding="utf-8", timeout=30)
    if proceso.returncode != 0:
        raise AssertionError(f"node falló:\n{proceso.stderr}")
    return json.loads(proceso.stdout.strip().splitlines()[-1])


@requiere_node
class Pop19SinModernModalFallaCerradoTests(SimpleTestCase):
    def test_sin_modernmodal_no_llama_al_fetch_de_eliminar(self):
        log = _correr("delete window.ModernModal;\n__click('eliminar', 'g-x');")
        self.assertEqual(log["fetches"], [])
        self.assertEqual(len(log["toasts"]), 1)
        self.assertEqual(log["toasts"][0][0], "error")

    def test_sin_modernmodal_no_llama_al_fetch_de_restablecer(self):
        log = _correr("delete window.ModernModal;\n__click('restablecer');")
        self.assertEqual(log["fetches"], [])

    def test_con_modernmodal_el_eliminar_confirmado_si_llama_al_fetch(self):
        log = _correr(
            "window.ModernModal = {show: function (op) { __log.modal.push(op); }};\n"
            "__click('eliminar', 'g-x');\n__confirmar();"
        )
        self.assertEqual(len(log["fetches"]), 1)
        self.assertIn("/becas/x/eliminar/", log["fetches"][0]["url"])


@requiere_node
class Da2AutoguardadoSinToastDeExitoTests(SimpleTestCase):
    def setUp(self):
        self.modernmodal = "window.ModernModal = {show: function (op) { __log.modal.push(op); }};\n"

    def test_restablecer_ok_no_crea_toast(self):
        log = _correr(
            self.modernmodal
            + "__fetchRespuestas.push({status: 200, data: {ok: true, message: 'Formulario restablecido.'}});\n"
            "__click('restablecer');\n__confirmar();"
        )
        self.assertEqual(log["toasts"], [])

    def test_restablecer_con_error_si_avisa_por_toast(self):
        log = _correr(
            self.modernmodal
            + "__fetchRespuestas.push({status: 400, data: {ok: false, message: 'No se pudo restablecer.'}});\n"
            "__click('restablecer');\n__confirmar();"
        )
        self.assertEqual(log["toasts"], [["error", "No se pudo restablecer."]])

    def test_eliminar_ok_no_crea_toast(self):
        log = _correr(
            self.modernmodal + "__fetchRespuestas.push({status: 200, data: {ok: true, message: 'Eliminado.'}});\n"
            "__click('eliminar', 'g-x');\n__confirmar();"
        )
        self.assertEqual(log["toasts"], [])


class RenderEncabezadoYModalesTests(TestCase):
    """Encabezado con page_header/migas, indicador de autoguardado visible y los
    5 modales del constructor como diálogos accesibles (x-becas-modal)."""

    def setUp(self):
        call_command("seed_becas", stdout=StringIO())
        self.admin = User.objects.create_user("admin-render-cons", password="x")
        self.admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        self.client.force_login(self.admin)
        segmento = Segmento.objects.create(nombre="Educación render", cupo_maximo=100)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Becas render 2026", segmento=segmento, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )
        self.html = self.client.get(
            reverse("becas:convocatoria_formulario", args=[self.convocatoria.pk])
        ).content.decode()
        self.elementos = atributos_de(self.html)

    def test_encabezado_usa_page_header_con_migas_y_volver(self):
        self.assertIn("<h1", self.html)
        self.assertIn(">Configurar formulario</h1>", self.html)
        self.assertIn('aria-label="Volver a la convocatoria"', self.html)
        migas = [attrs for tag, attrs in self.elementos if tag == "nav" and attrs.get("aria-label") == "Migas"]
        self.assertEqual(len(migas), 1)
        self.assertIn("Programas", self.html)
        self.assertIn(self.convocatoria.nombre, self.html)

    def test_indicador_de_autoguardado_es_visible_con_aria_live(self):
        vivos = [attrs for tag, attrs in self.elementos if attrs.get("aria-live") == "polite"]
        self.assertTrue(vivos, "el indicador de guardado debe llevar aria-live")
        # No debe estar oculto por `x-cloak` como los modales: solo controla el
        # ícono/texto vía `:class`/`x-text`, siempre visible en el encabezado.
        for _, attrs in vivos:
            self.assertNotIn("x-cloak", attrs)
        self.assertIn("Guardado en vivo", self.html)

    def test_los_5_modales_son_dialogos_accesibles(self):
        # El 6to `role="dialog"` de la página es el ModernModal global de
        # `includes/base.html` (`#modal-content`), no un modal del constructor.
        dialogos = [
            attrs
            for tag, attrs in self.elementos
            if attrs.get("role") == "dialog" and str(attrs.get("aria-labelledby", "")).startswith("cons-")
        ]
        self.assertEqual(len(dialogos), 5, dialogos)
        for attrs in dialogos:
            self.assertEqual(attrs.get("aria-modal"), "true")
            titulo_id = attrs.get("aria-labelledby")
            self.assertTrue(titulo_id)
            self.assertIn(f'id="{titulo_id}"', self.html)

    def test_los_5_overlays_usan_x_becas_modal_y_la_pagina_carga_el_script(self):
        overlays = [attrs for tag, attrs in self.elementos if "x-becas-modal" in attrs]
        self.assertEqual(len(overlays), 5, overlays)
        for attrs in overlays:
            self.assertEqual(attrs["x-becas-modal"], attrs.get("x-show"))
        self.assertIn("custom/js/becas-modal.js", self.html)

    def test_labels_de_los_modales_llevan_la_clase_canon(self):
        labels = [attrs for tag, attrs in self.elementos if tag == "label"]
        self.assertTrue(labels)
        for attrs in labels:
            clases = attrs.get("class", "").split()
            self.assertIn("block", clases)
            self.assertIn("text-sm", clases)
            self.assertIn("font-medium", clases)
            self.assertIn("text-heading", clases)
            self.assertIn("mb-1", clases)
