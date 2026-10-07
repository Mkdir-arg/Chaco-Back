/**
 * NODO — guardia de doble envío para los formularios clásicos (FE-26).
 *
 * Se carga una sola vez desde `templates/includes/base.html`, así que cubre todo el
 * backoffice: Dispositivos, Merenderos, Admisiones, Configuración y Legajos mandan sus
 * formularios con un POST normal y, hasta ahora, un doble clic sobre «Confirmar egreso»
 * o «Registrar entrega» mandaba dos POST. Los formularios de Becas no lo necesitan:
 * van por `data-ajax` y `programas/becas/_ajax_js.html` ya deshabilita su botón.
 *
 * Qué hace, en el `submit` del formulario:
 *   1. si el formulario ya está enviándose (`aria-busy`), **cancela** el segundo envío;
 *   2. si no, lo marca `aria-busy="true"` y deshabilita sus botones de envío —también
 *      los externos, los que apuntan al formulario con `form="<id>"`—;
 *   3. al volver con «atrás» (bfcache, `pageshow` con `persisted`) devuelve todo a su
 *      estado, o el formulario quedaría inutilizable.
 *
 * Dos recaudos que no son opcionales:
 *
 * - **El `disabled` se aplica en el turno siguiente** (`setTimeout(…, 0)`). El navegador
 *   arma la lista de entradas del POST *después* de despachar el evento `submit`, y un
 *   control deshabilitado queda fuera: deshabilitar en el acto borraría el `name`/`value`
 *   del botón que disparó el envío. La protección real es el paso 1, que sí es síncrona.
 * - **`event.defaultPrevented` se mira dos veces, y la que manda es la segunda.** Leerlo
 *   solo al entrar no alcanza: este script se registra en `document` al cargar el shell,
 *   y los scripts de `{% block customJS %}` se registran dentro de `DOMContentLoaded`, o
 *   sea **después**. Un listener delegado en `document` que cancele el envío corre detrás
 *   de esta guardia, así que al entrar `defaultPrevented` todavía es `false` y el POST no
 *   sale igual. Por eso se vuelve a mirar en el mismo turno diferido del `disabled`: si el
 *   envío terminó cancelado, se suelta la marca y no se deshabilita nada, o el formulario
 *   queda muerto. La lectura de entrada queda como atajo barato para los listeners que sí
 *   corren antes (los del propio `<form>`).
 */
(function () {
    'use strict';

    var MARCA = 'data-nodo-submit-guard';

    function esBotonDeEnvio(el) {
        if (el.tagName === 'BUTTON') {
            return (el.getAttribute('type') || 'submit').toLowerCase() === 'submit';
        }
        if (el.tagName === 'INPUT') {
            var tipo = (el.getAttribute('type') || '').toLowerCase();
            return tipo === 'submit' || tipo === 'image';
        }
        return false;
    }

    function botonesDe(form) {
        var botones = Array.prototype.filter.call(form.querySelectorAll('button, input'), esBotonDeEnvio);
        if (form.id) {
            // Los botones con `form="<id>"` viven fuera del formulario y no los
            // alcanza el querySelectorAll de arriba. Se compara el atributo en vez de
            // armar un selector: un id con caracteres especiales rompería el selector.
            Array.prototype.forEach.call(document.querySelectorAll('[form]'), function (el) {
                if (el.getAttribute('form') === form.id && esBotonDeEnvio(el)) {
                    botones.push(el);
                }
            });
        }
        return botones;
    }

    function bloquear(form, event) {
        form.setAttribute('aria-busy', 'true');
        var botones = botonesDe(form);
        setTimeout(function () {
            // Segunda lectura, la que manda: acá ya corrieron todos los listeners,
            // incluidos los delegados en `document` que se registraron después de
            // esta guardia. Si el envío quedó cancelado, el formulario no se fue a
            // ningún lado y hay que soltarlo.
            if (event.defaultPrevented) {
                form.removeAttribute('aria-busy');
                return;
            }
            botones.forEach(function (boton) {
                if (boton.disabled) return;
                boton.disabled = true;
                boton.setAttribute(MARCA, '');
            });
        }, 0);
    }

    function liberarTodo() {
        Array.prototype.forEach.call(document.querySelectorAll('[' + MARCA + ']'), function (boton) {
            boton.disabled = false;
            boton.removeAttribute(MARCA);
        });
        Array.prototype.forEach.call(document.querySelectorAll('form[aria-busy]'), function (form) {
            form.removeAttribute('aria-busy');
        });
    }

    document.addEventListener('submit', function (event) {
        if (event.defaultPrevented) return;
        var form = event.target;
        if (!form || form.tagName !== 'FORM') return;
        if ((form.getAttribute('method') || '').toLowerCase() !== 'post') return;
        if (form.hasAttribute('data-ajax')) return;
        if (form.hasAttribute('aria-busy')) {
            event.preventDefault();
            return;
        }
        bloquear(form, event);
    });

    window.addEventListener('pageshow', function (event) {
        if (event.persisted) liberarTodo();
    });
})();
