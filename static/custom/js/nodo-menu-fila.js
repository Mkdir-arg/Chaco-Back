/**
 * NODO — menú de fila accesible (botón ⋮ de las tablas densas).
 *
 * Se carga una sola vez desde `templates/includes/base.html` y funciona por delegación
 * sobre `[data-menu-fila]` (markup de `templates/components/_menu_fila.html`), así que
 * también sirve para filas que llegan después por AJAX. Sin este archivo el menú queda
 * cerrado (`hidden`): el botón existe pero no abre nada.
 *
 * Contrato de teclado y foco:
 *   - Enter o Espacio sobre el botón abren el menú y enfocan el primer ítem; ↓ / ↑ sobre
 *     el botón lo abren enfocando el primero / el último.
 *   - Dentro del menú: ↑ / ↓ mueven entre ítems con vuelta circular, Home y End van al
 *     primero y al último, Tab y Shift+Tab circulan **dentro** del menú (foco atrapado).
 *   - Enter o Espacio activan el ítem. Un ítem con `aria-disabled="true"` se alcanza (para
 *     que se anuncie su motivo) pero no actúa.
 *   - Escape cierra y devuelve el foco al botón; un clic afuera, el scroll de la página o
 *     de la tabla y el cambio de tamaño cierran sin mover el foco.
 *   - Activar un ítem cierra el menú y deja el foco en el botón **antes** de que corra el
 *     resto de los handlers: así `ModernModal` (confirmaciones `data-confirm-url`) toma el
 *     botón como el elemento al que devolver el foco al cerrarse.
 *
 * `aria-expanded` del botón refleja el estado. El menú se posiciona con `position: fixed`
 * calculado al abrir (ver `nodo-menu-fila.css`): no lo recorta ni el `overflow-x-auto` de la
 * tabla ni el `overflow-hidden` de la card, y si no entra hacia abajo se abre hacia arriba.
 */
(function () {
    'use strict';

    var MARGEN = 8;
    var SEP = 4;
    var abierto = null; // { disparador, menu }

    function menuDe(disparador) {
        var envoltorio = disparador.closest('[data-menu-fila]');
        return envoltorio ? envoltorio.querySelector('[role="menu"]') : null;
    }

    function itemsDe(menu) {
        return Array.prototype.slice.call(menu.querySelectorAll('[role="menuitem"]'));
    }

    function enfocar(el) {
        if (el) el.focus({ preventScroll: true });
    }

    function posicionar(disparador, menu) {
        var r = disparador.getBoundingClientRect();
        var ancho = menu.offsetWidth;
        var alto = menu.offsetHeight;
        var vw = document.documentElement.clientWidth;
        var vh = document.documentElement.clientHeight;
        var izquierda = Math.max(MARGEN, Math.min(r.right - ancho, vw - ancho - MARGEN));
        var arriba = r.bottom + SEP;
        if (arriba + alto > vh - MARGEN) {
            var encima = r.top - SEP - alto;
            arriba = encima >= MARGEN ? encima : Math.max(MARGEN, vh - alto - MARGEN);
        }
        menu.style.left = izquierda + 'px';
        menu.style.top = arriba + 'px';
    }

    function cerrar(devolverFoco) {
        if (!abierto) return;
        var actual = abierto;
        abierto = null;
        actual.menu.hidden = true;
        actual.disparador.setAttribute('aria-expanded', 'false');
        if (devolverFoco) enfocar(actual.disparador);
    }

    function abrir(disparador, cual) {
        var menu = menuDe(disparador);
        if (!menu) return;
        cerrar(false);
        menu.hidden = false;
        posicionar(disparador, menu);
        disparador.setAttribute('aria-expanded', 'true');
        abierto = { disparador: disparador, menu: menu };
        var items = itemsDe(menu);
        enfocar(cual === 'ultimo' ? items[items.length - 1] : items[0]);
    }

    function mover(menu, paso) {
        var items = itemsDe(menu);
        if (!items.length) return;
        var i = items.indexOf(document.activeElement);
        if (i === -1) i = paso > 0 ? -1 : 0;
        enfocar(items[(i + paso + items.length) % items.length]);
    }

    // Clic: el disparador alterna; un ítem cierra (o se bloquea si está deshabilitado);
    // cualquier otro lado cierra. En captura, para correr antes que los handlers de los
    // ítems (confirmaciones) y que cualquier stopPropagation de la pantalla.
    document.addEventListener('click', function (e) {
        var objetivo = e.target instanceof Element ? e.target : null;
        if (!objetivo) return;
        var disparador = objetivo.closest('[data-menu-fila-trigger]');
        if (disparador) {
            e.preventDefault();
            if (abierto && abierto.disparador === disparador) cerrar(true);
            else abrir(disparador, 'primero');
            return;
        }
        var item = objetivo.closest('[data-menu-fila] [role="menuitem"]');
        if (item) {
            if (item.getAttribute('aria-disabled') === 'true') {
                e.preventDefault();
                e.stopImmediatePropagation();
                return;
            }
            cerrar(true);
            return;
        }
        if (abierto && !abierto.menu.contains(objetivo)) cerrar(false);
    }, true);

    document.addEventListener('keydown', function (e) {
        var objetivo = e.target instanceof Element ? e.target : null;
        if (!objetivo) return;

        if (!abierto) {
            var disparador = objetivo.closest('[data-menu-fila-trigger]');
            if (disparador && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
                e.preventDefault();
                abrir(disparador, e.key === 'ArrowUp' ? 'ultimo' : 'primero');
            }
            return;
        }

        var menu = abierto.menu;
        var items = itemsDe(menu);
        switch (e.key) {
            case 'Escape':
                e.preventDefault();
                e.stopPropagation(); // que no cierre también un modal que contenga la tabla
                cerrar(true);
                break;
            case 'Tab':
                e.preventDefault();
                mover(menu, e.shiftKey ? -1 : 1);
                break;
            case 'ArrowDown':
                e.preventDefault();
                mover(menu, 1);
                break;
            case 'ArrowUp':
                e.preventDefault();
                mover(menu, -1);
                break;
            case 'Home':
                e.preventDefault();
                enfocar(items[0]);
                break;
            case 'End':
                e.preventDefault();
                enfocar(items[items.length - 1]);
                break;
            case ' ':
                // Un <a> no se activa con Espacio por defecto; un <button> sí, por su cuenta.
                if (objetivo.matches('a[role="menuitem"]')) {
                    e.preventDefault();
                    objetivo.click();
                }
                break;
        }
    }, true);

    // Con el menú abierto, mover la tabla lo dejaría flotando lejos de su fila.
    window.addEventListener('scroll', function (e) {
        if (abierto && !(e.target instanceof Node && abierto.menu.contains(e.target))) cerrar(false);
    }, true);
    window.addEventListener('resize', function () { cerrar(false); });
})();
