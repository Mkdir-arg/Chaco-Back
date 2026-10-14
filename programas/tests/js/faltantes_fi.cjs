// Comprueba que el resumen sigue los valores actuales sin bloquear el borrador.
const assert = require('node:assert/strict');
const script = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const inputs = {
  id_codigo: { value: 'FI-001' },
  id_responsable_nombre: { value: '' },
  id_contacto_telefono: { value: '123456' },
};
const clase = () => ({ hidden: false, toggle(_, value) { this.hidden = value; } });
const filas = Object.keys(inputs).map(id => ({ dataset: { requisitoCampo: id }, classList: clase() }));
const completo = { classList: clase() };
const enviar = { disabled: false };
Object.values(inputs).forEach(campo => { campo.addEventListener = (_, callback) => { campo.actualizar = callback; }; });
global.document = {
  querySelectorAll: () => filas,
  getElementById: id => inputs[id],
  querySelector: selector => selector.startsWith('button') ? enviar : completo,
};
eval(script);
assert.equal(filas[0].classList.hidden, true, 'El código cargado no está pendiente');
assert.equal(filas[1].classList.hidden, false, 'El responsable vacío debe mostrarse');
assert.equal(completo.classList.hidden, true, 'Un campo vacío impide anunciar datos completos');
assert.equal(enviar.disabled, true, 'Un requisito vacío deshabilita Enviar');
inputs.id_responsable_nombre.value = 'Responsable FI';
inputs.id_responsable_nombre.actualizar();
assert.equal(filas[1].classList.hidden, true);
assert.equal(completo.classList.hidden, false);
assert.equal(enviar.disabled, false, 'Completar todos los requisitos habilita Enviar');
inputs.id_responsable_nombre.value = '   ';
inputs.id_responsable_nombre.actualizar();
assert.equal(filas[1].classList.hidden, false, 'Espacios no completan un requisito');
assert.equal(completo.classList.hidden, true);
assert.equal(enviar.disabled, true, 'Vaciar un requisito vuelve a deshabilitar Enviar');
// Sin capacidad de envío el botón no existe, pero el resumen sigue funcionando.
document.querySelector = selector => selector.startsWith('button') ? null : completo;
eval(script);
inputs.id_responsable_nombre.value = 'Responsable FI';
inputs.id_responsable_nombre.actualizar();
assert.equal(completo.classList.hidden, false);
