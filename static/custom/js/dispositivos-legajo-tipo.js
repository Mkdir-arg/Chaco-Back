/* Dispositivos · P3: formulario «Crear dispositivo» del tipo (P17), se reemplaza al cambiar el tipo.
   Sacado de legajo/form.html (P3) sin cambiar la lógica; lo carga el bloque customJS de esa pantalla. */
(function () {
  // Formulario «Crear dispositivo» del tipo (P17). Al cambiar el tipo se reemplaza la
  // sección por la del tipo nuevo. Las condiciones las evalúa NodoFormularioTipo (con
  // NodoCondiciones, el mismo motor que el servidor, que las vuelve a evaluar al guardar) y lo
  // oculto se deshabilita para que no viaje. Los obligatorios visibles sin responder
  // van al resumen «Qué falta para validar».
  const seccion = document.querySelector('[data-formulario-tipo]');
  const tipo = document.getElementById('id_tipo');
  const lista = document.querySelector('[data-faltantes-validacion]');
  if (!seccion || !tipo || !lista) return;
  let controller;

  const formulario = window.NodoFormularioTipo.montar(seccion, {
    archivoGuardado: true,  // sin archivo nuevo vale el que ya estaba guardado
    alAplicar: function (info) {
      lista.querySelectorAll('[data-faltante-formulario]').forEach(function (fila) { fila.remove(); });
      info.faltantes.forEach(function (texto) {
        const fila = document.createElement('li');
        fila.dataset.faltanteFormulario = '';
        fila.textContent = texto;
        lista.appendChild(fila);
      });
      document.dispatchEvent(new CustomEvent('formulario-tipo:faltantes'));
    },
  });
  const aplicar = formulario.aplicar;
  async function cargar() {
    if (controller) controller.abort();
    if (!tipo.value) { seccion.replaceChildren(); aplicar(); return; }
    controller = new AbortController();
    const params = new URLSearchParams({tipo: tipo.value});
    if (seccion.dataset.dispositivo) params.set('dispositivo', seccion.dataset.dispositivo);
    const respuesta = await fetch(seccion.dataset.url + '?' + params, {signal: controller.signal, headers: {'X-Requested-With': 'XMLHttpRequest'}});
    if (!respuesta.ok) throw new Error('No se pudo cargar el formulario del tipo.');
    seccion.innerHTML = await respuesta.text();
    // El formulario del tipo llega por fetch: los campos con presentación buscador se montan acá.
    if (window.nodoBuscador) window.nodoBuscador.montar(seccion);
    aplicar();
  }
  tipo.addEventListener('change', function () {
    cargar().catch(function (error) {
      if (error.name === 'AbortError') return;
      console.error('No se pudo cargar el formulario del tipo.', error);
      // Sin la sección, guardar vuelve con ella dibujada para completarla.
      seccion.replaceChildren();
      aplicar();
      if (typeof window.toast === 'function') {
        window.toast('error', 'No se pudo cargar el formulario del tipo. Al guardar se muestra para completarlo.');
      }
    });
  });
}());
