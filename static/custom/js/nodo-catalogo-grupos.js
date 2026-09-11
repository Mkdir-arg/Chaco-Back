/**
 * Catálogo de requisitos generales agrupado (Cambio 58, task 337).
 *
 * Drag & drop con SortableJS (static/vendor/sortablejs): los grupos se
 * reordenan por su manija y las preguntas se mueven dentro de un grupo o a
 * otro. Cada soltada guarda en vivo contra `data-url-reordenar` (JSON) y el
 * servidor devuelve el parcial ya renderizado, que reemplaza `#preguntas-table`
 * y se vuelve a enlazar. Sin el permiso de edición no se inicializa nada.
 *
 * Alternativa de teclado (mejora registrada del Cambio 58): las manijas son
 * focusables y las flechas ↑/↓ mueven el grupo o la pregunta (una pregunta
 * cruza al grupo vecino en los bordes). Cada movimiento se anuncia en una
 * región aria-live y se guarda con una pequeña demora para no disparar un
 * POST por cada pulsación; al re-renderizar, el foco vuelve a la manija.
 */
(function () {
  'use strict';

  function getCookie(name) {
    var m = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
    return m ? decodeURIComponent(m.pop()) : '';
  }

  function aviso(mensaje, tipo) {
    if (typeof window.toast === 'function') { window.toast(mensaje, tipo || 'success'); }
  }

  function anunciar(texto) {
    var el = document.getElementById('catalogo-aria-vivo');
    if (!el) {
      el = document.createElement('div');
      el.id = 'catalogo-aria-vivo';
      el.className = 'sr-only';
      el.setAttribute('aria-live', 'polite');
      document.body.appendChild(el);
    }
    el.textContent = texto;
  }

  // La manija con foco, como selector re-localizable tras el re-render.
  function selectorDelFoco() {
    var foco = document.activeElement;
    if (!foco || !foco.classList) { return null; }
    if (foco.classList.contains('pregunta-grip')) {
      var tr = foco.closest('tr[data-pregunta-id]');
      return tr ? 'tr[data-pregunta-id="' + tr.getAttribute('data-pregunta-id') + '"] .pregunta-grip' : null;
    }
    if (foco.classList.contains('grupo-grip')) {
      var card = foco.closest('.grupo-card');
      return card ? '.grupo-card[data-grupo-id="' + card.getAttribute('data-grupo-id') + '"] .grupo-grip' : null;
    }
    return null;
  }

  function recolectar(root) {
    var grupos = [];
    root.querySelectorAll('.grupo-card').forEach(function (card) {
      var ids = [];
      card.querySelectorAll('tbody[data-sortable-preguntas] tr[data-pregunta-id]').forEach(function (tr) {
        ids.push(parseInt(tr.getAttribute('data-pregunta-id'), 10));
      });
      var gid = card.getAttribute('data-grupo-id');
      grupos.push({ id: gid ? parseInt(gid, 10) : null, preguntas: ids });
    });
    return { grupos: grupos };
  }

  var instancias = [];

  function destruir() {
    instancias.forEach(function (s) { try { s.destroy(); } catch (e) { /* ya desmontado */ } });
    instancias = [];
  }

  function init() {
    destruir();
    var root = document.querySelector('[data-sortable-grupos]');
    if (!root || !window.Sortable || root.getAttribute('data-puede-ordenar') !== '1') { return; }
    var url = root.getAttribute('data-url-reordenar');

    function guardar() {
      // Un guardado demorado puede dispararse después de que otro flujo
      // reemplazó el parcial: este root ya no está en el documento y su orden
      // es viejo — no hay nada que guardar.
      if (!root.isConnected) { return; }
      var focoSel = selectorDelFoco();
      root.classList.add('is-saving');
      fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify(recolectar(root))
      }).then(function (resp) {
        return resp.json().catch(function () { return {}; }).then(function (data) {
          return { status: resp.status, data: data };
        });
      }).then(function (r) {
        var data = r.data || {};
        if (r.status >= 200 && r.status < 300 && data.ok && data.target && typeof data.html === 'string') {
          var tgt = document.querySelector(data.target);
          if (tgt) {
            tgt.innerHTML = data.html;
            if (window.Alpine && typeof window.Alpine.initTree === 'function') { window.Alpine.initTree(tgt); }
          }
          aviso(data.message || 'Orden guardado.');
          init();
          if (focoSel) {
            var grip = document.querySelector(focoSel);
            if (grip) { grip.focus(); }
          }
        } else {
          root.classList.remove('is-saving');
          aviso(data.error || 'No se pudo guardar el orden. Recargá la página.', 'error');
        }
      }).catch(function () {
        root.classList.remove('is-saving');
        aviso('No se pudo guardar el orden. Revisá la conexión.', 'error');
      });
    }

    // Teclado: cada pulsación mueve en el DOM y el guardado va con demora
    // para que mantener la flecha apretada no dispare un POST por paso.
    var timerTeclado = null;
    function guardarConDemora() {
      root.classList.add('is-saving');
      window.clearTimeout(timerTeclado);
      timerTeclado = window.setTimeout(guardar, 700);
    }

    function anunciarPregunta(tr) {
      var filas = tr.parentElement.querySelectorAll('tr[data-pregunta-id]');
      var pos = Array.prototype.indexOf.call(filas, tr) + 1;
      var card = tr.closest('.grupo-card');
      var titulo = card && card.querySelector('h2') ? card.querySelector('h2').textContent.trim() : 'el grupo';
      var celda = tr.querySelector('.pregunta-texto');
      var texto = celda ? celda.textContent.trim().split('\n')[0].slice(0, 80) : 'Pregunta';
      anunciar(texto + ': posición ' + pos + ' de ' + filas.length + ' en ' + titulo + '.');
    }

    function moverGrupo(grip, delta) {
      var card = grip.closest('.grupo-card');
      var cards = Array.prototype.slice.call(root.querySelectorAll('.grupo-card'));
      var destino = cards[cards.indexOf(card) + delta];
      if (!card || !destino) { return; }
      root.insertBefore(card, delta < 0 ? destino : destino.nextSibling);
      grip.focus();
      var titulo = card.querySelector('h2') ? card.querySelector('h2').textContent.trim() : 'Grupo';
      anunciar(titulo + ': posición ' + (cards.indexOf(card) + delta + 1) + ' de ' + cards.length + '.');
      guardarConDemora();
    }

    function moverPregunta(grip, delta) {
      var tr = grip.closest('tr[data-pregunta-id]');
      if (!tr) { return; }
      var tbody = tr.parentElement;
      var filas = Array.prototype.filter.call(tbody.children, function (el) {
        return el.matches('tr[data-pregunta-id]');
      });
      var destinoIdx = filas.indexOf(tr) + delta;
      if (destinoIdx >= 0 && destinoIdx < filas.length) {
        tbody.insertBefore(tr, delta < 0 ? filas[destinoIdx] : filas[destinoIdx].nextSibling);
      } else {
        // En el borde: cruza al final del grupo anterior o al principio del siguiente.
        var cards = Array.prototype.slice.call(root.querySelectorAll('.grupo-card'));
        var vecino = cards[cards.indexOf(tr.closest('.grupo-card')) + delta];
        var tbodyVecino = vecino && vecino.querySelector('tbody[data-sortable-preguntas]');
        if (!tbodyVecino) { return; }
        var placeholder = tbodyVecino.querySelector('.sortable-placeholder');
        if (placeholder) { placeholder.remove(); }
        if (delta < 0) { tbodyVecino.appendChild(tr); }
        else { tbodyVecino.insertBefore(tr, tbodyVecino.querySelector('tr[data-pregunta-id]')); }
      }
      grip.focus();
      anunciarPregunta(tr);
      guardarConDemora();
    }

    // Una sola vez por root: `init()` puede volver a correr sobre el mismo
    // nodo (becas-saved sin re-render) y un listener duplicado movería doble.
    if (!root.dataset.tecladoEnlazado) {
      root.dataset.tecladoEnlazado = '1';
      root.addEventListener('keydown', function (e) {
        if (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') { return; }
        var grip = e.target.closest ? e.target.closest('.grupo-grip, .pregunta-grip') : null;
        if (!grip) { return; }
        e.preventDefault();
        var delta = e.key === 'ArrowUp' ? -1 : 1;
        if (grip.classList.contains('grupo-grip')) { moverGrupo(grip, delta); } else { moverPregunta(grip, delta); }
      });
    }

    instancias.push(new window.Sortable(root, {
      animation: 150,
      handle: '.grupo-grip',
      draggable: '.grupo-card',
      ghostClass: 'sortable-ghost',
      chosenClass: 'sortable-chosen',
      onEnd: function (evt) { if (evt.oldIndex !== evt.newIndex) { guardar(); } }
    }));

    root.querySelectorAll('tbody[data-sortable-preguntas]').forEach(function (tbody) {
      instancias.push(new window.Sortable(tbody, {
        group: 'preguntas',
        animation: 150,
        handle: '.pregunta-grip',
        draggable: 'tr[data-pregunta-id]',
        filter: '.sortable-placeholder',
        ghostClass: 'sortable-ghost',
        chosenClass: 'sortable-chosen',
        onEnd: function (evt) { if (evt.from !== evt.to || evt.oldIndex !== evt.newIndex) { guardar(); } }
      }));
    });
  }

  document.addEventListener('DOMContentLoaded', init);
  // Tras guardar una pregunta o un grupo por AJAX el parcial se reemplaza.
  window.addEventListener('becas-saved', function () { window.setTimeout(init, 0); });
  window.nodoCatalogoGrupos = { init: init };
})();
