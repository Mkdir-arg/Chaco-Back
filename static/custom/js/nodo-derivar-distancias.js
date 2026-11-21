/*
 * Distancia por calle del panel «Derivar» de la mesa de Emergencia (Cambio 520, fase 2).
 *
 * La vista publica en #derivar-distancias-config (json_script):
 *   origen     {lat, lng} del domicilio de la familia, o null si todavía no está ubicado.
 *   direccion  «calle, localidad, Chaco, Argentina» para ubicarlo con el Geocoder si origen es null.
 *   ubicar_url POST que guarda el punto del domicilio (csrf del formulario de la página).
 *   destinos   [{clave, lat, lng} o {clave, direccion}]: los edificios más cercanos en línea recta, sin
 *              los de ubicación reservada (esos nunca salen hacia Google).
 *
 * A pedido (SEC-33, Cambio 493): recién con el botón [data-derivar-por-calle] se le manda algo a Google.
 * Ubica el domicilio si hace falta, pide una matriz de rutas en auto (RouteMatrix; DistanceMatrixService si
 * la librería «routes» no está) y reemplaza el texto de cada tarjeta por «a 4,3 km por calle · 12 min».
 * Sin key, sin red o con la key rechazada, las tarjetas quedan con la distancia en línea recta y
 * [data-derivar-por-calle-estado] lo dice.
 */
(function () {
  'use strict';
  var nodo = document.getElementById('derivar-distancias-config');
  if (!nodo || !window.NodoMapa || !window.NodoMapa.configurado) { return; }
  var config;
  try { config = JSON.parse(nodo.textContent) || {}; } catch (e) { return; }
  var destinos = config.destinos || [];
  if (!destinos.length) { return; }

  // Un punto o una dirección: las dos APIs aceptan las dos formas.
  function lugar(destino) {
    return destino.direccion ? destino.direccion : { lat: destino.lat, lng: destino.lng };
  }

  function km(metros) {
    return (metros / 1000).toFixed(1).replace('.', ',');
  }

  function minutos(segundos) {
    var total = Math.max(1, Math.round(segundos / 60));
    if (total < 60) { return total + ' min'; }
    var horas = Math.floor(total / 60);
    var resto = total % 60;
    return horas + ' h' + (resto ? ' ' + resto + ' min' : '');
  }

  function pintar(clave, metros, segundos) {
    var tarjeta = document.querySelector('[data-derivar-clave="' + clave + '"] [data-distancia]');
    if (!tarjeta) { return; }
    tarjeta.textContent = 'a ' + km(metros) + ' km por calle' + (segundos ? ' · ' + minutos(segundos) : '');
  }

  function csrf() {
    var campo = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return campo ? campo.value : '';
  }

  function ubicarDomicilio() {
    if (config.origen) { return Promise.resolve(config.origen); }
    if (!config.direccion) { return Promise.reject(new Error('Sin dirección')); }
    return window.NodoMapa.importar('geocoding').then(function (librerias) {
      var geocoder = new librerias[0].Geocoder();
      return geocoder.geocode({ address: config.direccion, region: 'ar', componentRestrictions: { country: 'AR' } });
    }).then(function (respuesta) {
      var resultado = respuesta && respuesta.results && respuesta.results[0];
      if (!resultado) { throw new Error('Google no encontró el domicilio'); }
      var punto = { lat: resultado.geometry.location.lat(), lng: resultado.geometry.location.lng() };
      if (config.ubicar_url) {
        var datos = new FormData();
        datos.append('latitud', punto.lat.toFixed(6));
        datos.append('longitud', punto.lng.toFixed(6));
        // Si no se guarda, la distancia igual se calcula: se vuelve a ubicar la próxima vez.
        fetch(config.ubicar_url, {
          method: 'POST',
          body: datos,
          credentials: 'same-origin',
          headers: { 'X-CSRFToken': csrf(), 'X-Requested-With': 'XMLHttpRequest' }
        }).catch(function () {});
      }
      return punto;
    });
  }

  function conRouteMatrix(rutas, origen) {
    return rutas.RouteMatrix.computeRouteMatrix({
      origins: [origen],
      destinations: destinos.map(lugar),
      travelMode: 'DRIVING',
      fields: ['distanceMeters', 'durationMillis', 'condition']
    }).then(function (resultado) {
      var fila = (resultado.matrix && resultado.matrix.rows && resultado.matrix.rows[0]) || { items: [] };
      fila.items.forEach(function (item, indice) {
        if (item && item.distanceMeters != null && item.condition !== 'ROUTE_NOT_FOUND') {
          pintar(destinos[indice].clave, item.distanceMeters, (item.durationMillis || 0) / 1000);
        }
      });
    });
  }

  function conDistanceMatrix(origen) {
    return new Promise(function (resolve, reject) {
      var servicio = new window.google.maps.DistanceMatrixService();
      servicio.getDistanceMatrix({
        origins: [origen],
        destinations: destinos.map(lugar),
        travelMode: 'DRIVING'
      }, function (respuesta, estado) {
        if (estado !== 'OK') { reject(new Error(estado)); return; }
        respuesta.rows[0].elements.forEach(function (elemento, indice) {
          if (elemento.status === 'OK') {
            pintar(destinos[indice].clave, elemento.distance.value, elemento.duration.value);
          }
        });
        resolve();
      });
    });
  }

  var boton = document.querySelector('[data-derivar-por-calle]');
  var estado = document.querySelector('[data-derivar-por-calle-estado]');
  if (!boton) { return; }
  boton.hidden = false;

  function avisar(texto) {
    if (!estado) { return; }
    estado.textContent = texto;
    estado.hidden = false;
  }

  boton.addEventListener('click', function () {
    boton.disabled = true;
    avisar('Calculando la distancia por calle…');
    ubicarDomicilio().then(function (origen) {
      return window.NodoMapa.importar('routes').then(function (librerias) {
        var rutas = librerias[0];
        if (rutas && rutas.RouteMatrix && rutas.RouteMatrix.computeRouteMatrix) { return conRouteMatrix(rutas, origen); }
        return conDistanceMatrix(origen);
      });
    }).then(function () {
      boton.hidden = true;
      avisar('Distancia por calle en auto, según Google, para los ' + destinos.length + ' edificios más cercanos.');
    }).catch(function () {
      boton.disabled = false;
      avisar('No se pudo calcular la distancia por calle. Quedan las distancias en línea recta.');
    });
  });

  document.addEventListener('nodo-mapa:error', function () {
    boton.disabled = true;
    avisar('Google Maps no está disponible en este sitio. Quedan las distancias en línea recta.');
  });
})();
