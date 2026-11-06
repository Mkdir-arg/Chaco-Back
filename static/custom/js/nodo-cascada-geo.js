/* NODO — Cascada Provincia → Localidad del catálogo (Cambio 418)
 *
 * Los datos van embebidos en la página (<script id="catalogos-geo">: provincias
 * y localidades por provincia), sin endpoint público. El <select data-geo=
 * "localidad"> llega vacío del servidor y se llena acá con las localidades de
 * la provincia elegida; su atributo data-geo-provincia es el nombre del campo
 * de la Provincia. data-geo-valor es la localidad que había elegido la persona
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

    function poblar(selectLocalidad, provincia, elegida) {
        var nombres = porProvincia[provincia] || [];
        selectLocalidad.innerHTML = '';
        if (!provincia) {
            selectLocalidad.appendChild(opcion('', 'Elegí primero la provincia'));
            return;
        }
        selectLocalidad.appendChild(opcion('', nombres.length ? 'Elegí una localidad' : 'La provincia no tiene localidades cargadas'));
        var fragmento = document.createDocumentFragment();
        nombres.forEach(function (nombre) {
            fragmento.appendChild(opcion(nombre, nombre));
        });
        selectLocalidad.appendChild(fragmento);
        if (elegida && nombres.indexOf(elegida) !== -1) selectLocalidad.value = elegida;
    }

    function provinciaDe(selectLocalidad) {
        var form = selectLocalidad.closest('form');
        var nombre = selectLocalidad.getAttribute('data-geo-provincia');
        return form && nombre ? form.querySelector('[name="' + nombre + '"]') : null;
    }

    function iniciar(selectLocalidad) {
        var selectProvincia = provinciaDe(selectLocalidad);
        poblar(selectLocalidad, selectProvincia ? selectProvincia.value : '', selectLocalidad.getAttribute('data-geo-valor') || '');
    }

    document.querySelectorAll('select[data-geo="localidad"]').forEach(iniciar);

    document.addEventListener('change', function (e) {
        var el = e.target;
        if (!(el instanceof HTMLSelectElement) || el.getAttribute('data-geo') !== 'provincia') return;
        var form = el.closest('form');
        if (!form) return;
        form.querySelectorAll('select[data-geo="localidad"]').forEach(function (loc) {
            if (provinciaDe(loc) === el) poblar(loc, el.value, '');
        });
    });
})();
