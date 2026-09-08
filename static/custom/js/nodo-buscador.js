/* NODO — Buscador con píldoras (Cambio 56)
 *
 * Monta un control de búsqueda sobre cualquier <select data-buscador>, simple o
 * múltiple. El <select> original NO se reemplaza: sigue en el DOM y es el que
 * viaja en el POST, así que la validación del servidor (ChoiceField /
 * MultipleChoiceField contra las opciones configuradas) no cambia en nada.
 *
 * Si este archivo no se carga o falla, la persona ve el desplegable nativo y el
 * formulario funciona igual: el control es una mejora, no un requisito.
 *
 * Sin dependencias: el shell del portal público no carga Alpine.
 */
(function () {
    'use strict';

    var ATTR = 'data-buscador';
    var seq = 0;

    function crear(tag, clase) {
        var el = document.createElement(tag);
        if (clase) el.className = clase;
        return el;
    }

    /* Comparación tolerante: sin acentos, sin mayúsculas. Buscar "educacion"
       tiene que encontrar "Educación". */
    function normalizar(texto) {
        var t = (texto || '').toLowerCase();
        if (t.normalize) t = t.normalize('NFD').replace(/[̀-ͯ]/g, '');
        return t;
    }

    function montar(select) {
        if (select.dataset.buscadorMontado === '1') return;
        select.dataset.buscadorMontado = '1';

        var multiple = select.multiple;
        var id = 'nodo-buscador-' + ++seq;
        // Las opciones reales del campo; la vacía ("Elegí una opción") no es un
        // valor elegible, es el placeholder del select simple.
        var opciones = Array.prototype.filter.call(select.options, function (o) {
            return o.value !== '';
        });

        var raiz = crear('div', 'nodo-buscador');
        var control = crear('div', 'nodo-buscador__control');
        var input = crear('input', 'nodo-buscador__input');
        var lista = crear('ul', 'nodo-buscador__lista');

        input.type = 'text';
        input.setAttribute('role', 'combobox');
        input.setAttribute('aria-expanded', 'false');
        input.setAttribute('aria-autocomplete', 'list');
        input.setAttribute('aria-controls', id);
        input.autocomplete = 'off';
        input.placeholder = select.getAttribute('data-buscador-placeholder') || 'Buscá una opción';
        // El <label for> del template apunta al select, que queda oculto: sin
        // esto el control nuevo se quedaría sin nombre accesible.
        var etiqueta = select.id ? document.querySelector('label[for="' + select.id + '"]') : null;
        if (etiqueta) input.setAttribute('aria-label', etiqueta.textContent.trim().replace(/\s*\*$/, ''));

        lista.id = id;
        lista.setAttribute('role', 'listbox');
        lista.hidden = true;
        if (multiple) lista.setAttribute('aria-multiselectable', 'true');

        control.appendChild(input);
        raiz.appendChild(control);
        raiz.appendChild(lista);
        select.parentNode.insertBefore(raiz, select);
        raiz.appendChild(select);
        select.classList.add('nodo-buscador__nativo');
        select.setAttribute('tabindex', '-1');
        select.setAttribute('aria-hidden', 'true');

        var activa = -1;

        function elegidas() {
            return opciones.filter(function (o) { return o.selected; });
        }

        function visibles() {
            return Array.prototype.filter.call(lista.children, function (li) {
                return li.dataset.valor !== undefined;
            });
        }

        function avisarCambio() {
            select.dispatchEvent(new Event('change', { bubbles: true }));
        }

        function pintarPildoras() {
            Array.prototype.slice.call(control.querySelectorAll('.nodo-buscador__pildora')).forEach(function (p) {
                control.removeChild(p);
            });
            elegidas().forEach(function (opcion) {
                var pildora = crear('span', 'nodo-buscador__pildora');
                var texto = crear('span', 'nodo-buscador__pildora-texto');
                texto.textContent = opcion.text;
                var quitar = crear('button', 'nodo-buscador__quitar');
                quitar.type = 'button';
                quitar.innerHTML = '&times;';
                quitar.setAttribute('aria-label', 'Quitar ' + opcion.text);
                quitar.addEventListener('click', function (ev) {
                    ev.stopPropagation();
                    opcion.selected = false;
                    pintarPildoras();
                    pintarLista();
                    avisarCambio();
                    input.focus();
                });
                pildora.appendChild(texto);
                pildora.appendChild(quitar);
                control.insertBefore(pildora, input);
            });
            // En el simple, una vez elegido no hace falta seguir invitando a buscar.
            if (!multiple && elegidas().length) {
                input.placeholder = '';
            } else {
                input.placeholder = select.getAttribute('data-buscador-placeholder') || 'Buscá una opción';
            }
        }

        function seleccionar(opcion) {
            if (!multiple) {
                opciones.forEach(function (o) { o.selected = false; });
            }
            opcion.selected = true;
            input.value = '';
            pintarPildoras();
            if (multiple) {
                pintarLista();
            } else {
                cerrar();
            }
            avisarCambio();
        }

        function pintarLista() {
            var filtro = normalizar(input.value);
            lista.innerHTML = '';
            activa = -1;
            var candidatas = opciones.filter(function (o) {
                // En el múltiple, lo ya elegido está en píldoras: no se repite.
                if (multiple && o.selected) return false;
                return !filtro || normalizar(o.text).indexOf(filtro) !== -1;
            });
            if (!candidatas.length) {
                var vacio = crear('li', 'nodo-buscador__vacio');
                vacio.textContent = filtro ? 'Sin resultados para «' + input.value + '»' : 'No quedan opciones';
                lista.appendChild(vacio);
                return;
            }
            candidatas.forEach(function (opcion) {
                var li = crear('li', 'nodo-buscador__opcion');
                li.textContent = opcion.text;
                li.dataset.valor = opcion.value;
                li.setAttribute('role', 'option');
                li.setAttribute('aria-selected', opcion.selected ? 'true' : 'false');
                li.addEventListener('mousedown', function (ev) {
                    // mousedown y no click: el blur del input cerraría la lista antes.
                    ev.preventDefault();
                    seleccionar(opcion);
                });
                lista.appendChild(li);
            });
        }

        function abrir() {
            if (!lista.hidden) return;
            pintarLista();
            lista.hidden = false;
            raiz.classList.add('nodo-buscador--abierto');
            input.setAttribute('aria-expanded', 'true');
        }

        function cerrar() {
            lista.hidden = true;
            raiz.classList.remove('nodo-buscador--abierto');
            input.setAttribute('aria-expanded', 'false');
            input.value = '';
            activa = -1;
        }

        function moverActiva(paso) {
            var items = visibles();
            if (!items.length) return;
            if (activa >= 0 && items[activa]) items[activa].removeAttribute('data-activa');
            activa = (activa + paso + items.length) % items.length;
            items[activa].setAttribute('data-activa', '1');
            var item = items[activa];
            if (item.offsetTop < lista.scrollTop) {
                lista.scrollTop = item.offsetTop;
            } else if (item.offsetTop + item.offsetHeight > lista.scrollTop + lista.clientHeight) {
                lista.scrollTop = item.offsetTop + item.offsetHeight - lista.clientHeight;
            }
        }

        control.addEventListener('click', function () { input.focus(); abrir(); });
        input.addEventListener('focus', abrir);
        input.addEventListener('input', function () { abrir(); pintarLista(); });

        input.addEventListener('keydown', function (ev) {
            if (ev.key === 'ArrowDown') { ev.preventDefault(); abrir(); moverActiva(1); return; }
            if (ev.key === 'ArrowUp') { ev.preventDefault(); abrir(); moverActiva(-1); return; }
            if (ev.key === 'Enter') {
                var items = visibles();
                if (!lista.hidden && activa >= 0 && items[activa]) {
                    ev.preventDefault();
                    var valor = items[activa].dataset.valor;
                    var opcion = opciones.filter(function (o) { return o.value === valor; })[0];
                    if (opcion) seleccionar(opcion);
                }
                return;
            }
            if (ev.key === 'Escape') { cerrar(); return; }
            if (ev.key === 'Backspace' && input.value === '') {
                var puestas = elegidas();
                if (puestas.length) {
                    puestas[puestas.length - 1].selected = false;
                    pintarPildoras();
                    pintarLista();
                    avisarCambio();
                }
            }
        });

        document.addEventListener('click', function (ev) {
            if (!raiz.contains(ev.target)) cerrar();
        });

        pintarPildoras();
    }

    function montarTodos(raiz) {
        var nodos = (raiz || document).querySelectorAll('select[' + ATTR + ']');
        Array.prototype.forEach.call(nodos, montar);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () { montarTodos(); });
    } else {
        montarTodos();
    }

    // Por si algún día el formulario se inyecta por AJAX.
    window.nodoBuscador = { montar: montarTodos };
})();
