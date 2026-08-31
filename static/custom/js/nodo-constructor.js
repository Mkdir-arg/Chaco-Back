/**
 * Constructor del formulario de la convocatoria (Cambio 58, tasks 342-344).
 *
 * - Drag & drop con SortableJS: grupos en la raíz, campos y textos dentro de
 *   los grupos. Cada soltada guarda al instante (`mover`); si el servidor la
 *   rechaza (rompe una condición, RN-6) se restaura el HTML anterior.
 * - Acciones por delegación (`data-accion`): editar / condición / eliminar /
 *   restablecer. Los modales son Alpine (`constructorPagina`).
 * - Vista previa en vivo, renderizada desde `#constructor-datos` con el motor
 *   `NodoCondiciones` (espejo del servidor). Respondé y mirá qué se oculta.
 *
 * Contrato con el servidor: toda mutación devuelve `{ok, target, html, datos,
 * message}`; `html` reemplaza `#constructor-items` y `datos` alimenta la vista
 * previa y los modales.
 */
(function () {
  'use strict';

  var raiz, urls = {}, sortables = [], datos = { version: 0, items: [] };
  var respuestas = {};
  var canalActual = 'link';

  function getCookie(name) {
    var m = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
    return m ? decodeURIComponent(m.pop()) : '';
  }
  function aviso(mensaje, tipo) {
    if (typeof window.toast === 'function') { window.toast(mensaje, tipo || 'success'); }
  }
  function esc(s) {
    return String(s === null || s === undefined ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
  function urlDe(nombre, clave) {
    var u = urls[nombre] || '';
    return clave ? u.replace('__clave__', encodeURIComponent(clave)) : u;
  }
  function setGuardando(v) {
    window.dispatchEvent(new CustomEvent('constructor-guardando', { detail: !!v }));
  }

  // ── Datos ────────────────────────────────────────────────────────────────
  function leerDatos() {
    var el = document.getElementById('constructor-datos');
    if (!el) { return; }
    try { datos = JSON.parse(el.textContent); } catch (e) { datos = { version: 0, items: [] }; }
    window.dispatchEvent(new CustomEvent('constructor-datos', { detail: datos }));
  }
  function itemPorClave(clave) {
    for (var i = 0; i < datos.items.length; i++) { if (datos.items[i].clave === clave) { return datos.items[i]; } }
    return null;
  }
  function grupos() { return datos.items.filter(function (i) { return i.tipo === 'grupo'; }); }

  /** Campos anteriores a `clave` en el orden del formulario (RN-6). */
  function fuentesPara(clave) {
    var fuentes = [];
    for (var i = 0; i < datos.items.length; i++) {
      var it = datos.items[i];
      if (it.clave === clave) { break; }
      if (it.tipo === 'campo') { fuentes.push(it); }
    }
    return fuentes;
  }

  // ── Respuestas del servidor ──────────────────────────────────────────────

  // La manija con foco (teclado), re-localizable después de un re-render.
  function selectorDelFoco() {
    var foco = document.activeElement;
    if (!foco || !foco.classList || !foco.closest) { return null; }
    var esGrupo = foco.classList.contains('grupo-grip');
    if (!esGrupo && !foco.classList.contains('item-grip')) { return null; }
    var duenio = foco.closest(esGrupo ? '.cons-grupo' : '.cons-item');
    if (!duenio || !duenio.getAttribute('data-clave')) { return null; }
    return (esGrupo ? '.cons-grupo' : '.cons-item') +
      '[data-clave="' + duenio.getAttribute('data-clave') + '"] ' +
      (esGrupo ? '.grupo-grip' : '.item-grip');
  }

  function restaurarFoco(focoSel) {
    if (!focoSel) { return; }
    var grip = document.querySelector(focoSel);
    if (grip) { grip.focus(); }
  }

  function anunciar(texto) {
    var el = document.getElementById('constructor-aria-vivo');
    if (!el) {
      el = document.createElement('div');
      el.id = 'constructor-aria-vivo';
      el.className = 'sr-only';
      el.setAttribute('aria-live', 'polite');
      document.body.appendChild(el);
    }
    el.textContent = texto;
  }

  function aplicarRespuesta(data) {
    var focoSel = selectorDelFoco();
    var tgt = document.querySelector(data.target || '#constructor-items');
    if (tgt && typeof data.html === 'string') {
      tgt.innerHTML = data.html;
      if (window.Alpine && typeof window.Alpine.initTree === 'function') { window.Alpine.initTree(tgt); }
    }
    leerDatos();
    initSortables();
    renderPreview();
    restaurarFoco(focoSel);
  }

  function post(url, payload, ok, fallo) {
    setGuardando(true);
    fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify(payload || {})
    }).then(function (resp) {
      return resp.json().catch(function () { return {}; }).then(function (data) { return { status: resp.status, data: data }; });
    }).then(function (r) {
      setGuardando(false);
      var data = r.data || {};
      if (r.status >= 200 && r.status < 300 && data.ok) {
        aplicarRespuesta(data);
        aviso(data.message || 'Guardado.');
        if (ok) { ok(data); }
      } else {
        var msg = data.message || 'No se pudo guardar. Recargá la página.';
        if (fallo) { fallo(msg, data); } else { aviso(msg, 'error'); }
      }
    }).catch(function () {
      setGuardando(false);
      var msg = 'No se pudo guardar. Revisá la conexión.';
      if (fallo) { fallo(msg, {}); } else { aviso(msg, 'error'); }
    });
  }

  // ── Drag & drop ──────────────────────────────────────────────────────────
  function destruirSortables() {
    sortables.forEach(function (s) { try { s.destroy(); } catch (e) { /* ya desmontado */ } });
    sortables = [];
  }

  function initSortables() {
    destruirSortables();
    var root = document.querySelector('[data-constructor-root]');
    if (!root || !window.Sortable) { return; }
    var snapshot = null;
    var contenedor = document.getElementById('constructor-items');

    function empezar() { snapshot = contenedor.innerHTML; }

    function hijosQue(lista, selector) {
      return Array.prototype.filter.call(lista.children, function (el) { return el.matches(selector); });
    }

    function postMover(claveItem, clavePadre, posicion) {
      var focoSel = selectorDelFoco();
      post(urlDe('mover'), { clave: claveItem, padre: clavePadre || null, posicion: posicion < 0 ? 0 : posicion }, null, function (msg) {
        aviso(msg, 'error');
        if (snapshot !== null) {
          contenedor.innerHTML = snapshot;
          if (window.Alpine && window.Alpine.initTree) { window.Alpine.initTree(contenedor); }
          leerDatos();
          initSortables();
          renderPreview();
          restaurarFoco(focoSel);
        }
      });
    }

    function mover(evt, claveItem, clavePadre) {
      var hermanos = hijosQue(evt.to, clavePadre ? '.cons-item' : '.cons-grupo');
      postMover(claveItem, clavePadre, hermanos.indexOf(evt.item));
    }

    // ── Alternativa de teclado (mejora del Cambio 58, misma que el catálogo):
    // las flechas mueven en el DOM y el `mover` viaja una sola vez, con la
    // posición final, cuando la ráfaga termina (700 ms sin pulsaciones).
    var timerTeclado = null;
    var pendiente = null; // {clave, esGrupo}

    function flushTeclado() {
      window.clearTimeout(timerTeclado);
      timerTeclado = null;
      if (!pendiente) { return; }
      var p = pendiente;
      pendiente = null;
      var el = contenedor.querySelector((p.esGrupo ? '.cons-grupo' : '.cons-item') + '[data-clave="' + p.clave + '"]');
      if (!el || !el.isConnected) { return; }
      if (p.esGrupo) {
        postMover(p.clave, null, hijosQue(el.parentElement, '.cons-grupo').indexOf(el));
      } else {
        var ul = el.closest('[data-sortable-hijos]');
        postMover(p.clave, ul.getAttribute('data-clave') || null, hijosQue(ul, '.cons-item').indexOf(el));
      }
    }

    function anunciarTeclado(el, esGrupo) {
      var it = itemPorClave(el.getAttribute('data-clave')) || {};
      var nombre = String(it.etiqueta || it.titulo || it.texto || (esGrupo ? 'Grupo' : 'Ítem')).slice(0, 80);
      var lista = esGrupo ? el.parentElement : el.closest('[data-sortable-hijos]');
      var hermanos = hijosQue(lista, esGrupo ? '.cons-grupo' : '.cons-item');
      var texto = nombre + ': posición ' + (hermanos.indexOf(el) + 1) + ' de ' + hermanos.length;
      if (!esGrupo) {
        var seccion = el.closest('.cons-grupo');
        var titulo = seccion && seccion.querySelector('header .text-heading');
        if (titulo) { texto += ' en ' + titulo.textContent.trim().slice(0, 60); }
      }
      anunciar(texto + '.');
    }

    function tecladoMover(grip, delta) {
      var esGrupo = grip.classList.contains('grupo-grip');
      var el = grip.closest(esGrupo ? '.cons-grupo' : '.cons-item');
      if (!el || !el.getAttribute('data-clave')) { return; }
      var clave = el.getAttribute('data-clave');
      // Cambio de ítem a mitad de ráfaga: el movimiento anterior viaja ya.
      if (pendiente && pendiente.clave !== clave) { flushTeclado(); }
      if (!pendiente) { empezar(); }
      if (esGrupo) {
        var grupos = hijosQue(el.parentElement, '.cons-grupo');
        var destino = grupos[grupos.indexOf(el) + delta];
        if (!destino) { return; }
        el.parentElement.insertBefore(el, delta < 0 ? destino : destino.nextSibling);
      } else {
        var ul = el.closest('[data-sortable-hijos]');
        var items = hijosQue(ul, '.cons-item');
        var idx = items.indexOf(el) + delta;
        if (idx >= 0 && idx < items.length) {
          ul.insertBefore(el, delta < 0 ? items[idx] : items[idx].nextSibling);
        } else {
          // En el borde: cruza al final del grupo anterior o al principio del siguiente.
          var listas = Array.prototype.slice.call(contenedor.querySelectorAll('[data-sortable-hijos]'));
          var vecina = listas[listas.indexOf(ul) + delta];
          if (!vecina) { return; }
          var ph = vecina.querySelector('.sortable-placeholder');
          if (ph) { ph.remove(); }
          if (delta < 0) { vecina.appendChild(el); }
          else { vecina.insertBefore(el, vecina.querySelector('.cons-item')); }
        }
      }
      grip.focus();
      anunciarTeclado(el, esGrupo);
      pendiente = { clave: clave, esGrupo: esGrupo };
      window.clearTimeout(timerTeclado);
      timerTeclado = window.setTimeout(flushTeclado, 700);
    }

    // Una sola vez por root: `initSortables()` puede re-correr sobre el mismo
    // nodo y un listener duplicado movería doble.
    if (!root.dataset.tecladoEnlazado) {
      root.dataset.tecladoEnlazado = '1';
      root.addEventListener('keydown', function (e) {
        if (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') { return; }
        var grip = e.target.closest ? e.target.closest('.grupo-grip, .item-grip') : null;
        if (!grip) { return; }
        e.preventDefault();
        tecladoMover(grip, e.key === 'ArrowUp' ? -1 : 1);
      });
    }

    sortables.push(new window.Sortable(root, {
      animation: 150,
      handle: '.grupo-grip',
      draggable: '.cons-grupo',
      ghostClass: 'sortable-ghost',
      chosenClass: 'sortable-chosen',
      onStart: empezar,
      onEnd: function (evt) {
        if (evt.oldIndex === evt.newIndex) { return; }
        mover(evt, evt.item.getAttribute('data-clave'), null);
      }
    }));

    root.querySelectorAll('[data-sortable-hijos]').forEach(function (ul) {
      sortables.push(new window.Sortable(ul, {
        group: 'cons-items',
        animation: 150,
        handle: '.item-grip',
        draggable: '.cons-item',
        filter: '.sortable-placeholder',
        ghostClass: 'sortable-ghost',
        chosenClass: 'sortable-chosen',
        onStart: empezar,
        onEnd: function (evt) {
          if (evt.from === evt.to && evt.oldIndex === evt.newIndex) { return; }
          mover(evt, evt.item.getAttribute('data-clave'), evt.to.getAttribute('data-clave'));
        }
      }));
    });
  }

  // ── Acciones ─────────────────────────────────────────────────────────────
  function confirmar(opts, onConfirm) {
    if (window.ModernModal && typeof window.ModernModal.show === 'function') {
      window.ModernModal.show({
        type: 'confirm',
        danger: !!opts.danger,
        title: opts.title,
        message: opts.message || '',
        confirmText: opts.ok || 'Sí, confirmar',
        cancelText: 'Cancelar',
        onConfirm: onConfirm
      });
    } else {
      onConfirm();
    }
  }

  function modalPara(dato) {
    if (dato.tipo === 'grupo') { return 'grupo'; }
    if (dato.tipo === 'texto') { return 'texto'; }
    return dato.propio ? 'propio' : 'etiqueta';
  }

  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-accion]');
    if (!btn || !raiz || !raiz.contains(btn)) { return; }
    var accion = btn.getAttribute('data-accion');
    var clave = btn.getAttribute('data-clave');
    var dato = clave ? itemPorClave(clave) : null;

    if (accion === 'editar' && dato) {
      window.dispatchEvent(new CustomEvent('constructor-abrir', { detail: { modal: modalPara(dato), clave: clave } }));
    } else if (accion === 'condicion' && dato) {
      window.dispatchEvent(new CustomEvent('constructor-abrir', { detail: { modal: 'condicion', clave: clave } }));
    } else if (accion === 'eliminar' && dato) {
      confirmar({
        danger: true,
        title: dato.tipo === 'grupo' ? '¿Eliminar el grupo?' : '¿Eliminar del formulario?',
        message: dato.titulo || dato.texto || '',
        ok: 'Sí, eliminar'
      }, function () { post(urlDe('eliminar', clave)); });
    } else if (accion === 'restablecer') {
      confirmar({
        danger: true,
        title: '¿Restablecer el formulario?',
        message: 'Vuelve al orden del catálogo: se pierden los grupos propios, los textos, los campos propios, las etiquetas y las condiciones de esta convocatoria.',
        ok: 'Sí, restablecer'
      }, function () { post(urlDe('restablecer')); });
    }
  });

  // ── Vista previa ─────────────────────────────────────────────────────────
  function linkify(texto) {
    var partes = esc(texto).split(/(https?:\/\/[^\s<]+)/g);
    return partes.map(function (p, i) {
      return i % 2 ? '<a href="' + p + '" target="_blank" rel="noopener" class="text-fg-brand underline">' + p + '</a>' : p;
    }).join('');
  }

  function inputDe(item) {
    var clave = esc(item.clave), v = respuestas[item.clave];
    // Lo que el paso 1 ya sabe del titular no se pide en el paso 2.
    var solo_lectura = item.origen === 'legajo' && (item.vinculo === 'dni' || item.vinculo === 'genero');
    switch (item.tipo_campo) {
      case 'INT':
        return '<input type="number" class="nodo-field" data-clave="' + clave + '" value="' + esc(v) + '">';
      case 'DATE':
        return '<input type="date" class="nodo-field" data-clave="' + clave + '" value="' + esc(v) + '">';
      case 'ARCHIVO':
        return '<label class="pv-archivo"><input type="checkbox" data-clave="' + clave + '" ' + (v ? 'checked' : '') + '> <span>Simular archivo adjuntado</span></label>';
      case 'SELECTOR': {
        if (solo_lectura) {
          return '<input type="text" class="nodo-field" data-clave="' + clave + '" value="' + esc(v) + '" readonly placeholder="Se toma de la identificación del paso 1">';
        }
        var out = '<select class="nodo-field" data-clave="' + clave + '"><option value="">Elegí…</option>';
        // El sexo se elige con nombre, como lo rinde el portal (F/M es el valor).
        var etiquetas = item.vinculo === 'genero' ? { F: 'Femenino', M: 'Masculino' } : {};
        (item.opciones || []).forEach(function (o) {
          out += '<option value="' + esc(o) + '"' + (String(v) === String(o) ? ' selected' : '') + '>' + esc(etiquetas[o] || o) + '</option>';
        });
        return out + '</select>' + (item.presentacion === 'BUSCADOR' ? '<p class="pv-ayuda">Se muestra como buscador con píldoras.</p>' : '');
      }
      case 'SELECTOR_MULTIPLE': {
        var marcados = Array.isArray(v) ? v : [];
        var html = '<div class="pv-checks" data-clave-grupo="' + clave + '">';
        (item.opciones || []).forEach(function (o) {
          html += '<label><input type="checkbox" data-clave="' + clave + '" data-multiple="1" value="' + esc(o) + '"' + (marcados.indexOf(o) !== -1 ? ' checked' : '') + '> <span>' + esc(o) + '</span></label>';
        });
        return html + '</div>' + (item.presentacion === 'BUSCADOR' ? '<p class="pv-ayuda">Se muestra como buscador con píldoras.</p>' : '');
      }
      default:
        if (solo_lectura) {
          return '<input type="text" class="nodo-field" data-clave="' + clave + '" value="' + esc(v) + '" readonly placeholder="Se toma de la identificación del paso 1">';
        }
        return '<input type="text" class="nodo-field" data-clave="' + clave + '" value="' + esc(v) + '">';
    }
  }

  function renderPreview() {
    var cont = document.getElementById('constructor-preview');
    if (!cont) { return; }
    var incluidos = {};
    var visiblesCanal = datos.items.filter(function (it) {
      var entra = it.canal === 'ambos' || it.canal === canalActual;
      if (it.padre && !incluidos[it.padre]) { entra = false; }
      if (entra) { incluidos[it.clave] = true; }
      return entra;
    });
    var planos = visiblesCanal.map(function (it) { return { clave: it.clave, tipo: it.tipo, padre: it.padre, condicion: it.condicion }; });
    var res = window.NodoCondiciones ? window.NodoCondiciones.aplicar(planos, respuestas) : { visibles: new Set(planos.map(function (p) { return p.clave; })), ocultos: new Set() };

    var html = '', ocultos = [];
    var grupoAbierto = false, grupoConHijos = false, bufferGrupo = '';
    function cerrarGrupo() {
      if (grupoAbierto) {
        if (grupoConHijos) { html += bufferGrupo + '</div></fieldset>'; }
        grupoAbierto = false; grupoConHijos = false; bufferGrupo = '';
      }
    }
    visiblesCanal.forEach(function (it) {
      if (it.tipo === 'grupo') {
        cerrarGrupo();
        if (res.ocultos.has(it.clave)) { ocultos.push(it.titulo || '(grupo)'); return; }
        grupoAbierto = true;
        bufferGrupo = '<fieldset class="pv-grupo"><legend class="pv-legend">' + esc(it.titulo || '(grupo sin título)') + '</legend>' +
          (it.subtitulo ? '<p class="pv-subtitulo">' + esc(it.subtitulo) + '</p>' : '') + '<div class="pv-campos">';
        return;
      }
      if (!grupoAbierto) { return; }
      if (res.ocultos.has(it.clave)) { ocultos.push(it.titulo || it.texto || it.clave); return; }
      grupoConHijos = true;
      if (it.tipo === 'texto') {
        bufferGrupo += '<p class="pv-texto">' + linkify(it.texto) + '</p>';
      } else {
        bufferGrupo += '<div class="pv-campo"><label class="pv-label">' + esc(it.titulo) +
          (it.obligatorio ? ' <span class="text-fg-danger">*</span>' : '') + '</label>' + inputDe(it) + '</div>';
      }
    });
    cerrarGrupo();

    if (!html) {
      html = '<div class="py-10 text-center text-sm text-body-subtle">Nada para mostrar en este canal.</div>';
    }
    if (ocultos.length) {
      html += '<div class="pv-ocultos"><i class="fas fa-eye-slash"></i> Ocultos ahora por sus condiciones: ' + ocultos.map(esc).join(', ') + '.</div>';
    }
    cont.innerHTML = html;
  }

  function leerRespuesta(el) {
    var clave = el.getAttribute('data-clave');
    if (!clave) { return; }
    if (el.getAttribute('data-multiple') === '1') {
      var marcados = [];
      document.querySelectorAll('#constructor-preview input[data-clave="' + clave + '"]:checked').forEach(function (c) { marcados.push(c.value); });
      respuestas[clave] = marcados;
    } else if (el.type === 'checkbox') {
      respuestas[clave] = el.checked ? 'adjuntado' : '';
    } else {
      respuestas[clave] = el.value;
    }
    renderPreview();
  }

  document.addEventListener('change', function (e) {
    var el = e.target;
    if (el && el.closest && el.closest('#constructor-preview') && el.hasAttribute('data-clave')) { leerRespuesta(el); }
  });

  // ── Estado Alpine de la página ───────────────────────────────────────────
  window.constructorPagina = function (versionInicial) {
    var operadores = {};
    try { operadores = JSON.parse(document.getElementById('constructor-operadores').textContent); } catch (e) { operadores = { por_tipo: {}, etiquetas: {}, sin_valor: [], con_lista: [] }; }
    return {
      version: versionInicial || 0,
      guardando: false,
      canal: 'link',
      modal: '',
      edicion: null,
      url: '',
      grupos: [],
      f: { etiqueta: '', subtitulo: '', canal: 'ambos', texto: '', tipo: 'STRING', opciones: '', presentacion: 'LISTA', obligatorio: 'si', padre: '', texto_catalogo: '' },
      cond: { clave: '', titulo: '', modo: 'todas', reglas: [], fuentes: [], error: '', tenia: false },

      init: function () {
        var self = this;
        this.$watch('canal', function (v) { canalActual = v; renderPreview(); });
        window.addEventListener('constructor-guardando', function (e) { self.guardando = !!e.detail; });
        window.addEventListener('constructor-datos', function () { self.grupos = grupos(); });
        this.grupos = grupos();
      },

      abrir: function (detail) {
        var dato = detail.clave ? itemPorClave(detail.clave) : null;
        this.edicion = detail.clave || null;
        this.grupos = grupos();
        var f = this.f;
        f.padre = (dato && dato.padre) || (this.grupos[0] ? this.grupos[0].clave : '');
        f.canal = (dato && dato.canal) || 'ambos';
        if (detail.modal === 'grupo') {
          f.etiqueta = dato ? (dato.etiqueta || dato.titulo || '') : '';
          f.subtitulo = dato ? (dato.subtitulo || '') : '';
          this.url = dato ? urlDe('editar', dato.clave) : urlDe('grupo');
        } else if (detail.modal === 'texto') {
          f.texto = dato ? (dato.texto || '') : '';
          this.url = dato ? urlDe('editar', dato.clave) : urlDe('texto');
        } else if (detail.modal === 'propio') {
          f.texto = dato ? (dato.texto_catalogo || dato.titulo || '') : '';
          f.tipo = dato ? (dato.tipo_campo || 'STRING') : 'STRING';
          f.opciones = dato ? (dato.opciones || []).join('\n') : '';
          f.presentacion = dato ? (dato.presentacion || 'LISTA') : 'LISTA';
          f.obligatorio = dato ? (dato.obligatorio ? 'si' : '') : 'si';
          this.url = dato ? urlDe('editar', dato.clave) : urlDe('propio');
        } else if (detail.modal === 'etiqueta' && dato) {
          f.etiqueta = dato.etiqueta || '';
          f.texto_catalogo = dato.texto_catalogo || '';
          this.url = urlDe('editar', dato.clave);
        } else if (detail.modal === 'condicion' && dato) {
          var c = dato.condicion || { modo: 'todas', reglas: [] };
          this.cond = {
            clave: dato.clave,
            titulo: dato.titulo || dato.texto || dato.clave,
            modo: c.modo || 'todas',
            reglas: (c.reglas || []).map(function (r) {
              return { fuente: r.fuente || '', op: r.op || '', valor: Array.isArray(r.valor) ? r.valor.join(', ') : (r.valor === null || r.valor === undefined ? '' : String(r.valor)) };
            }),
            fuentes: fuentesPara(dato.clave),
            error: '',
            tenia: !!(dato.condicion && (dato.condicion.reglas || []).length)
          };
          if (!this.cond.reglas.length && this.cond.fuentes.length) { this.cond.reglas.push({ fuente: '', op: '', valor: '' }); }
        }
        this.modal = detail.modal;
      },

      cerrar: function () { this.modal = ''; this.edicion = null; },

      fuente: function (clave) {
        for (var i = 0; i < this.cond.fuentes.length; i++) { if (this.cond.fuentes[i].clave === clave) { return this.cond.fuentes[i]; } }
        return null;
      },
      operadoresDe: function (clave) {
        var fu = this.fuente(clave);
        return fu ? (operadores.por_tipo[fu.tipo_campo] || []) : [];
      },
      opcionesDe: function (clave) {
        var fu = this.fuente(clave);
        return fu ? (fu.opciones || []) : [];
      },
      etiquetaOp: function (op) { return operadores.etiquetas[op] || op; },
      necesitaValor: function (r) { return !!r.op && operadores.sin_valor.indexOf(r.op) === -1; },
      conLista: function (op) { return operadores.con_lista.indexOf(op) !== -1; },
      tipoInput: function (r) {
        var fu = this.fuente(r.fuente);
        if (!fu) { return 'text'; }
        if (this.conLista(r.op)) { return 'text'; }
        if (fu.tipo_campo === 'INT' || /^edad_/.test(r.op)) { return 'number'; }
        if (fu.tipo_campo === 'DATE') { return 'date'; }
        return 'text';
      },

      guardarCondicion: function (quitar) {
        var self = this;
        var condicion = null;
        if (!quitar) {
          var reglas = [];
          for (var i = 0; i < this.cond.reglas.length; i++) {
            var r = this.cond.reglas[i];
            if (!r.fuente || !r.op) { this.cond.error = 'Completá el campo y el operador de cada regla.'; return; }
            var valor = r.valor;
            if (this.conLista(r.op)) {
              valor = String(valor || '').split(',').map(function (v) { return v.trim(); }).filter(Boolean);
              if (/^edad_/.test(r.op)) { valor = valor.map(Number); }
            } else if (this.necesitaValor(r) && this.tipoInput(r) === 'number') {
              valor = valor === '' ? '' : Number(valor);
            }
            if (this.necesitaValor(r) && (valor === '' || (Array.isArray(valor) && !valor.length))) {
              this.cond.error = 'La regla ' + (i + 1) + ' necesita un valor.'; return;
            }
            reglas.push({ fuente: r.fuente, op: r.op, valor: this.necesitaValor(r) ? valor : null });
          }
          if (!reglas.length) { quitar = true; }
          else { condicion = { modo: this.cond.modo, reglas: reglas }; }
        }
        this.cond.error = '';
        post(urlDe('condicion', this.cond.clave), { condicion: condicion }, function () { self.cerrar(); }, function (msg) { self.cond.error = msg; });
      }
    };
  };

  // ── Arranque ─────────────────────────────────────────────────────────────
  function init() {
    raiz = document.getElementById('constructor');
    if (!raiz) { return; }
    ['mover', 'editar', 'condicion', 'eliminar', 'restablecer', 'grupo', 'texto', 'propio'].forEach(function (n) {
      urls[n] = raiz.getAttribute('data-url-' + n) || '';
    });
    leerDatos();
    initSortables();
    renderPreview();
  }
  document.addEventListener('DOMContentLoaded', init);
  // Los modales `data-ajax` reemplazan #constructor-items y disparan becas-saved.
  window.addEventListener('becas-saved', function () { window.setTimeout(function () { leerDatos(); initSortables(); renderPreview(); }, 0); });
  window.NodoConstructor = { render: renderPreview, datos: function () { return datos; } };
})();
