/* Dispositivos · P3: horario de atención (formset de franjas) con Agregar y Quitar.
   Sacado de legajo/form.html (P3) sin cambiar la lógica; lo carga el bloque customJS de esa pantalla. */
(function () {
  // Horario de atención: «Agregar» pasa la primera fila vacía a la tabla como una fila nueva
  // del formset, y «Quitar» la marca para borrar y la oculta. Las mismas reglas que acá
  // avisan al lado del control las vuelve a exigir el servidor al guardar.
  const bloque = document.querySelector('[data-franjas]');
  if (!bloque) return;
  const prefijo = bloque.dataset.prefijo;
  const total = document.getElementById('id_' + prefijo + '-TOTAL_FORMS');
  const filas = bloque.querySelector('[data-franjas-filas]');
  const vacio = bloque.querySelector('[data-franjas-vacio]');
  const vacias = Array.from(bloque.querySelectorAll('[data-franja-vacia]'));
  const agregar = bloque.querySelector('[data-franja-agregar]');
  const MAX_POR_DIA = 4;
  if (!vacias.length) return;
  const control = vacias[0];
  vacias.slice(1).forEach(function (fila) { fila.classList.add('hidden'); });
  bloque.querySelector('[data-ayuda-sin-js]').classList.add('hidden');
  agregar.classList.remove('hidden');
  const dia = control.querySelector('select');
  const [desde, hasta] = control.querySelectorAll('input[type="time"]');

  function visibles() {
    return Array.from(filas.querySelectorAll('[data-franja]:not(.hidden)'));
  }
  function actualizarVacio() {
    vacio.classList.toggle('hidden', visibles().length > 0);
  }
  function quitar(fila) {
    const marca = fila.querySelector('input[type="checkbox"]');
    if (marca) { marca.checked = true; fila.classList.add('hidden'); } else { fila.remove(); }
    actualizarVacio();
  }
  function prepararQuitar(fila) {
    // Una franja que volvió del servidor ya marcada para quitar (el guardado falló por
    // otra cosa) se oculta y no cuenta para la validación de acá: el servidor la borra.
    const marca = fila.querySelector('input[type="checkbox"]');
    if (marca && marca.checked) fila.classList.add('hidden');
    const sinJs = fila.querySelector('[data-quitar-sin-js]');
    if (sinJs) sinJs.classList.add('hidden');
    const boton = fila.querySelector('[data-quitar]');
    boton.classList.remove('hidden');
    boton.addEventListener('click', function () { quitar(fila); });
  }
  function error(campo, mensaje) {
    const p = document.getElementById(campo.id + '-error');
    p.textContent = mensaje || '';
    p.classList.toggle('hidden', !mensaje);
    if (mensaje) campo.setAttribute('aria-invalid', 'true'); else campo.removeAttribute('aria-invalid');
  }
  function oculto(nombre, valor) {
    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = prefijo + '-' + total.value + '-' + nombre;
    input.value = valor;
    return input;
  }
  function celda(texto) {
    const td = document.createElement('td');
    td.className = 'nodo-td';
    td.textContent = texto;
    return td;
  }

  Array.from(filas.querySelectorAll('[data-franja]')).forEach(prepararQuitar);
  actualizarVacio();
  agregar.addEventListener('click', function () {
    [dia, desde, hasta].forEach(function (campo) { error(campo, ''); });
    let valido = true;
    if (!dia.value) { error(dia, 'Elegí el día.'); valido = false; }
    if (!desde.value) { error(desde, 'Indicá desde qué hora.'); valido = false; }
    if (!hasta.value) { error(hasta, 'Indicá hasta qué hora.'); valido = false; }
    if (!valido) return;
    if (desde.value >= hasta.value) { error(hasta, 'La hora «Hasta» tiene que ser posterior a «Desde».'); return; }
    const delDia = visibles().filter(function (fila) { return fila.dataset.dia === dia.value; });
    const pisada = delDia.find(function (fila) { return desde.value < fila.dataset.hasta && fila.dataset.desde < hasta.value; });
    const nombreDia = dia.options[dia.selectedIndex].text;
    if (pisada) {
      error(desde, 'Se superpone con la franja del ' + nombreDia.toLowerCase() + ' de ' + pisada.dataset.desde + ' a ' + pisada.dataset.hasta + '.');
      return;
    }
    if (delDia.length >= MAX_POR_DIA) { error(dia, 'Un día admite hasta ' + MAX_POR_DIA + ' franjas.'); return; }

    const fila = document.createElement('tr');
    fila.className = 'hover:bg-secondary';
    fila.dataset.franja = '';
    fila.dataset.dia = dia.value;
    fila.dataset.desde = desde.value;
    fila.dataset.hasta = hasta.value;
    const primera = celda(nombreDia);
    primera.classList.add('text-heading', 'font-medium');
    primera.append(oculto('dia', dia.value), oculto('hora_desde', desde.value), oculto('hora_hasta', hasta.value));
    const acciones = document.createElement('td');
    acciones.className = 'nodo-td nodo-col-acciones text-right';
    const boton = document.createElement('button');
    boton.type = 'button';
    boton.className = 'btn-nodo btn-tertiary btn-sm btn-fit';
    boton.dataset.quitar = '';
    boton.textContent = 'Quitar';
    boton.setAttribute('aria-label', 'Quitar la franja del ' + nombreDia.toLowerCase() + ' de ' + desde.value + ' a ' + hasta.value);
    acciones.append(boton);
    fila.append(primera, celda(desde.value), celda(hasta.value), acciones);
    total.value = Number(total.value) + 1;
    // En orden de día y hora, como queda al guardar.
    const despues = visibles().find(function (otra) {
      return Number(otra.dataset.dia) > Number(dia.value) || (otra.dataset.dia === dia.value && otra.dataset.desde > desde.value);
    });
    filas.insertBefore(fila, despues || vacio);
    prepararQuitar(fila);
    dia.value = '';
    desde.value = '';
    hasta.value = '';
    actualizarVacio();
    dia.focus();
  });
}());
