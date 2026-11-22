/**
 * Índice de secciones de un modal largo (`components/_indice_secciones.html`).
 *
 * El índice se arma en el navegador a partir de las secciones del cuerpo: cada una es un elemento con
 * `data-indice-seccion`, un `id`, `tabindex="-1"` y su título en `data-indice-titulo`. Sin JS el `<nav>` queda
 * oculto y las secciones se apilan, que es lo que ya hay hoy.
 *
 *   <div data-indice-cuerpo class="overflow-y-auto">      <- el que scrollea
 *     <nav data-indice-secciones aria-label="…" hidden>…</nav>
 *     <section id="a" tabindex="-1" data-indice-seccion data-indice-titulo="Datos">…</section>
 *
 * - Cada entrada es un `<button>`: Tab llega, Enter/Espacio llevan a la sección y le dan el foco.
 * - La sección que se está leyendo queda con `aria-current="true"` (sigue al scroll).
 * - Una sección oculta (`hidden`, p. ej. por una condición del formulario) sale del índice; con menos de dos
 *   visibles el índice entero se oculta.
 * - Una sección con un campo en error (`aria-invalid="true"` o un `[data-error]` visible con texto) marca su
 *   entrada con «Revisar», porque el color solo no alcanza.
 * - Los títulos se escriben con `textContent`, nunca con `innerHTML`.
 *
 * `NodoIndiceSecciones.montar(nav)` lo monta a mano; al cargar la página se montan todos los
 * `[data-indice-secciones]`. Sin `nav` o sin cuerpo devuelve `null`.
 */
(function (global) {
  'use strict';

  var ACTIVA = ['bg-brand-soft', 'text-fg-brand', 'font-bold'];
  var INACTIVA = ['text-body', 'font-medium', 'hover:bg-secondary'];
  var BOTON = 'inline-flex items-center justify-between gap-2 rounded-lg px-3 py-2 min-h-11 lg:min-h-0 text-sm text-left transition focus-visible:ring-2 focus-visible:ring-brand lg:w-full';
  var MARGEN = 24;

  function conError(seccion) {
    if (seccion.querySelector('[aria-invalid="true"]')) { return true; }
    var avisos = seccion.querySelectorAll('[data-error]');
    for (var i = 0; i < avisos.length; i++) {
      var aviso = avisos[i];
      var visible = !aviso.classList.contains('hidden') && !aviso.hasAttribute('hidden');
      if (visible && (aviso.textContent || '').trim()) { return true; }
    }
    return false;
  }

  function montar(nav) {
    if (!nav) { return null; }
    var cuerpo = nav.closest('[data-indice-cuerpo]');
    var lista = nav.querySelector('[data-indice-lista]');
    if (!cuerpo || !lista) { return null; }
    var secciones = Array.prototype.slice.call(cuerpo.querySelectorAll('[data-indice-seccion]'));
    if (!secciones.length) { return null; }
    if (nav.getAttribute('data-indice-montado')) { return null; }
    nav.setAttribute('data-indice-montado', 'true');

    var entradas = secciones.map(function (seccion) {
      var item = document.createElement('li');
      item.className = 'lg:w-full';
      var boton = document.createElement('button');
      boton.type = 'button';
      boton.className = BOTON + ' ' + INACTIVA.join(' ');
      var texto = document.createElement('span');
      texto.textContent = seccion.getAttribute('data-indice-titulo') || '';
      var aviso = document.createElement('span');
      aviso.className = 'badge badge-danger';
      aviso.textContent = 'Revisar';
      aviso.hidden = true;
      boton.appendChild(texto);
      boton.appendChild(aviso);
      item.appendChild(boton);
      lista.appendChild(item);
      boton.addEventListener('click', function () { ir(seccion); });
      return { seccion: seccion, item: item, boton: boton, aviso: aviso };
    });

    // Tras un clic, la entrada elegida queda activa mientras dura el desplazamiento (secciones cortas: no se pisa).
    var fijada = false;

    function ir(seccion) {
      var quieto = global.matchMedia && global.matchMedia('(prefers-reduced-motion: reduce)').matches;
      seccion.scrollIntoView({ block: 'start', behavior: quieto ? 'auto' : 'smooth' });
      seccion.focus({ preventScroll: true });
      fijada = true;
      marcar(seccion);
    }

    function marcar(actual) {
      entradas.forEach(function (entrada) {
        var es = entrada.seccion === actual;
        if (es) { entrada.boton.setAttribute('aria-current', 'true'); } else { entrada.boton.removeAttribute('aria-current'); }
        ACTIVA.forEach(function (clase) { entrada.boton.classList.toggle(clase, es); });
        INACTIVA.forEach(function (clase) { entrada.boton.classList.toggle(clase, !es); });
      });
    }

    function visibles() {
      return entradas.filter(function (entrada) { return !entrada.seccion.hidden; });
    }

    function seguirScroll() {
      if (fijada) { return; }
      var lectura = visibles();
      if (!lectura.length) { return; }
      // Modal cerrado (sin alto) o cuerpo arriba de todo: se lee la primera; con todo en top 0 no se puede medir.
      if (!cuerpo.clientHeight || cuerpo.scrollTop <= 0) { marcar(lectura[0].seccion); return; }
      var tope = cuerpo.getBoundingClientRect().top;
      var elegida = lectura[0];
      lectura.forEach(function (entrada) {
        if (entrada.seccion.getBoundingClientRect().top - tope <= MARGEN) { elegida = entrada; }
      });
      if (cuerpo.scrollTop + cuerpo.clientHeight >= cuerpo.scrollHeight - 2 && cuerpo.scrollTop > 0) {
        elegida = lectura[lectura.length - 1];
      }
      marcar(elegida.seccion);
    }

    function sincronizar() {
      var activas = visibles();
      entradas.forEach(function (entrada) {
        entrada.item.hidden = entrada.seccion.hidden;
        entrada.aviso.hidden = entrada.seccion.hidden || !conError(entrada.seccion);
      });
      nav.hidden = activas.length < 2;
      seguirScroll();
    }

    cuerpo.addEventListener('scroll', seguirScroll);
    // La persona retoma el scroll: el seguimiento vuelve a mandar.
    ['wheel', 'touchmove', 'keydown', 'mousedown'].forEach(function (tipo) {
      cuerpo.addEventListener(tipo, function () { fijada = false; });
    });
    // Un error de validación (u otro código) lleva el foco a un control de otra sección: la elegida ya no manda.
    cuerpo.addEventListener('focusin', function (evento) {
      var destino = evento && evento.target;
      if (destino && destino.hasAttribute && !destino.hasAttribute('data-indice-seccion')) { fijada = false; }
    });
    if (global.MutationObserver) {
      var observador = new global.MutationObserver(sincronizar);
      secciones.forEach(function (seccion) {
        observador.observe(seccion, {
          attributes: true,
          attributeFilter: ['hidden', 'class', 'aria-invalid'],
          subtree: true,
          childList: true,
          characterData: true,
        });
      });
    }
    sincronizar();
    return { sincronizar: sincronizar, ir: ir };
  }

  function montarTodos() {
    Array.prototype.forEach.call(document.querySelectorAll('[data-indice-secciones]'), function (nav) { montar(nav); });
  }

  global.NodoIndiceSecciones = { montar: montar };
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', montarTodos);
  } else {
    montarTodos();
  }
}(window));
