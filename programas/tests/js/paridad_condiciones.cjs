// Corre el motor de condiciones del navegador sobre la tabla compartida (#895).
// Uso: node paridad_condiciones.cjs <nodo-condiciones.js> <condiciones_paridad.json>
// Imprime {"<caso>#<n>": ["clave oculta", ...]} por variante; la comparación con
// el servidor la hace programas/tests/test_condiciones_paridad.py.
const fs = require('node:fs');
const path = require('node:path');

const [motor, tablaRuta] = process.argv.slice(2);
// El motor se cuelga de `window` (IIFE del navegador).
globalThis.window = globalThis;
require(path.resolve(motor));

const tabla = JSON.parse(fs.readFileSync(tablaRuta, 'utf8'));
const [anio, mes, dia] = tabla.hoy.split('-').map(Number);
// Fecha fija, en hora local como la arma el navegador: nunca la del runner.
const hoy = new Date(anio, mes - 1, dia);

const salida = {};
tabla.casos.forEach((caso) => {
  caso.variantes.forEach((variante, n) => {
    const resultado = window.NodoCondiciones.aplicar(caso.items, variante.respuestas, hoy);
    salida[`${caso.caso}#${n}`] = {
      visibles: Array.from(resultado.visibles).sort(),
      ocultos: Array.from(resultado.ocultos).sort(),
    };
  });
});
process.stdout.write(JSON.stringify(salida));
