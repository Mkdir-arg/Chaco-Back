/**
 * Condiciones en vivo del formulario público (Cambio 58, task 345).
 *
 * Lee los ítems del formulario de `#formulario-items` (clave, tipo, padre,
 * condición) y, cada vez que la persona responde, oculta o muestra lo que
 * corresponda con `NodoCondiciones` —el mismo motor que corre en el servidor—.
 * Un campo oculto se deshabilita para que no viaje en el POST; el servidor lo
 * vuelve a evaluar igual, así que esto es comodidad, no seguridad.
 *
 * Sin JS (o si algo falla) el formulario se muestra completo y se envía: el
 * servidor decide qué se exige y qué se guarda.
 */
(function () {
  'use strict';

  function init() {
    var form = document.querySelector('form[data-formulario-dinamico]');
    var datos = document.getElementById('formulario-items');
    if (!form || !datos || !window.NodoCondiciones) { return; }

    var items;
    try { items = JSON.parse(datos.textContent); } catch (e) { return; }
    if (!items || !items.length) { return; }

    // Sin ninguna condición no hay nada que recalcular.
    var hayCondiciones = items.some(function (i) {
      return i.condicion && (i.condicion.reglas || []).length;
    });
    if (!hayCondiciones) { return; }

    var contenedores = {};
    items.forEach(function (item) {
      contenedores[item.clave] = form.querySelector('[data-item="' + item.clave + '"]');
    });

    // Valor actual de cada campo, leído de sus controles.
    function respuestas() {
      var out = {};
      items.forEach(function (item) {
        var caja = contenedores[item.clave];
        if (!caja || item.tipo !== 'campo') { return; }
        var multiples = caja.querySelectorAll('input[type="checkbox"]');
        if (multiples.length) {
          var marcados = [];
          multiples.forEach(function (c) { if (c.checked) { marcados.push(c.value); } });
          if (marcados.length) { out[item.clave] = marcados; }
          return;
        }
        // El <select> va primero: el buscador con píldoras (nodo-buscador.js)
        // monta su input de búsqueda antes del select nativo y lo vacía al
        // elegir; leer el primer control diría «vacío» con una opción elegida.
        var control = caja.querySelector('select') ||
          caja.querySelector('textarea, input:not([type="hidden"]):not(.nodo-buscador__input)');
        if (!control) {
          // Dato fijo del paso 1 (identidad ya validada): se muestra como texto.
          // El dato fijo viaja crudo en data-valor (lo que se ve está formateado).
          if (caja.dataset.valor) { out[item.clave] = caja.dataset.valor; }
          return;
        }
        if (control.multiple) {
          var elegidos = Array.prototype.filter.call(control.options, function (o) { return o.selected; })
            .map(function (o) { return o.value; });
          if (elegidos.length) { out[item.clave] = elegidos; }
          return;
        }
        if (control.type === 'file') {
          if (control.files && control.files.length) { out[item.clave] = control.files[0].name; }
          return;
        }
        if (control.value) { out[item.clave] = control.value; }
      });
      return out;
    }

    function aplicar() {
      var resultado = window.NodoCondiciones.aplicar(items, respuestas());
      items.forEach(function (item) {
        var caja = contenedores[item.clave];
        if (!caja) { return; }
        var oculto = resultado.ocultos.has(item.clave);
        caja.hidden = oculto;
        // Un control deshabilitado no viaja en el POST: lo oculto no se guarda.
        caja.querySelectorAll('select, textarea, input').forEach(function (control) {
          control.disabled = oculto;
        });
      });
    }

    form.addEventListener('change', aplicar);
    form.addEventListener('input', aplicar);
    aplicar();
  }

  document.addEventListener('DOMContentLoaded', init);
})();
