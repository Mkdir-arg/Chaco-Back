/*
 * `/mapa/` (mapa/templates/mapa/mapa.html): lo que la pieza Mapa con capas no hace porque guarda.
 * Agregar un punto (modo clic + modal), moverlo (PATCH al soltarlo) y eliminarlo (ModernModal + DELETE).
 * Habla con `/mapa/api/puntos/` con el token CSRF de Django; el servidor vuelve a validar todo.
 * Solo se carga con `mapa.editar`.
 */
(function () {
  'use strict';

  var contenedor = document.querySelector('[data-mapa-capas="mapa"]');
  var form = document.querySelector('[data-mapa-form]');
  if (!contenedor || !form) { return; }
  var api = function () { return contenedor.nodoMapaCapas; };
  var botonAgregar = document.querySelector('[data-mapa-agregar]');
  var barra = document.querySelector('[data-mapa-barra]');
  var lista = document.querySelector('[data-mapa-lista]');
  var urlPuntos = form.getAttribute('action');

  // Copia de cada punto, para volverlo a su lugar si el servidor rechaza un movimiento.
  var copias = {};
  try {
    JSON.parse(document.getElementById(contenedor.getAttribute('data-puntos')).textContent).forEach(function (p) { copias[p.id] = p; });
  } catch (e) { copias = {}; }

  function token() {
    var campo = form.querySelector('input[name="csrfmiddlewaretoken"]');
    return campo ? campo.value : '';
  }
  function aviso(tipo, mensaje) { if (typeof window.toast === 'function') { window.toast(tipo, mensaje); } }
  function pk(id) { return String(id).replace(/^punto-/, ''); }
  function pedir(metodo, url, cuerpo, tipo) {
    var cabeceras = { 'X-CSRFToken': token(), 'X-Requested-With': 'XMLHttpRequest' };
    if (tipo) { cabeceras['Content-Type'] = tipo; }
    return fetch(url, { method: metodo, headers: cabeceras, body: cuerpo, credentials: 'same-origin' }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (datos) { return { status: r.status, datos: datos || {} }; });
    });
  }
  function errorGeneral(r) {
    if (r.status === 403 || r.status === 401) { return r.datos.message || 'No tenés permiso para hacer esto en el mapa.'; }
    if (r.status === 404) { return 'Ese punto ya no existe. Recargá la página.'; }
    return r.datos.message || 'Ocurrió un error del sistema. Si persiste, avisá al administrador.';
  }

  // ---------- agregar ----------
  function modoAgregar(si) {
    api().modoClic(si);
    if (barra) { barra.hidden = !si; }
    if (botonAgregar) { botonAgregar.setAttribute('aria-pressed', si ? 'true' : 'false'); }
  }
  if (botonAgregar) { botonAgregar.addEventListener('click', function () { modoAgregar(botonAgregar.getAttribute('aria-pressed') !== 'true'); }); }
  var cancelar = document.querySelector('[data-mapa-agregar-cancelar]');
  if (cancelar) { cancelar.addEventListener('click', function () { modoAgregar(false); }); }
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && barra && !barra.hidden) { modoAgregar(false); }
  });

  // El envío, los errores bajo cada campo, «Guardando…» y el aviso los hace _ajax_js.html (data-ajax).
  contenedor.addEventListener('nodo-mapa-capas:clic', function (e) {
    modoAgregar(false);
    form.reset();
    // Los errores de un alta anterior que se canceló no se arrastran al punto nuevo.
    if (window.becasAjax) { window.becasAjax.limpiarErrores(form); }
    form.elements.latitud.value = e.detail.lat.toFixed(6);
    form.elements.longitud.value = e.detail.lng.toFixed(6);
    form.querySelector('[data-mapa-form-posicion]').textContent =
      'Ubicación: ' + e.detail.lat.toFixed(6) + ', ' + e.detail.lng.toFixed(6) + '. Después la podés ajustar arrastrando el marcador.';
    window.dispatchEvent(new CustomEvent('mapa-punto-abrir'));
  });

  // Guardado: la pantalla solo suma el punto al mapa y su ítem (HTML de components/_item_lista.html, del servidor).
  window.addEventListener('becas-saved', function (e) {
    var datos = e.detail || {};
    var p = datos.punto;
    if (!p || !p.id) { return; }
    copias[p.id] = p;
    if (lista && typeof datos.item === 'string') { lista.insertAdjacentHTML('beforeend', datos.item); }
    api().agregar(p);
    api().seleccionar(p.id);
  });

  // ---------- mover ----------
  contenedor.addEventListener('nodo-mapa-capas:movido', function (e) {
    var id = e.detail.id;
    var cuerpo = JSON.stringify({ latitud: e.detail.lat.toFixed(6), longitud: e.detail.lng.toFixed(6) });
    pedir('PATCH', urlPuntos + pk(id) + '/', cuerpo, 'application/json').then(function (r) {
      if (r.status === 200 && r.datos.ok) {
        copias[id] = r.datos.punto;
        aviso('success', r.datos.message);
        return;
      }
      volverAtras(id);
      aviso('error', r.status === 400 ? 'Esa ubicación no es válida: el punto volvió a su lugar.' : errorGeneral(r));
    }).catch(function () {
      volverAtras(id);
      aviso('error', 'No se pudo guardar la nueva ubicación: el punto volvió a su lugar.');
    });
  });
  function volverAtras(id) {
    if (!copias[id]) { return; }
    api().quitar(id);
    api().agregar(copias[id]);
  }

  // ---------- eliminar ----------
  contenedor.addEventListener('nodo-mapa-capas:accion', function (e) {
    if (e.detail.accion !== 'eliminar') { return; }
    var id = e.detail.id;
    var p = copias[id];
    var nombre = p ? p.titulo : 'el punto';
    var borrar = function () {
      pedir('DELETE', urlPuntos + pk(id) + '/').then(function (r) {
        if (r.status === 200 && r.datos.ok) {
          api().quitar(id);
          delete copias[id];
          var item = lista && lista.querySelector('[data-item="' + CSS.escape(id) + '"]');
          if (item) { item.remove(); }
          aviso('success', r.datos.message);
          return;
        }
        aviso('error', errorGeneral(r));
      }).catch(function () {
        aviso('error', 'No se pudo conectar con el servidor. Revisá la conexión y reintentá.');
      });
    };
    if (!window.ModernModal || typeof window.ModernModal.show !== 'function') { return; }
    window.ModernModal.show({
      type: 'confirm',
      danger: true,
      title: '¿Eliminar el punto?',
      message: '«' + nombre + '» deja de verse en el mapa para todos. No se puede deshacer.',
      confirmText: 'Eliminar',
      cancelText: 'Cancelar',
      onConfirm: borrar
    });
  });
})();
