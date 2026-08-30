/**
 * Motor de condiciones del formulario — espejo en JS de
 * `programas/services/condiciones.py` (Cambio 58, RN-6 y RN-7).
 *
 * Misma semántica y mismos nombres de operador: lo que decide el navegador
 * mientras la persona completa lo vuelve a decidir el servidor al guardar.
 * Una fuente vacía no cumple nada salvo `vacio` / `no_adjuntado`; un ítem
 * oculto cuenta como vacío para los que dependen de él; el hijo de un grupo
 * oculto está oculto.
 */
(function (global) {
  'use strict';

  function estaVacio(valor) {
    if (valor === null || valor === undefined) { return true; }
    if (typeof valor === 'string') { return valor.trim() === ''; }
    if (Array.isArray(valor)) { return valor.length === 0; }
    if (typeof valor === 'object') { return Object.keys(valor).length === 0; }
    return false;
  }

  function aFecha(valor) {
    if (valor instanceof Date) { return isNaN(valor.getTime()) ? null : valor; }
    if (typeof valor !== 'string') { return null; }
    var t = valor.trim();
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(t);
    if (m) { return new Date(+m[1], +m[2] - 1, +m[3]); }
    m = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(t);
    if (m) { return new Date(+m[3], +m[2] - 1, +m[1]); }
    return null;
  }

  function aNumero(valor) {
    if (typeof valor === 'boolean') { return null; }
    if (typeof valor === 'number') { return isNaN(valor) ? null : valor; }
    if (valor === null || valor === undefined) { return null; }
    var t = String(valor).trim().replace(',', '.');
    if (t === '') { return null; }
    var n = Number(t);
    return isNaN(n) ? null : n;
  }

  function aLista(valor) {
    if (valor === null || valor === undefined) { return []; }
    if (Array.isArray(valor)) { return valor.map(String); }
    return [String(valor)];
  }

  function edadEnAnios(fechaNacimiento, hoy) {
    var nac = aFecha(fechaNacimiento);
    if (!nac) { return null; }
    hoy = hoy || new Date();
    var edad = hoy.getFullYear() - nac.getFullYear();
    var antes = (hoy.getMonth() < nac.getMonth()) || (hoy.getMonth() === nac.getMonth() && hoy.getDate() < nac.getDate());
    return edad - (antes ? 1 : 0);
  }

  function evaluarRegla(regla, valor, hoy) {
    var op = regla.op;
    var esperado = regla.valor;
    var vacio = estaVacio(valor);

    if (op === 'vacio' || op === 'no_adjuntado') { return vacio; }
    if (vacio) { return false; }
    if (op === 'completo' || op === 'adjuntado') { return true; }

    if (op === 'es') { return String(valor) === String(esperado); }
    if (op === 'no_es') { return String(valor) !== String(esperado); }
    if (op === 'es_alguno') { return aLista(esperado).indexOf(String(valor)) !== -1; }
    if (op === 'incluye') { return aLista(valor).indexOf(String(esperado)) !== -1; }
    if (op === 'no_incluye') { return aLista(valor).indexOf(String(esperado)) === -1; }
    if (op === 'incluye_alguno') {
      var propios = aLista(valor);
      return aLista(esperado).some(function (v) { return propios.indexOf(v) !== -1; });
    }

    if (['eq', 'ne', 'lt', 'gt', 'le', 'ge'].indexOf(op) !== -1) {
      var a = aNumero(valor), b = aNumero(esperado);
      if (a === null || b === null) { return false; }
      return { eq: a === b, ne: a !== b, lt: a < b, gt: a > b, le: a <= b, ge: a >= b }[op];
    }

    if (op === 'edad_menor' || op === 'edad_mayor' || op === 'edad_igual') {
      var edad = edadEnAnios(valor, hoy), limite = aNumero(esperado);
      if (edad === null || limite === null) { return false; }
      return { edad_menor: edad < limite, edad_mayor: edad > limite, edad_igual: edad === limite }[op];
    }
    if (op === 'edad_entre') {
      var e = edadEnAnios(valor, hoy);
      var rango = aLista(esperado).map(aNumero);
      if (e === null || rango.length !== 2 || rango.indexOf(null) !== -1) { return false; }
      return Math.min(rango[0], rango[1]) <= e && e <= Math.max(rango[0], rango[1]);
    }
    if (op === 'anterior' || op === 'posterior') {
      var f = aFecha(valor), l = aFecha(esperado);
      if (!f || !l) { return false; }
      return op === 'anterior' ? f < l : f > l;
    }
    return false;
  }

  function evaluar(condicion, respuestas, hoy) {
    if (!condicion) { return true; }
    var reglas = condicion.reglas || [];
    if (!reglas.length) { return true; }
    var modo = condicion.modo || 'todas';
    var resultados = reglas.map(function (r) { return evaluarRegla(r, respuestas[r.fuente], hoy); });
    return modo === 'todas' ? resultados.every(Boolean) : resultados.some(Boolean);
  }

  /**
   * items: [{clave, tipo, padre, condicion}] en orden; respuestas: {clave: valor}.
   * Devuelve {visibles: Set, ocultos: Set, efectivas: {clave: valor}}.
   */
  function aplicar(items, respuestas, hoy) {
    var visibles = new Set(), ocultos = new Set(), efectivas = {};
    items.forEach(function (item) {
      var padre = item.padre;
      if (padre && ocultos.has(padre)) { ocultos.add(item.clave); return; }
      if (evaluar(item.condicion, efectivas, hoy)) {
        visibles.add(item.clave);
        if (item.tipo !== 'grupo' && Object.prototype.hasOwnProperty.call(respuestas, item.clave)) {
          efectivas[item.clave] = respuestas[item.clave];
        }
      } else {
        ocultos.add(item.clave);
      }
    });
    return { visibles: visibles, ocultos: ocultos, efectivas: efectivas };
  }

  global.NodoCondiciones = {
    estaVacio: estaVacio,
    edadEnAnios: edadEnAnios,
    evaluarRegla: evaluarRegla,
    evaluar: evaluar,
    aplicar: aplicar
  };
})(window);
