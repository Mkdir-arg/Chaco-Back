// Una franja que vuelve del servidor ya marcada para quitar se oculta y no pisa a la nueva.
const assert = require('node:assert/strict');
const script = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));

function clases(iniciales) {
  const set = new Set(iniciales || []);
  return {
    add(...nombres) { nombres.forEach(n => set.add(n)); },
    remove(...nombres) { nombres.forEach(n => set.delete(n)); },
    toggle(nombre, valor) { if (valor) set.add(nombre); else set.delete(nombre); },
    contains(nombre) { return set.has(nombre); },
  };
}
function elemento(extra) {
  const el = {
    dataset: {}, classList: clases(), hijos: [], atributos: {}, oyentes: {},
    append(...hijos) { el.hijos.push(...hijos); },
    setAttribute(nombre, valor) { el.atributos[nombre] = valor; },
    removeAttribute(nombre) { delete el.atributos[nombre]; },
    addEventListener(evento, callback) { el.oyentes[evento] = callback; },
    focus() {},
    // Lo que el script busca dentro de una fila que armó él mismo: el botón «Quitar».
    querySelector: sel => {
      const atributo = /^\[data-([a-z-]+)\]$/.exec(sel);
      if (!atributo) return null;
      const clave = atributo[1].replace(/-([a-z])/g, (_, letra) => letra.toUpperCase());
      const buscar = nodo => nodo.hijos.find(h => h.dataset && clave in h.dataset)
        || nodo.hijos.map(h => (h.hijos ? buscar(h) : null)).find(Boolean) || null;
      return buscar(el);
    },
    querySelectorAll: () => [],
  };
  return Object.assign(el, extra);
}

// La fila guardada del lunes de 09:00 a 12:00, con su DELETE tildado.
const marca = { checked: true };
const quitar = elemento();
const guardada = elemento({
  dataset: { franja: '', dia: '1', desde: '09:00', hasta: '12:00' },
  querySelector: sel => (sel === 'input[type="checkbox"]' ? marca : sel === '[data-quitar]' ? quitar : null),
});
const vacio = elemento();
const filasFormset = [guardada];
const filas = elemento({
  querySelectorAll: sel => {
    if (sel === '[data-franja]') return filasFormset;
    if (sel === '[data-franja]:not(.hidden)') return filasFormset.filter(f => !f.classList.contains('hidden'));
    return [];
  },
  insertBefore(fila) { filasFormset.push(fila); },
});
const dia = elemento({ id: 'id_franjas-1-dia', value: '', options: [{ text: 'Lunes' }], selectedIndex: 0 });
const desde = elemento({ id: 'id_franjas-1-hora_desde', value: '' });
const hasta = elemento({ id: 'id_franjas-1-hora_hasta', value: '' });
const control = elemento({
  querySelector: sel => (sel === 'select' ? dia : null),
  querySelectorAll: sel => (sel === 'input[type="time"]' ? [desde, hasta] : []),
});
const agregar = elemento({ classList: clases(['hidden']) });
const ayuda = elemento();
const bloque = elemento({
  dataset: { prefijo: 'franjas' },
  querySelector: sel => ({
    '[data-franjas-filas]': filas,
    '[data-franjas-vacio]': vacio,
    '[data-franja-agregar]': agregar,
    '[data-ayuda-sin-js]': ayuda,
  })[sel] || null,
  querySelectorAll: sel => (sel === '[data-franja-vacia]' ? [control] : []),
});
const total = { value: '1' };
const errores = {};
global.document = {
  querySelector: sel => (sel === '[data-franjas]' ? bloque : null),
  getElementById: id => {
    if (id === 'id_franjas-TOTAL_FORMS') return total;
    errores[id] = errores[id] || elemento({ textContent: '' });
    return errores[id];
  },
  createElement: () => elemento(),
};
eval(script);

assert.equal(guardada.classList.contains('hidden'), true, 'La franja marcada para quitar no se muestra');
assert.equal(vacio.classList.contains('hidden'), false, 'Sin franjas visibles vuelve el «Todavía no hay franjas»');

dia.value = '1';
desde.value = '10:00';
hasta.value = '11:00';
agregar.oyentes.click();
assert.equal(errores['id_franjas-1-hora_desde-error'].textContent, '', 'La franja marcada no cuenta para la superposición');
assert.equal(filasFormset.length, 2, 'La franja nueva se agrega');
assert.equal(total.value, 2);
