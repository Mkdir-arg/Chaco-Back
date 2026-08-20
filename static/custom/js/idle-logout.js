/*
 * idle-logout.js — Cierre de sesión automático por inactividad.
 *
 * Detecta actividad del usuario (movimiento del mouse, teclado, scroll, touch,
 * clicks). Mientras hay actividad NO cuenta; cuando el usuario se queda quieto
 * arranca a contar. Al llegar al timeout configurado cierra la sesión.
 *
 * El tiempo es configurable por variable de entorno
 * (SESSION_IDLE_TIMEOUT_MINUTES) y llega acá vía `window.idleLogoutConfig`,
 * que arma el template a partir del setting de Django. No hay valores mágicos
 * hardcodeados de tiempo en este archivo.
 *
 * Config esperada (window.idleLogoutConfig):
 *   { timeoutMinutes, warningSeconds, logoutUrl, csrfToken, redirectUrl }
 *
 * Nota: "detectar el mouse" se interpreta como "detectar actividad del
 * usuario". Además del mouse se escucha teclado / scroll / touch para no
 * cerrar la sesión de alguien que está tipeando un formulario largo sin mover
 * el mouse. Cualquiera de esos eventos reinicia el contador.
 */
(function () {
    "use strict";

    var cfg = window.idleLogoutConfig;
    if (!cfg || !cfg.logoutUrl) {
        return; // Sin config no hacemos nada (p. ej. usuario no autenticado).
    }

    var timeoutMs = Math.round((Number(cfg.timeoutMinutes) || 0) * 60 * 1000);
    if (timeoutMs <= 0) {
        return; // Timeout 0 o inválido => feature desactivada por entorno.
    }

    // Ventana de aviso previo (modal con cuenta regresiva). Se acota para que
    // nunca sea mayor a la mitad del timeout.
    var warningMs = Math.round((Number(cfg.warningSeconds) || 0) * 1000);
    if (warningMs < 0) warningMs = 0;
    if (warningMs > timeoutMs / 2) warningMs = Math.floor(timeoutMs / 2);

    var STORAGE_ACTIVITY = "chaco:idle:lastActivity";
    var STORAGE_LOGOUT = "chaco:idle:loggedOut";

    var lastActivity = Date.now();
    var lastBroadcast = 0;
    var warningShown = false;
    var loggingOut = false;
    var overlayEl = null;
    var countdownEl = null;

    // ── Actividad ────────────────────────────────────────────────────────────
    function markActivity() {
        if (loggingOut) return;
        lastActivity = Date.now();

        // Si el aviso estaba en pantalla y el usuario volvió (mouse/teclado/etc),
        // lo ocultamos: hay actividad, no cuenta.
        if (warningShown) hideWarning();

        // Propagar a otras pestañas (throttle ~2s para no castigar el mousemove).
        if (lastActivity - lastBroadcast > 2000) {
            lastBroadcast = lastActivity;
            try {
                localStorage.setItem(STORAGE_ACTIVITY, String(lastActivity));
            } catch (e) {
                /* localStorage puede fallar en modo privado: no es crítico */
            }
        }
    }

    var ACTIVITY_EVENTS = [
        "mousemove",
        "mousedown",
        "keydown",
        "wheel",
        "scroll",
        "touchstart",
        "click",
    ];
    ACTIVITY_EVENTS.forEach(function (evt) {
        window.addEventListener(evt, markActivity, { passive: true });
    });

    // Actividad en otra pestaña mantiene viva esta sesión; logout en otra
    // pestaña cierra también acá.
    window.addEventListener("storage", function (e) {
        if (e.key === STORAGE_ACTIVITY && e.newValue) {
            var ts = Number(e.newValue);
            if (ts > lastActivity) {
                lastActivity = ts;
                if (warningShown) hideWarning();
            }
        } else if (e.key === STORAGE_LOGOUT) {
            // Otra pestaña ya cerró sesión: recargar para que el backend
            // redirija al login (la sesión de servidor ya no existe).
            if (!loggingOut) {
                loggingOut = true;
                window.location.reload();
            }
        }
    });

    // ── Cierre de sesión ──────────────────────────────────────────────────────
    function doLogout() {
        if (loggingOut) return;
        loggingOut = true;

        try {
            localStorage.setItem(STORAGE_LOGOUT, String(Date.now()));
        } catch (e) {
            /* no crítico */
        }

        // POST al endpoint de logout con CSRF (Django LogoutView y el logout del
        // portal aceptan POST). El servidor redirige al login.
        var form = document.createElement("form");
        form.method = "POST";
        form.action = cfg.logoutUrl;
        form.style.display = "none";

        var token =
            cfg.csrfToken ||
            (document.querySelector("input[name=csrfmiddlewaretoken]") || {}).value;
        if (token) {
            var input = document.createElement("input");
            input.type = "hidden";
            input.name = "csrfmiddlewaretoken";
            input.value = token;
            form.appendChild(input);
        }

        document.body.appendChild(form);
        form.submit();
    }

    // ── Modal de aviso ─────────────────────────────────────────────────────────
    function buildOverlay() {
        var overlay = document.createElement("div");
        overlay.id = "idle-warning-overlay";
        overlay.setAttribute("role", "dialog");
        overlay.setAttribute("aria-modal", "true");
        overlay.setAttribute("aria-labelledby", "idle-warning-title");
        overlay.style.cssText =
            "position:fixed;inset:0;z-index:2000;display:flex;align-items:center;" +
            "justify-content:center;padding:1rem;background:rgba(0,0,0,0.5);" +
            "backdrop-filter:blur(4px);";

        var card = document.createElement("div");
        card.style.cssText =
            "width:100%;max-width:28rem;background:var(--bg-white);border-radius:1rem;" +
            "border:1px solid var(--border-base);box-shadow:var(--shadow-md);overflow:hidden;";

        card.innerHTML =
            '<div style="padding:1.5rem;border-bottom:1px solid var(--border-base);">' +
            '<div style="display:flex;align-items:center;gap:0.75rem;">' +
            '<div style="width:2.5rem;height:2.5rem;border-radius:0.5rem;display:flex;' +
            "align-items:center;justify-content:center;background:var(--bg-warning-soft);" +
            'color:var(--text-fg-warning);flex-shrink:0;">' +
            '<i class="fas fa-clock" aria-hidden="true"></i></div>' +
            '<h3 id="idle-warning-title" style="font-size:18px;font-weight:600;' +
            'color:var(--text-heading);margin:0;">Tu sesión está por cerrarse</h3>' +
            "</div></div>" +
            '<div style="padding:1.5rem;">' +
            '<p style="color:var(--text-body);line-height:1.6;margin:0;">' +
            "Detectamos inactividad. Por seguridad vamos a cerrar tu sesión en " +
            '<strong id="idle-warning-countdown" style="color:var(--text-heading);">--</strong> segundos.' +
            "</p></div>" +
            '<div style="padding:1.5rem;border-top:1px solid var(--border-base);display:flex;' +
            'flex-direction:column-reverse;gap:0.75rem;">' +
            '<button type="button" id="idle-warning-logout" class="btn-nodo btn-secondary btn-sm">' +
            "Cerrar sesión ahora</button>" +
            '<button type="button" id="idle-warning-stay" class="btn-nodo btn-brand btn-sm">' +
            "Seguir conectado</button>" +
            "</div>";

        overlay.appendChild(card);
        overlay.addEventListener("mousedown", function (e) {
            // Click fuera del card = seguir conectado (es actividad).
            if (e.target === overlay) markActivity();
        });
        return overlay;
    }

    function showWarning() {
        warningShown = true;
        if (!overlayEl) {
            overlayEl = buildOverlay();
            document.body.appendChild(overlayEl);
            countdownEl = overlayEl.querySelector("#idle-warning-countdown");
            overlayEl
                .querySelector("#idle-warning-stay")
                .addEventListener("click", markActivity);
            overlayEl
                .querySelector("#idle-warning-logout")
                .addEventListener("click", doLogout);
        }
        overlayEl.style.display = "flex";
        var stayBtn = overlayEl.querySelector("#idle-warning-stay");
        if (stayBtn) stayBtn.focus();
    }

    function hideWarning() {
        warningShown = false;
        if (overlayEl) overlayEl.style.display = "none";
    }

    // ── Loop de control (1s) ────────────────────────────────────────────────────
    function tick() {
        if (loggingOut) return;
        var idle = Date.now() - lastActivity;

        if (idle >= timeoutMs) {
            doLogout();
            return;
        }

        if (warningMs > 0 && idle >= timeoutMs - warningMs) {
            if (!warningShown) showWarning();
            var remaining = Math.max(0, Math.ceil((timeoutMs - idle) / 1000));
            if (countdownEl) countdownEl.textContent = String(remaining);
        } else if (warningShown) {
            hideWarning();
        }
    }

    setInterval(tick, 1000);
})();
