(function () {
    "use strict";

    const ACTION_SELECTOR = "button, a[href], [role='button']";
    const ICON_LABELS = {
        "fa-pen": "Editar",
        "fa-pencil": "Editar",
        "fa-edit": "Editar",
        "fa-trash": "Eliminar",
        "fa-trash-alt": "Eliminar",
        "fa-eye": "Ver detalles",
        "fa-search": "Buscar",
        "fa-download": "Descargar",
        "fa-upload": "Subir",
        "fa-print": "Imprimir",
        "fa-copy": "Copiar",
        "fa-plus": "Agregar",
        "fa-times": "Cerrar",
        "fa-xmark": "Cerrar",
        "fa-ellipsis-v": "Más acciones",
        "fa-ellipsis-vertical": "Más acciones",
        "fa-chevron-left": "Anterior",
        "fa-chevron-right": "Siguiente",
    };

    let tooltip;
    let activeTrigger;

    function iconLabel(element) {
        const icon = element.querySelector("i, svg");
        if (!icon) return "";
        for (const [className, label] of Object.entries(ICON_LABELS)) {
            if (icon.classList.contains(className)) return label;
        }
        return "";
    }

    function labelFor(element) {
        const explicit = element.dataset.tooltip || element.getAttribute("aria-label") || element.getAttribute("title");
        if (explicit && explicit.trim()) return explicit.trim();

        const visibleText = element.textContent.replace(/\s+/g, " ").trim();
        if (!visibleText) {
            const inferred = iconLabel(element);
            if (inferred) {
                element.setAttribute("aria-label", inferred);
                return inferred;
            }
        }
        return "";
    }

    function ensureTooltip() {
        if (tooltip) return tooltip;
        tooltip = document.createElement("div");
        tooltip.id = "nodo-global-tooltip";
        tooltip.className = "nodo-tooltip";
        tooltip.setAttribute("role", "tooltip");
        tooltip.setAttribute("data-visible", "false");
        tooltip.hidden = true;
        document.body.appendChild(tooltip);
        return tooltip;
    }

    function positionTooltip(trigger) {
        const tip = ensureTooltip();
        const triggerRect = trigger.getBoundingClientRect();
        const tipRect = tip.getBoundingClientRect();
        const margin = 8;
        const left = Math.min(
            window.innerWidth - tipRect.width - margin,
            Math.max(margin, triggerRect.left + (triggerRect.width - tipRect.width) / 2)
        );
        const fitsAbove = triggerRect.top >= tipRect.height + margin;
        const top = fitsAbove
            ? triggerRect.top - tipRect.height - margin
            : triggerRect.bottom + margin;
        tip.style.left = `${left}px`;
        tip.style.top = `${Math.max(margin, top)}px`;
    }

    function show(trigger) {
        const label = labelFor(trigger);
        if (!label) return;

        const tip = ensureTooltip();
        activeTrigger = trigger;
        tip.textContent = label;
        tip.hidden = false;
        trigger.setAttribute("aria-describedby", tip.id);
        requestAnimationFrame(function () {
            positionTooltip(trigger);
            tip.setAttribute("data-visible", "true");
        });
    }

    function hide(trigger) {
        if (!activeTrigger || (trigger && activeTrigger !== trigger)) return;
        const tip = ensureTooltip();
        activeTrigger.removeAttribute("aria-describedby");
        activeTrigger = null;
        tip.setAttribute("data-visible", "false");
        window.setTimeout(function () {
            if (!activeTrigger) tip.hidden = true;
        }, 150);
    }

    function actionFrom(target) {
        return target instanceof Element ? target.closest(ACTION_SELECTOR) : null;
    }

    document.addEventListener("pointerover", function (event) {
        const trigger = actionFrom(event.target);
        if (trigger && !trigger.contains(event.relatedTarget)) show(trigger);
    });
    document.addEventListener("pointerout", function (event) {
        const trigger = actionFrom(event.target);
        if (trigger && !trigger.contains(event.relatedTarget)) hide(trigger);
    });
    document.addEventListener("focusin", function (event) {
        const trigger = actionFrom(event.target);
        if (trigger) show(trigger);
    });
    document.addEventListener("focusout", function (event) {
        const trigger = actionFrom(event.target);
        if (trigger) hide(trigger);
    });
    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") hide();
    });
    window.addEventListener("scroll", function () { hide(); }, true);
    window.addEventListener("resize", function () { hide(); });
})();
