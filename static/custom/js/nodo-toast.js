/* =============================================================
 * NODO Toast / Notification
 * -------------------------------------------------------------
 * Sistema único de notificaciones toast del sistema. Reemplaza
 * los mensajes de Django que antes se renderizaban fijos dentro
 * del HTML (y que se duplicaban entre el template base y el hijo).
 *
 * · Posición: abajo-derecha (contenedor en nodo-toast.css)
 * · Duración: success / info / warning duran 7 segundos, con barra de
 *   progreso y pausa al hover/foco. Los ERRORES no se cierran solos
 *   (sin barra ni temporizador): quedan hasta que el usuario los cierra
 *   con el botón o con Escape. Una opts.duration explícita manda siempre.
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
 *               duration explícita también cierra un error solo.
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
        var isError = (variant === VARIANTS.error);
        var isUrgent = (isError || variant === VARIANTS.warning);
        // Un error sin duración explícita es persistente: no se cierra solo.
        var persistent = isError && !(typeof opts.duration === 'number' && opts.duration > 0);

        var container = getContainer();
        ubicarPila();

        // Deduplicación: un error persistente idéntico ya visible no se apila.
        if (persistent) {
            for (var p = 0; p < persistentes.length; p++) {
                if (persistentes[p]._msg === String(message) && !persistentes[p]._closed) {
                    return persistentes[p];
                }
            }
        }

        var toast = document.createElement('div');
        toast.className = 'toast ' + variant.cls;
        // Los urgentes (error/warning) se anuncian de inmediato; el resto, cortés.
        toast.setAttribute('role', isUrgent ? 'alert' : 'status');
        toast.setAttribute('aria-live', isUrgent ? 'assertive' : 'polite');
        if (persistent) {
            toast._msg = String(message);
            persistentes.push(toast);
        }
        toast._prevFocus = document.activeElement || null;

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

        // Barra de progreso (el auto-cierre se ata a su animationend).
        // Los errores persistentes no la llevan: no hay cuenta regresiva.
        var progress = null;
        if (!persistent) {
            progress = document.createElement('span');
            progress.className = 'toast__progress';
            progress.setAttribute('aria-hidden', 'true');
            progress.style.animationDuration = duration + 'ms';
        }

        toast.appendChild(iconWrap);
        toast.appendChild(body);
        toast.appendChild(closeBtn);
        if (progress) { toast.appendChild(progress); }
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
            toast._closed = true;
            var teniaFoco = !!(document.activeElement && typeof toast.contains === 'function' &&
                toast.contains(document.activeElement));
            var idx = persistentes.indexOf(toast);
            if (idx !== -1) { persistentes.splice(idx, 1); }
            toast.classList.add('toast--leaving');
            toast.classList.remove('toast--visible');
            if (teniaFoco) { devolverFoco(toast); }

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
        if (progress) { progress.addEventListener('animationend', dismiss); }
        toast._dismiss = dismiss;
        toast._closeBtn = closeBtn;

        // Tope de errores persistentes visibles: el más viejo se descarta.
        while (persistentes.length > MAX_ERRORES) { persistentes[0]._dismiss(); }

        return toast;
    }

    // Errores persistentes visibles (en orden de aparición).
    var persistentes = [];
    var MAX_ERRORES = 3;

    // Al cerrar un toast con el foco adentro: al botón de cerrar del siguiente
    // toast visible o, si no hay, al elemento que tenía el foco antes.
    function devolverFoco(toast) {
        var box = toast.parentNode;
        var hijos = (box && box.children) ? Array.prototype.slice.call(box.children) : [];
        for (var i = hijos.length - 1; i >= 0; i--) {
            var h = hijos[i];
            if (h !== toast && !h._closed && h._closeBtn && typeof h._closeBtn.focus === 'function') {
                h._closeBtn.focus();
                return;
            }
        }
        var prev = toast._prevFocus;
        if (prev && prev !== document.body && typeof prev.focus === 'function') { prev.focus(); }
    }

    // ¿Hay un modal / SweetAlert abierto? Escape le pertenece a él.
    function modalAbierto() {
        if (typeof document.querySelectorAll !== 'function') { return null; }
        var modales = document.querySelectorAll('[aria-modal="true"], .swal2-container');
        var visible = null;
        for (var i = 0; i < modales.length; i++) {
            var m = modales[i];
            if (typeof m.getClientRects !== 'function' || m.getClientRects().length > 0) { visible = m; }
        }
        return visible;
    }
    function hayModalAbierto() { return !!modalAbierto(); }

    // Encabezado del panel del modal: [data-modal-header], el ancestro con
    // border-b del título (aria-labelledby) o el primer .border-b.
    function encabezadoDe(m) {
        var h = m.querySelector('[data-modal-header]');
        if (h) { return h; }
        var id = m.getAttribute && m.getAttribute('aria-labelledby');
        var t = id ? document.getElementById(id) : null;
        while (t && t !== m) {
            if (t.classList && t.classList.contains('border-b')) { return t; }
            t = t.parentNode;
        }
        return m.querySelector('.border-b');
    }

    // Móvil (≤640px): la pila se apoya justo debajo del encabezado del modal y
    // termina antes de su pie, para no tapar la X ni Cancelar / Guardar.
    function posicionarSobreModal(box, m) {
        var st = box.style;
        var movil = typeof window.innerWidth === 'number' && window.innerWidth <= 640;
        if (!m || !movil || typeof m.querySelector !== 'function') {
            st.top = ''; st.bottom = ''; st.maxHeight = '';
            return;
        }
        var h = encabezadoDe(m);
        var hr = h && h.getBoundingClientRect ? h.getBoundingClientRect() : null;
        var top = (hr && hr.bottom > 0) ? Math.round(hr.bottom + 8) : null;
        var pies = m.querySelectorAll ? m.querySelectorAll('.border-t') : [];
        var pr = pies.length ? pies[pies.length - 1].getBoundingClientRect() : null;
        st.bottom = 'auto';
        if (top === null) {
            st.top = 'calc(72px + env(safe-area-inset-top, 0px))';
            st.maxHeight = '40vh';
            return;
        }
        st.top = top + 'px';
        st.maxHeight = (pr && pr.top - top - 8 > 48) ? Math.round(pr.top - top - 8) + 'px' : '40vh';
    }

    // Con un modal abierto la pila sube y se apoya bajo su encabezado. La clase
    // la usa nodo-toast.css (≤640px); el top/max-height los calcula el JS.
    function ubicarPila() {
        var box = document.getElementById('toast-container');
        if (!box || !box.classList) { return; }
        var m = modalAbierto();
        if (m) { box.classList.add('toast-container--sobre-modal'); }
        else { box.classList.remove('toast-container--sobre-modal'); }
        if (box.style) { posicionarSobreModal(box, m); }
    }
    var ubicarPendiente = false;
    function ubicarPilaLiviano(registros) {
        // Los cambios de estilo de la propia pila no reprograman nada (evita bucles).
        var box = document.getElementById('toast-container');
        if (registros && registros.length && box && typeof box.contains === 'function') {
            var ajeno = false;
            for (var i = 0; i < registros.length; i++) {
                if (!box.contains(registros[i].target)) { ajeno = true; break; }
            }
            if (!ajeno) { return; }
        }
        if (ubicarPendiente) { return; }
        ubicarPendiente = true;
        setTimeout(function () { ubicarPendiente = false; ubicarPila(); }, 50);
    }
    if (typeof MutationObserver === 'function' && document.body) {
        new MutationObserver(ubicarPilaLiviano).observe(document.body, {
            subtree: true, childList: true, attributes: true,
            attributeFilter: ['class', 'hidden', 'style', 'aria-modal']
        });
    }
    if (typeof window.addEventListener === 'function') { window.addEventListener('resize', ubicarPilaLiviano); }

    // Escape: cierra el error con foco; si no, el último error visible, salvo que
    // haya un modal abierto (ese Escape es del modal) o alguien ya lo consumió.
    document.addEventListener('keydown', function (e) {
        if (e.key !== 'Escape' && e.key !== 'Esc') { return; }
        if (e.defaultPrevented) { return; }
        var f = document.activeElement;
        for (var i = 0; i < persistentes.length; i++) {
            if (f && typeof persistentes[i].contains === 'function' && persistentes[i].contains(f)) {
                persistentes[i]._dismiss();
                return;
            }
        }
        if (hayModalAbierto()) { return; }
        var target = persistentes[persistentes.length - 1];
        if (target) { target._dismiss(); }
    });

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
