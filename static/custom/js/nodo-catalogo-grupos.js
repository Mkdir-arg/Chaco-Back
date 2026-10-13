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
 *
 * Confirmación del autoguardado (DA-2): sin toast de éxito. El estado
 * «Guardando…» / «Orden guardado» vive en `#catalogo-guardado` (indicador de
 * la página) y en la región aria-live; los errores sí salen por toast.
 *
 * Listas planas (Cambio 264): el mismo archivo ordena los requisitos propios
 * del programa, del segmento y del subsegmento (`[data-sortable-lista]`, ver
 * el bloque del final). Una sola lista por tbody, sin grupos.
 *
 * Si el guardado falla (4xx/5xx o red), las dos variantes vuelven el DOM al
 * último orden que vino del servidor: la pantalla no muestra un orden que no
 * se guardó. El aviso de error queda igual y el foco vuelve a la manija.
 */
(function () {
  'use strict';

  function getCookie(name) {
    var m = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
    return m ? decodeURIComponent(m.pop()) : '';
  }

  // Solo los errores van por toast (DA-2): un autoguardado exitoso no debe
  // apilar un aviso por cada soltada; su confirmación es el indicador de la página.
  function aviso(mensaje, tipo) {
    if (typeof window.toast === 'function') { window.toast(tipo || 'success', mensaje); }
  }

  function indicar(texto) {
    var el = document.getElementById('catalogo-guardado');
    if (el) { el.textContent = texto; }
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

  // Foto del orden tal como lo renderizó el servidor: por cada contenedor, sus
  // hijos en orden (filas, tarjetas y el placeholder de grupo vacío, que el
  // teclado saca al entrar). `restaurar` los vuelve a colgar en ese orden con
  // los mismos nodos, sin re-render: appendChild mueve el nodo de donde esté.
  function fotoDe(contenedores) {
    return contenedores.map(function (padre) {
      return { padre: padre, hijos: Array.prototype.slice.call(padre.children) };
    });
  }

  function restaurar(foto) {
    foto.forEach(function (f) {
      f.hijos.forEach(function (hijo) { f.padre.appendChild(hijo); });
    });
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
    // Orden confirmado: `init()` corre al cargar y tras cada guardado exitoso.
    var fotoGrupos = fotoDe([root].concat(Array.prototype.slice.call(
      root.querySelectorAll('tbody[data-sortable-preguntas]'))));

    function revertir(focoSel) {
      restaurar(fotoGrupos);
      if (focoSel) {
        var grip = document.querySelector(focoSel);
        if (grip) { grip.focus(); }
      }
    }

    function guardar() {
      // Un guardado demorado puede dispararse después de que otro flujo
      // reemplazó el parcial: este root ya no está en el documento y su orden
      // es viejo — no hay nada que guardar.
      if (!root.isConnected) { return; }
      var focoSel = selectorDelFoco();
      root.classList.add('is-saving');
      indicar('Guardando…');
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
          indicar('Orden guardado');
          anunciar('Orden guardado.');
          init();
          if (focoSel) {
            var grip = document.querySelector(focoSel);
            if (grip) { grip.focus(); }
          }
        } else {
          root.classList.remove('is-saving');
          revertir(focoSel);
          indicar('No se guardó el orden');
          aviso(data.error || 'No se pudo guardar el orden. Recargá la página.', 'error');
        }
      }).catch(function () {
        root.classList.remove('is-saving');
        revertir(focoSel);
        indicar('No se guardó el orden');
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

  // ------------------------------------------------------------------
  // Listas planas (Cambio 264): los requisitos propios del programa, del
  // segmento y del subsegmento. Mismo contrato que el catálogo agrupado:
  // `tbody[data-sortable-lista]` con `data-url-reordenar` y
  // `data-puede-ordenar`, filas `tr[data-item-id]` y manija `.lista-grip`.
  // Se manda la lista entera `{ids: [...]}` y el servidor devuelve
  // `{ok, target, html}` con el panel ya renderizado. Los heredados no van en
  // la lista: no tienen manija ni fila ordenable.
  // ------------------------------------------------------------------
  var instanciasLista = [];

  function filasDe(lista) {
    return Array.prototype.filter.call(lista.children, function (el) {
      return el.matches('tr[data-item-id]');
    });
  }

  function enlazarLista(lista) {
    var url = lista.getAttribute('data-url-reordenar');
    var indicador = document.getElementById(lista.getAttribute('data-indicador') || '');
    var sortable = null;
    // Orden confirmado por el servidor (al enlazar) y el último ítem movido, con
    // mouse o con teclado: si el guardado falla se vuelve a esa foto y el foco
    // a la manija de ese ítem.
    var fotoLista = fotoDe([lista]);
    var movidoId = null;

    function indicarLista(texto) {
      if (indicador) { indicador.textContent = texto; }
    }

    function revertirLista() {
      restaurar(fotoLista);
      var tr = movidoId ? lista.querySelector('tr[data-item-id="' + movidoId + '"]') : null;
      var grip = tr ? tr.querySelector('.lista-grip') : null;
      if (grip) { grip.focus(); }
    }

    function guardarLista() {
      // Mismo resguardo que el catálogo: si otro flujo ya reemplazó el panel,
      // este orden es viejo y no se manda.
      if (!lista.isConnected) { return; }
      var foco = document.activeElement;
      var filaFoco = foco && foco.closest && lista.contains(foco) ? foco.closest('tr[data-item-id]') : null;
      var focoId = filaFoco ? filaFoco.getAttribute('data-item-id') : null;
      if (sortable) { sortable.option('disabled', true); }
      indicarLista('Guardando…');
      fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
          ids: filasDe(lista).map(function (tr) { return parseInt(tr.getAttribute('data-item-id'), 10); })
        })
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
          indicarLista('Orden guardado');
          anunciar('Orden guardado.');
          initListas();
          if (focoId) {
            var grip = document.querySelector('[data-sortable-lista] tr[data-item-id="' + focoId + '"] .lista-grip');
            if (grip) { grip.focus(); }
          }
        } else {
          if (sortable) { sortable.option('disabled', false); }
          revertirLista();
          indicarLista('No se guardó el orden');
          aviso(data.error || 'No se pudo guardar el orden. Recargá la página.', 'error');
        }
      }).catch(function () {
        if (sortable) { sortable.option('disabled', false); }
        revertirLista();
        indicarLista('No se guardó el orden');
        aviso('No se pudo guardar el orden. Revisá la conexión.', 'error');
      });
    }

    var timerLista = null;
    function guardarListaConDemora() {
      window.clearTimeout(timerLista);
      timerLista = window.setTimeout(guardarLista, 700);
    }

    if (!lista.dataset.tecladoEnlazado) {
      lista.dataset.tecladoEnlazado = '1';
      lista.addEventListener('keydown', function (e) {
        if (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') { return; }
        var grip = e.target.closest ? e.target.closest('.lista-grip') : null;
        if (!grip) { return; }
        e.preventDefault();
        var tr = grip.closest('tr[data-item-id]');
        var filas = filasDe(lista);
        var destino = filas[filas.indexOf(tr) + (e.key === 'ArrowUp' ? -1 : 1)];
        if (!tr || !destino) { return; }
        lista.insertBefore(tr, e.key === 'ArrowUp' ? destino : destino.nextSibling);
        movidoId = tr.getAttribute('data-item-id');
        grip.focus();
        filas = filasDe(lista);
        var celda = tr.querySelector('.js-lista-texto');
        var texto = celda ? celda.textContent.trim().split('\n')[0].slice(0, 80) : 'Requisito';
        anunciar(texto + ': posición ' + (filas.indexOf(tr) + 1) + ' de ' + filas.length + '.');
        guardarListaConDemora();
      });
    }

    sortable = new window.Sortable(lista, {
      animation: 150,
      handle: '.lista-grip',
      draggable: 'tr[data-item-id]',
      ghostClass: 'sortable-ghost',
      chosenClass: 'sortable-chosen',
      onEnd: function (evt) {
        if (evt.oldIndex === evt.newIndex) { return; }
        movidoId = evt.item ? evt.item.getAttribute('data-item-id') : null;
        guardarLista();
      }
    });
    instanciasLista.push(sortable);
  }

  function initListas() {
    instanciasLista.forEach(function (s) { try { s.destroy(); } catch (e) { /* ya desmontado */ } });
    instanciasLista = [];
    if (!window.Sortable) { return; }
    document.querySelectorAll('[data-sortable-lista]').forEach(function (lista) {
      if (lista.getAttribute('data-puede-ordenar') === '1') { enlazarLista(lista); }
    });
  }

  function initTodo() { init(); initListas(); }

  document.addEventListener('DOMContentLoaded', initTodo);
  // Tras guardar una pregunta, un grupo o un requisito por AJAX el parcial se reemplaza.
  window.addEventListener('becas-saved', function () { window.setTimeout(initTodo, 0); });
  window.nodoCatalogoGrupos = { init: init, initListas: initListas };
})();
