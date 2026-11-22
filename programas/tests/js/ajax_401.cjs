// Ejecuta el JS de `_ajax_js.html` con DOM y fetch controlados: sesión vencida (401) con `redirect`.
const assert = require('node:assert/strict');
const script = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));

class FormularioFalso {
  constructor() {
    this.elements = [];
    this.attrs = { 'data-ajax': '' };
  }
  hasAttribute(nombre) { return nombre in this.attrs; }
  getAttribute(nombre) { return this.attrs[nombre] ?? null; }
  setAttribute(nombre, valor) { this.attrs[nombre] = String(valor); }
  removeAttribute(nombre) { delete this.attrs[nombre]; }
  querySelectorAll() { return []; }
  querySelector() { return null; }
}

function correr(respuesta) {
  const oyentes = {};
  const avisos = [];
  global.HTMLFormElement = FormularioFalso;
  global.FormData = function () {};
  global.CustomEvent = function (nombre, opciones) { this.type = nombre; this.detail = opciones.detail; };
  global.document = {
    cookie: '',
    addEventListener: (evento, callback) => { oyentes[evento] = callback; },
    querySelectorAll: () => [],
    querySelector: () => null,
  };
  global.window = {
    location: { href: 'https://ejemplo.invalid/tipo/1/' },
    toast: (tipo, mensaje) => { avisos.push([tipo, mensaje]); return null; },
    addEventListener: () => {},
    dispatchEvent: () => { avisos.push(['evento', 'becas-saved']); },
  };
  global.fetch = () => Promise.resolve({ status: respuesta.status, json: () => Promise.resolve(respuesta.data) });
  eval(script);
  const form = new FormularioFalso();
  form.action = 'https://ejemplo.invalid/guardar/';
  oyentes.submit({ target: form, preventDefault() {}, submitter: null });
  // fetch -> json -> then -> finally: unos cuantos turnos de microtareas.
  return new Promise(resolve => setTimeout(() => resolve({ avisos, window: global.window, form }), 20));
}

(async () => {
  const vencida = await correr({
    status: 401,
    data: { ok: false, message: 'Tu sesión venció.', redirect: 'https://ejemplo.invalid/login/?next=/tipo/1/' },
  });
  assert.equal(vencida.window.location.href, 'https://ejemplo.invalid/login/?next=/tipo/1/', 'Navega al login');
  assert.deepEqual(vencida.avisos, [], 'Sin error genérico: la página se va');
  assert.equal(vencida.form.getAttribute('aria-busy'), 'true', 'El form queda ocupado hasta cambiar de página');

  // Un 401 sin `redirect` no tiene a dónde ir: avisa como cualquier otro error.
  const sinDestino = await correr({ status: 401, data: { ok: false, message: 'Sin sesión.' } });
  assert.equal(sinDestino.window.location.href, 'https://ejemplo.invalid/tipo/1/');
  assert.deepEqual(sinDestino.avisos, [['error', 'Sin sesión.']]);
})().catch(error => { console.error(error); process.exit(1); });
