/* NODO — Cascada Provincia → Localidad del catálogo (Cambio 418)
 *
 * Los datos van embebidos en la página (<script id="catalogos-geo">: provincias
 * y localidades por provincia), sin endpoint público. El <select data-geo=
 * "localidad"> llega vacío del servidor y se llena acá con las localidades de
 * la provincia elegida; su atributo data-geo-provincia es el nombre del campo
 * de la Provincia; sin esa Provincia visible se ofrecen todas las localidades,
 * sin repetir (data-geo-modo="todas"). data-geo-valor es la localidad que había elegido la persona
 * cuando el formulario vuelve con errores.
 *
 * El servidor revalida que la localidad sea de la provincia: esto es comodidad
 * de carga, no un control. Sin dependencias (el portal público no carga Alpine).
 */
(function () {
    'use strict';

    var nodo = document.getElementById('catalogos-geo');
    if (!nodo) return;
    var catalogos;
    try {
        catalogos = JSON.parse(nodo.textContent);
    } catch (e) {
        return;
    }
    var porProvincia = catalogos.localidades || {};

    function opcion(valor, texto) {
        var op = document.createElement('option');
        op.value = valor;
        op.textContent = texto;
        return op;
    }

    // Todas las localidades del catálogo, sin repetir y en orden: lo que el servidor
    // acepta cuando la Localidad llega sin Provincia que la filtre.
    var todas = (function () {
        var vistas = {};
        Object.keys(porProvincia).forEach(function (prov) {
            (porProvincia[prov] || []).forEach(function (n) { vistas[n] = true; });
        });
        return Object.keys(vistas).sort(function (x, y) { return x.localeCompare(y, 'es'); });
    })();

    function llenar(selectLocalidad, nombres, vacio, elegida) {
        selectLocalidad.innerHTML = '';
        selectLocalidad.appendChild(opcion('', vacio));
        var fragmento = document.createDocumentFragment();
        nombres.forEach(function (nombre) {
            fragmento.appendChild(opcion(nombre, nombre));
        });
        selectLocalidad.appendChild(fragmento);
        if (elegida && nombres.indexOf(elegida) !== -1) selectLocalidad.value = elegida;
    }

    function poblar(selectLocalidad, provincia, elegida) {
        if (!provincia) {
            selectLocalidad.innerHTML = '';
            selectLocalidad.appendChild(opcion('', 'Elegí primero la provincia'));
            return;
        }
        var nombres = porProvincia[provincia] || [];
        llenar(selectLocalidad, nombres, nombres.length ? 'Elegí una localidad' : 'La provincia no tiene localidades cargadas', elegida);
    }

    function visible(el) {
        return !el.closest('[hidden]') && el.getClientRects().length > 0;
    }

    function provinciaDe(selectLocalidad) {
        var form = selectLocalidad.closest('form');
        var nombre = selectLocalidad.getAttribute('data-geo-provincia');
        return form && nombre ? form.querySelector('[name="' + nombre + '"]') : null;
    }

    // Sin Provincia en la página, o con la Provincia oculta (otro canal, una
    // condición del diseño), no hay con qué filtrar: se ofrecen todas.
    function iniciar(selectLocalidad, elegida) {
        var selectProvincia = provinciaDe(selectLocalidad);
        if (!selectProvincia || !visible(selectProvincia)) {
            selectLocalidad.setAttribute('data-geo-modo', 'todas');
            llenar(selectLocalidad, todas, 'Elegí una localidad', elegida);
            return;
        }
        selectLocalidad.removeAttribute('data-geo-modo');
        poblar(selectLocalidad, selectProvincia.value, elegida);
    }

    // La pasada inicial espera a DOMContentLoaded: nodo-formulario.js aplica las
    // condiciones ahí, y hasta entonces una Provincia oculta por condición todavía
    // cuenta como visible. Este script carga después, así que su listener corre después.
    function arrancar() {
        document.querySelectorAll('select[data-geo="localidad"]').forEach(function (loc) {
            iniciar(loc, loc.getAttribute('data-geo-valor') || '');
        });
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', arrancar);
    else arrancar();

    document.addEventListener('change', function (e) {
        var el = e.target;
        var form = el instanceof Element ? el.closest('form') : null;
        if (!form) return;
        var esProvincia = el instanceof HTMLSelectElement && el.getAttribute('data-geo') === 'provincia';
        form.querySelectorAll('select[data-geo="localidad"]').forEach(function (loc) {
            if (esProvincia && provinciaDe(loc) === el) {
                poblar(loc, el.value, '');
            } else if (!esProvincia) {
                // Una condición pudo ocultar o mostrar la Provincia: se reevalúa el modo.
                var antes = loc.getAttribute('data-geo-modo') === 'todas';
                var sel = provinciaDe(loc);
                var ahora = !sel || !visible(sel);
                if (antes !== ahora) iniciar(loc, loc.value || loc.getAttribute('data-geo-valor') || '');
            }
        });
    });
})();
