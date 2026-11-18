/*
 * Cargador de Google Maps del backoffice (pieza: templates/components/_google_maps.html).
 *
 * Lee la configuración de #nodo-mapa-config y expone window.NodoMapa. Carga la Maps
 * JavaScript API con el script directo, `loading=async` y `callback`, que deja disponible
 * `google.maps.importLibrary` (guía «Load the Maps JavaScript API»). El script se pide una
 * sola vez, recién cuando una pantalla crea su primer mapa.
 */
(function () {
  'use strict';
  if (window.NodoMapa) { return; }

  var config = {};
  var nodoConfig = document.getElementById('nodo-mapa-config');
  try { config = nodoConfig ? JSON.parse(nodoConfig.textContent) || {} : {}; } catch (e) { config = {}; }

  // Plaza 25 de Mayo, Resistencia: centro por defecto cuando la pantalla no pide otro.
  var CENTRO = { lat: -27.451198, lng: -58.986695 };
  var CALLBACK = '__nodoMapaListo';
  var promesa = null;
  var falloDeClave = null;

  // Google llama a `gm_authFailure` cuando la key no vale para este sitio (referente o API
  // no habilitados). El mapa queda gris con su propio cartel: avisamos a la pantalla.
  var authAnterior = window.gm_authFailure;
  window.gm_authFailure = function () {
    falloDeClave = new Error('La clave de Google Maps no está habilitada para este sitio.');
    document.dispatchEvent(new CustomEvent('nodo-mapa:error', { detail: { mensaje: falloDeClave.message } }));
    if (typeof authAnterior === 'function') { authAnterior(); }
  };

  function cargar() {
    if (!config.key) { return Promise.reject(new Error('Google Maps no está configurado en este ambiente.')); }
    if (falloDeClave) { return Promise.reject(falloDeClave); }
    if (promesa) { return promesa; }
    promesa = new Promise(function (resolve, reject) {
      if (window.google && window.google.maps && window.google.maps.importLibrary) {
        resolve(window.google.maps);
        return;
      }
      window[CALLBACK] = function () {
        window[CALLBACK] = undefined;
        resolve(window.google.maps);
      };
      var parametros = new URLSearchParams({
        key: config.key,
        v: 'weekly',
        loading: 'async',
        callback: CALLBACK,
        language: config.idioma || 'es',
        region: config.region || 'AR'
      });
      var script = document.createElement('script');
      script.src = 'https://maps.googleapis.com/maps/api/js?' + parametros.toString();
      script.async = true;
      script.onerror = function () {
        // Sin red o bloqueado: se libera para que un reintento vuelva a pedirlo.
        promesa = null;
        script.remove();
        reject(new Error('No se pudo cargar Google Maps. Revisá la conexión y volvé a intentar.'));
      };
      document.head.appendChild(script);
    });
    return promesa;
  }

  function importar() {
    var nombres = Array.prototype.slice.call(arguments);
    return cargar().then(function (maps) {
      return Promise.all(nombres.map(function (nombre) { return maps.importLibrary(nombre); }));
    });
  }

  function crearMapa(elemento, opciones) {
    return importar('maps').then(function (librerias) {
      var base = {
        center: CENTRO,
        zoom: 13,
        mapTypeControl: false,
        streetViewControl: false,
        fullscreenControl: false,
        clickableIcons: false,
        // En una pantalla con scroll, la rueda desplaza la página; Ctrl + rueda hace zoom.
        gestureHandling: 'cooperative'
      };
      if (config.mapId) { base.mapId = config.mapId; }
      return new librerias[0].Map(elemento, Object.assign(base, opciones || {}));
    });
  }

  window.NodoMapa = {
    configurado: Boolean(config.key),
    mapId: config.mapId || '',
    centro: CENTRO,
    cargar: cargar,
    importar: importar,
    crearMapa: crearMapa
  };
})();
