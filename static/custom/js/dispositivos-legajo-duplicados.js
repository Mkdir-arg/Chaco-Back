/* Dispositivos · P3 (alta): búsqueda de duplicados y confirmación de coincidencias. La URL viaja en data-url del propio <script>.
   Sacado de legajo/form.html (P3) sin cambiar la lógica; lo carga el bloque customJS de esa pantalla. */
(function () {
  // Se lee ahora: dentro de los callbacks asíncronos `currentScript` ya es null.
  const urlDuplicados = document.currentScript.dataset.url;
  const codigo = document.getElementById('id_codigo');
  const nombre = document.getElementById('id_nombre');
  const localidad = document.getElementById('id_localidad');
  const aviso = document.getElementById('duplicate-search');
  const vacio = document.getElementById('duplicate-empty');
  const contador = document.getElementById('duplicate-count');
  const formulario = codigo.closest('form');
  let controller;
  let enviando = false;
  let accion;

  function mostrarCoincidencias(data) {
    contador.textContent = data.coincidencias.length;
    vacio.classList.toggle('hidden', data.codigo_duplicado || data.coincidencias.length > 0);
    if (!data.codigo_duplicado && !data.coincidencias.length) { aviso.classList.add('hidden'); return; }
    const mensaje = aviso.querySelector('[data-duplicados-mensaje]');
    mensaje.textContent = data.codigo_duplicado ? 'El código ya está en uso. No se podrá guardar un duplicado.' : 'Posible coincidencia. Podés continuar si es una institución diferente.';
    const lista = document.createElement('ul');
    lista.className = 'mt-2 list-disc pl-5';
    data.coincidencias.forEach(function (item) {
      const fila = document.createElement('li');
      fila.textContent = item.codigo + ' · ' + item.nombre + ' (' + (item.localidad || 'sin localidad') + ')';
      lista.appendChild(fila);
    });
    aviso.querySelector('[data-duplicados-lista]').replaceChildren(lista);
    aviso.classList.remove('hidden');
  }

  async function buscar() {
    if (!codigo.value.trim() && !(nombre.value.trim() && localidad.value.trim())) {
      aviso.classList.add('hidden');
      vacio.classList.remove('hidden');
      contador.textContent = 0;
      return {codigo_duplicado: false, coincidencias: []};
    }
    if (controller) controller.abort();
    controller = new AbortController();
    const params = new URLSearchParams({codigo: codigo.value, nombre: nombre.value, localidad: localidad.value});
    const response = await fetch(urlDuplicados + '?' + params, {signal: controller.signal, headers: {'X-Requested-With': 'XMLHttpRequest'}});
    if (!response.ok) throw new Error('No se pudo verificar duplicados.');
    const data = await response.json();
    mostrarCoincidencias(data);
    return data;
  }
  [codigo, nombre, localidad].forEach(function (input) {
    input.addEventListener('blur', function () { buscar().catch(function (error) {
      if (error.name !== 'AbortError') {
        console.error('No se pudo verificar duplicados.', error);
        aviso.classList.add('hidden');
      }
    }); });
  });
  formulario.addEventListener('submit', function (event) {
    if (enviando) return;
    event.preventDefault();
    accion = event.submitter;
    buscar().then(function (data) {
      if (data.codigo_duplicado) {
        aviso.scrollIntoView({block: 'center'});
        aviso.focus({preventScroll: true});
        return;
      }
      if (!data.coincidencias.length) { enviar(); return; }
      confirmarCoincidencias();
    }).catch(function (error) {
      if (error.name !== 'AbortError') {
        console.error('No se pudo verificar duplicados.', error);
        if (typeof window.toast === 'function') {
          window.toast('error', 'No se pudo verificar duplicados. Reintentá antes de guardar.');
        }
      }
    });
  });

  // Coincidencia blanda (nombre y localidad): avisa y deja seguir. No es destructiva,
  // así que el modal va en `warning` con el botón de marca. Sin ModernModal —que el
  // shell siempre carga— no se envía a ciegas: el aviso lateral ya muestra cuáles son.
  function confirmarCoincidencias() {
    if (!window.ModernModal || typeof window.ModernModal.show !== 'function') {
      aviso.scrollIntoView({block: 'center'});
      aviso.focus({preventScroll: true});
      return;
    }
    window.ModernModal.show({
      type: 'confirm',
      icon: 'warning',
      title: '¿Confirmás el alta?',
      message: 'Hay una institución con nombre y localidad coincidentes.',
      confirmText: 'Sí, es diferente',
      cancelText: 'Revisar datos',
      onConfirm: enviar,
    });
  }
  function enviar() {
    enviando = true;
    formulario.requestSubmit(accion);
  }
}());
