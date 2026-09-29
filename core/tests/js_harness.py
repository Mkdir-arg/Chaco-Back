"""Utilidades de test para los scripts inline de los templates.

Dos piezas:

- ``atributos_de(html)``: los atributos de cada elemento **ya decodificados**, como
  los ve el navegador (``&#x27;`` vuelve a ser ``'``). Sirve para afirmar qué termina
  dentro de un handler ``on*`` una vez que el parser HTML lo entrega al motor JS.
- ``correr_script(...)``: ejecuta con ``node`` el ``<script>`` inline que contiene un
  marcador, sobre un DOM mínimo simulado (``document``, ``ModernModal``, ``Swal``), y
  devuelve lo que el script le pasó a esas APIs. Si ``node`` no está instalado, el
  test que lo usa se saltea (``requiere_node``).
"""

import json
import re
import shutil
import subprocess
import unittest
from html.parser import HTMLParser

NODE = shutil.which("node")
requiere_node = unittest.skipUnless(NODE, "node no está instalado")

_SCRIPT_INLINE = re.compile(r"<script>(.*?)</script>", re.S)

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
