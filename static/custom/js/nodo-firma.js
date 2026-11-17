/**
 * Recuadro de firma de los formularios del constructor (Cambio 480): `programas/widgets/firma.html`.
 *
 * Se dibuja con eventos de puntero (dedo, lápiz o mouse) sobre un `<canvas>` de 600x200 con fondo
 * blanco. Al terminar cada trazo, el PNG (`toDataURL`) se escribe en el campo oculto
 * `[data-firma-trazo]` y se dispara `change`, que es lo que escuchan las condiciones y el panel de
 * faltantes. «Limpiar» vacía el recuadro y el campo. Todo por delegación sobre `document`: sirve para
 * los formularios que llegan después por AJAX, y el script se puede cargar más de una vez.
 */
(function () {
  'use strict';
  if (window.__nodoFirma) { return; }
  window.__nodoFirma = true;

  var dibujando = null;

  function caja(elemento) { return elemento.closest('[data-firma]'); }

  function preparar(canvas) {
    if (canvas.dataset.listo) { return canvas.getContext('2d'); }
    var ctx = canvas.getContext('2d');
    // La imagen se guarda: fondo blanco y trazo oscuro también con el tema oscuro (token del texto principal claro).
    ctx.fillStyle = 'white';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.lineWidth = 2.5;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.strokeStyle = 'black';
    canvas.dataset.listo = '1';
    return ctx;
  }

  function punto(canvas, evento) {
    var rect = canvas.getBoundingClientRect();
    return {
      x: (evento.clientX - rect.left) * (canvas.width / rect.width),
      y: (evento.clientY - rect.top) * (canvas.height / rect.height),
    };
  }

  function guardar(canvas) {
    var oculto = caja(canvas).querySelector('[data-firma-trazo]');
    if (!oculto) { return; }
    oculto.value = canvas.dataset.trazado ? canvas.toDataURL('image/png') : '';
    oculto.dispatchEvent(new Event('change', { bubbles: true }));
  }

  document.addEventListener('pointerdown', function (evento) {
    var canvas = evento.target.closest && evento.target.closest('[data-firma-canvas]');
    if (!canvas || canvas.closest('[disabled], [hidden]')) { return; }
    evento.preventDefault();
    var ctx = preparar(canvas);
    var p = punto(canvas, evento);
    ctx.beginPath();
    ctx.moveTo(p.x, p.y);
    ctx.lineTo(p.x + 0.1, p.y + 0.1);
    ctx.stroke();
    canvas.setPointerCapture(evento.pointerId);
    canvas.dataset.trazado = '1';
    dibujando = { canvas: canvas, ctx: ctx };
  });

  document.addEventListener('pointermove', function (evento) {
    if (!dibujando || evento.target !== dibujando.canvas) { return; }
    evento.preventDefault();
    var p = punto(dibujando.canvas, evento);
    dibujando.ctx.lineTo(p.x, p.y);
    dibujando.ctx.stroke();
  });

  function terminar() {
    if (!dibujando) { return; }
    guardar(dibujando.canvas);
    dibujando = null;
  }
  document.addEventListener('pointerup', terminar);
  document.addEventListener('pointercancel', terminar);

  document.addEventListener('click', function (evento) {
    var boton = evento.target.closest && evento.target.closest('[data-firma-limpiar]');
    if (!boton) { return; }
    var canvas = caja(boton).querySelector('[data-firma-canvas]');
    if (!canvas) { return; }
    delete canvas.dataset.listo;
    delete canvas.dataset.trazado;
    preparar(canvas);
    guardar(canvas);
  });

  // El fondo blanco desde el arranque: sin esto el canvas se ve transparente hasta el primer trazo.
  function pintarFondos(raiz) {
    (raiz || document).querySelectorAll('[data-firma-canvas]').forEach(function (canvas) {
      if (canvas.dataset.listo) { return; }
      var ctx = preparar(canvas);
      // Un formulario que volvió con errores trae el trazo en el campo oculto: se redibuja.
      var oculto = caja(canvas).querySelector('[data-firma-trazo]');
      if (oculto && oculto.value.indexOf('data:image/png;base64,') === 0) {
        var imagen = new Image();
        imagen.onload = function () { ctx.drawImage(imagen, 0, 0, canvas.width, canvas.height); };
        imagen.src = oculto.value;
        canvas.dataset.trazado = '1';
      }
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { pintarFondos(); });
  } else {
    pintarFondos();
  }
  new MutationObserver(function () { pintarFondos(); }).observe(document.documentElement, { childList: true, subtree: true });
})();
