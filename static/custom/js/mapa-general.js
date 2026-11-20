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

  function limpiarErrores() {
    form.querySelectorAll('[data-error]').forEach(function (p) { p.textContent = ''; p.classList.add('hidden'); });
    form.querySelectorAll('[aria-invalid]').forEach(function (c) { c.removeAttribute('aria-invalid'); });
  }
  contenedor.addEventListener('nodo-mapa-capas:clic', function (e) {
    modoAgregar(false);
    form.reset();
    limpiarErrores();
    form.elements.latitud.value = e.detail.lat.toFixed(6);
    form.elements.longitud.value = e.detail.lng.toFixed(6);
    form.querySelector('[data-mapa-form-posicion]').textContent =
      'Ubicación: ' + e.detail.lat.toFixed(6) + ', ' + e.detail.lng.toFixed(6) + '. Después la podés ajustar arrastrando el marcador.';
    window.dispatchEvent(new CustomEvent('mapa-punto-abrir'));
  });
  window.addEventListener('mapa-punto-cancelar', function () { window.dispatchEvent(new CustomEvent('mapa-punto-cerrar')); });

  function itemDeLista(p) {
    var boton = document.createElement('button');
    boton.type = 'button';
    boton.className = 'nodo-item-lista';
    boton.setAttribute('aria-pressed', 'false');
    boton.setAttribute('data-item', p.id);
    var texto = document.createElement('span');
    texto.className = 'nodo-item-lista__texto';
    texto.title = p.titulo;
    var nombre = document.createElement('span');
    nombre.className = 'nodo-item-lista__nombre';
    nombre.textContent = p.titulo;
    texto.appendChild(nombre);
    if (p.subtitulo) {
      var meta = document.createElement('span');
      meta.className = 'nodo-item-lista__meta';
      meta.textContent = p.subtitulo;
      texto.appendChild(meta);
    }
    boton.appendChild(texto);
    return boton;
  }

  var enviando = false;
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    if (enviando) { return; }
    enviando = true;
    limpiarErrores();
    var boton = form.querySelector('[type="submit"]');
    if (boton) { boton.disabled = true; }
    pedir('POST', urlPuntos, new FormData(form)).then(function (r) {
      if (r.status === 201 && r.datos.ok) {
        var p = r.datos.punto;
        copias[p.id] = p;
        if (lista) { lista.appendChild(itemDeLista(p)); }
        api().agregar(p);
        api().seleccionar(p.id);
        window.dispatchEvent(new CustomEvent('mapa-punto-cerrar'));
        aviso('success', r.datos.message);
        return;
      }
      if (r.status === 400 && r.datos.errors) {
        Object.keys(r.datos.errors).forEach(function (campo) {
          var caja = form.querySelector('[data-error="' + campo + '"]') || form.querySelector('[data-error="__all__"]');
          if (!caja) { return; }
          caja.textContent = r.datos.errors[campo].join(' ');
          caja.classList.remove('hidden');
          var control = form.elements[campo];
          if (control && control.setAttribute) { control.setAttribute('aria-invalid', 'true'); }
        });
        var primero = form.querySelector('[aria-invalid="true"]');
        if (primero) { primero.focus(); }
        aviso('error', 'Revisá los datos del punto.');
        return;
      }
      aviso('error', errorGeneral(r));
    }).catch(function () {
      aviso('error', 'No se pudo conectar con el servidor. Revisá la conexión y reintentá.');
    }).finally(function () {
      enviando = false;
      if (boton) { boton.disabled = false; }
    });
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
