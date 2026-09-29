/*
 * becas-modal.js — comportamiento accesible común de los modales de Becas.
 *
 * Qué hace mientras el modal está abierto:
 *   - guarda el elemento que tenía el foco y lo devuelve al cerrar;
 *   - mueve el foco a `[autofocus]`, si no al primer campo, si no al primer control,
 *     y si no hay ninguno al propio panel;
 *   - atrapa Tab / Shift+Tab dentro del panel (`[role="dialog"]`);
 *   - Escape pide el cierre;
 *   - bloquea el scroll del fondo (el viewport scrollea en <html>, ver base.html).
 *
 * Dos formas de usarlo:
 *   1. Alpine: `x-becas-modal="modalCrear"` en el overlay que lleva `x-show`. Escape
 *      hace `modalCrear = false`. La directiva se registra en `alpine:init`: este
 *      archivo es un <script> clásico al final del <body> y Alpine se carga con
 *      `defer`, así que corre antes y alcanza el evento.
 *   2. Vanilla: `window.becasModal.bind(overlay, {onClose})`. Observa la visibilidad
 *      del overlay (clase `hidden`, `style.display`, atributo `hidden`) y se activa
 *      solo; Escape y los `[data-becas-modal-cerrar]` llaman a `onClose` (sin
 *      `onClose`, le ponen la clase `hidden`). Devuelve {abrir, cerrar, destruir}.
 *
 * Sin dependencias: no hay @alpinejs/focus en el repo (decisión DP-3).
 */
(function () {
  'use strict';

  var FOCUSABLES = [
    'a[href]',
    'area[href]',
    'button:not([disabled])',
    'input:not([disabled]):not([type="hidden"])',
    'select:not([disabled])',
    'textarea:not([disabled])',
    'iframe',
    '[contenteditable="true"]',
    '[tabindex]:not([tabindex="-1"])'
  ].join(',');
  var CAMPOS = 'input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled])';

  var pila = [];          // modales abiertos, el último es el de arriba
  var scrollPrevio = null;

  function visible(el) {
    if (typeof el.getClientRects !== 'function') return true;
    return !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
  }

  function enfocables(panel, selector) {
    return Array.prototype.filter.call(panel.querySelectorAll(selector || FOCUSABLES), visible);
  }

  function enfocar(el) {
    if (!el || typeof el.focus !== 'function') return;
    try { el.focus({ preventScroll: true }); } catch (e) { el.focus(); }
  }

  function panelDe(overlay) {
    if (overlay.getAttribute && overlay.getAttribute('role') === 'dialog') return overlay;
    return overlay.querySelector('[role="dialog"]') || overlay;
  }

  function bloquearScroll() {
    if (scrollPrevio) return;
    var html = document.documentElement;
    scrollPrevio = { html: html.style.overflow, body: document.body.style.overflow };
    html.style.overflow = 'hidden';
    document.body.style.overflow = 'hidden';
  }

  function liberarScroll() {
    if (!scrollPrevio || pila.length) return;
    document.documentElement.style.overflow = scrollPrevio.html;
    document.body.style.overflow = scrollPrevio.body;
    scrollPrevio = null;
  }

  function focoInicial(ctrl) {
    if (!ctrl.activo) return;
    var panel = ctrl.panel;
    var destino = enfocables(panel, '[autofocus]')[0] || enfocables(panel, CAMPOS)[0] || enfocables(panel)[0];
    if (!destino) {
      if (!panel.hasAttribute('tabindex')) panel.setAttribute('tabindex', '-1');
      destino = panel;
    }
    enfocar(destino);
  }

  function activar(ctrl) {
    if (ctrl.activo) return;
    ctrl.activo = true;
    ctrl.previo = document.activeElement;
    pila.push(ctrl);
    bloquearScroll();
    // x-show y las transiciones terminan de mostrar el overlay después de este
    // tick: el foco se mueve cuando el panel ya es visible.
    var diferir = window.requestAnimationFrame || function (fn) { return setTimeout(fn, 0); };
    diferir(function () { focoInicial(ctrl); });
  }

  function desactivar(ctrl) {
    if (!ctrl.activo) return;
    ctrl.activo = false;
    var i = pila.indexOf(ctrl);
    if (i !== -1) pila.splice(i, 1);
    liberarScroll();
    var previo = ctrl.previo;
    ctrl.previo = null;
    if (previo && previo !== document.body && previo.isConnected !== false) enfocar(previo);
  }

  function atraparTab(ctrl, evento) {
    var panel = ctrl.panel;
    var lista = enfocables(panel);
    var actual = document.activeElement;
    var adentro = panel.contains(actual);
    if (!lista.length) {
      evento.preventDefault();
      enfocar(panel);
      return;
    }
    var primero = lista[0];
    var ultimo = lista[lista.length - 1];
    if (evento.shiftKey) {
      if (!adentro || actual === primero || actual === panel) {
        evento.preventDefault();
        enfocar(ultimo);
      }
    } else if (!adentro || actual === ultimo) {
      evento.preventDefault();
      enfocar(primero);
    }
  }

  // Una confirmación (SweetAlert2, ModernModal) abierta encima del modal maneja su
  // propio teclado: si el foco está en otro diálogo, no se lo disputamos.
  function focoEnOtroDialogo(ctrl) {
    var actual = document.activeElement;
    if (!actual || !actual.closest || ctrl.panel.contains(actual)) return false;
    return !!actual.closest('[role="dialog"], [role="alertdialog"], [aria-modal="true"]');
  }

  document.addEventListener('keydown', function (evento) {
    var ctrl = pila[pila.length - 1];
    if (!ctrl || focoEnOtroDialogo(ctrl)) return;
    if (evento.key === 'Escape' || evento.key === 'Esc') {
      if (evento.defaultPrevented) return;
      evento.preventDefault();
      ctrl.pedirCierre();
    } else if (evento.key === 'Tab') {
      atraparTab(ctrl, evento);
    }
  }, true);

  function crear(overlay, pedirCierre) {
    return { overlay: overlay, panel: panelDe(overlay), pedirCierre: pedirCierre, activo: false, previo: null };
  }

  // --- API vanilla -------------------------------------------------------------

  function overlayVisible(overlay) {
    if (overlay.hidden) return false;
    if (overlay.classList && overlay.classList.contains('hidden')) return false;
    return !(overlay.style && overlay.style.display === 'none');
  }

  function bind(overlay, opciones) {
    opciones = opciones || {};
    var ctrl = crear(overlay, function () {
      if (typeof opciones.onClose === 'function') opciones.onClose();
      else overlay.classList.add('hidden');
      if (!overlayVisible(overlay)) desactivar(ctrl);
    });
    function sincronizar() {
      if (overlayVisible(overlay)) activar(ctrl); else desactivar(ctrl);
    }
    function alClic(evento) {
      var boton = evento.target && evento.target.closest ? evento.target.closest('[data-becas-modal-cerrar]') : null;
      if (boton && overlay.contains(boton)) ctrl.pedirCierre();
    }
    overlay.addEventListener('click', alClic);
    var observador = null;
    if (typeof MutationObserver === 'function') {
      observador = new MutationObserver(sincronizar);
      observador.observe(overlay, { attributes: true, attributeFilter: ['class', 'style', 'hidden'] });
    }
    sincronizar();
    return {
      abrir: function () { activar(ctrl); },
      cerrar: function () { desactivar(ctrl); },
      destruir: function () {
        if (observador) observador.disconnect();
        overlay.removeEventListener('click', alClic);
        desactivar(ctrl);
      }
    };
  }

  window.becasModal = { bind: bind };

  // --- Directiva Alpine ----------------------------------------------------------

  function registrar(Alpine) {
    if (Alpine.__becasModal) return;
    Alpine.__becasModal = true;
    Alpine.directive('becas-modal', function (el, datos, utiles) {
      var leer = utiles.evaluateLater(datos.expression);
      var ctrl = crear(el, function () { utiles.evaluate(datos.expression + ' = false'); });
      utiles.effect(function () {
        leer(function (abierto) {
          if (abierto) activar(ctrl); else desactivar(ctrl);
        });
      });
      utiles.cleanup(function () { desactivar(ctrl); });
    });
  }

  if (window.Alpine && typeof window.Alpine.directive === 'function') registrar(window.Alpine);
  document.addEventListener('alpine:init', function () { registrar(window.Alpine); });
})();
