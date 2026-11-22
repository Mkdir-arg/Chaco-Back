/* Dispositivos · P3 (alta): contacto del legajo desde el primer responsable elegido.
   Sacado de legajo/form.html (P3) sin cambiar la lógica; lo carga el bloque customJS de esa pantalla. */
(function () {
  // Alta (Cambio 450): el contacto del legajo sale de la primera persona elegida en el
  // buscador. Se muestra debajo y, si no hay nadie o su perfil no trae un nombre o un
  // teléfono válidos, va al resumen «Qué falta para validar». El servidor copia los mismos
  // datos al guardar.
  const select = document.getElementById('id_responsables');
  const contacto = document.querySelector('[data-contacto-responsable]');
  const ninguno = document.querySelector('[data-faltante-responsable="ninguno"]');
  const sinNombre = document.querySelector('[data-faltante-responsable="nombre"]');
  const sinTelefono = document.querySelector('[data-faltante-responsable="telefono"]');
  if (!select || !contacto || !ninguno || !sinNombre || !sinTelefono) return;
  function actualizar() {
    const primera = Array.from(select.options).find(function (opcion) { return opcion.selected; });
    const persona = primera ? primera.dataset.persona || '' : '';
    const nombre = primera ? primera.dataset.nombre || '' : '';
    const telefono = primera ? primera.dataset.telefono || '' : '';
    contacto.classList.toggle('hidden', !primera);
    contacto.querySelector('[data-contacto-texto]').textContent = primera ? persona + ' · ' + (telefono || 'sin teléfono en su perfil') : '';
    ninguno.classList.toggle('hidden', !!primera);
    sinNombre.classList.toggle('hidden', !primera || !!nombre);
    sinTelefono.classList.toggle('hidden', !primera || !!telefono);
    [sinNombre, sinTelefono].forEach(function (fila) { fila.querySelector('[data-nombre-responsable]').textContent = persona; });
    document.dispatchEvent(new CustomEvent('formulario-tipo:faltantes'));
  }
  select.addEventListener('change', actualizar);
  actualizar();
}());
