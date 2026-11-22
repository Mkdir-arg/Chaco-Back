// Ejecuta el JS de `tipo_detail.html` con un DOM mínimo: `becas-saved` cierra el modal «Editar tipo»
// solo si el formulario que se envió sigue montado.
const assert = require('node:assert/strict');
const script = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));

function montar() {
  const ventana = {};
  const raiz = {
    hijos: [],
    modal: null,
    cerrado: 0,
    oyentes: {},
    addEventListener(nombre, callback) { this.oyentes[nombre] = callback; },
    contains(nodo) { return this.hijos.includes(nodo); },
    querySelector(selector) { return selector === '[data-edit-modal]' ? this.modal : null; },
    replaceChildren() { this.hijos = []; this.modal = null; this.cerrado++; },
    // Lo que hace el servidor al abrir el modal: un form nuevo dentro del panel.
    abrir() {
      const form = { closest: selector => (selector === 'form[data-ajax]' ? form : null) };
      this.hijos = [form];
      this.modal = { dataset: { editUrl: '/tipo/1/editar/', cancelUrl: '/tipo/1/' } };
      return form;
    },
  };
  global.document = {
    getElementById: id => (id === 'dispositivos-modal-root' ? raiz : null),
    addEventListener: () => {},
    querySelectorAll: () => [],
    contains: () => false,
  };
  global.window = {
    location: { pathname: '/tipo/1/' },
    history: { replaceState() {} },
    becasModal: { bind: () => ({ destruir() {} }) },
    addEventListener: (nombre, callback) => { ventana[nombre] = callback; },
    toast: { error() {} },
  };
  eval(script);
  return { raiz, guardado: () => ventana['becas-saved']({ detail: { ok: true } }) };
}

// 1. Se envía el form del modal y el guardado vuelve con ese form montado: cierra.
{
  const { raiz, guardado } = montar();
  const form = raiz.abrir();
  raiz.oyentes.submit({ target: form });
  guardado();
  assert.equal(raiz.cerrado, 1, 'El form enviado sigue montado: el modal se cierra');
}

// 2. El modal se reemplazó mientras el guardado viajaba (otro form): no cierra el actual.
{
  const { raiz, guardado } = montar();
  const viejo = raiz.abrir();
  raiz.oyentes.submit({ target: viejo });
  raiz.abrir();
  guardado();
  assert.equal(raiz.cerrado, 0, 'El form enviado ya no está: el modal nuevo no se cierra');
}

// 3. Un `becas-saved` sin envío del modal (otro form de la página) tampoco lo cierra.
{
  const { raiz, guardado } = montar();
  raiz.abrir();
  guardado();
  assert.equal(raiz.cerrado, 0, 'Sin un envío desde el modal no hay nada que cerrar');
}

// 4. El aviso vale una sola vez: un segundo `becas-saved` no vuelve a cerrar.
{
  const { raiz, guardado } = montar();
  const form = raiz.abrir();
  raiz.oyentes.submit({ target: form });
  guardado();
  raiz.abrir();
  guardado();
  assert.equal(raiz.cerrado, 1);
}
