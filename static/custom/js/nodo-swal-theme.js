/**
 * NODO Design System — theming global de SweetAlert2 (fuente única).
 *
 * Se carga siempre desde includes/base.html, DESPUÉS de {% block customJS %}.
 * Como cada Swal.fire(...) existente referencia la variable global `Swal` recién
 * en el momento del click (no al parsear el script), reasignar `window.Swal` acá
 * -aunque este archivo se ejecute después del script de la página- alcanza para
 * que los 29 usos del repo (13 templates) hereden el theme sin tocar cada uno.
 *
 * Complementa a static/custom/css/nodo-swal.css (chrome del popup: radius,
 * shadow, tipografía, grid header/body/footer). Acá van los defaults de
 * comportamiento/clases que sólo se pueden fijar por JS:
 *   - buttonsStyling:false + customClass .btn-nodo (fallback para los
 *     Swal.fire('Error', msg, 'error') abreviados que hoy no pasan customClass).
 *   - showCloseButton (× en el header, requisito del canon §11) con aria-label
 *     "Cerrar" en es-AR.
 *   - recolor del ícono default de swal2 al tono del DS (bg/color por token)
 *     vía didRender — no depende de selectores CSS internos de swal2.
 */
(function () {
  function initNodoSwalTheme() {
    if (typeof Swal === 'undefined') return;

    var TONE_ICON = {
      success: { bg: 'var(--bg-success-soft)', fg: 'var(--text-fg-success)' },
      error: { bg: 'var(--bg-danger-soft)', fg: 'var(--text-fg-danger)' },
      warning: { bg: 'var(--bg-warning-soft)', fg: 'var(--text-fg-warning)' },
      info: { bg: 'var(--bg-info-soft)', fg: 'var(--text-fg-info)' },
      question: { bg: 'var(--bg-brand-soft)', fg: 'var(--text-fg-brand)' }
    };

    window.Swal = Swal.mixin({
      buttonsStyling: false,
      showCloseButton: true,
      showCloseButtonAriaLabel: 'Cerrar',
      customClass: {
        confirmButton: 'btn-nodo btn-brand btn-base',
        cancelButton: 'btn-nodo btn-tertiary btn-base',
        denyButton: 'btn-nodo btn-danger btn-base'
      },
      didRender: function (popup) {
        var icon = popup.querySelector('.swal2-icon');
        if (!icon) return;
        var tone = null;
        ['success', 'error', 'warning', 'info', 'question'].some(function (t) {
          if (icon.classList.contains('swal2-' + t)) {
            tone = TONE_ICON[t];
            return true;
          }
          return false;
        });
        if (tone) {
          icon.style.setProperty('background', tone.bg, 'important');
          icon.style.setProperty('color', tone.fg, 'important');
          icon.style.setProperty('border-color', 'transparent', 'important');
        }
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initNodoSwalTheme);
  } else {
    initNodoSwalTheme();
  }
})();
