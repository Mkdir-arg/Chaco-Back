/* Dispositivos · P3: resumen «Qué falta para validar» y estado del botón Enviar a validación.
   Sacado de legajo/form.html (P3) sin cambiar la lógica; lo carga el bloque customJS de esa pantalla. */
(function () {
  const requisitos = Array.from(document.querySelectorAll('[data-requisito-campo]'));
  const enviar = document.querySelector('button[value="enviar_validacion"]');
  function actualizarFaltantes() {
    // Los obligatorios del formulario del tipo y, en el alta, los del responsable los
    // ponen en la lista sus propios scripts.
    let faltantes = document.querySelectorAll('[data-faltante-formulario]').length
      + document.querySelectorAll('[data-faltante-responsable]:not(.hidden)').length;
    requisitos.forEach(function (fila) {
      const campo = document.getElementById(fila.dataset.requisitoCampo);
      const falta = !campo.value.trim();
      fila.classList.toggle('hidden', !falta);
      if (falta) faltantes++;
    });
    document.querySelector('[data-validacion-completa]').classList.toggle('hidden', faltantes > 0);
    if (enviar) enviar.disabled = faltantes > 0;
  }
  requisitos.forEach(function (fila) {
    document.getElementById(fila.dataset.requisitoCampo).addEventListener('input', actualizarFaltantes);
  });
  document.addEventListener('formulario-tipo:faltantes', actualizarFaltantes);
  actualizarFaltantes();
}());
