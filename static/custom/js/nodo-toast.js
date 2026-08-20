/* =============================================================
 * NODO Toast / Notification
 * -------------------------------------------------------------
 * Sistema único de notificaciones toast del sistema. Reemplaza
 * los mensajes de Django que antes se renderizaban fijos dentro
 * del HTML (y que se duplicaban entre el template base y el hijo).
 *
 * · Posición: abajo-derecha (contenedor en nodo-toast.css)
 * · Duración: 7 segundos, con barra de progreso y pausa al hover
 * · Dos familias (definición del cliente):
 *       confirmación → success (verde)
 *       alerta       → error (rojo) / warning (ámbar)
 *   más "info" (neutro) para mensajes informativos.
 *
 * API pública:
 *     toast(tipo, mensaje, opciones)
 *     toast.success(mensaje, opciones)
 *     toast.error(mensaje, opciones)
 *     toast.warning(mensaje, opciones)
 *     toast.info(mensaje, opciones)
 *
 *   tipo      : 'success' | 'error' | 'warning' | 'info'
 *               (o alias es-AR: 'confirmacion', 'alerta', ...)
 *   mensaje   : string
 *   opciones  : { duration?: ms, title?: string|null }
 *               title === '' o null oculta el título.
 * ============================================================= */
(function () {
    'use strict';

    var DEFAULT_DURATION = 7000; // 7 s — pedido explícito del cliente

    // Configuración por variante canónica: clase CSS, icono FontAwesome
    // (ya cargado en ambos base.html) y título por defecto (es-AR).
    var VARIANTS = {
        success: { cls: 'toast--success', icon: 'fa-check-circle',         title: 'Listo' },
        error:   { cls: 'toast--error',   icon: 'fa-exclamation-circle',   title: 'Error' },
        warning: { cls: 'toast--warning', icon: 'fa-exclamation-triangle', title: 'Atención' },
        info:    { cls: 'toast--info',    icon: 'fa-info-circle',          title: 'Información' }
    };

    // Alias → variante canónica. Incluye los nombres del cliente
    // ("confirmación", "alerta") y los niveles de Django.
    var ALIASES = {
        success: 'success', confirmacion: 'success', 'confirmación': 'success',
        exito: 'success', 'éxito': 'success', ok: 'success', guardado: 'success',
        error: 'error', danger: 'error', alerta: 'error', peligro: 'error',
        warning: 'warning', warn: 'warning', atencion: 'warning', 'atención': 'warning', advertencia: 'warning',
        info: 'info', debug: 'info', primary: 'info', 'default': 'info'
    };

    // Resuelve el tipo a partir del string de tags de Django, que puede
    // combinar el nivel con extra_tags (p. ej. "success algo-custom").
    // Prioridad: error > warning > success > info.
    function resolveType(raw) {
        if (!raw) { return 'info'; }
        var tokens = String(raw).toLowerCase().trim().split(/\s+/);
        if (tokens.indexOf('error') !== -1) { return 'error'; }
        if (tokens.indexOf('warning') !== -1) { return 'warning'; }
        if (tokens.indexOf('success') !== -1) { return 'success'; }
        for (var i = 0; i < tokens.length; i++) {
            if (ALIASES.hasOwnProperty(tokens[i])) { return ALIASES[tokens[i]]; }
        }
        return 'info';
    }

    function getContainer() {
        var c = document.getElementById('toast-container');
        if (!c) {
            c = document.createElement('div');
            c.id = 'toast-container';
            c.className = 'toast-container';
            document.body.appendChild(c);
        }
        return c;
    }

    function show(type, message, opts) {
        opts = opts || {};
        if (message === null || message === undefined || String(message).trim() === '') {
            return null;
        }

        var variant = VARIANTS[resolveType(type)];
        var duration = (typeof opts.duration === 'number' && opts.duration > 0)
            ? opts.duration
            : DEFAULT_DURATION;
        var isUrgent = (variant === VARIANTS.error || variant === VARIANTS.warning);

        var container = getContainer();

        var toast = document.createElement('div');
        toast.className = 'toast ' + variant.cls;
        // Los urgentes (error/warning) se anuncian de inmediato; el resto, cortés.
        toast.setAttribute('role', isUrgent ? 'alert' : 'status');
        toast.setAttribute('aria-live', isUrgent ? 'assertive' : 'polite');

        // Icono (decorativo: el texto ya comunica la variante)
        var iconWrap = document.createElement('span');
        iconWrap.className = 'toast__icon';
        iconWrap.setAttribute('aria-hidden', 'true');
        var icon = document.createElement('i');
        icon.className = 'fas ' + variant.icon;
        iconWrap.appendChild(icon);

        // Cuerpo: título opcional + mensaje
        var body = document.createElement('div');
        body.className = 'toast__body';

        var title = (opts.title !== undefined) ? opts.title : variant.title;
        if (title) {
            var titleEl = document.createElement('p');
            titleEl.className = 'toast__title';
            titleEl.textContent = title;
            body.appendChild(titleEl);
        }

        var msgEl = document.createElement('p');
        msgEl.className = 'toast__message';
        msgEl.textContent = String(message); // textContent → seguro contra XSS
        body.appendChild(msgEl);

        // Botón cerrar
        var closeBtn = document.createElement('button');
        closeBtn.type = 'button';
        closeBtn.className = 'toast__close';
        closeBtn.setAttribute('aria-label', 'Cerrar notificación');
        closeBtn.innerHTML = '<i class="fas fa-times" aria-hidden="true"></i>';

        // Barra de progreso (el auto-cierre se ata a su animationend)
        var progress = document.createElement('span');
        progress.className = 'toast__progress';
        progress.setAttribute('aria-hidden', 'true');
        progress.style.animationDuration = duration + 'ms';

        toast.appendChild(iconWrap);
        toast.appendChild(body);
        toast.appendChild(closeBtn);
        toast.appendChild(progress);
        container.appendChild(toast);

        // Entrada: dos frames para asegurar que la transición dispare.
        requestAnimationFrame(function () {
            requestAnimationFrame(function () {
                toast.classList.add('toast--visible');
            });
        });

        var dismissed = false;
        function dismiss() {
            if (dismissed) { return; }
            dismissed = true;
            toast.classList.add('toast--leaving');
            toast.classList.remove('toast--visible');

            var removed = false;
            function cleanup() {
                if (removed) { return; }
                removed = true;
                if (toast.parentNode) { toast.parentNode.removeChild(toast); }
            }
            toast.addEventListener('transitionend', cleanup);
            setTimeout(cleanup, 500); // respaldo si transitionend no dispara
        }

        closeBtn.addEventListener('click', dismiss);
        // Fin de la barra de progreso → cierre. Como el CSS pausa la
        // animación en :hover / :focus-within, el cierre se pausa solo.
        progress.addEventListener('animationend', dismiss);

        return toast;
    }

    // ── API pública ──────────────────────────────────────────────
    var api = function (type, message, opts) { return show(type, message, opts); };
    api.success = function (m, o) { return show('success', m, o); };
    api.error   = function (m, o) { return show('error', m, o); };
    api.warning = function (m, o) { return show('warning', m, o); };
    api.info    = function (m, o) { return show('info', m, o); };
    api.show    = show;
    window.toast = api;

    // ── Bootstrap: leer los mensajes de Django y dispararlos ──────
    // El base.html imprime cada mensaje en un contenedor oculto
    // (#dj-messages). Los convertimos en toasts y quitamos el nodo.
    function flushDjangoMessages() {
        var box = document.getElementById('dj-messages');
        if (!box) { return; }
        var items = box.querySelectorAll('.dj-message');
        var seen = {};
        for (var i = 0; i < items.length; i++) {
            var el = items[i];
            var tags = el.getAttribute('data-tags') || '';
            var text = (el.textContent || '').trim();
            var key = tags + '|' + text;
            if (!text || seen[key]) { continue; } // dedupe exacto en la carga
            seen[key] = true;
            show(tags, text);
        }
        if (box.parentNode) { box.parentNode.removeChild(box); }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', flushDjangoMessages);
    } else {
        flushDjangoMessages();
    }
})();
