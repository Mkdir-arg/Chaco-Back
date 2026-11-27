"""Pieza «Domicilio con mapa» en node, con Google simulado: aviso «aproximado» (Cambio 619), qué alertas se van al
escribir las coordenadas a mano (Cambio 621) y la regla de precisión compartida con el panel «Derivar»."""

import json
import os
import subprocess
from pathlib import Path

from django import forms
from django.template.loader import render_to_string
from django.test import SimpleTestCase

from core.tests.js_harness import NODE, requiere_node

JS = Path(__file__).resolve().parents[2] / "static" / "custom" / "js"

# DOM mínimo para correr `nodo-ubicacion.js` en node: Google queda simulado (Geocoder, mapa y marcador) y cada
# escenario devuelve qué aviso quedó a la vista después de cada acción.
_HARNESS_UBICACION = r"""
const fs = require('fs'), vm = require('vm');
const fuente = fs.readFileSync(process.env.FUENTE, 'utf8');
const fuenteMapa = fs.readFileSync(process.env.FUENTE_MAPA, 'utf8');
const escenarios = JSON.parse(process.env.ESCENARIOS);
function el() {
  const e = {dataset: {}, hidden: false, className: '', disabled: false, value: '', children: [], listeners: {},
    textContent: '', _h: '', classList: {toggle() {}},
    addEventListener(t, f) { this.listeners[t] = f; }, setAttribute() {}, removeAttribute() {},
    hasAttribute() { return false; }, appendChild(c) { this.children.push(c); return c; },
    querySelector() { return el(); }, querySelectorAll() { return []; }, focus() {}, dispatchEvent() {}};
  Object.defineProperty(e, 'innerHTML', {get() { return this._h; }, set(v) { this._h = v; if (v === '') { this.children = []; } }});
  return e;
}
async function correr(esc) {
  const piezas = {}, campos = {d: el(), la: el(), lo: el()};
  campos.d.id = 'd';
  const raiz = el();
  Object.assign(raiz.dataset, {domicilio: 'd', latitud: 'la', longitud: 'lo', provincia: 'Chaco'});
  raiz.querySelector = function (sel) {
    const alerta = /data-ubicacion-alerta="([^"]+)"/.exec(sel);
    if (alerta) { return {content: {cloneNode() { return {alerta: alerta[1]}; }}}; }
    const clave = /\[data-([a-z-]+)\]/.exec(sel)[1];
    return piezas[clave] || (piezas[clave] = el());
  };
  const lista = raiz.querySelector('[data-ubicacion-candidatos-lista]');
  lista.querySelector = function () { return this.children[0].children[0]; };
  let marcador = null, llamadas = 0;
  const mapa = {};
  class Marcador {
    constructor(o) { this.position = o.position; marcador = this; }
    addListener(t, f) { this[t] = f; }
  }
  const librerias = [
    {AdvancedMarkerElement: Marcador, PinElement: class { constructor() { this.element = {}; } }},
    {Geocoder: class { geocode() { llamadas += 1; if (esc.falla) { return Promise.reject(new Error('sin red')); } return Promise.resolve({results: llamadas > 1 && esc.siguiente ? esc.siguiente : esc.resultados}); } }}
  ];
  Object.assign(globalThis, {
    window: globalThis, MutationObserver: class { observe() {} },
    getComputedStyle: () => ({getPropertyValue: () => 'x'}),
    document: {readyState: 'complete', addEventListener() {}, createElement: el,
      createTextNode: (t) => ({t}), documentElement: {},
      getElementById: (id) => campos[id] || null, querySelectorAll: () => [raiz]},
    addEventListener() {}
  });
  // El nodo-mapa.js real: así `NodoMapa.esPreciso` es la regla verdadera. Solo se simula lo que habla con Google.
  delete globalThis.NodoMapa;
  vm.runInThisContext(fuenteMapa);
  if (process.env.INVERTIR === '1') { const real = NodoMapa.esPreciso; NodoMapa.esPreciso = (r) => !real(r); }
  Object.assign(NodoMapa, {configurado: true, importar: () => Promise.resolve(librerias),
    crearMapa: () => Promise.resolve({addListener(t, f) { mapa[t] = f; }, panTo() {}, setZoom() {}})});
  vm.runInThisContext(fuente);
  const espera = () => new Promise((r) => setTimeout(r, 15));
  await espera();
  const aviso = () => (piezas['ubicacion-aviso'].hidden ? null : piezas['ubicacion-aviso'].children[0].alerta);
  const vistos = [];
  for (const accion of esc.acciones) {
    if (accion === 'ubicar') {
      campos.d.value = 'Calle 1';
      piezas['ubicacion-buscar'].disabled = false;
      piezas['ubicacion-buscar'].listeners.click();
    } else if (accion.startsWith('elegir:')) {
      lista.children[Number(accion.split(':')[1])].children[0].listeners.click();
    } else if (accion === 'arrastrar') {
      marcador.position = {lat: 1, lng: 2};
      marcador.dragend();
    } else if (accion === 'campos' || accion === 'campos-js') {
      campos.la.value = '-27.100000';
      campos.lo.value = '-58.100000';
      campos.la.listeners.change({isTrusted: accion === 'campos'});
    } else if (accion === 'tocar') {
      mapa.click({latLng: {lat: 3, lng: 4}});
    }
    await espera();
    vistos.push(aviso());
  }
  return vistos;
}
(async () => {
  const salida = [];
  for (const esc of escenarios) { salida.push(await correr(esc)); }
  console.log(JSON.stringify(salida));
})();
"""


def _resultado(tipo, parcial=False, direccion="Calle 1, Resistencia"):
    r = {
        "formatted_address": direccion,
        "geometry": {"location_type": tipo, "location": {"lat": -27.45, "lng": -58.98}},
    }
    if parcial:
        r["partial_match"] = True
    return r


@requiere_node
class UbicacionAvisoAproximadoTest(SimpleTestCase):
    """Cambio 619: con un resultado aproximado de Google el marcador se pone y aparece un aviso que no bloquea."""

    FUENTE = JS / "nodo-ubicacion.js"

    def correr(self, escenarios, invertir=False):
        proceso = subprocess.run(
            [NODE, "-e", _HARNESS_UBICACION],
            env={
                **os.environ,
                "FUENTE": str(self.FUENTE),
                "FUENTE_MAPA": str(JS / "nodo-mapa.js"),
                "ESCENARIOS": json.dumps(escenarios),
                "INVERTIR": "1" if invertir else "0",
            },
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
        self.assertEqual(proceso.returncode, 0, proceso.stderr)
        return json.loads(proceso.stdout)

    def test_la_pieza_decide_con_NodoMapa_esPreciso_y_no_con_una_copia(self):
        escenarios = [
            {"resultados": [_resultado("ROOFTOP")], "acciones": ["ubicar"]},
            {"resultados": [_resultado("GEOMETRIC_CENTER")], "acciones": ["ubicar"]},
        ]

        salida = self.correr(escenarios, invertir=True)

        # Con la regla compartida invertida, la decisión de la pieza se invierte.
        self.assertEqual([s[0] for s in salida], ["aproximado", None])

    def test_la_regla_de_precision_es_la_de_derivar(self):
        casos = [
            ("ROOFTOP", False, None),
            ("RANGE_INTERPOLATED", False, None),
            ("GEOMETRIC_CENTER", False, "aproximado"),
            ("APPROXIMATE", False, "aproximado"),
            ("ROOFTOP", True, "aproximado"),
            ("RANGE_INTERPOLATED", True, "aproximado"),
        ]
        escenarios = [{"resultados": [_resultado(t, p)], "acciones": ["ubicar"]} for t, p, _ in casos]

        salida = self.correr(escenarios)

        self.assertEqual([s[0] for s in salida], [esperado for _, _, esperado in casos])

    def test_con_varios_resultados_avisa_solo_si_la_persona_elige_uno_aproximado(self):
        resultados = [_resultado("ROOFTOP", direccion="A"), _resultado("GEOMETRIC_CENTER", direccion="B")]
        escenarios = [
            {"resultados": resultados, "acciones": ["ubicar", "elegir:1"]},
            {"resultados": resultados, "acciones": ["ubicar", "elegir:0"]},
        ]

        salida = self.correr(escenarios)

        self.assertEqual(salida[0], [None, "aproximado"])
        self.assertEqual(salida[1], [None, None])

    def test_el_aviso_se_va_al_mover_el_marcador_tocar_el_mapa_o_ubicar_con_precision(self):
        aprox = [_resultado("GEOMETRIC_CENTER")]
        escenarios = [
            {"resultados": aprox, "acciones": ["ubicar", "arrastrar"]},
            {"resultados": aprox, "acciones": ["ubicar", "tocar"]},
            {"resultados": aprox, "siguiente": [_resultado("ROOFTOP")], "acciones": ["ubicar", "ubicar"]},
        ]

        salida = self.correr(escenarios)

        self.assertEqual(salida[0], ["aproximado", None])
        self.assertEqual(salida[1], ["aproximado", None])
        self.assertEqual(salida[2], ["aproximado", None])

    def test_escribir_las_coordenadas_a_mano_limpia_el_aviso_pero_no_cuando_las_rellena_el_js(self):
        aprox = [_resultado("GEOMETRIC_CENTER")]
        escenarios = [
            {"resultados": aprox, "acciones": ["ubicar", "campos"]},
            {"resultados": aprox, "acciones": ["ubicar", "campos-js"]},
        ]

        salida = self.correr(escenarios)

        self.assertEqual(salida[0], ["aproximado", None])
        self.assertEqual(salida[1], ["aproximado", "aproximado"])

    def test_escribir_las_coordenadas_a_mano_no_borra_otras_alertas_solo_la_aproximada(self):
        escenarios = [
            {"resultados": [], "falla": True, "acciones": ["ubicar", "campos"]},
            {"resultados": [], "acciones": ["ubicar", "campos"]},
            {"resultados": [_resultado("GEOMETRIC_CENTER")], "acciones": ["ubicar", "campos"]},
            {"resultados": [], "acciones": ["ubicar", "tocar"]},
        ]

        salida = self.correr(escenarios)

        # Con la alerta roja de Google (falla la búsqueda) o «no encontrado», las coordenadas a mano no las borran.
        self.assertEqual(salida[0], ["error", "error"])
        self.assertEqual(salida[1], ["no-encontrado", "no-encontrado"])
        # La aproximada sí: las coordenadas escritas reemplazan el punto que Google dio.
        self.assertEqual(salida[2], ["aproximado", None])
        # Marcar el punto tocando el mapa resuelve «no encontrado»: la persona ya eligió el lugar.
        self.assertEqual(salida[3], ["no-encontrado", None])


class UbicacionAlertaAproximadoTemplateTest(SimpleTestCase):
    class Form(forms.Form):
        domicilio = forms.CharField(required=False)
        latitud = forms.DecimalField(required=False, max_digits=9, decimal_places=6)
        longitud = forms.DecimalField(required=False, max_digits=9, decimal_places=6)
        localidad = forms.CharField(required=False)

    def test_el_template_trae_la_alerta_aproximado_como_warning(self):
        form = self.Form()
        html = render_to_string(
            "components/_ubicacion_domicilio.html",
            {
                "domicilio": form["domicilio"],
                "latitud": form["latitud"],
                "longitud": form["longitud"],
                "localidad_id": form["localidad"].id_for_label,
            },
        )

        plantilla = html.split('data-ubicacion-alerta="aproximado"')[1].split("</template>")[0]
        self.assertIn(
            "Google ubicó esta dirección en forma aproximada. Mové el marcador al lugar exacto antes de guardar.",
            plantilla,
        )
        self.assertIn('role="alert"', plantilla)
        self.assertIn("bg-warning-soft", plantilla)
        self.assertNotIn("danger", plantilla)


_HARNESS_DERIVAR = r"""
const fs = require('fs'), vm = require('vm');
const resultado = JSON.parse(process.env.RESULTADO);
const oyentes = {}, guardados = [];
const boton = {hidden: true, disabled: false, addEventListener: (t, f) => { oyentes[t] = f; }};
const config = {origen: null, direccion: 'Calle 1, Resistencia, Chaco, Argentina', ubicar_url: '/guardar/',
  destinos: [{clave: 'a', lat: -27.46, lng: -58.99}]};
const punto = {lat: () => -27.45, lng: () => -58.98};
resultado.geometry.location = punto;
Object.assign(globalThis, {
  window: globalThis, FormData: class { append() {} },
  fetch: (url) => { guardados.push(url); return Promise.resolve({}); },
  document: {
    getElementById: (id) => (id === 'derivar-distancias-config' ? {textContent: JSON.stringify(config)} : null),
    querySelector: (s) => (s === '[data-derivar-por-calle]' ? boton : null),
    addEventListener() {}
  }
});
vm.runInThisContext(fs.readFileSync(process.env.FUENTE_MAPA, 'utf8'));
if (process.env.INVERTIR === '1') { const real = NodoMapa.esPreciso; NodoMapa.esPreciso = (r) => !real(r); }
Object.assign(NodoMapa, {configurado: true, importar: (nombre) => Promise.resolve(nombre === 'geocoding' ?
  [{Geocoder: class { geocode() { return Promise.resolve({results: [resultado]}); } }}] : [{}])});
vm.runInThisContext(fs.readFileSync(process.env.FUENTE, 'utf8'));
oyentes.click();
setTimeout(() => console.log(JSON.stringify(guardados)), 30);
"""


@requiere_node
class DerivarUsaLaReglaDePrecisionCompartidaTest(SimpleTestCase):
    """«Derivar» guarda el domicilio de la familia solo con un resultado preciso: la regla es `NodoMapa.esPreciso`."""

    def guardados(self, tipo, parcial=False, invertir=False):
        proceso = subprocess.run(
            [NODE, "-e", _HARNESS_DERIVAR],
            env={
                **os.environ,
                "FUENTE": str(JS / "nodo-derivar-distancias.js"),
                "FUENTE_MAPA": str(JS / "nodo-mapa.js"),
                "RESULTADO": json.dumps(_resultado(tipo, parcial)),
                "INVERTIR": "1" if invertir else "0",
            },
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
        self.assertEqual(proceso.returncode, 0, proceso.stderr)
        return json.loads(proceso.stdout)

    def test_guarda_el_domicilio_solo_con_un_resultado_preciso(self):
        self.assertEqual(self.guardados("ROOFTOP"), ["/guardar/"])
        self.assertEqual(self.guardados("RANGE_INTERPOLATED"), ["/guardar/"])
        self.assertEqual(self.guardados("GEOMETRIC_CENTER"), [])
        self.assertEqual(self.guardados("ROOFTOP", parcial=True), [])

    def test_derivar_decide_con_NodoMapa_esPreciso_y_no_con_una_copia(self):
        # Con la regla compartida invertida, la decisión de Derivar se invierte.
        self.assertEqual(self.guardados("ROOFTOP", invertir=True), [])
        self.assertEqual(self.guardados("GEOMETRIC_CENTER", invertir=True), ["/guardar/"])
