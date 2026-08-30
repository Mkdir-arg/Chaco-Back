/**
 * Catálogo de requisitos generales agrupado (Cambio 58, task 337).
 *
 * Drag & drop con SortableJS (static/vendor/sortablejs): los grupos se
 * reordenan por su manija y las preguntas se mueven dentro de un grupo o a
 * otro. Cada soltada guarda en vivo contra `data-url-reordenar` (JSON) y el
 * servidor devuelve el parcial ya renderizado, que reemplaza `#preguntas-table`
 * y se vuelve a enlazar. Sin el permiso de edición no se inicializa nada.
 */
(function () {
  'use strict';

  function getCookie(name) {
    var m = document.cookie.match('(^|;)\s*' + name + '\s*=\s*([^;]+)');
    return m ? decodeURIComponent(m.pop()) : '';
  }

  function aviso(mensaje, tipo) {
    if (typeof window.toast === 'function') { window.toast(mensaje, tipo || 'success'); }
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
        } else {
          root.classList.remove('is-saving');
          aviso(data.error || 'No se pudo guardar el orden. Recargá la página.', 'error');
        }
      }).catch(function () {
        root.classList.remove('is-saving');
        aviso('No se pudo guardar el orden. Revisá la conexión.', 'error');
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
