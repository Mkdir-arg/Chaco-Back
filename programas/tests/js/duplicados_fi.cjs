// Ejecuta el JS renderizado de P3 con DOM y fetch controlados; no consulta la red.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const script = JSON.parse(fs.readFileSync(0, 'utf8'));
const errores = [];
console.error = (...args) => errores.push(args);
const clases = () => ({
  hidden: true,
  add() { this.hidden = true; },
  remove() { this.hidden = false; },
  toggle(_, value) { this.hidden = value; },
});
const mensaje = {};
const lista = { hijos: [], replaceChildren(n) { this.hijos = [n]; }, appendChild(n) { this.hijos.push(n); } };
let scrolls = 0;
let focos = 0;
const aviso = { classList: clases(), querySelector: s => s.includes('mensaje') ? mensaje : lista,
  scrollIntoView(options) { assert.equal(options.block, 'center'); scrolls++; },
  focus(options) { assert.equal(options.preventScroll, true); focos++; } };
const contador = { textContent: 0 };
const vacio = { classList: clases() };
let enviado = 0;
let ultimoBoton;
const form = {
  listeners: {},
  addEventListener(name, callback) { this.listeners[name] = callback; },
  requestSubmit(boton) { enviado++; ultimoBoton = boton; },
  submit() { throw new Error('Se perdió el submitter'); },
};
const input = value => ({ value, listeners: {}, closest: () => form,
  addEventListener(name, callback) { this.listeners[name] = callback; } });
const codigo = input('FI-LIBRE');
const nombre = input('Institución FI');
const localidad = input('Resistencia');
const elementos = { id_codigo: codigo, id_nombre: nombre, id_localidad: localidad,
  'duplicate-search': aviso, 'duplicate-empty': vacio, 'duplicate-count': contador };
global.document = {
  getElementById: id => elementos[id],
  createElement: () => ({ appendChild() {} }),
};
let avisosDeError = 0;
global.Swal = { fire: (...args) => {
  if (args[2] === 'error') avisosDeError++;
  return Promise.resolve({ isConfirmed: true });
} };
const limpio = { codigo_duplicado: false, coincidencias: [] };
const respuesta = data => Promise.resolve({ ok: true, json: () => Promise.resolve(data) });
const tick = () => new Promise(resolve => setImmediate(resolve));
function pendienteQueSeAborta() {
  let primera = true;
  global.fetch = (_, options) => {
    if (!primera) return respuesta(limpio);
    primera = false;
    return new Promise((resolve, reject) => options.signal.addEventListener('abort',
      () => reject(new DOMException('Cancelada intencionalmente', 'AbortError'))));
  };
}
eval(script);
(async () => {
  pendienteQueSeAborta();
  codigo.listeners.blur();
  nombre.listeners.blur();
  await tick();
  assert.equal(errores.length, 0, 'El catch de blur registra un aborto intencional');

  const boton = { name: 'accion', value: 'enviar_validacion' };
  const evento = { preventDefault() {}, submitter: boton };
  pendienteQueSeAborta();
  form.listeners.submit(evento);
  codigo.listeners.blur();
  await tick();
  assert.equal(errores.length, 0, 'El catch de submit registra un aborto intencional');
  assert.equal(avisosDeError, 0, 'El aborto no debe abrir una alerta de fallo');
  assert.equal(enviado, 0);

  const coincidencias = [{codigo: 'FJ-1', nombre: 'Institución FJ', localidad: 'Resistencia'}];
  global.fetch = () => respuesta({ codigo_duplicado: false, coincidencias });
  codigo.listeners.blur();
  await tick();
  nombre.listeners.blur();
  await tick();
  assert.equal(lista.hijos.length, 1, 'Dos búsquedas deben reemplazar la lista, sin acumular hijos');
  assert.equal(Number(contador.textContent), 1, 'El badge cuenta las coincidencias visibles');
  global.fetch = () => respuesta({ codigo_duplicado: false, coincidencias: [...coincidencias, ...coincidencias] });
  codigo.listeners.blur();
  await tick();
  assert.equal(Number(contador.textContent), 2, 'El badge se actualiza con cada búsqueda');

  // Coincidencia que el endpoint no puede revelar por alcance: explica y bloquea.
  global.fetch = () => respuesta({ codigo_duplicado: true, coincidencias: [] });
  codigo.listeners.blur();
  await tick();
  assert.equal(aviso.classList.hidden, false, 'El código repetido sin filas visibles debe explicar el bloqueo');
  assert.equal(vacio.classList.hidden, true);
  form.listeners.submit(evento);
  await tick();
  assert.equal(enviado, 0, 'El código repetido no se envía');
  assert.equal(scrolls, 1, 'El bloqueo debe llevar el aviso a la vista');
  assert.equal(focos, 1, 'El bloqueo debe llevar el foco al aviso');
  assert.equal(Number(contador.textContent), 0, 'No se cuentan coincidencias fuera del alcance');

  global.fetch = () => respuesta(limpio);
  codigo.listeners.blur();
  await tick();
  assert.equal(aviso.classList.hidden, true);
  assert.equal(vacio.classList.hidden, false);
  assert.equal(Number(contador.textContent), 0);
  codigo.value = '';
  nombre.value = '';
  contador.textContent = 2;
  codigo.listeners.blur();
  await tick();
  assert.equal(Number(contador.textContent), 0, 'Limpiar los campos también limpia el contador');
  codigo.value = 'FI-LIBRE';
  form.listeners.submit(evento);
  await tick();
  assert.equal(enviado, 1);
  assert.equal(ultimoBoton, boton, 'El envío debe conservar accion=enviar_validacion');
})().catch(error => { process.stderr.write(error.stack); process.exitCode = 1; });
