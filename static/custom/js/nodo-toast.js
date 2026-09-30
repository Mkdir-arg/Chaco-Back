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
        // Excepción: en móvil con un modal abierto donde la pila no cabe entre
        // su encabezado y su pie, se comporta como antes (7 s, con barra, 1 solo).
        var explicita = (typeof opts.duration === 'number' && opts.duration > 0);
        var ctx = contextoModal();
        var persistent = isError && !explicita && !ctx.sinLugar;
        var temporalDeModal = isError && !explicita && ctx.sinLugar;

        var container = getContainer();
        ubicarPila();
        if (temporalDeModal) { soloUnErrorTemporal(); }

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
            reservarEspacio();

            var removed = false;
            function cleanup() {
                if (removed) { return; }
                removed = true;
                if (toast.parentNode) { toast.parentNode.removeChild(toast); }
                reservarEspacio();
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

        // Un error temporal de modal reemplaza a los anteriores (máx. 1 visible).
        if (temporalDeModal) { temporales.push(toast); }

        // Convierte un error persistente en temporal (7 s con barra) cuando se
        // abre un modal donde la pila no cabe.
        toast._volverTemporal = function () {
            var i = persistentes.indexOf(toast);
            if (i !== -1) { persistentes.splice(i, 1); }
            if (progress || dismissed) { return; }
            progress = document.createElement('span');
            progress.className = 'toast__progress';
            progress.setAttribute('aria-hidden', 'true');
            progress.style.animationDuration = DEFAULT_DURATION + 'ms';
            toast.appendChild(progress);
            progress.addEventListener('animationend', dismiss);
            temporales.push(toast);
        };

        // Tope de errores persistentes visibles: el más viejo se descarta.
        // En móvil sin modal, 1 solo, para no tapar la zona inferior.
        var tope = (ctx.movil && !ctx.modal) ? 1 : MAX_ERRORES;
        while (persistentes.length > tope) { persistentes[0]._dismiss(); }
        reservarEspacio();

        return toast;
    }

    // Errores persistentes visibles (en orden de aparición).
    var persistentes = [];
    // Errores temporales de modal (7 s con barra).
    var temporales = [];
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

    // Espacio mínimo entre encabezado y pie del modal para alojar la pila.
    var ESPACIO_MIN = 120;

    // Móvil (≤640px): mide dónde apoyar la pila entre el encabezado y el pie
    // del modal. null si alguno no es detectable o el espacio es insuficiente.
    function medirEntreEncabezadoYPie(m) {
        if (typeof m.querySelector !== 'function' || typeof m.querySelectorAll !== 'function') { return null; }
        var h = encabezadoDe(m);
        var hr = h && h.getBoundingClientRect ? h.getBoundingClientRect() : null;
        var pies = m.querySelectorAll('.border-t');
        var pr = pies.length ? pies[pies.length - 1].getBoundingClientRect() : null;
        if (!hr || !pr || !(hr.bottom > 0)) { return null; }
        if (pr.top - hr.bottom < ESPACIO_MIN) { return null; }
        var top = Math.round(hr.bottom + 8);
        return {top: top, max: Math.max(48, Math.round(pr.top - top - 8))};
    }

    // Estado del modal para decidir la ubicación y la persistencia:
    //   movil     : ancho ≤ 640px
    //   modal     : el modal visible (o null)
    //   medidas   : {top, max} si la pila cabe entre encabezado y pie (solo móvil)
    //   sinLugar  : móvil + modal abierto + la pila NO cabe → errores como antes
    function contextoModal() {
        var m = modalAbierto();
        var movil = typeof window.innerWidth === 'number' && window.innerWidth <= 640;
        var medidas = (m && movil) ? medirEntreEncabezadoYPie(m) : null;
        return {modal: m, movil: movil, medidas: medidas, sinLugar: !!(m && movil && !medidas)};
    }

    // Deja como máximo 1 error visible (el que se está por crear): los
    // persistentes y temporales anteriores se descartan.
    function soloUnErrorTemporal() {
        persistentes.slice().forEach(function (t) { t._dismiss(); });
        temporales.slice().forEach(function (t) { t._dismiss(); });
        temporales = [];
    }

    // Con un modal abierto la pila sube y se apoya bajo su encabezado. La clase
    // la usa nodo-toast.css (≤640px); el top/max-height los calcula el JS.
    function ubicarPila() {
        var box = document.getElementById('toast-container');
        if (!box || !box.classList) { return; }
        var ctx = contextoModal();
        temporales = temporales.filter(function (t) { return !t._closed; });
        if (ctx.sinLugar) {
            // No cabe: los errores ya visibles pasan a temporales y queda el último.
            var ult = persistentes[persistentes.length - 1];
            persistentes.slice(0, -1).forEach(function (t) { t._dismiss(); });
            if (ult) { ult._volverTemporal(); }
        }
        if (ctx.modal && !ctx.sinLugar) { box.classList.add('toast-container--sobre-modal'); }
        else { box.classList.remove('toast-container--sobre-modal'); }
        if (box.style) {
            if (ctx.medidas) {
                box.style.bottom = 'auto';
                box.style.top = ctx.medidas.top + 'px';
                box.style.maxHeight = ctx.medidas.max + 'px';
            } else {
                box.style.top = ''; box.style.bottom = ''; box.style.maxHeight = '';
            }
        }
    }

    // Sin modal, mientras haya un error persistente visible, se reserva abajo
    // (padding-bottom del body) el alto de la pila + el offset del breakpoint
    // (12px ≤640px, 24px escritorio) para que no tape el último botón de la
    // página. Se restaura el valor previo al cerrarse el último error.
    var padPrevio = null;   // {inline, base} guardados al aplicar por primera vez
    function restaurarEspacio() {
        if (padPrevio === null) { return; }
        document.body.style.paddingBottom = padPrevio.inline;
        padPrevio = null;
    }
    // Alto real de la pila visible: suma los toasts que no están saliendo
    // (los que llevan .toast--leaving siguen en el DOM hasta su cleanup pero
    // ya no deben contarse, o el padding sobrepica de forma transitoria al
    // encadenar errores) más el gap entre ellos (12px, nodo-toast.css).
    function altoPilaVisible(box) {
        var hijos = box.children || [];
        var alto = 0;
        var count = 0;
        for (var i = 0; i < hijos.length; i++) {
            var h = hijos[i];
            if (h.classList && h.classList.contains('toast--leaving')) { continue; }
            alto += h.getBoundingClientRect().height;
            count++;
        }
        if (count > 1) { alto += (count - 1) * 12; }
        return alto;
    }
    function reservarEspacio() {
        var body = document.body;
        if (!body || !body.style) { return; }
        var box = document.getElementById('toast-container');
        var visibles = persistentes.filter(function (t) { return !t._closed; });
        var ctx = contextoModal();
        if (!box || ctx.modal || !visibles.length ||
            typeof box.getBoundingClientRect !== 'function') {
            restaurarEspacio();
            return;
        }
        var offset = ctx.movil ? 12 : 24;
        var alto = Math.ceil(altoPilaVisible(box)) + offset;
        if (padPrevio === null) {
            var cs = (typeof window.getComputedStyle === 'function') ? window.getComputedStyle(body) : null;
            padPrevio = {inline: body.style.paddingBottom || '', base: cs ? (parseFloat(cs.paddingBottom) || 0) : 0};
        }
        var nuevo = (padPrevio.base + alto) + 'px';
        if (body.style.paddingBottom !== nuevo) { body.style.paddingBottom = nuevo; }
    }

    var ubicarPendiente = false;
    function ubicarPilaLiviano(registros) {
        // Los cambios de estilo de la propia pila no reprograman nada (evita bucles).
        var box = document.getElementById('toast-container');
        if (registros && registros.length && box && typeof box.contains === 'function') {
            var ajeno = false;
            for (var i = 0; i < registros.length; i++) {
                var r = registros[i];
                // ni el estilo de la pila ni el padding del body (lo pone este módulo)
                if (box.contains(r.target) || (r.target === document.body && r.attributeName === 'style')) { continue; }
                ajeno = true; break;
            }
            if (!ajeno) { return; }
        }
        if (ubicarPendiente) { return; }
        ubicarPendiente = true;
        setTimeout(function () { ubicarPendiente = false; ubicarPila(); reservarEspacio(); }, 50);
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
