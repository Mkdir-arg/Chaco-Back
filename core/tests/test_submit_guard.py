"""FE-26 · Guardia de doble envío de los formularios clásicos.

Fuera de Becas todo el backoffice manda formularios con un POST normal y nada impedía
que un doble clic sobre «Confirmar egreso», «Registrar entrega» o «Guardar» mandara dos
POST: dos egresos, dos entregas, dos altas. Becas no lo sufre porque sus formularios van
por `data-ajax` y `programas/becas/_ajax_js.html` ya deshabilita el botón.

El guard es `static/custom/js/nodo-submit-guard.js`, cargado una sola vez desde el shell.
Se ejecuta el archivo real con `node` sobre un DOM mínimo escrito acá: el `setTimeout`
es una cola manual, así que los tests pueden mirar el estado **durante** el despacho del
evento (donde deshabilitar un botón le borraría el `name`/`value` al POST) y después.
"""

import json
import subprocess
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from core.tests.js_harness import NODE, requiere_node

JS = Path(settings.BASE_DIR) / "static" / "custom" / "js" / "nodo-submit-guard.js"
SHELL = Path(settings.BASE_DIR) / "templates" / "includes" / "base.html"

# DOM mínimo: elementos con atributos, un registro global para `querySelectorAll`,
# `setTimeout` como cola manual y un despachador de `submit`/`pageshow`.
_DOM = r"""
var __log = {};
var __handlers = {};
var __cola = [];
var __todos = [];
setTimeout = function (fn) { __cola.push(fn); return 0; };
function __turno() { var c = __cola; __cola = []; c.forEach(function (f) { f(); }); }

function Elemento(tagName, attrs) {
  this.tagName = tagName;
  this._attrs = Object.assign({}, attrs || {});
  this.id = this._attrs.id || '';
  this.disabled = false;
  this.hijos = [];
  __todos.push(this);
}
Elemento.prototype.getAttribute = function (n) { return n in this._attrs ? this._attrs[n] : null; };
Elemento.prototype.setAttribute = function (n, v) { this._attrs[n] = String(v); };
Elemento.prototype.removeAttribute = function (n) { delete this._attrs[n]; };
Elemento.prototype.hasAttribute = function (n) { return n in this._attrs; };
Elemento.prototype.querySelectorAll = function () { return this.hijos; };

function __form(attrs, hijos) {
  var f = new Elemento('FORM', attrs);
  f.hijos = hijos || [];
  return f;
}
function __boton(attrs) { return new Elemento('BUTTON', attrs || {}); }
function __input(attrs) { return new Elemento('INPUT', attrs || {}); }

var document = {
  addEventListener: function (tipo, fn) { (__handlers[tipo] = __handlers[tipo] || []).push(fn); },
  querySelectorAll: function (selector) {
    if (selector === '[form]') { return __todos.filter(function (e) { return e.hasAttribute('form'); }); }
    if (selector === 'form[aria-busy]') {
      return __todos.filter(function (e) { return e.tagName === 'FORM' && e.hasAttribute('aria-busy'); });
    }
    var m = /^\[([^\]]+)\]$/.exec(selector);
    return __todos.filter(function (e) { return m && e.hasAttribute(m[1]); });
  }
};
var window = {addEventListener: function (tipo, fn) { (__handlers[tipo] = __handlers[tipo] || []).push(fn); }};

function __enviar(form, opciones) {
  opciones = opciones || {};
  var ev = {
    target: form,
    defaultPrevented: !!opciones.cancelado,
    preventDefault: function () { this.defaultPrevented = true; }
  };
  (__handlers.submit || []).forEach(function (fn) { fn(ev); });
  return ev;
}
function __pageshow(persisted) {
  (__handlers.pageshow || []).forEach(function (fn) { fn({persisted: persisted}); });
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
class DobleEnvioBloqueadoTests(SimpleTestCase):
    def test_el_primer_envio_pasa_y_el_segundo_se_cancela(self):
        log = _correr(
            "var f = __form({method: 'post'}, [__boton()]);\n"
            "__log.primero = __enviar(f).defaultPrevented;\n"
            "__log.segundo = __enviar(f).defaultPrevented;\n"
        )
        self.assertFalse(log["primero"], "el primer POST tiene que salir")
        self.assertTrue(log["segundo"], "el segundo POST tiene que quedar cancelado")

    def test_el_formulario_queda_marcado_como_ocupado(self):
        log = _correr(
            "var f = __form({method: 'post'}, [__boton()]);\n"
            "__enviar(f);\n"
            "__log.ariaBusy = f.getAttribute('aria-busy');\n"
        )
        self.assertEqual(log["ariaBusy"], "true")

    def test_los_botones_de_envio_quedan_deshabilitados(self):
        log = _correr(
            "var b = __boton();\nvar s = __input({type: 'submit'});\nvar t = __input({type: 'text'});\n"
            "var f = __form({method: 'post'}, [b, s, t]);\n"
            "__enviar(f);\n__turno();\n"
            "__log.boton = b.disabled;\n__log.submit = s.disabled;\n__log.texto = t.disabled;\n"
        )
        self.assertTrue(log["boton"])
        self.assertTrue(log["submit"])
        self.assertFalse(log["texto"], "un input de texto no es un botón de envío")

    def test_un_boton_type_button_no_se_toca(self):
        log = _correr(
            "var b = __boton({type: 'button'});\nvar f = __form({method: 'post'}, [b]);\n"
            "__enviar(f);\n__turno();\n__log.boton = b.disabled;\n"
        )
        self.assertFalse(log["boton"])

    def test_el_boton_no_se_deshabilita_durante_el_despacho(self):
        """Deshabilitarlo ahí lo saca del cuerpo del POST: se perdería su name/value."""
        log = _correr(
            "var b = __boton({name: 'accion', value: 'egresar'});\n"
            "var f = __form({method: 'post'}, [b]);\n"
            "__enviar(f);\n__log.durante = b.disabled;\n__turno();\n__log.despues = b.disabled;\n"
        )
        self.assertFalse(log["durante"], "el disabled tiene que esperar al turno siguiente")
        self.assertTrue(log["despues"])

    def test_alcanza_a_los_botones_externos_con_atributo_form(self):
        log = _correr(
            "var externo = __boton({form: 'alta'});\n"
            "var f = __form({method: 'post', id: 'alta'}, []);\n"
            "__enviar(f);\n__turno();\n__log.externo = externo.disabled;\n"
        )
        self.assertTrue(log["externo"])

    def test_un_boton_de_otro_formulario_no_se_toca(self):
        log = _correr(
            "var ajeno = __boton({form: 'otro'});\n"
            "var f = __form({method: 'post', id: 'alta'}, []);\n"
            "__enviar(f);\n__turno();\n__log.ajeno = ajeno.disabled;\n"
        )
        self.assertFalse(log["ajeno"])


@requiere_node
class LoQueElGuardNoToca(SimpleTestCase):
    def test_un_formulario_get_queda_libre(self):
        log = _correr(
            "var f = __form({method: 'get'}, [__boton()]);\n"
            "__enviar(f);\n__log.segundo = __enviar(f).defaultPrevented;\n"
            "__log.ariaBusy = f.getAttribute('aria-busy');\n"
        )
        self.assertFalse(log["segundo"])
        self.assertIsNone(log["ariaBusy"])

    def test_un_formulario_data_ajax_queda_libre(self):
        """Becas ya deshabilita su botón en `_ajax_js.html`."""
        log = _correr(
            "var f = __form({method: 'post', 'data-ajax': ''}, [__boton()]);\n"
            "__enviar(f);\n__log.segundo = __enviar(f).defaultPrevented;\n"
            "__log.ariaBusy = f.getAttribute('aria-busy');\n"
        )
        self.assertFalse(log["segundo"])
        self.assertIsNone(log["ariaBusy"])

    def test_un_envio_ya_cancelado_no_bloquea_el_formulario(self):
        """Si una validación o una confirmación canceló el envío, no pasó nada."""
        log = _correr(
            "var f = __form({method: 'post'}, [__boton()]);\n"
            "__enviar(f, {cancelado: true});\n__turno();\n"
            "__log.ariaBusy = f.getAttribute('aria-busy');\n"
            "__log.segundo = __enviar(f).defaultPrevented;\n"
        )
        self.assertIsNone(log["ariaBusy"])
        self.assertFalse(log["segundo"], "el formulario tiene que seguir enviable")


@requiere_node
class VolverConAtrasTests(SimpleTestCase):
    def test_el_bfcache_devuelve_el_formulario_a_su_estado(self):
        log = _correr(
            "var b = __boton();\nvar f = __form({method: 'post'}, [b]);\n"
            "__enviar(f);\n__turno();\n__pageshow(true);\n"
            "__log.boton = b.disabled;\n__log.ariaBusy = f.getAttribute('aria-busy');\n"
            "__log.segundo = __enviar(f).defaultPrevented;\n"
        )
        self.assertFalse(log["boton"])
        self.assertIsNone(log["ariaBusy"])
        self.assertFalse(log["segundo"], "después de volver con «atrás» se tiene que poder reenviar")

    def test_un_pageshow_que_no_viene_del_bfcache_no_libera_nada(self):
        log = _correr(
            "var b = __boton();\nvar f = __form({method: 'post'}, [b]);\n"
            "__enviar(f);\n__turno();\n__pageshow(false);\n__log.boton = b.disabled;\n"
        )
        self.assertTrue(log["boton"])


class ElShellCargaLaGuardiaTests(SimpleTestCase):
    def test_el_script_existe(self):
        self.assertTrue(JS.is_file())

    def test_el_shell_lo_carga_una_sola_vez(self):
        texto = SHELL.read_text(encoding="utf-8")
        self.assertEqual(texto.count("custom/js/nodo-submit-guard.js"), 1)

    def test_ninguna_pantalla_lo_repite(self):
        repo = Path(settings.BASE_DIR)
        ignorados = {".claude", ".git", "node_modules", "staticfiles", "site-packages"}
        culpables = []
        for ruta in repo.rglob("*.html"):
            relativa = ruta.relative_to(repo)
            if ignorados & set(relativa.parts) or ruta == SHELL:
                continue
            if "custom/js/nodo-submit-guard.js" in ruta.read_text(encoding="utf-8", errors="replace"):
                culpables.append(relativa.as_posix())
        self.assertEqual(culpables, [])
