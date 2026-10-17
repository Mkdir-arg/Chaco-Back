// Corre el aviso del selector de roles (Cambio 332) sobre un DOM mínimo.
// Uso: node roles_alcance.cjs <usuarios-roles-alcance.js> <escenario.json>
// El escenario trae la plantilla del mensaje, los roles ({id, nombre, alcance}) y la
// secuencia de clics. Imprime {tildados, modales, vistos}: qué quedó tildado, qué
// avisos abrió ModernModal y qué estado vio un listener del propio checkbox (el que
// en la pantalla recalcula chips y contadores). Lo lee
// users/tests/test_roles_becas_sin_pisarse.py.
const fs = require('node:fs');
const path = require('node:path');

const [script, escenarioRuta] = process.argv.slice(2);
const escenario = JSON.parse(fs.readFileSync(escenarioRuta, 'utf8'));

const modales = [];
const vistos = [];

function nodo() {
  return {
    _captura: [],
    _burbuja: [],
    addEventListener(tipo, fn, captura) {
      if (tipo !== 'change') return;
      (captura ? this._captura : this._burbuja).push(fn);
    },
  };
}

const picker = nodo();
picker.dataset = { mensajeRolesSePisan: escenario.plantilla };

const checks = escenario.roles.map((rol) => {
  const check = nodo();
  check.id = rol.id;
  check.checked = false;
  check.dataset = { nombre: rol.nombre };
  if (rol.alcance) check.dataset.alcanceBecas = rol.alcance;
  check.matches = (selector) => selector === '[data-rol-check]';
  // El listener del selector de la pantalla: está en el checkbox, fase de destino.
  check.addEventListener('change', () => vistos.push(`${check.id}:${check.checked}`));
  return check;
});

picker.querySelectorAll = (selector) =>
  selector === '[data-rol-check]:checked' ? checks.filter((c) => c.checked) : checks;

globalThis.window = globalThis;
globalThis.ModernModal = { show: (opciones) => modales.push(opciones) };
globalThis.document = {
  readyState: 'complete',
  getElementById: (id) => (id === 'roles-picker' ? picker : null),
  addEventListener() {},
};

require(path.resolve(script));

// Un clic de verdad: cambia el estado y despacha `change` en captura (ancestros)
// antes que en el destino, como el navegador.
escenario.clics.forEach((id) => {
  const check = checks.find((c) => c.id === id);
  check.checked = !check.checked;
  const evento = { target: check, type: 'change' };
  picker._captura.forEach((fn) => fn(evento));
  check._burbuja.forEach((fn) => fn(evento));
  picker._burbuja.forEach((fn) => fn(evento));
});

process.stdout.write(
  JSON.stringify({
    tildados: checks.filter((c) => c.checked).map((c) => c.id),
    modales: modales.map((m) => ({ type: m.type, title: m.title, message: m.message })),
    vistos,
  }),
);
