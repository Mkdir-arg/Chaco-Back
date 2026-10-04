"""Utilidades de test para los scripts inline de los templates.

Dos piezas:

- ``atributos_de(html)``: los atributos de cada elemento **ya decodificados**, como
  los ve el navegador (``&#x27;`` vuelve a ser ``'``). Sirve para afirmar qué termina
  dentro de un handler ``on*`` una vez que el parser HTML lo entrega al motor JS.
- ``correr_script(...)``: ejecuta con ``node`` el ``<script>`` inline que contiene un
  marcador, sobre un DOM mínimo simulado (``document``, ``ModernModal``, ``Swal``), y
  devuelve lo que el script le pasó a esas APIs. Si ``node`` no está instalado, el
  test que lo usa se saltea (``requiere_node``).
- ``correr_script_pagina(...)``: lo mismo para el script completo de una página, con
  un DOM permisivo (stubs para todo lo desconocido), ``fetch`` con respuestas fijas y
  registro de cada ``innerHTML`` y ``value`` asignados.
"""

import json
import re
import shutil
import subprocess
import unittest
from html.parser import HTMLParser

NODE = shutil.which("node")
requiere_node = unittest.skipUnless(NODE, "node no está instalado")

# Acepta atributos en la etiqueta (p. ej. un nonce de CSP); los <script src> no tienen cuerpo.
_SCRIPT_INLINE = re.compile(r"<script\b[^>]*>(.*?)</script>", re.S)

# DOM mínimo: registra listeners, modales, llamadas a Swal y submits de formularios.
_PRELUDIO = r"""
var __handlers = {};
var __log = {modal: [], swal: [], submits: []};
var window = globalThis;
function __form(id) {
  return {id: id, action: '', value: '', appendChild: function () {},
          submit: function () { __log.submits.push(this.id || this.action); }};
}
var document = {
  addEventListener: function (tipo, fn) { (__handlers[tipo] = __handlers[tipo] || []).push(fn); },
  getElementById: function (id) { return __form(id); },
  querySelector: function () { return null; },
  createElement: function () { return __form(''); },
  body: {appendChild: function () {}}
};
var ModernModal = {show: function (opciones) { __log.modal.push(opciones); }};
var Swal = {
  fire: function (opciones) { __log.swal.push(opciones); return {then: function () {}}; },
  showValidationMessage: function () {}
};
function __click(dataset) {
  var boton = {dataset: dataset, closest: function () { return boton; }};
  (__handlers.click || []).forEach(function (fn) { fn({target: boton, preventDefault: function () {}}); });
}
function __confirmar() {
  __log.modal.forEach(function (m) { if (m.onConfirm) m.onConfirm(); });
}
"""

_EPILOGO = r"""
console.log(JSON.stringify(__log, function (clave, valor) {
  return typeof valor === 'function' ? '[fn]' : valor;
}));
"""


class _Atributos(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.elementos = []

    def handle_starttag(self, tag, attrs):
        self.elementos.append((tag, {nombre: valor or "" for nombre, valor in attrs}))

    handle_startendtag = handle_starttag


def atributos_de(html):
    """Lista de ``(tag, {atributo: valor_decodificado})`` de todo el documento."""
    parser = _Atributos()
    parser.feed(html)
    return parser.elementos


def script_con(html, marcador):
    """El primer ``<script>`` inline del HTML que contiene ``marcador``."""
    for bloque in _SCRIPT_INLINE.findall(html):
        if marcador in bloque:
            return bloque
    raise AssertionError(f"No hay un <script> inline que contenga {marcador!r}")


def correr_script(script, acciones):
    """Ejecuta ``script`` con el DOM simulado, luego ``acciones`` (JS), y devuelve el log."""
    programa = _PRELUDIO + "\n" + script + "\n" + acciones + "\n" + _EPILOGO
    proceso = subprocess.run([NODE, "-"], input=programa, capture_output=True, text=True, encoding="utf-8", timeout=30)
    if proceso.returncode != 0:
        raise AssertionError(f"node falló:\n{proceso.stderr}")
    return json.loads(proceso.stdout.strip().splitlines()[-1])


# DOM permisivo para scripts de página completos: cualquier elemento o propiedad
# desconocida es un stub que acepta llamadas. Registra cada innerHTML asignado (el
# último por elemento), los valores de los inputs y los listeners; ``fetch`` responde
# con ``__respuestas`` (clave = fragmento de la URL) y ``setTimeout`` corre en el acto.
_PRELUDIO_PAGINA = r"""
var __log = {html: {}, valores: {}, fetches: []};
var __listeners = {};
var __els = {};
var __respuestas = {};
var __setTimeoutReal = setTimeout;
function __stub(ruta) {
  var datos = {};
  return new Proxy(function () {}, {
    get: function (t, k) {
      if (k in datos) return datos[k];
      if (k === Symbol.toPrimitive) return function () { return ''; };
      if (typeof k === 'symbol' || k === 'then') return undefined;
      if (k === 'addEventListener') {
        return function (tipo, fn) { (__listeners[ruta + ':' + tipo] = __listeners[ruta + ':' + tipo] || []).push(fn); };
      }
      return (datos[k] = __stub(ruta + '.' + String(k)));
    },
    set: function (t, k, v) {
      datos[k] = v;
      if (k === 'innerHTML') __log.html[ruta] = String(v);
      if (k === 'value') __log.valores[ruta] = String(v);
      return true;
    },
    apply: function () { return __stub(ruta + '()'); }
  });
}
function __el(id) { return __els[id] || (__els[id] = __stub('#' + id)); }
var document = __stub('document');
document.getElementById = __el;
var window = __stub('window');
var history = __stub('history');
var toastr = __stub('toastr');
var Swal = __stub('Swal');
var getComputedStyle = function () { return __stub('estilo'); };
setTimeout = function (fn) { fn(); return 0; };
clearTimeout = function () {};
var fetch = function (url) {
  url = String(url);
  __log.fetches.push(url);
  var clave = Object.keys(__respuestas).find(function (k) { return url.indexOf(k) !== -1; });
  var cuerpo = clave ? __respuestas[clave] : {};
  // `headers` incluido a propósito: una Response real siempre las trae, y hay
  // scripts que miran el content-type antes de `json()` para no reventar con un
  // HTML (el rebote por permisos devuelve el inicio, no JSON).
  return Promise.resolve({
    ok: true, status: 200,
    headers: {get: function (nombre) { return String(nombre).toLowerCase() === 'content-type' ? 'application/json' : null; }},
    json: function () { return Promise.resolve(cuerpo); }
  });
};
function __disparar(ruta, tipo, evento) {
  var destino = ruta.charAt(0) === '#' ? __el(ruta.slice(1)) : document;
  (__listeners[ruta + ':' + tipo] || []).forEach(function (fn) { fn.call(destino, evento || {}); });
}
function __item(dataset) {
  var item = {dataset: dataset, closest: function () { return item; }};
  return item;
}
"""

_EPILOGO_PAGINA = r"""
__setTimeoutReal(function () { console.log(JSON.stringify(__log)); }, 50);
"""


def correr_script_pagina(script, acciones):
    """Como ``correr_script`` pero con el DOM permisivo, para el script completo de una página."""
    programa = _PRELUDIO_PAGINA + "\n" + script + "\n" + acciones + "\n" + _EPILOGO_PAGINA
    proceso = subprocess.run([NODE, "-"], input=programa, capture_output=True, text=True, encoding="utf-8", timeout=30)
    if proceso.returncode != 0:
        raise AssertionError(f"node falló:\n{proceso.stderr}")
    return json.loads(proceso.stdout.strip().splitlines()[-1])
