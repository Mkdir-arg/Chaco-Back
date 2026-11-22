// Ejecuta el JS de `_ajax_js.html` con DOM y fetch controlados: sesión vencida (401) con `redirect`.
const assert = require('node:assert/strict');
const script = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));

const ORIGEN = 'https://ejemplo.invalid';

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
    location: { href: `${ORIGEN}/tipo/1/?tab=x`, origin: ORIGEN, pathname: '/tipo/1/', search: '?tab=x' },
    toast: (tipo, mensaje) => { avisos.push([tipo, mensaje]); return null; },
    addEventListener: () => {},
    dispatchEvent: () => { avisos.push(['evento', 'becas-saved']); },
  };
  global.fetch = () => Promise.resolve({ status: respuesta.status, json: () => Promise.resolve(respuesta.data) });
  eval(script);
  const form = new FormularioFalso();
  form.action = `${ORIGEN}/guardar/`;
  oyentes.submit({ target: form, preventDefault() {}, submitter: null });
  // fetch -> json -> then -> finally: unos cuantos turnos de microtareas.
  return new Promise(resolve => setTimeout(() => resolve({ avisos, window: global.window, form }), 20));
}

const URL_INICIAL = `${ORIGEN}/tipo/1/?tab=x`;

(async () => {
  // El `next` que trae la vista es el endpoint del POST: se reescribe a la página actual.
  const vencida = await correr({
    status: 401,
    data: { ok: false, message: 'Tu sesión venció.', redirect: `${ORIGEN}/login/?next=/dispositivos/accion/` },
  });
  const destino = new URL(vencida.window.location.href);
  assert.equal(destino.origin + destino.pathname, `${ORIGEN}/login/`, 'Navega al login');
  assert.equal(destino.searchParams.get('next'), '/tipo/1/?tab=x', 'Vuelve a la página actual, no al POST');
  assert.deepEqual(vencida.avisos, [], 'Sin error: la página se va');
  assert.equal(vencida.form.getAttribute('aria-busy'), 'true', 'El form queda ocupado hasta cambiar de página');

  // Un redirect relativo del mismo origen también vale.
  const relativa = await correr({ status: 401, data: { ok: false, redirect: '/login/' } });
  assert.equal(new URL(relativa.window.location.href).searchParams.get('next'), '/tipo/1/?tab=x');

  // Un redirect de otro origen no se sigue: aviso común y el form se libera.
  const ajeno = await correr({
    status: 401,
    data: { ok: false, message: 'Tu sesión venció.', redirect: 'https://otro.invalid/login/?next=/x/' },
  });
  assert.equal(ajeno.window.location.href, URL_INICIAL, 'No navega a otro origen');
  assert.deepEqual(ajeno.avisos, [['error', 'Tu sesión venció.']]);
  assert.equal(ajeno.form.getAttribute('aria-busy'), null, 'El form se libera');

  // Un 401 sin `redirect` no tiene a dónde ir: avisa como cualquier otro error.
  const sinDestino = await correr({ status: 401, data: { ok: false, message: 'Sin sesión.' } });
  assert.equal(sinDestino.window.location.href, URL_INICIAL);
  assert.deepEqual(sinDestino.avisos, [['error', 'Sin sesión.']]);
})().catch(error => { console.error(error); process.exit(1); });
