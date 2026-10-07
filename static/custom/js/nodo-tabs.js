/**
 * NODO — teclado de las solapas del backoffice (FE-24).
 *
 * Se carga una sola vez desde `templates/includes/base.html` y cubre **toda**
 * `[role="tablist"]` que tenga `[role="tab"]` adentro: el detalle del ciudadano, los
 * tres detalles de Becas, el ABM de roles y la golden del cupo. Reemplaza el handler
 * inline que vivía en `legajos/templates/legajos/ciudadano_detail.html`, que era la
 * única implementación y valía para una sola pantalla.
 *
 * Es una **mejora progresiva**: no cambia nada visual, no toca el estado de Alpine ni
 * el de ningún otro script. Para activar una solapa dispara su `click()`, que es
 * exactamente lo que ya hacía el mouse (en Alpine, el `@click` que mueve `tab`; en el
 * detalle del ciudadano, `cambiarTab(...)`). Sin este archivo las solapas siguen
 * funcionando con el mouse igual que antes.
 *
 * Qué agrega, siguiendo el patrón «tabs» de WAI-ARIA:
 *   - ← y → mueven el foco a la solapa anterior/siguiente, con vuelta circular;
 *   - Home y End van a la primera y a la última;
 *   - `tabindex` itinerante: solo la solapa activa es tabulable, así que Tab entra y
 *     sale de la barra en un paso en lugar de recorrer una solapa por vez.
 *
 * El `tabindex` se recalcula leyendo `aria-selected`, que es quien sabe cuál está
 * activa, y un `MutationObserver` lo vuelve a calcular cuando ese atributo cambia:
 * Alpine lo escribe con `:aria-selected` después del click, y el detalle del ciudadano
 * desde `cambiarTab()`, incluido el deep-link por hash al cargar la página.
 */
(function () {
    'use strict';

    var SELECTOR_LISTA = '[role="tablist"]';
    var SELECTOR_TAB = '[role="tab"]';

    // Las solapas que el usuario puede activar: se saltean las ocultas y las
    // deshabilitadas (una solapa condicionada por permiso no se dibuja, pero una
    // pantalla puede esconder la suya con `hidden`).
    function solapasDe(lista) {
        return Array.prototype.filter.call(lista.querySelectorAll(SELECTOR_TAB), function (tab) {
            return !tab.disabled && !tab.hasAttribute('hidden') && tab.closest(SELECTOR_LISTA) === lista;
        });
    }

    function activa(solapas) {
        for (var i = 0; i < solapas.length; i++) {
            if (solapas[i].getAttribute('aria-selected') === 'true') return i;
        }
        return 0;
    }

    // `tabindex` itinerante. Si la barra no declara `aria-selected` en ninguna solapa
    // —no todas lo hacen— la tabulable es la primera, que es lo que el navegador haría.
    function repartirTabindex(lista) {
        var solapas = solapasDe(lista);
        if (!solapas.length) return;
        var seleccionada = activa(solapas);
        solapas.forEach(function (tab, i) {
            tab.setAttribute('tabindex', i === seleccionada ? '0' : '-1');
        });
    }

    function mover(lista, desde, delta) {
        var solapas = solapasDe(lista);
        if (solapas.length < 2) return;
        var destino = solapas[(desde + delta + solapas.length) % solapas.length];
        destino.setAttribute('tabindex', '0');
        destino.focus();
        destino.click();
    }

    function irA(lista, indice) {
        var solapas = solapasDe(lista);
        if (!solapas.length) return;
        var destino = solapas[indice < 0 ? solapas.length - 1 : indice];
        destino.setAttribute('tabindex', '0');
        destino.focus();
        destino.click();
    }

    document.addEventListener('keydown', function (event) {
        if (event.altKey || event.ctrlKey || event.metaKey) return;
        var tab = event.target instanceof Element ? event.target.closest(SELECTOR_TAB) : null;
        if (!tab) return;
        var lista = tab.closest(SELECTOR_LISTA);
        if (!lista) return;
        var solapas = solapasDe(lista);
        var indice = solapas.indexOf(tab);
        if (indice === -1) return;

        if (event.key === 'ArrowRight') {
            event.preventDefault();
            mover(lista, indice, 1);
        } else if (event.key === 'ArrowLeft') {
            event.preventDefault();
            mover(lista, indice, -1);
        } else if (event.key === 'Home') {
            event.preventDefault();
            irA(lista, 0);
        } else if (event.key === 'End') {
            event.preventDefault();
            irA(lista, -1);
        }
    });

    function observar(lista) {
        repartirTabindex(lista);
        if (typeof MutationObserver !== 'function') return;
        new MutationObserver(function () {
            repartirTabindex(lista);
        }).observe(lista, { subtree: true, attributes: true, attributeFilter: ['aria-selected'] });
    }

    function montar() {
        Array.prototype.forEach.call(document.querySelectorAll(SELECTOR_LISTA), observar);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', montar);
    } else {
        montar();
    }

    // Para los tests: el comportamiento se ejerce desde afuera, sin tocar el DOM real.
    window.NodoTabs = { repartirTabindex: repartirTabindex, montar: montar };
})();
