/**
 * Condiciones del formulario del tipo de dispositivo (P17) en el navegador.
 *
 * Lo comparten las cuatro pantallas que lo dibujan: «Crear dispositivo» (P3), el último paso del
 * asistente de ingreso (P6) y los modales de egreso de P4 y P7. Las condiciones las evalúa
 * `NodoCondiciones` (cargar `nodo-condiciones.js` antes), el mismo motor que el servidor, que las
 * vuelve a evaluar al guardar: lo oculto se deshabilita para que no viaje.
 *
 *   var formulario = NodoFormularioTipo.montar(contenedor, {
 *     itemsId: 'formulario-tipo-items',   // id del json_script con los ítems planos (por defecto ese)
 *     archivoGuardado: true,              // un ARCHIVO ya guardado (`data-valor`) cuenta como respondido
 *     alAplicar: function (info) {},      // info.faltantes: textos de los obligatorios visibles sin responder
 *   });
 *   formulario.aplicar();                 // volver a evaluar (p. ej. si cambió el contenido del contenedor)
 *
 * Los oyentes `change` e `input` quedan en el contenedor, así que sirven aunque su contenido se
 * reemplace. Sin contenedor devuelve `null`.
 */
(function (global) {
  'use strict';

  function leerItems(contenedor, itemsId) {
    var datos = contenedor.querySelector('#' + itemsId) || document.getElementById(itemsId);
    if (!datos) { return []; }
    try { return JSON.parse(datos.textContent) || []; } catch (error) { return []; }
  }

  function valorDe(caja, archivoGuardado) {
    var marcas = caja.querySelectorAll('input[type="checkbox"]');
    if (marcas.length) {
      var marcadas = Array.prototype.filter.call(marcas, function (marca) { return marca.checked; })
        .map(function (marca) { return marca.value; });
      return marcadas.length ? marcadas : null;
    }
    var control = caja.querySelector('select') || caja.querySelector('textarea, input:not([type="hidden"])');
    if (!control) { return null; }
    if (control.multiple) {
      var elegidos = Array.prototype.filter.call(control.options, function (opcion) { return opcion.selected; })
        .map(function (opcion) { return opcion.value; });
      return elegidos.length ? elegidos : null;
    }
    if (control.type === 'file') {
      if (control.files && control.files.length) { return control.files[0].name; }
      return archivoGuardado ? (caja.dataset.valor || null) : null;
    }
    return control.value.trim() ? control.value : null;
  }

  function montar(contenedor, opciones) {
    if (!contenedor) { return null; }
    var config = opciones || {};
    var itemsId = config.itemsId || 'formulario-tipo-items';

    function aplicar() {
      var items = leerItems(contenedor, itemsId);
      var cajas = {};
      var respuestas = {};
      items.forEach(function (item) {
        cajas[item.clave] = contenedor.querySelector('[data-item="' + item.clave + '"]');
        if (item.tipo !== 'campo' || !cajas[item.clave]) { return; }
        var actual = valorDe(cajas[item.clave], config.archivoGuardado);
        if (actual !== null) { respuestas[item.clave] = actual; }
      });
      var ocultos = global.NodoCondiciones ? global.NodoCondiciones.aplicar(items, respuestas).ocultos : new Set();
      var faltantes = [];
      items.forEach(function (item) {
        var caja = cajas[item.clave];
        if (!caja) { return; }
        var oculto = ocultos.has(item.clave);
        caja.hidden = oculto;
        caja.querySelectorAll('select, textarea, input').forEach(function (control) { control.disabled = oculto; });
        if (!oculto && caja.hasAttribute('data-obligatorio') && !Object.prototype.hasOwnProperty.call(respuestas, item.clave)) {
          faltantes.push(caja.dataset.texto);
        }
      });
      if (config.alAplicar) { config.alAplicar({ faltantes: faltantes }); }
    }

    contenedor.addEventListener('change', aplicar);
    contenedor.addEventListener('input', aplicar);
    aplicar();
    return { aplicar: aplicar };
  }

  global.NodoFormularioTipo = { montar: montar };
}(window));
