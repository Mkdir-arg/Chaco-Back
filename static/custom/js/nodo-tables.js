/* NODO — pista de scroll horizontal en tablas (mejora progresiva).
   Marca con `nodo-scroll-mas` a cada `.overflow-x-auto` que tiene una tabla con
   contenido oculto a la derecha; el CSS de nodo-tables.css dibuja la sombra.
   Si el script no carga, la tabla funciona igual. */
(function () {
    'use strict';

    function actualizar(el) {
        var oculto = el.scrollWidth - el.clientWidth - el.scrollLeft > 1;
        el.classList.toggle('nodo-scroll-mas', oculto);
    }

    function iniciar(el) {
        if (el.dataset.nodoScrollInit === '1' || !el.querySelector('.nodo-col-acciones')) return;
        el.dataset.nodoScrollInit = '1';
        el.addEventListener('scroll', function () { actualizar(el); }, { passive: true });
        if (window.ResizeObserver) {
            var ro = new ResizeObserver(function () { actualizar(el); });
            ro.observe(el);
            var tabla = el.querySelector('table');
            if (tabla) ro.observe(tabla);
        }
        actualizar(el);
    }

    function barrer() {
        document.querySelectorAll('.overflow-x-auto').forEach(iniciar);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', barrer);
    } else {
        barrer();
    }
    window.addEventListener('resize', barrer);
    document.addEventListener('alpine:initialized', barrer);
})();
