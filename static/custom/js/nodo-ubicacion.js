/*
 * Domicilio con mapa (pieza: templates/components/_ubicacion_domicilio.html).
 *
 * Mejora progresiva sobre los campos reales del form: sin JS, o sin Google Maps configurado,
 * quedan domicilio, latitud y longitud a mano. Con Google Maps:
 *   - «Ubicar en el mapa» (o Enter en el domicilio) geocodifica «domicilio, localidad, provincia, Argentina».
 *   - Un resultado: pone el marcador. Varios: lista para elegir. Ninguno: aviso y se marca tocando el mapa.
 *   - El marcador se arrastra y un clic en el mapa lo mueve; latitud y longitud se escriben en los campos.
 * `data-domicilio-extra` (opcional): id de otro control cuyo texto se suma al domicilio (calle + número).
 * Con `data-a-pedido` (domicilio de una persona, SEC-33) no se le pide nada a Google al abrir la
 * pantalla: el mapa carga recién con «Ubicar en el mapa» o «Ver en el mapa».
 * Requiere window.NodoMapa (components/_google_maps.html), cargado antes que este archivo.
 */
(function () {
  'use strict';

  var ESTADOS = {
    vacio: ['badge-gray', 'fa-location-dot', 'Sin ubicar'],
    guardado: ['badge-success', 'fa-circle-check', 'Con ubicación'],
    google: ['badge-success', 'fa-circle-check', 'Ubicado con Google'],
    ajustado: ['badge-info', 'fa-hand-pointer', 'Ajustado a mano'],
    manual: ['badge-info', 'fa-hand-pointer', 'Marcado a mano'],
    elegir: ['badge-warning', 'fa-list-ul', 'Elegí una opción'],
    cambio: ['badge-warning', 'fa-rotate', 'El domicilio cambió: volvé a ubicarlo'],
    nada: ['badge-warning', 'fa-circle-question', 'No encontrado']
  };
  var ZOOM_PUNTO = 17;
  var MAX_CANDIDATOS = 5;

  function numero(valor) {
    var n = parseFloat(String(valor || '').replace(',', '.'));
    return isNaN(n) ? null : n;
  }
  function valida(lat, lng) {
    return lat !== null && lng !== null && lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180;
  }
  function comoLiteral(pos) {
    if (!pos) { return null; }
    return typeof pos.lat === 'function' ? { lat: pos.lat(), lng: pos.lng() } : { lat: pos.lat, lng: pos.lng };
  }

  function montar(raiz) {
    var q = function (sel) { return raiz.querySelector('[data-' + sel + ']'); };
    var campoDomicilio = document.getElementById(raiz.dataset.domicilio);
    var campoLat = document.getElementById(raiz.dataset.latitud);
    var campoLng = document.getElementById(raiz.dataset.longitud);
    var campoExtra = raiz.dataset.domicilioExtra ? document.getElementById(raiz.dataset.domicilioExtra) : null;
    var campoLocalidad = raiz.dataset.localidad ? document.getElementById(raiz.dataset.localidad) : null;
    var campoProvincia = raiz.dataset.provinciaId ? document.getElementById(raiz.dataset.provinciaId) : null;
    var aPedido = raiz.hasAttribute('data-a-pedido');
    var ver = q('ubicacion-ver');
    var boton = q('ubicacion-buscar');
    var badge = q('ubicacion-estado');
    var aviso = q('ubicacion-aviso');
    var candidatos = q('ubicacion-candidatos');
    var lista = q('ubicacion-candidatos-lista');
    var marco = q('ubicacion-marco');
    var vacio = q('ubicacion-vacio');
    var resumen = q('ubicacion-resumen');
    var manual = q('ubicacion-manual');
    var toggle = q('ubicacion-manual-toggle');
    var textoBoton = boton.innerHTML;
    var mapa = null, marcador = null, geocoder = null, Marcador = null, Pin = null;
    var consultaUbicada = '';

    function estado(clave) {
      var e = ESTADOS[clave];
      badge.className = 'badge ' + e[0];
      badge.innerHTML = '<i class="fas ' + e[1] + '" aria-hidden="true"></i> ';
      badge.appendChild(document.createTextNode(e[2]));
      badge.hidden = false;
    }
    function mostrarAviso(clave) {
      aviso.innerHTML = '';
      aviso.hidden = !clave;
      if (clave) { aviso.appendChild(raiz.querySelector('[data-ubicacion-alerta="' + clave + '"]').content.cloneNode(true)); }
    }
    function abrirManual(abrir) {
      manual.hidden = !abrir;
      toggle.setAttribute('aria-expanded', String(abrir));
    }
    function textoDe(campo) {
      if (!campo) { return ''; }
      if (!campo.options) { return campo.value.trim(); }
      var opcion = campo.options[campo.selectedIndex];
      return opcion && opcion.value ? opcion.text.trim() : '';
    }
    function consulta() {
      // `data-domicilio-extra`: la altura cuando va en su propio control (el edificio separa calle y número).
      var partes = [[campoDomicilio.value, campoExtra ? campoExtra.value : ''].join(' ').trim().replace(/\s+/g, ' ')];
      var localidad = textoDe(campoLocalidad);
      if (localidad) { partes.push(localidad); }
      partes.push(textoDe(campoProvincia) || raiz.dataset.provincia || 'Chaco', 'Argentina');
      return partes.join(', ');
    }
    function escribir(lat, lng) {
      campoLat.value = lat.toFixed(6);
      campoLng.value = lng.toFixed(6);
      [campoLat, campoLng].forEach(function (c) {
        c.dispatchEvent(new Event('input', { bubbles: true }));
        c.dispatchEvent(new Event('change', { bubbles: true }));
      });
      q('ubicacion-lat').textContent = campoLat.value;
      q('ubicacion-lng').textContent = campoLng.value;
    }
    function ponerMarcador(lat, lng) {
      var posicion = { lat: lat, lng: lng };
      if (!marcador) {
        var tokens = getComputedStyle(document.documentElement);
        var marca = tokens.getPropertyValue('--bg-brand').trim();
        var pin = new Pin({ background: marca, borderColor: marca, glyphColor: tokens.getPropertyValue('--text-white').trim() });
        marcador = new Marcador({
          map: mapa, position: posicion, gmpDraggable: true,
          title: 'Ubicación del domicilio. Arrastrá para ajustar.',
          content: pin.element || pin
        });
        marcador.addListener('dragend', function () {
          var p = comoLiteral(marcador.position);
          escribir(p.lat, p.lng);
          estado(consultaUbicada ? 'ajustado' : 'manual');
        });
      } else {
        marcador.position = posicion;
      }
      vacio.hidden = true;
    }
    function fijar(lat, lng, clave, centrar) {
      ponerMarcador(lat, lng);
      escribir(lat, lng);
      if (clave) { estado(clave); }
      if (centrar) { mapa.panTo({ lat: lat, lng: lng }); mapa.setZoom(ZOOM_PUNTO); }
    }

    function ocupado(si) {
      boton.disabled = si;
      boton.innerHTML = si ? '<i class="fas fa-circle-notch fa-spin" aria-hidden="true"></i> <span>Buscando…</span>' : textoBoton;
    }
    function errorDomicilio(texto) {
      var p = document.getElementById(campoDomicilio.id + '-error');
      if (!p) { return; }
      p.textContent = texto;
      p.classList.toggle('hidden', !texto);
      if (texto) { campoDomicilio.setAttribute('aria-invalid', 'true'); } else { campoDomicilio.removeAttribute('aria-invalid'); }
    }
    function elegir(resultados) {
      lista.innerHTML = '';
      resultados.forEach(function (r) {
        var li = document.createElement('li');
        var b = document.createElement('button');
        b.type = 'button';
        b.className = 'nodo-ubicacion__candidato';
        b.innerHTML = '<i class="fas fa-location-dot" aria-hidden="true"></i><span></span>';
        b.querySelector('span').textContent = r.formatted_address;
        b.addEventListener('click', function () {
          candidatos.hidden = true;
          var p = comoLiteral(r.geometry.location);
          consultaUbicada = consulta();
          fijar(p.lat, p.lng, 'google', true);
        });
        li.appendChild(b);
        lista.appendChild(li);
      });
      candidatos.hidden = false;
      estado('elegir');
      lista.querySelector('button').focus();
    }
    function ubicar() {
      if (!campoDomicilio.value.trim()) {
        // Pudo vaciarse mientras cargaba Google, con el botón ya en «Buscando…»: se libera.
        ocupado(false);
        errorDomicilio('Escribí calle y número para buscar.');
        campoDomicilio.focus();
        return;
      }
      errorDomicilio('');
      mostrarAviso(null);
      candidatos.hidden = true;
      ocupado(true);
      var pedido = consulta();
      geocoder.geocode({ address: pedido, region: 'ar', componentRestrictions: { country: 'AR' }, fulfillOnZeroResults: true })
        .then(function (respuesta) {
          var vistos = {};
          var resultados = (respuesta.results || []).filter(function (r) {
            if (vistos[r.formatted_address]) { return false; }
            vistos[r.formatted_address] = true;
            return true;
          }).slice(0, MAX_CANDIDATOS);
          if (!resultados.length) {
            estado('nada');
            mostrarAviso('no-encontrado');
            return;
          }
          if (resultados.length > 1) {
            elegir(resultados);
            return;
          }
          var p = comoLiteral(resultados[0].geometry.location);
          consultaUbicada = pedido;
          fijar(p.lat, p.lng, 'google', true);
        })
        .catch(function () {
          mostrarAviso('error');
          abrirManual(true);
        })
        .then(function () { ocupado(false); });
    }

    function sinMapa(clave) {
      marco.hidden = true;
      boton.hidden = true;
      ver.hidden = true;
      resumen.hidden = true;
      candidatos.hidden = true;
      badge.hidden = true;
      q('ubicacion-ayuda-mapa').hidden = true;
      mostrarAviso(clave);
      abrirManual(true);
    }

    if (!window.NodoMapa || !window.NodoMapa.configurado) {
      sinMapa('sin-mapa');
      return;
    }
    document.addEventListener('nodo-mapa:error', function () { sinMapa('error'); });

    var lat0 = numero(campoLat.value), lng0 = numero(campoLng.value);
    var conPunto = valida(lat0, lng0);
    var carga = null;
    boton.hidden = false;
    resumen.hidden = false;
    q('ubicacion-ayuda-mapa').hidden = false;
    abrirManual(raiz.hasAttribute('data-manual-abierto'));
    // El guardado AJAX escribe el error de latitud o longitud sin recargar: si el bloque está plegado, quedaría escondido.
    new MutationObserver(function () {
      var conError = Array.prototype.some.call(manual.querySelectorAll('[data-error]'), function (p) {
        return p.textContent.trim() && !p.classList.contains('hidden');
      });
      if (conError && manual.hidden) { abrirManual(true); }
    }).observe(manual, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['class'] });
    estado(conPunto ? 'guardado' : 'vacio');
    if (conPunto) {
      q('ubicacion-lat').textContent = lat0.toFixed(6);
      q('ubicacion-lng').textContent = lng0.toFixed(6);
    }

    function cargarMapa() {
      if (carga) { return carga; }
      marco.hidden = false;
      ver.hidden = true;
      carga = window.NodoMapa.importar('marker', 'geocoding')
        .then(function (librerias) {
          Marcador = librerias[0].AdvancedMarkerElement;
          Pin = librerias[0].PinElement;
          geocoder = new librerias[1].Geocoder();
          // El punto vigente al cargar: en un mapa a pedido pudo cambiar a mano antes de abrirlo.
          var lat = numero(campoLat.value), lng = numero(campoLng.value);
          var opciones = valida(lat, lng) ? { center: { lat: lat, lng: lng }, zoom: ZOOM_PUNTO } : {};
          return window.NodoMapa.crearMapa(q('ubicacion-mapa'), opciones).then(function (m) {
            mapa = m;
            if (valida(lat, lng)) { ponerMarcador(lat, lng); }
            mapa.addListener('click', function (evento) {
              var p = comoLiteral(evento.latLng);
              if (!p) { return; }
              candidatos.hidden = true;
              mostrarAviso(null);
              fijar(p.lat, p.lng, consultaUbicada || conPunto ? 'ajustado' : 'manual', false);
            });
            return m;
          });
        })
        .catch(function (error) {
          sinMapa('error');
          throw error;
        });
      return carga;
    }
    function pedirUbicacion() {
      if (!campoDomicilio.value.trim()) {
        errorDomicilio('Escribí calle y número para buscar.');
        campoDomicilio.focus();
        return;
      }
      // «Buscando…» desde que se pide: en un mapa a pedido, la carga de Google tarda, y un
      // segundo Enter o clic durante ese rato colgaría otro `ubicar` (otra consulta cobrada).
      ocupado(true);
      cargarMapa().then(ubicar, function () { ocupado(false); });
    }

    if (aPedido) {
      marco.hidden = true;
      ver.hidden = !conPunto;
    } else {
      cargarMapa().catch(function () {});
    }

    boton.addEventListener('click', pedirUbicacion);
    ver.addEventListener('click', function () { cargarMapa().catch(function () {}); });
    campoDomicilio.addEventListener('keydown', function (e) {
      // Con una búsqueda en curso el botón está deshabilitado: Enter tampoco pide otra (cada una se cobra).
      if (e.key === 'Enter') { e.preventDefault(); if (!boton.hidden && !boton.disabled) { pedirUbicacion(); } }
    });
    function revisarCambio() {
      if (consultaUbicada && marcador) { estado(consulta() === consultaUbicada ? 'google' : 'cambio'); }
    }
    campoDomicilio.addEventListener('input', revisarCambio);
    if (campoLocalidad) { campoLocalidad.addEventListener('change', revisarCambio); campoLocalidad.addEventListener('input', revisarCambio); }
    if (campoExtra) { campoExtra.addEventListener('input', revisarCambio); }
    toggle.addEventListener('click', function () { abrirManual(manual.hidden); });
    function desdeCampos() {
      var lat = numero(campoLat.value), lng = numero(campoLng.value);
      if (!valida(lat, lng)) { return; }
      q('ubicacion-lat').textContent = lat.toFixed(6);
      q('ubicacion-lng').textContent = lng.toFixed(6);
      estado('manual');
      if (!mapa) { ver.hidden = !aPedido || Boolean(carga); return; }
      ponerMarcador(lat, lng);
      mapa.panTo({ lat: lat, lng: lng });
    }
    // `change` lo dispara también `escribir`: solo se atiende el que viene del operador.
    [campoLat, campoLng].forEach(function (c) {
      c.addEventListener('change', function (e) { if (e.isTrusted) { desdeCampos(); } });
    });
  }

  function iniciar() {
    Array.prototype.forEach.call(document.querySelectorAll('[data-nodo-ubicacion]'), montar);
  }
  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', iniciar); } else { iniciar(); }
})();
