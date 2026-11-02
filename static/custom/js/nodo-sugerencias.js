/* NODO — Sugerencias de personas (Cambio 415)
 *
 * Monta un desplegable de sugerencias sobre cualquier <input data-sugerencias-url="...">.
 * Desde 3 caracteres pide al endpoint (GET ?q=) una lista de {apellido, nombre, dni} y,
 * al elegir una, completa el campo con el DNI (o con `valor`, si la fila lo trae: el buscador
 * de agentes lo usa para dejar nombre y apellido). El <input> sigue siendo el mismo: es el
 * que viaja en el POST y el servidor valida igual que siempre.
 *
 * Si este archivo no se carga o falla, el campo funciona como un input de texto común.
 *
 * Atributos:
 *   data-sugerencias-url       endpoint (obligatorio). Se lee en cada consulta: una pantalla puede
 *                              cambiarlo o quitarlo (sin URL no se consulta nada); para montar un
 *                              campo que lo recibe después, window.NodoSugerencias.montar(contenedor)
 *   data-sugerencias-vacio     texto cuando nadie coincide
 *   data-sugerencias-hay-mas   texto cuando el servidor avisa que hay más resultados
 *
 * Todo texto del servidor se escribe con textContent: nunca innerHTML con datos.
 * Sin dependencias: no usa Alpine.
 */
(function () {
    'use strict';

    var ATTR = 'data-sugerencias-url';
    var MINIMO = 3;
    var DEMORA_MS = 250;
    var seq = 0;

    function crear(tag, clase) {
        var el = document.createElement(tag);
        if (clase) el.className = clase;
        return el;
    }

    function montar(input) {
        if (input.dataset.sugerenciasMontado === '1') return;
        input.dataset.sugerenciasMontado = '1';

        var textoVacio = input.getAttribute('data-sugerencias-vacio') || 'No encontramos a nadie.';
        var textoHayMas = input.getAttribute('data-sugerencias-hay-mas') || 'Hay más resultados: escribí más datos.';
        var id = 'nodo-sugerencias-' + (++seq);

        var raiz = crear('div', 'nodo-sugerencias');
        var panel = crear('div', 'nodo-sugerencias__panel');
        var lista = crear('ul', 'nodo-sugerencias__lista');
        var aviso = crear('p', 'nodo-sugerencias__aviso');

        lista.id = id;
        lista.setAttribute('role', 'listbox');
        aviso.setAttribute('role', 'status');
        panel.hidden = true;
        panel.appendChild(lista);
        panel.appendChild(aviso);

        input.parentNode.insertBefore(raiz, input);
        raiz.appendChild(input);
        raiz.appendChild(panel);

        input.setAttribute('role', 'combobox');
        input.setAttribute('aria-autocomplete', 'list');
        input.setAttribute('aria-expanded', 'false');
        input.setAttribute('aria-controls', id);
        input.autocomplete = 'off';

        var opciones = [];
        var activa = -1;
        var temporizador = null;
        var pedido = null;
        var ultimaConsulta = '';

        function marcar(indice) {
            activa = indice;
            opciones.forEach(function (li, i) {
                if (i === indice) {
                    li.setAttribute('aria-selected', 'true');
                    li.setAttribute('data-activa', '1');
                    li.scrollIntoView({ block: 'nearest' });
                } else {
                    li.setAttribute('aria-selected', 'false');
                    li.removeAttribute('data-activa');
                }
            });
            if (indice >= 0) input.setAttribute('aria-activedescendant', opciones[indice].id);
            else input.removeAttribute('aria-activedescendant');
        }

        function abrir(abierto) {
            panel.hidden = !abierto;
            input.setAttribute('aria-expanded', abierto ? 'true' : 'false');
            if (!abierto) marcar(-1);
        }

        function elegir(indice) {
            var li = opciones[indice];
            if (!li) return;
            input.value = li.getAttribute('data-valor');
            abrir(false);
            ultimaConsulta = input.value.trim();
            // Quien escucha el campo se entera igual que si la persona lo hubiera tecleado.
            input.dispatchEvent(new Event('input', { bubbles: true }));
            input.dispatchEvent(new Event('change', { bubbles: true }));
        }

        function dibujar(datos) {
            lista.textContent = '';
            opciones = [];
            activa = -1;
            input.removeAttribute('aria-activedescendant');
            var filas = (datos && datos.resultados) || [];
            filas.forEach(function (fila, i) {
                var li = crear('li', 'nodo-sugerencias__opcion');
                li.id = id + '-' + i;
                li.setAttribute('role', 'option');
                li.setAttribute('aria-selected', 'false');
                li.setAttribute('data-valor', fila.valor || fila.dni);
                li.textContent = fila.apellido + ', ' + fila.nombre + (fila.dni ? ' · ' + fila.dni : '');
                // mousedown y no click: el click llega después del blur y el panel ya se cerró.
                li.addEventListener('mousedown', function (e) {
                    e.preventDefault();
                    elegir(i);
                });
                lista.appendChild(li);
                opciones.push(li);
            });
            lista.hidden = filas.length === 0;
            if (filas.length === 0) aviso.textContent = textoVacio;
            else aviso.textContent = datos.hay_mas ? textoHayMas : '';
            aviso.hidden = aviso.textContent === '';
            abrir(true);
        }

        function consultar() {
            var texto = input.value.trim();
            if (texto === ultimaConsulta) return;
            ultimaConsulta = texto;
            if (pedido) pedido.abort();
            var url = input.getAttribute(ATTR);
            if (!url || texto.length < MINIMO) {
                pedido = null;
                abrir(false);
                return;
            }
            var control = new AbortController();
            pedido = control;
            fetch(url + (url.indexOf('?') === -1 ? '?' : '&') + 'q=' + encodeURIComponent(texto), {
                credentials: 'same-origin',
                headers: { 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
                signal: control.signal
            }).then(function (r) {
                if (!r.ok) throw new Error('sugerencias ' + r.status);
                return r.json();
            }).then(function (datos) {
                if (pedido !== control) return;
                pedido = null;
                dibujar(datos);
            }).catch(function (error) {
                if (error && error.name === 'AbortError') return;
                // Sin sugerencias el campo sigue funcionando: se calla y se deja escribir.
                if (pedido === control) pedido = null;
                abrir(false);
            });
        }

        input.addEventListener('input', function () {
            clearTimeout(temporizador);
            temporizador = setTimeout(consultar, DEMORA_MS);
        });

        input.addEventListener('keydown', function (e) {
            var abierto = !panel.hidden;
            if (e.key === 'ArrowDown' && abierto && opciones.length) {
                e.preventDefault();
                marcar((activa + 1) % opciones.length);
            } else if (e.key === 'ArrowUp' && abierto && opciones.length) {
                e.preventDefault();
                marcar(activa <= 0 ? opciones.length - 1 : activa - 1);
            } else if (e.key === 'Enter' && abierto && activa >= 0) {
                // Sin una opción marcada, Enter envía el formulario como siempre.
                e.preventDefault();
                elegir(activa);
            } else if (e.key === 'Escape' && abierto) {
                // Cierra solo la lista: que el Escape no llegue al modal que la contiene.
                e.preventDefault();
                e.stopPropagation();
                abrir(false);
            }
        });

        input.addEventListener('blur', function () {
            clearTimeout(temporizador);
            if (pedido) { pedido.abort(); pedido = null; }
            // La consulta cancelada no cuenta como hecha: al volver al campo se repite.
            ultimaConsulta = '';
            abrir(false);
        });
    }

    function montarTodo(contexto) {
        (contexto || document).querySelectorAll('input[' + ATTR + ']').forEach(montar);
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { montarTodo(); });
    else montarTodo();
    window.NodoSugerencias = { montar: montarTodo };
})();
