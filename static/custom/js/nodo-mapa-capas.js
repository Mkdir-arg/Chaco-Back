/*
 * Mapa con capas (pieza: templates/components/_mapa_capas.html; ficha .claude/design/componentes/mapa_capas.md).
 *
 * Dibuja los puntos que armó la vista como AdvancedMarkerElement en píldora, abre su detalle en un InfoWindow
 * y sincroniza el panel de la pantalla (capas, subfiltros, buscador, lista) por atributos `data-`. No decide
 * qué se muestra ni con qué color: todo llega en el JSON. Se apoya en window.NodoMapa (nodo-mapa.js).
 */
(function () {
  'use strict';

  var TONOS = ['brand', 'success', 'warning', 'danger', 'info', 'gray', 'navy'];
  var TONO_BADGE = { brand: 'brand', success: 'success', warning: 'warning', danger: 'danger', info: 'info', gray: 'gray', navy: 'gray' };
  var ZOOM_CERCA = 14;
  var ZOOM_UN_PUNTO = 15;

  function tonoValido(t) { return TONOS.indexOf(t) === -1 ? 'gray' : t; }
  function iconoValido(i) { return /^fa-[a-z0-9-]+$/.test(i || '') ? i : 'fa-location-dot'; }
  // Solo rutas del propio sitio: un `url` armado con datos de usuario nunca abre «javascript:» ni otro dominio.
  function rutaInterna(u) { return typeof u === 'string' && /^\/(?![\/\\])/.test(u) ? u : ''; }
  function sinTildes(s) { return String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').trim(); }
  function texto(v) { return v === null || v === undefined ? '' : String(v); }
  function leerJson(id) {
    var nodo = id && document.getElementById(id);
    try { return nodo ? JSON.parse(nodo.textContent) : null; } catch (e) { return null; }
  }
  function nodo(etiqueta, clase, contenido) {
    var el = document.createElement(etiqueta);
    if (clase) { el.className = clase; }
    if (contenido !== undefined) { el.textContent = contenido; }
    return el;
  }
  function icono(nombre) { var i = nodo('i', 'fas ' + iconoValido(nombre)); i.setAttribute('aria-hidden', 'true'); return i; }
  function coordenada(v) { return typeof v === 'function' ? v() : v; }

  function normalizar(p) {
    if (!p || p.id === undefined || p.id === null) { return null; }
    var lat = Number(p.lat), lng = Number(p.lng);
    if (!isFinite(lat) || !isFinite(lng) || Math.abs(lat) > 90 || Math.abs(lng) > 180) { return null; }
    return {
      id: String(p.id), capa: texto(p.capa), lat: lat, lng: lng,
      etiqueta: texto(p.etiqueta || p.titulo), icono: iconoValido(p.icono), tono: tonoValido(p.tono),
      titulo: texto(p.titulo), subtitulo: texto(p.subtitulo),
      estado: p.estado && p.estado.texto ? { texto: texto(p.estado.texto), tono: TONO_BADGE[p.estado.tono] || 'gray' } : null,
      datos: Array.isArray(p.datos) ? p.datos.filter(Array.isArray) : [],
      url: rutaInterna(p.url), urlTexto: texto(p.url_texto) || 'Abrir',
      acciones: Array.isArray(p.acciones) ? p.acciones.filter(function (a) { return a && a.accion; }) : [],
      grupo: texto(p.grupo), movible: p.movible === true,
      forma: p.forma === 'circulo' ? 'circulo' : 'pin',
      tamano: [1, 2, 3].indexOf(p.tamano) === -1 ? 2 : p.tamano
    };
  }

  function MapaCapas(contenedor) {
    this.c = contenedor;
    this.nombre = contenedor.getAttribute('data-mapa-capas');
    this.puntos = [];
    this.porId = {};
    this.capasApagadas = {};
    this.gruposApagados = {};
    this.busqueda = '';
    this.activo = null;
    this.marcadores = {};
    this.mapa = null;
    this.libs = null;
    this.info = null;
    this.clic = false;
    this.cargando = null;
    this.conDetalle = !contenedor.hasAttribute('data-sin-detalle');
    var self = this;
    (leerJson(contenedor.getAttribute('data-puntos')) || []).forEach(function (p) { self._sumar(p); });
    this._leerControles();
    this._escuchar();
    this.sincronizar();
    contenedor.nodoMapaCapas = {
      seleccionar: function (id) { self.seleccionar(id, true); },
      cerrar: function () { self.cerrar(); },
      encuadrar: function () { self.encuadrar(); },
      agregar: function (p) { return self.agregar(p); },
      quitar: function (id) { self.quitar(id); },
      modoClic: function (si) { self.modoClic(si); }
    };
    this._programarCarga();
  }

  MapaCapas.prototype._emitir = function (nombre, detalle) {
    this.c.dispatchEvent(new CustomEvent('nodo-mapa-capas:' + nombre, { bubbles: true, detail: detalle || {} }));
  };

  // Controles de la pantalla: dentro del contenedor o en cualquier nodo con data-mapa="<nombre>".
  MapaCapas.prototype._raices = function () {
    var externas = Array.prototype.slice.call(document.querySelectorAll('[data-mapa="' + CSS.escape(this.nombre) + '"]'));
    return [this.c].concat(externas);
  };
  MapaCapas.prototype._todos = function (selector) {
    var vistos = [];
    this._raices().forEach(function (raiz) {
      if (raiz.matches(selector)) { vistos.push(raiz); }
      Array.prototype.forEach.call(raiz.querySelectorAll(selector), function (el) { if (vistos.indexOf(el) === -1) { vistos.push(el); } });
    });
    return vistos;
  };
  MapaCapas.prototype._propio = function (el) {
    if (this.c.contains(el)) { return true; }
    var raiz = el.closest('[data-mapa]');
    return Boolean(raiz) && raiz.getAttribute('data-mapa') === this.nombre;
  };
  MapaCapas.prototype._leerControles = function () {
    var self = this;
    this._todos('[data-mapa-capa]').forEach(function (b) {
      if (b.getAttribute('aria-pressed') === 'false') { self.capasApagadas[b.getAttribute('data-mapa-capa')] = true; }
    });
    this._todos('[data-mapa-grupo]').forEach(function (b) {
      if (b.getAttribute('aria-pressed') === 'false') { self.gruposApagados[b.getAttribute('data-mapa-grupo')] = true; }
    });
    var caja = this._todos('[data-mapa-buscar]')[0];
    if (caja) { this.busqueda = sinTildes(caja.value); }
  };
  MapaCapas.prototype._escuchar = function () {
    var self = this;
    document.addEventListener('click', function (e) {
      var el = e.target.closest('[data-mapa-capa], [data-mapa-grupo], [data-item]');
      if (!el || !self._propio(el)) { return; }
      if (el.hasAttribute('data-mapa-capa')) {
        var capa = el.getAttribute('data-mapa-capa');
        self.capasApagadas[capa] = !self.capasApagadas[capa];
        self.sincronizar();
      } else if (el.hasAttribute('data-mapa-grupo')) {
        var grupo = el.getAttribute('data-mapa-grupo');
        self.gruposApagados[grupo] = !self.gruposApagados[grupo];
        self.sincronizar();
      } else if (self.porId[el.getAttribute('data-item')]) {
        self.seleccionar(el.getAttribute('data-item'), true);
      }
    });
    document.addEventListener('input', function (e) {
      if (!e.target.matches('[data-mapa-buscar]') || !self._propio(e.target)) { return; }
      self.busqueda = sinTildes(e.target.value);
      self.sincronizar();
    });
    var encuadre = this.c.querySelector('[data-mapa-encuadrar]');
    if (encuadre) { encuadre.addEventListener('click', function () { self.cerrar(); self.encuadrar(); }); }
    var ver = this.c.querySelector('[data-mapa-ver]');
    if (ver) { ver.addEventListener('click', function () { self.cargar(); }); }
    document.addEventListener('nodo-mapa:error', function () { if (self.cargando) { self._mostrarError(); } });
  };

  MapaCapas.prototype._sumar = function (crudo) {
    var p = normalizar(crudo);
    if (!p || this.porId[p.id]) { return null; }
    this.puntos.push(p);
    this.porId[p.id] = p;
    return p;
  };
  MapaCapas.prototype.visible = function (p) {
    if (this.capasApagadas[p.capa]) { return false; }
    if (p.grupo && this.gruposApagados[p.grupo]) { return false; }
    if (this.busqueda) { return sinTildes(p.titulo + ' ' + p.subtitulo + ' ' + p.etiqueta).indexOf(this.busqueda) !== -1; }
    return true;
  };

  MapaCapas.prototype.sincronizar = function () {
    var self = this;
    var visibles = this.puntos.filter(function (p) { return self.visible(p); });
    this._todos('[data-mapa-capa]').forEach(function (b) {
      var capa = b.getAttribute('data-mapa-capa');
      b.setAttribute('aria-pressed', self.capasApagadas[capa] ? 'false' : 'true');
      var n = b.querySelector('[data-mapa-capa-n]');
      if (n) { n.textContent = self.puntos.filter(function (p) { return p.capa === capa; }).length; }
    });
    this._todos('[data-mapa-grupo]').forEach(function (b) {
      b.setAttribute('aria-pressed', self.gruposApagados[b.getAttribute('data-mapa-grupo')] ? 'false' : 'true');
    });
    this._todos('[data-item]').forEach(function (el) {
      var p = self.porId[el.getAttribute('data-item')];
      if (!p) { return; }
      var item = el.closest('li') || el;
      item.hidden = !self.visible(p);
      el.setAttribute('aria-pressed', p.id === self.activo ? 'true' : 'false');
    });
    this._todos('[data-mapa-total]').forEach(function (el) { el.textContent = visibles.length; });
    this._todos('[data-mapa-vacio]').forEach(function (el) { el.hidden = visibles.length > 0; });
    this.puntos.forEach(function (p) {
      var m = self.marcadores[p.id];
      if (!m) { return; }
      m.map = self.visible(p) ? self.mapa : null;
      m.content.classList.toggle('is-activo', p.id === self.activo);
      m.zIndex = p.id === self.activo ? 1000 : null;
    });
    if (this.activo && (!this.porId[this.activo] || !this.visible(this.porId[this.activo]))) { this.cerrar(); }
  };

  // ---------- carga del mapa ----------
  MapaCapas.prototype._programarCarga = function () {
    var self = this;
    if (!window.NodoMapa || !window.NodoMapa.configurado || this.c.hasAttribute('data-a-pedido')) { return; }
    if (!('IntersectionObserver' in window)) { this.cargar(); return; }
    var observador = new IntersectionObserver(function (entradas) {
      if (entradas.some(function (e) { return e.isIntersecting; })) { observador.disconnect(); self.cargar(); }
    }, { rootMargin: '200px' });
    observador.observe(this.c);
  };
  MapaCapas.prototype._mostrarError = function () {
    var error = this.c.querySelector('[data-mapa-error]');
    if (error) { error.hidden = false; }
    var pedido = this.c.querySelector('[data-mapa-pedido]');
    if (pedido) { pedido.hidden = true; }
  };
  MapaCapas.prototype.cargar = function () {
    var self = this;
    if (this.cargando) { return this.cargando; }
    if (!window.NodoMapa || !window.NodoMapa.configurado) { return Promise.resolve(null); }
    var ver = this.c.querySelector('[data-mapa-ver]');
    if (ver) { ver.disabled = true; }
    this.cargando = window.NodoMapa.crearMapa(this.c.querySelector('[data-mapa-lienzo]'), { zoom: 13 }).then(function (mapa) {
      self.mapa = mapa;
      return window.NodoMapa.importar('maps', 'marker', 'core');
    }).then(function (libs) {
      self.libs = { maps: libs[0], marker: libs[1], core: libs[2] };
      self.info = new self.libs.maps.InfoWindow({ maxWidth: 300 });
      self.info.addListener('closeclick', function () { self._soltar(); });
      self.mapa.addListener('zoom_changed', function () { self._distancia(); });
      self.mapa.addListener('click', function (e) {
        if (!self.clic || !e.latLng) { return; }
        self._emitir('clic', { lat: coordenada(e.latLng.lat), lng: coordenada(e.latLng.lng) });
      });
      self.puntos.forEach(function (p) { self._marcador(p); });
      var pedido = self.c.querySelector('[data-mapa-pedido]');
      if (pedido) { pedido.hidden = true; }
      var encuadre = self.c.querySelector('[data-mapa-encuadrar]');
      if (encuadre) { encuadre.hidden = false; }
      self.sincronizar();
      self.encuadrar();
      self._distancia();
      self._vigilarTamano();
      self._emitir('listo');
      return self.mapa;
    }).catch(function () {
      self._mostrarError();
      return null;
    });
    return this.cargando;
  };
  // En una solapa oculta (x-show) el contenedor mide 0: al mostrarse, el mapa se vuelve a encuadrar.
  MapaCapas.prototype._vigilarTamano = function () {
    if (!('ResizeObserver' in window)) { return; }
    var self = this;
    var oculto = this.c.offsetWidth === 0 || this.c.offsetHeight === 0;
    new ResizeObserver(function () {
      var ahora = self.c.offsetWidth === 0 || self.c.offsetHeight === 0;
      if (oculto && !ahora) { self.encuadrar(); }
      oculto = ahora;
    }).observe(this.c);
  };
  MapaCapas.prototype._distancia = function () {
    var zoom = this.mapa && this.mapa.getZoom ? this.mapa.getZoom() : ZOOM_CERCA;
    this.c.classList.toggle('is-lejos', zoom < ZOOM_CERCA);
  };
  MapaCapas.prototype._marcador = function (p) {
    var self = this;
    var pil;
    if (p.forma === 'circulo') {
      // Círculo centrado en la coordenada: el tamaño (1 a 3) y el tono los decide la vista.
      pil = nodo('div', 'nodo-mapa-circulo nodo-mapa-circulo--' + p.tamano + ' nodo-mapa-tono-' + p.tono);
    } else {
      pil = nodo('div', 'nodo-mapa-pil nodo-mapa-tono-' + p.tono);
      var circulo = nodo('span', 'nodo-mapa-pil__icono');
      circulo.appendChild(icono(p.icono));
      pil.appendChild(circulo);
      pil.appendChild(nodo('span', 'nodo-mapa-pil__texto', p.etiqueta));
    }
    var m = new this.libs.marker.AdvancedMarkerElement({
      map: this.visible(p) ? this.mapa : null,
      position: { lat: p.lat, lng: p.lng },
      content: pil,
      title: p.titulo || p.etiqueta,
      gmpClickable: true,
      gmpDraggable: p.movible
    });
    m.addListener('click', function () { self.seleccionar(p.id, false); });
    if (p.movible) {
      m.addListener('dragend', function () {
        var pos = m.position;
        p.lat = coordenada(pos.lat);
        p.lng = coordenada(pos.lng);
        self._emitir('movido', { id: p.id, lat: p.lat, lng: p.lng });
        if (self.activo === p.id) { self._abrirInfo(p); }
      });
    }
    this.marcadores[p.id] = m;
  };

  // ---------- selección y detalle ----------
  MapaCapas.prototype._contenido = function (p) {
    var self = this;
    var caja = nodo('div', 'nodo-mapa-info');
    if (p.subtitulo) { caja.appendChild(nodo('p', 'nodo-mapa-info__sub', p.subtitulo)); }
    if (p.estado) {
      var fila = nodo('p', 'nodo-mapa-info__estado');
      fila.appendChild(nodo('span', 'badge badge-dot badge-' + p.estado.tono, p.estado.texto));
      caja.appendChild(fila);
    }
    if (p.datos.length) {
      var dl = nodo('dl', 'nodo-mapa-info__datos');
      p.datos.forEach(function (d) { dl.appendChild(nodo('dt', '', texto(d[0]))); dl.appendChild(nodo('dd', '', texto(d[1]))); });
      caja.appendChild(dl);
    }
    if (p.acciones.length || p.url) {
      var pie = nodo('div', 'nodo-mapa-info__pie');
      p.acciones.forEach(function (a) {
        var b = nodo('button', 'btn-nodo btn-sm ' + (a.tono === 'danger' ? 'btn-danger' : 'btn-tertiary'));
        b.type = 'button';
        if (a.icono) { b.appendChild(icono(a.icono)); b.appendChild(document.createTextNode(' ')); }
        b.appendChild(document.createTextNode(texto(a.texto || a.accion)));
        b.addEventListener('click', function () { self._emitir('accion', { id: p.id, accion: String(a.accion) }); });
        pie.appendChild(b);
      });
      if (p.url) {
        var enlace = nodo('a', 'btn-nodo btn-brand btn-sm', p.urlTexto + ' ');
        enlace.href = p.url;
        enlace.appendChild(icono('fa-arrow-right'));
        pie.appendChild(enlace);
      }
      caja.appendChild(pie);
    }
    return caja;
  };
  MapaCapas.prototype._abrirInfo = function (p) {
    if (!this.conDetalle || !this.info || !this.marcadores[p.id]) { return; }
    this.info.setOptions({ headerContent: nodo('p', 'nodo-mapa-info__titulo', p.titulo), content: this._contenido(p), ariaLabel: p.titulo });
    this.info.open({ map: this.mapa, anchor: this.marcadores[p.id], shouldFocus: false });
  };
  MapaCapas.prototype.seleccionar = function (id, centrar) {
    var p = this.porId[String(id)];
    if (!p || !this.visible(p)) { return; }
    this.activo = p.id;
    this.sincronizar();
    if (this.mapa) {
      if (centrar) {
        this.mapa.panTo({ lat: p.lat, lng: p.lng });
        if (this.mapa.getZoom && this.mapa.getZoom() < ZOOM_UN_PUNTO) { this.mapa.setZoom(ZOOM_UN_PUNTO); }
      }
      this._abrirInfo(p);
    }
    this._emitir('seleccion', { id: p.id });
  };
  MapaCapas.prototype._soltar = function () {
    if (this.activo === null) { return; }
    this.activo = null;
    this.sincronizar();
    this._emitir('seleccion', { id: null });
  };
  MapaCapas.prototype.cerrar = function () {
    if (this.info) { this.info.close(); }
    this._soltar();
  };

  // ---------- encuadre ----------
  // El panel flotante de la pantalla tapa parte del mapa: el encuadre deja ese margen libre.
  MapaCapas.prototype._margen = function () {
    var margen = { top: 48, right: 56, bottom: 48, left: 48 };
    var caja = this.c.getBoundingClientRect();
    this._todos('.nodo-mapa-panel').forEach(function (panel) {
      if (panel.hidden || !panel.offsetParent) { return; }
      var r = panel.getBoundingClientRect();
      if (r.right <= caja.left || r.left >= caja.right || r.bottom <= caja.top || r.top >= caja.bottom) { return; }
      if (r.width < caja.width * 0.6) {
        margen.left = Math.max(margen.left, r.right - caja.left + 32);
      } else {
        margen.bottom = Math.max(margen.bottom, caja.bottom - r.top + 32);
      }
    });
    return margen;
  };
  MapaCapas.prototype.encuadrar = function () {
    if (!this.mapa) { return; }
    var self = this;
    var visibles = this.puntos.filter(function (p) { return self.visible(p); });
    if (!visibles.length) { return; }
    if (visibles.length === 1) {
      this.mapa.setCenter({ lat: visibles[0].lat, lng: visibles[0].lng });
      this.mapa.setZoom(ZOOM_UN_PUNTO);
      return;
    }
    var limites = new this.libs.core.LatLngBounds();
    visibles.forEach(function (p) { limites.extend({ lat: p.lat, lng: p.lng }); });
    this.mapa.fitBounds(limites, this._margen());
  };

  // ---------- edición desde la pantalla ----------
  MapaCapas.prototype.agregar = function (crudo) {
    var p = this._sumar(crudo);
    if (!p) { return null; }
    if (this.mapa) { this._marcador(p); }
    this.sincronizar();
    return p.id;
  };
  MapaCapas.prototype.quitar = function (id) {
    var p = this.porId[String(id)];
    if (!p) { return; }
    if (this.activo === p.id) { this.cerrar(); }
    if (this.marcadores[p.id]) { this.marcadores[p.id].map = null; delete this.marcadores[p.id]; }
    this.puntos.splice(this.puntos.indexOf(p), 1);
    delete this.porId[p.id];
    this.sincronizar();
  };
  MapaCapas.prototype.modoClic = function (si) {
    this.clic = Boolean(si);
    this.c.classList.toggle('is-clic', this.clic);
    if (this.clic) { this.cerrar(); }
    if (this.mapa && this.mapa.setOptions) { this.mapa.setOptions({ draggableCursor: this.clic ? 'crosshair' : null }); }
  };

  function iniciar() {
    Array.prototype.forEach.call(document.querySelectorAll('[data-mapa-capas]'), function (c) {
      if (!c.nodoMapaCapas) { new MapaCapas(c); }
    });
  }
  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', iniciar); } else { iniciar(); }
})();
