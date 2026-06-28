/* @ds-bundle: {"format":3,"namespace":"ChacoNODODesignSystem_dc2a68","components":[{"name":"Avatar","sourcePath":"components/core/Avatar.jsx"},{"name":"Badge","sourcePath":"components/core/Badge.jsx"},{"name":"Button","sourcePath":"components/core/Button.jsx"},{"name":"Card","sourcePath":"components/core/Card.jsx"},{"name":"StatCard","sourcePath":"components/core/StatCard.jsx"},{"name":"Alert","sourcePath":"components/feedback/Alert.jsx"},{"name":"Modal","sourcePath":"components/feedback/Modal.jsx"},{"name":"Input","sourcePath":"components/forms/Input.jsx"},{"name":"Select","sourcePath":"components/forms/Select.jsx"},{"name":"Tabs","sourcePath":"components/navigation/Tabs.jsx"}],"sourceHashes":{"components/core/Avatar.jsx":"ff809a946a5e","components/core/Badge.jsx":"ed0703a0e961","components/core/Button.jsx":"97be62e4c702","components/core/Card.jsx":"59b0744781c4","components/core/StatCard.jsx":"e39a45dfb705","components/feedback/Alert.jsx":"060a3b2883a3","components/feedback/Modal.jsx":"e532a68e4715","components/forms/Input.jsx":"ceef20e31948","components/forms/Select.jsx":"267d40ef6a15","components/navigation/Tabs.jsx":"72acfe05d446","ui_kits/backoffice/Dashboard.jsx":"6f7a3a9964b9","ui_kits/backoffice/LegajoDetail.jsx":"44488b117a9a","ui_kits/backoffice/Legajos.jsx":"b2fff978535a","ui_kits/backoffice/Shell.jsx":"0264f1f57027","ui_kits/backoffice/data.js":"7d0ca8858bb7","ui_kits/inicio/data.js":"e3e453cd2185","ui_kits/inicio/icons.jsx":"fa513b8fae15","ui_kits/portal-ciudadano/PortalShell.jsx":"11905b990658","ui_kits/portal-ciudadano/data.js":"0edef666485c","ui_kits/programa-becas/data.js":"42b1c2610226","ui_kits/programa-becas/icons.jsx":"fa513b8fae15","ui_kits/programa-becas/inicio-data.js":"e3e453cd2185"},"inlinedExternals":[],"unexposedExports":[]} */

(() => {

const __ds_ns = (window.ChacoNODODesignSystem_dc2a68 = window.ChacoNODODesignSystem_dc2a68 || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// components/core/Avatar.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Avatar — circular user marker. Falls back to gradient initials (the
 * navbar avatar pattern) when no image is supplied.
 */
function Avatar({
  name = '',
  src,
  size = 40,
  square = false,
  style,
  ...rest
}) {
  const initials = name.split(' ').filter(Boolean).slice(0, 2).map(w => w[0].toUpperCase()).join('');
  return /*#__PURE__*/React.createElement("div", _extends({
    style: {
      width: size,
      height: size,
      flexShrink: 0,
      borderRadius: square ? 'var(--radius-lg)' : 'var(--radius-full)',
      background: src ? `center / cover no-repeat url(${src})` : 'var(--gradient-brand)',
      color: '#ffffff',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontFamily: 'var(--font-sans)',
      fontWeight: 700,
      fontSize: Math.round(size * 0.4),
      lineHeight: 1,
      userSelect: 'none',
      ...style
    },
    title: name || undefined
  }, rest), !src && (initials || /*#__PURE__*/React.createElement("i", {
    className: "fas fa-user",
    "aria-hidden": "true"
  })));
}
Object.assign(__ds_scope, { Avatar });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Avatar.jsx", error: String((e && e.message) || e) }); }

// components/core/Badge.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Badge — compact status pill. Soft tinted background + colored text,
 * matching the app's .badge-* rules (success/warning/danger/brand).
 */
function Badge({
  children,
  variant = 'neutral',
  size = 'sm',
  dot = false,
  icon,
  style,
  ...rest
}) {
  const variants = {
    neutral: {
      background: 'var(--bg-tertiary)',
      color: 'var(--color-gray-600)',
      border: 'var(--border-base)'
    },
    brand: {
      background: 'var(--bg-brand-soft)',
      color: 'var(--color-pink-900)',
      border: 'var(--border-brand-subtle)'
    },
    info: {
      background: 'var(--bg-info-soft)',
      color: 'var(--text-fg-info)',
      border: 'var(--color-brand-200)'
    },
    success: {
      background: 'var(--bg-success-soft)',
      color: 'var(--text-fg-success)',
      border: 'var(--border-success-subtle)'
    },
    warning: {
      background: 'var(--bg-warning-soft)',
      color: 'var(--text-fg-warning)',
      border: 'var(--border-warning-subtle)'
    },
    danger: {
      background: 'var(--bg-danger-soft)',
      color: 'var(--text-fg-danger)',
      border: 'var(--border-danger-subtle)'
    },
    solid: {
      background: 'var(--bg-brand)',
      color: '#ffffff',
      border: 'transparent'
    }
  };
  const sizes = {
    xs: {
      fontSize: 11,
      padding: '2px 8px',
      gap: 4
    },
    sm: {
      fontSize: 12,
      padding: '4px 12px',
      gap: 5
    },
    md: {
      fontSize: 14,
      padding: '6px 14px',
      gap: 6
    }
  };
  const vr = variants[variant] || variants.neutral;
  const sz = sizes[size] || sizes.sm;
  return /*#__PURE__*/React.createElement("span", _extends({
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: sz.gap,
      fontFamily: 'var(--font-sans)',
      fontSize: sz.fontSize,
      fontWeight: 600,
      lineHeight: 1.2,
      padding: sz.padding,
      borderRadius: 'var(--radius-full)',
      background: vr.background,
      color: vr.color,
      border: `1px solid ${vr.border}`,
      whiteSpace: 'nowrap',
      ...style
    }
  }, rest), dot && /*#__PURE__*/React.createElement("span", {
    style: {
      width: 6,
      height: 6,
      borderRadius: '50%',
      background: 'currentColor',
      flexShrink: 0
    }
  }), icon && /*#__PURE__*/React.createElement("i", {
    className: icon,
    "aria-hidden": "true"
  }), children);
}
Object.assign(__ds_scope, { Badge });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Badge.jsx", error: String((e && e.message) || e) }); }

// components/core/Button.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Button — the primary interactive control for Chaco / NODO surfaces.
 * Variants map 1:1 to the app's nodo-buttons.css (.btn-brand / .btn-secondary / .btn-tertiary).
 */
function Button({
  children,
  variant = 'brand',
  size = 'base',
  icon,
  iconNode,
  iconRight,
  block = false,
  disabled = false,
  type = 'button',
  onClick,
  style,
  ...rest
}) {
  const sizes = {
    xs: {
      height: 32,
      padding: '6px 12px',
      fontSize: 12
    },
    sm: {
      height: 36,
      padding: '8px 14px',
      fontSize: 14
    },
    base: {
      height: 40,
      padding: '10px 16px',
      fontSize: 14
    },
    lg: {
      height: 48,
      padding: '12px 20px',
      fontSize: 16
    },
    xl: {
      height: 52,
      padding: '14px 24px',
      fontSize: 16
    }
  };
  const variants = {
    brand: {
      background: 'var(--gradient-brand)',
      color: '#ffffff',
      border: '1px solid transparent'
    },
    primary: {
      background: 'var(--bg-brand)',
      color: '#ffffff',
      border: '1px solid transparent'
    },
    secondary: {
      background: 'var(--bg-secondary)',
      color: 'var(--color-gray-600)',
      border: '1px solid var(--border-base)'
    },
    tertiary: {
      background: 'var(--bg-white)',
      color: 'var(--text-fg-brand)',
      border: '1px solid var(--border-brand)'
    },
    ghost: {
      background: 'transparent',
      color: 'var(--text-fg-brand)',
      border: '1px solid transparent'
    },
    danger: {
      background: 'var(--bg-danger)',
      color: '#ffffff',
      border: '1px solid transparent'
    }
  };
  const sz = sizes[size] || sizes.base;
  const vr = variants[variant] || variants.brand;
  return /*#__PURE__*/React.createElement("button", _extends({
    type: type,
    disabled: disabled,
    onClick: onClick,
    style: {
      display: block ? 'flex' : 'inline-flex',
      width: block ? '100%' : undefined,
      alignItems: 'center',
      justifyContent: 'center',
      gap: 8,
      height: sz.height,
      padding: sz.padding,
      fontFamily: 'var(--font-sans)',
      fontSize: sz.fontSize,
      fontWeight: 600,
      lineHeight: 1,
      borderRadius: 'var(--radius-full)',
      cursor: disabled ? 'not-allowed' : 'pointer',
      opacity: disabled ? 0.55 : 1,
      transition: 'filter var(--duration-fast) var(--ease-standard), background var(--duration-fast) var(--ease-standard)',
      whiteSpace: 'nowrap',
      ...vr,
      ...style
    },
    onMouseEnter: e => {
      if (disabled) return;
      if (variant === 'tertiary') e.currentTarget.style.background = 'var(--bg-brand-tint)';else e.currentTarget.style.filter = 'brightness(0.93)';
    },
    onMouseLeave: e => {
      e.currentTarget.style.filter = 'none';
      if (variant === 'tertiary') e.currentTarget.style.background = 'var(--bg-white)';
    }
  }, rest), iconNode, icon && /*#__PURE__*/React.createElement("i", {
    className: icon,
    "aria-hidden": "true"
  }), children && /*#__PURE__*/React.createElement("span", null, children), iconRight && /*#__PURE__*/React.createElement("i", {
    className: iconRight,
    "aria-hidden": "true"
  }));
}
Object.assign(__ds_scope, { Button });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Button.jsx", error: String((e && e.message) || e) }); }

// components/core/Card.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Card — the base white surface used everywhere in the backoffice and portal.
 * 12px radius, hairline border, soft shadow. Optional header / footer slots.
 */
function Card({
  children,
  title,
  subtitle,
  headerRight,
  footer,
  padding = 24,
  hover = false,
  accent,
  style,
  ...rest
}) {
  return /*#__PURE__*/React.createElement("div", _extends({
    style: {
      background: 'var(--bg-primary)',
      border: '1px solid var(--border-base)',
      borderRadius: 'var(--radius-xl)',
      boxShadow: 'var(--shadow-sm)',
      overflow: 'hidden',
      transition: 'box-shadow var(--duration-normal) var(--ease-standard), transform var(--duration-normal) var(--ease-standard)',
      ...(accent ? {
        borderTop: `3px solid ${accent}`
      } : null),
      ...style
    },
    onMouseEnter: e => {
      if (hover) {
        e.currentTarget.style.boxShadow = 'var(--shadow-lg)';
        e.currentTarget.style.transform = 'translateY(-2px)';
      }
    },
    onMouseLeave: e => {
      if (hover) {
        e.currentTarget.style.boxShadow = 'var(--shadow-sm)';
        e.currentTarget.style.transform = 'none';
      }
    }
  }, rest), (title || headerRight) && /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'flex-start',
      justifyContent: 'space-between',
      gap: 16,
      padding: '16px 20px',
      borderBottom: '1px solid var(--border-light)'
    }
  }, /*#__PURE__*/React.createElement("div", null, title && /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'var(--font-sans)',
      fontSize: 16,
      fontWeight: 700,
      color: 'var(--text-heading)'
    }
  }, title), subtitle && /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 13,
      color: 'var(--text-body-subtle)',
      marginTop: 2
    }
  }, subtitle)), headerRight && /*#__PURE__*/React.createElement("div", {
    style: {
      flexShrink: 0
    }
  }, headerRight)), /*#__PURE__*/React.createElement("div", {
    style: {
      padding
    }
  }, children), footer && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '14px 20px',
      borderTop: '1px solid var(--border-light)',
      background: 'var(--bg-secondary)'
    }
  }, footer));
}
Object.assign(__ds_scope, { Card });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Card.jsx", error: String((e && e.message) || e) }); }

// components/core/StatCard.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * StatCard — KPI tile with a tinted icon square, value and label, plus an
 * optional trend indicator. Mirrors the dashboard stat cards.
 */
function StatCard({
  label,
  value,
  icon,
  iconNode,
  tone = 'brand',
  change,
  changeDir = 'up',
  footnote,
  gradientIcon = false,
  alert = false,
  style,
  ...rest
}) {
  const tones = {
    brand: {
      bg: 'var(--bg-brand-soft)',
      fg: 'var(--text-fg-brand)'
    },
    success: {
      bg: 'var(--bg-success-soft)',
      fg: 'var(--text-fg-success)'
    },
    warning: {
      bg: 'var(--bg-warning-soft)',
      fg: 'var(--text-fg-warning)'
    },
    danger: {
      bg: 'var(--bg-danger-soft)',
      fg: 'var(--text-fg-danger)'
    },
    olive: {
      bg: 'var(--color-olive-200)',
      fg: 'var(--color-olive-700)'
    },
    neutral: {
      bg: 'var(--bg-tertiary)',
      fg: 'var(--color-gray-600)'
    }
  };
  const t = tones[tone] || tones.brand;
  const trend = {
    up: {
      color: 'var(--text-fg-success)',
      icon: 'fas fa-arrow-up'
    },
    down: {
      color: 'var(--text-fg-danger)',
      icon: 'fas fa-arrow-down'
    },
    flat: {
      color: 'var(--text-body-subtle)',
      icon: 'fas fa-minus'
    }
  }[changeDir] || {};
  return /*#__PURE__*/React.createElement("div", _extends({
    style: {
      background: 'var(--bg-primary)',
      border: '1px solid var(--border-base)',
      borderRadius: 'var(--radius-xl)',
      boxShadow: 'var(--shadow-sm)',
      padding: 20,
      display: 'flex',
      flexDirection: 'column',
      gap: 14,
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: 12
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 13,
      fontWeight: 600,
      color: 'var(--text-body-subtle)'
    }
  }, label), (icon || iconNode) && /*#__PURE__*/React.createElement("div", {
    style: {
      width: 44,
      height: 44,
      flexShrink: 0,
      borderRadius: 'var(--radius-lg)',
      background: gradientIcon ? 'var(--gradient-brand)' : t.bg,
      color: gradientIcon ? '#fff' : t.fg,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontSize: 18,
      position: 'relative'
    }
  }, iconNode || /*#__PURE__*/React.createElement("i", {
    className: icon,
    "aria-hidden": "true"
  }), alert && /*#__PURE__*/React.createElement("span", {
    style: {
      position: 'absolute',
      top: -2,
      right: -2,
      width: 10,
      height: 10,
      borderRadius: '50%',
      background: 'var(--bg-danger)',
      border: '2px solid var(--bg-primary)'
    }
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'baseline',
      gap: 10
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'var(--font-sans)',
      fontSize: 32,
      fontWeight: 800,
      color: 'var(--text-heading)',
      lineHeight: 1
    }
  }, value), change != null && /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 4,
      fontSize: 13,
      fontWeight: 600,
      color: trend.color
    }
  }, /*#__PURE__*/React.createElement("i", {
    className: trend.icon,
    "aria-hidden": "true"
  }), change)), footnote && /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      color: 'var(--text-body-subtle)'
    }
  }, footnote));
}
Object.assign(__ds_scope, { StatCard });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/StatCard.jsx", error: String((e && e.message) || e) }); }

// components/feedback/Alert.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Alert — inline message banner. Soft tinted background, leading icon,
 * optional title and dismiss. Matches the portal/backoffice message style.
 */
function Alert({
  children,
  variant = 'info',
  title,
  icon,
  onClose,
  style,
  ...rest
}) {
  const variants = {
    info: {
      bg: 'var(--bg-info-soft)',
      fg: 'var(--text-fg-info)',
      bd: 'var(--color-brand-200)',
      ic: 'fas fa-circle-info'
    },
    success: {
      bg: 'var(--bg-success-soft)',
      fg: 'var(--text-fg-success)',
      bd: 'var(--border-success-subtle)',
      ic: 'fas fa-circle-check'
    },
    warning: {
      bg: 'var(--bg-warning-soft)',
      fg: 'var(--text-fg-warning)',
      bd: 'var(--border-warning-subtle)',
      ic: 'fas fa-triangle-exclamation'
    },
    danger: {
      bg: 'var(--bg-danger-soft)',
      fg: 'var(--text-fg-danger)',
      bd: 'var(--border-danger-subtle)',
      ic: 'fas fa-circle-exclamation'
    }
  };
  const v = variants[variant] || variants.info;
  return /*#__PURE__*/React.createElement("div", _extends({
    role: "alert",
    style: {
      display: 'flex',
      alignItems: 'flex-start',
      gap: 12,
      padding: '14px 16px',
      background: v.bg,
      border: `1px solid ${v.bd}`,
      borderRadius: 'var(--radius-xl)',
      color: v.fg,
      fontFamily: 'var(--font-sans)',
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("i", {
    className: icon || v.ic,
    "aria-hidden": "true",
    style: {
      fontSize: 16,
      marginTop: 2,
      flexShrink: 0
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      minWidth: 0
    }
  }, title && /*#__PURE__*/React.createElement("div", {
    style: {
      fontWeight: 700,
      fontSize: 14,
      marginBottom: children ? 2 : 0
    }
  }, title), children && /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 13.5,
      lineHeight: 1.5,
      color: 'var(--text-body)'
    }
  }, children)), onClose && /*#__PURE__*/React.createElement("button", {
    onClick: onClose,
    "aria-label": "Cerrar",
    style: {
      background: 'none',
      border: 'none',
      color: 'inherit',
      cursor: 'pointer',
      fontSize: 15,
      opacity: 0.7,
      padding: 2,
      lineHeight: 1
    }
  }, /*#__PURE__*/React.createElement("i", {
    className: "fas fa-xmark",
    "aria-hidden": "true"
  })));
}
Object.assign(__ds_scope, { Alert });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/Alert.jsx", error: String((e && e.message) || e) }); }

// components/feedback/Modal.jsx
try { (() => {
/**
 * Modal — centered dialog over a dimmed, blurred backdrop. Matches the
 * app's ModernModal: header with tinted icon, body, action footer.
 */
function Modal({
  open = true,
  title,
  icon,
  tone = 'info',
  children,
  onClose,
  footer,
  width = 480,
  style
}) {
  if (!open) return null;
  const tones = {
    info: {
      bg: 'var(--bg-info-soft)',
      fg: 'var(--text-fg-info)',
      ic: 'fas fa-circle-info'
    },
    success: {
      bg: 'var(--bg-success-soft)',
      fg: 'var(--text-fg-success)',
      ic: 'fas fa-circle-check'
    },
    warning: {
      bg: 'var(--bg-warning-soft)',
      fg: 'var(--text-fg-warning)',
      ic: 'fas fa-triangle-exclamation'
    },
    danger: {
      bg: 'var(--bg-danger-soft)',
      fg: 'var(--text-fg-danger)',
      ic: 'fas fa-circle-exclamation'
    },
    brand: {
      bg: 'var(--bg-brand-soft)',
      fg: 'var(--text-fg-brand)',
      ic: 'fas fa-bell'
    }
  };
  const t = tones[tone] || tones.info;
  return /*#__PURE__*/React.createElement("div", {
    onClick: e => {
      if (e.target === e.currentTarget && onClose) onClose();
    },
    style: {
      position: 'fixed',
      inset: 0,
      zIndex: 50,
      background: 'rgba(0,0,0,0.5)',
      backdropFilter: 'blur(4px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: 16
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: '100%',
      maxWidth: width,
      background: 'var(--bg-white)',
      borderRadius: 'var(--radius-2xl)',
      boxShadow: 'var(--shadow-xl)',
      overflow: 'hidden',
      fontFamily: 'var(--font-sans)',
      ...style
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: 12,
      padding: '20px 24px',
      borderBottom: '1px solid var(--border-light)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 12
    }
  }, (icon || t.ic) && /*#__PURE__*/React.createElement("div", {
    style: {
      width: 40,
      height: 40,
      borderRadius: 'var(--radius-lg)',
      background: t.bg,
      color: t.fg,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontSize: 18
    }
  }, /*#__PURE__*/React.createElement("i", {
    className: icon || t.ic,
    "aria-hidden": "true"
  })), /*#__PURE__*/React.createElement("h3", {
    style: {
      margin: 0,
      fontSize: 18,
      fontWeight: 700,
      color: 'var(--text-heading)'
    }
  }, title)), onClose && /*#__PURE__*/React.createElement("button", {
    onClick: onClose,
    "aria-label": "Cerrar",
    style: {
      background: 'none',
      border: 'none',
      color: 'var(--text-body-subtle)',
      cursor: 'pointer',
      fontSize: 18,
      padding: 4,
      lineHeight: 1
    }
  }, /*#__PURE__*/React.createElement("i", {
    className: "fas fa-xmark",
    "aria-hidden": "true"
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 24,
      fontSize: 14,
      lineHeight: 1.6,
      color: 'var(--text-body)'
    }
  }, children), footer && /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'flex-end',
      gap: 12,
      padding: '16px 24px',
      borderTop: '1px solid var(--border-light)',
      background: 'var(--bg-secondary)'
    }
  }, footer)));
}
Object.assign(__ds_scope, { Modal });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/Modal.jsx", error: String((e && e.message) || e) }); }

// components/forms/Input.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Input — labelled text field with optional leading icon, helper / error text.
 * Focus ring uses the brand color; error switches border + ring to rose.
 */
function Input({
  label,
  value,
  defaultValue,
  placeholder,
  type = 'text',
  icon,
  iconNode,
  error,
  helper,
  required = false,
  disabled = false,
  onChange,
  id,
  style,
  ...rest
}) {
  const [focused, setFocused] = React.useState(false);
  const fieldId = id || (label ? `inp-${String(label).replace(/\s+/g, '-').toLowerCase()}` : undefined);
  const borderColor = error ? 'var(--border-danger)' : focused ? 'var(--border-brand)' : 'var(--border-base)';
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 6,
      ...style
    }
  }, label && /*#__PURE__*/React.createElement("label", {
    htmlFor: fieldId,
    style: {
      fontFamily: 'var(--font-sans)',
      fontSize: 13,
      fontWeight: 600,
      color: 'var(--text-heading)'
    }
  }, label, required && /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-fg-danger)',
      marginLeft: 3
    }
  }, "*")), /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'relative',
      display: 'flex',
      alignItems: 'center'
    }
  }, icon && /*#__PURE__*/React.createElement("i", {
    className: icon,
    "aria-hidden": "true",
    style: {
      position: 'absolute',
      left: 14,
      color: 'var(--text-body-subtle)',
      fontSize: 14,
      pointerEvents: 'none'
    }
  }), iconNode && /*#__PURE__*/React.createElement("span", {
    "aria-hidden": "true",
    style: {
      position: 'absolute',
      left: 12,
      color: 'var(--text-body-subtle)',
      display: 'inline-flex',
      pointerEvents: 'none'
    }
  }, iconNode), /*#__PURE__*/React.createElement("input", _extends({
    id: fieldId,
    type: type,
    value: value,
    defaultValue: defaultValue,
    placeholder: placeholder,
    required: required,
    disabled: disabled,
    onChange: onChange,
    onFocus: () => setFocused(true),
    onBlur: () => setFocused(false),
    style: {
      width: '100%',
      height: 42,
      padding: icon || iconNode ? '0 14px 0 40px' : '0 14px',
      fontFamily: 'var(--font-sans)',
      fontSize: 14,
      color: 'var(--text-heading)',
      background: disabled ? 'var(--bg-disabled)' : 'var(--bg-white)',
      border: `1px solid ${borderColor}`,
      borderRadius: 'var(--radius-lg)',
      outline: 'none',
      boxShadow: focused ? error ? 'var(--ring-danger)' : 'var(--ring-brand)' : 'none',
      transition: 'border-color var(--duration-fast) var(--ease-standard), box-shadow var(--duration-fast) var(--ease-standard)'
    }
  }, rest))), (error || helper) && /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      color: error ? 'var(--text-fg-danger)' : 'var(--text-body-subtle)'
    }
  }, error || helper));
}
Object.assign(__ds_scope, { Input });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Input.jsx", error: String((e && e.message) || e) }); }

// components/forms/Select.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Select — labelled native dropdown styled to match Input.
 */
function Select({
  label,
  value,
  defaultValue,
  options = [],
  placeholder,
  error,
  helper,
  required = false,
  disabled = false,
  onChange,
  id,
  style,
  ...rest
}) {
  const [focused, setFocused] = React.useState(false);
  const fieldId = id || (label ? `sel-${String(label).replace(/\s+/g, '-').toLowerCase()}` : undefined);
  const borderColor = error ? 'var(--border-danger)' : focused ? 'var(--border-brand)' : 'var(--border-base)';
  const norm = options.map(o => typeof o === 'string' ? {
    value: o,
    label: o
  } : o);
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 6,
      ...style
    }
  }, label && /*#__PURE__*/React.createElement("label", {
    htmlFor: fieldId,
    style: {
      fontFamily: 'var(--font-sans)',
      fontSize: 13,
      fontWeight: 600,
      color: 'var(--text-heading)'
    }
  }, label, required && /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-fg-danger)',
      marginLeft: 3
    }
  }, "*")), /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'relative',
      display: 'flex',
      alignItems: 'center'
    }
  }, /*#__PURE__*/React.createElement("select", _extends({
    id: fieldId,
    value: value,
    defaultValue: defaultValue,
    required: required,
    disabled: disabled,
    onChange: onChange,
    onFocus: () => setFocused(true),
    onBlur: () => setFocused(false),
    style: {
      width: '100%',
      height: 42,
      padding: '0 38px 0 14px',
      fontFamily: 'var(--font-sans)',
      fontSize: 14,
      color: 'var(--text-heading)',
      background: disabled ? 'var(--bg-disabled)' : 'var(--bg-white)',
      border: `1px solid ${borderColor}`,
      borderRadius: 'var(--radius-lg)',
      outline: 'none',
      appearance: 'none',
      WebkitAppearance: 'none',
      cursor: disabled ? 'not-allowed' : 'pointer',
      boxShadow: focused ? 'var(--ring-brand)' : 'none',
      transition: 'border-color var(--duration-fast) var(--ease-standard), box-shadow var(--duration-fast) var(--ease-standard)'
    }
  }, rest), placeholder && /*#__PURE__*/React.createElement("option", {
    value: "",
    disabled: true
  }, placeholder), norm.map(o => /*#__PURE__*/React.createElement("option", {
    key: o.value,
    value: o.value
  }, o.label))), /*#__PURE__*/React.createElement("i", {
    className: "fas fa-chevron-down",
    "aria-hidden": "true",
    style: {
      position: 'absolute',
      right: 14,
      color: 'var(--text-body-subtle)',
      fontSize: 12,
      pointerEvents: 'none'
    }
  })), (error || helper) && /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      color: error ? 'var(--text-fg-danger)' : 'var(--text-body-subtle)'
    }
  }, error || helper));
}
Object.assign(__ds_scope, { Select });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Select.jsx", error: String((e && e.message) || e) }); }

// components/navigation/Tabs.jsx
try { (() => {
/**
 * Tabs — horizontal tab bar with an underline indicator on the active item.
 * Controlled (value/onChange) or uncontrolled (defaultValue).
 */
function Tabs({
  tabs = [],
  value,
  defaultValue,
  onChange,
  style
}) {
  const norm = tabs.map(t => typeof t === 'string' ? {
    value: t,
    label: t
  } : t);
  const [internal, setInternal] = React.useState(defaultValue ?? norm[0]?.value);
  const active = value ?? internal;
  const select = v => {
    if (value === undefined) setInternal(v);
    onChange && onChange(v);
  };
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 4,
      borderBottom: '1px solid var(--border-base)',
      fontFamily: 'var(--font-sans)',
      ...style
    }
  }, norm.map(t => {
    const on = t.value === active;
    return /*#__PURE__*/React.createElement("button", {
      key: t.value,
      onClick: () => select(t.value),
      style: {
        display: 'inline-flex',
        alignItems: 'center',
        gap: 8,
        padding: '12px 16px',
        background: 'none',
        border: 'none',
        cursor: 'pointer',
        fontSize: 14,
        fontWeight: on ? 700 : 500,
        color: on ? 'var(--text-fg-brand)' : 'var(--text-body-subtle)',
        borderBottom: `2px solid ${on ? 'var(--bg-brand)' : 'transparent'}`,
        marginBottom: -1,
        transition: 'color var(--duration-fast) var(--ease-standard)',
        whiteSpace: 'nowrap'
      }
    }, t.iconNode, t.icon && /*#__PURE__*/React.createElement("i", {
      className: t.icon,
      "aria-hidden": "true"
    }), t.label, t.count != null && /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 11,
        fontWeight: 700,
        padding: '1px 7px',
        borderRadius: 'var(--radius-full)',
        background: on ? 'var(--bg-brand-soft)' : 'var(--bg-tertiary)',
        color: on ? 'var(--text-fg-brand)' : 'var(--text-body-subtle)'
      }
    }, t.count));
  }));
}
Object.assign(__ds_scope, { Tabs });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/navigation/Tabs.jsx", error: String((e && e.message) || e) }); }

// ui_kits/backoffice/Dashboard.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
// Dashboard (Inicio) screen.
(function () {
  const DS = window.ChacoNODODesignSystem_dc2a68;
  function Dashboard({
    onOpenLegajo
  }) {
    const M = window.MOCK;
    const toneColor = {
      brand: 'var(--text-fg-brand)',
      success: 'var(--text-fg-success)',
      olive: 'var(--color-olive-600)',
      danger: 'var(--text-fg-danger)'
    };
    const toneBg = {
      brand: 'var(--bg-brand-soft)',
      success: 'var(--bg-success-soft)',
      olive: 'var(--color-olive-200)',
      danger: 'var(--bg-danger-soft)'
    };
    return /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        flexDirection: 'column',
        gap: 20
      }
    }, /*#__PURE__*/React.createElement(DS.Alert, {
      variant: "info",
      title: "Bienvenida, Mar\xEDa"
    }, "Ten\xE9s 6 consultas sin asignar y 4 alertas cr\xEDticas pendientes de revisi\xF3n esta semana."), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'grid',
        gridTemplateColumns: 'repeat(4, 1fr)',
        gap: 16
      }
    }, M.stats.map((s, i) => /*#__PURE__*/React.createElement(DS.StatCard, _extends({
      key: i
    }, s)))), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'grid',
        gridTemplateColumns: '1.6fr 1fr',
        gap: 20,
        alignItems: 'start'
      }
    }, /*#__PURE__*/React.createElement(DS.Card, {
      title: "Legajos recientes",
      subtitle: "\xDAltimas actualizaciones",
      headerRight: /*#__PURE__*/React.createElement(DS.Button, {
        size: "sm",
        variant: "ghost",
        iconRight: "fas fa-arrow-right",
        onClick: () => onOpenLegajo()
      }, "Ver todos"),
      padding: 0
    }, /*#__PURE__*/React.createElement("table", {
      style: {
        width: '100%',
        borderCollapse: 'collapse',
        fontFamily: 'var(--font-sans)'
      }
    }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", {
      style: {
        textAlign: 'left',
        fontSize: 11,
        textTransform: 'uppercase',
        letterSpacing: '.05em',
        color: 'var(--text-body-subtle)'
      }
    }, /*#__PURE__*/React.createElement("th", {
      style: {
        padding: '10px 20px',
        fontWeight: 700
      }
    }, "Ciudadano"), /*#__PURE__*/React.createElement("th", {
      style: {
        padding: '10px 12px',
        fontWeight: 700
      }
    }, "Programa"), /*#__PURE__*/React.createElement("th", {
      style: {
        padding: '10px 12px',
        fontWeight: 700
      }
    }, "Estado"), /*#__PURE__*/React.createElement("th", {
      style: {
        padding: '10px 20px',
        fontWeight: 700,
        textAlign: 'right'
      }
    }, "Actualizado"))), /*#__PURE__*/React.createElement("tbody", null, M.legajos.slice(0, 5).map(l => {
      const e = M.estados[l.estado];
      return /*#__PURE__*/React.createElement("tr", {
        key: l.id,
        onClick: () => onOpenLegajo(l),
        style: {
          cursor: 'pointer',
          borderTop: '1px solid var(--border-light)'
        },
        onMouseEnter: ev => ev.currentTarget.style.background = 'var(--bg-secondary)',
        onMouseLeave: ev => ev.currentTarget.style.background = 'transparent'
      }, /*#__PURE__*/React.createElement("td", {
        style: {
          padding: '12px 20px'
        }
      }, /*#__PURE__*/React.createElement("div", {
        style: {
          display: 'flex',
          alignItems: 'center',
          gap: 10
        }
      }, /*#__PURE__*/React.createElement(DS.Avatar, {
        name: l.nombre,
        size: 32
      }), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
        style: {
          fontSize: 13.5,
          fontWeight: 700,
          color: 'var(--text-heading)'
        }
      }, l.nombre), /*#__PURE__*/React.createElement("div", {
        style: {
          fontSize: 11.5,
          color: 'var(--text-body-subtle)'
        }
      }, "DNI ", l.dni, " \xB7 ", l.localidad)))), /*#__PURE__*/React.createElement("td", {
        style: {
          padding: '12px',
          fontSize: 13,
          color: 'var(--text-body)'
        }
      }, l.programa), /*#__PURE__*/React.createElement("td", {
        style: {
          padding: '12px'
        }
      }, /*#__PURE__*/React.createElement(DS.Badge, {
        variant: e.variant,
        dot: e.dot
      }, e.label)), /*#__PURE__*/React.createElement("td", {
        style: {
          padding: '12px 20px',
          fontSize: 12.5,
          color: 'var(--text-body-subtle)',
          textAlign: 'right'
        }
      }, l.actualizado));
    })))), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        flexDirection: 'column',
        gap: 20
      }
    }, /*#__PURE__*/React.createElement(DS.Card, {
      title: "Actividad reciente",
      padding: 0
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        flexDirection: 'column'
      }
    }, M.actividad.map((a, i) => /*#__PURE__*/React.createElement("div", {
      key: i,
      style: {
        display: 'flex',
        gap: 12,
        padding: '12px 20px',
        borderTop: i ? '1px solid var(--border-light)' : 'none'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        width: 32,
        height: 32,
        flexShrink: 0,
        borderRadius: 'var(--radius-lg)',
        background: toneBg[a.tone],
        color: toneColor[a.tone],
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: 13
      }
    }, /*#__PURE__*/React.createElement("i", {
      className: a.icon
    })), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 13,
        color: 'var(--text-body)',
        lineHeight: 1.4
      }
    }, a.text), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 11,
        color: 'var(--text-body-subtle)',
        marginTop: 2
      }
    }, a.time)))))), /*#__PURE__*/React.createElement(DS.Card, {
      title: "Cobertura por programa",
      subtitle: "Distribuci\xF3n de legajos activos"
    }, [['Tarjeta Alimentar', 46, 'var(--bg-brand)'], ['Potenciar Trabajo', 28, 'var(--color-olive-500)'], ['Becas Progresar', 18, 'var(--bg-pink)'], ['Otros', 8, 'var(--bg-quaternary)']].map(([name, pct, color]) => /*#__PURE__*/React.createElement("div", {
      key: name,
      style: {
        marginBottom: 12
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        justifyContent: 'space-between',
        fontSize: 12.5,
        marginBottom: 5,
        color: 'var(--text-body)'
      }
    }, /*#__PURE__*/React.createElement("span", null, name), /*#__PURE__*/React.createElement("span", {
      style: {
        fontWeight: 700,
        color: 'var(--text-heading)'
      }
    }, pct, "%")), /*#__PURE__*/React.createElement("div", {
      style: {
        height: 8,
        borderRadius: 'var(--radius-full)',
        background: 'var(--bg-tertiary)'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        width: pct + '%',
        height: '100%',
        borderRadius: 'var(--radius-full)',
        background: color
      }
    }))))))));
  }
  window.Dashboard = Dashboard;
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/backoffice/Dashboard.jsx", error: String((e && e.message) || e) }); }

// ui_kits/backoffice/LegajoDetail.jsx
try { (() => {
// Legajo detail screen: header + tabs + per-tab content.
(function () {
  const DS = window.ChacoNODODesignSystem_dc2a68;
  function LegajoDetail({
    legajo,
    onBack
  }) {
    const M = window.MOCK;
    const l = legajo || M.legajos[0];
    const e = M.estados[l.estado];
    const [tab, setTab] = React.useState('datos');
    const Field = ({
      label,
      value
    }) => /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 11,
        textTransform: 'uppercase',
        letterSpacing: '.05em',
        color: 'var(--text-body-subtle)',
        fontWeight: 700,
        marginBottom: 3
      }
    }, label), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 14,
        color: 'var(--text-heading)',
        fontWeight: 600
      }
    }, value));
    return /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        flexDirection: 'column',
        gap: 18
      }
    }, /*#__PURE__*/React.createElement("button", {
      onClick: onBack,
      style: {
        alignSelf: 'flex-start',
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        background: 'none',
        border: 'none',
        cursor: 'pointer',
        color: 'var(--text-fg-brand)',
        fontFamily: 'var(--font-sans)',
        fontSize: 13.5,
        fontWeight: 600,
        padding: 0
      }
    }, /*#__PURE__*/React.createElement("i", {
      className: "fas fa-arrow-left"
    }), " Volver a legajos"), /*#__PURE__*/React.createElement(DS.Card, {
      padding: 20
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 16,
        flexWrap: 'wrap'
      }
    }, /*#__PURE__*/React.createElement(DS.Avatar, {
      name: l.nombre,
      size: 60
    }), /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1,
        minWidth: 200
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        flexWrap: 'wrap'
      }
    }, /*#__PURE__*/React.createElement("h2", {
      style: {
        margin: 0,
        fontSize: 22,
        color: 'var(--text-heading)'
      }
    }, l.nombre), /*#__PURE__*/React.createElement(DS.Badge, {
      variant: e.variant,
      dot: e.dot
    }, e.label)), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 13,
        color: 'var(--text-body-subtle)',
        marginTop: 4
      }
    }, "Legajo #", String(l.id).padStart(5, '0'), " \xB7 DNI ", l.dni, " \xB7 ", l.localidad, ", Chaco")), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        gap: 10
      }
    }, /*#__PURE__*/React.createElement(DS.Button, {
      variant: "secondary",
      icon: "fas fa-print"
    }, "Imprimir"), /*#__PURE__*/React.createElement(DS.Button, {
      variant: "brand",
      icon: "fas fa-pen"
    }, "Editar legajo")))), /*#__PURE__*/React.createElement(DS.Card, {
      padding: 0
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        padding: '4px 16px 0'
      }
    }, /*#__PURE__*/React.createElement(DS.Tabs, {
      value: tab,
      onChange: setTab,
      tabs: [{
        value: 'datos',
        label: 'Datos personales',
        icon: 'fas fa-user'
      }, {
        value: 'familia',
        label: 'Grupo familiar',
        icon: 'fas fa-people-roof',
        count: M.familia.length
      }, {
        value: 'programas',
        label: 'Programas',
        icon: 'fas fa-hand-holding-heart'
      }, {
        value: 'archivos',
        label: 'Archivos',
        icon: 'fas fa-paperclip',
        count: 12
      }]
    })), /*#__PURE__*/React.createElement("div", {
      style: {
        padding: 24
      }
    }, tab === 'datos' && /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'grid',
        gridTemplateColumns: 'repeat(3, 1fr)',
        gap: 22
      }
    }, /*#__PURE__*/React.createElement(Field, {
      label: "Apellido y nombre",
      value: l.nombre
    }), /*#__PURE__*/React.createElement(Field, {
      label: "DNI",
      value: l.dni
    }), /*#__PURE__*/React.createElement(Field, {
      label: "Fecha de nacimiento",
      value: "14/03/1987"
    }), /*#__PURE__*/React.createElement(Field, {
      label: "Localidad",
      value: l.localidad
    }), /*#__PURE__*/React.createElement(Field, {
      label: "Domicilio",
      value: "Av. 25 de Mayo 1240"
    }), /*#__PURE__*/React.createElement(Field, {
      label: "Tel\xE9fono",
      value: "362 4 55-1188"
    }), /*#__PURE__*/React.createElement(Field, {
      label: "Programa principal",
      value: l.programa
    }), /*#__PURE__*/React.createElement(Field, {
      label: "Integrantes",
      value: l.integrantes + ' personas'
    }), /*#__PURE__*/React.createElement(Field, {
      label: "\xDAltima actualizaci\xF3n",
      value: l.actualizado
    })), tab === 'familia' && /*#__PURE__*/React.createElement("table", {
      style: {
        width: '100%',
        borderCollapse: 'collapse',
        fontFamily: 'var(--font-sans)'
      }
    }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", {
      style: {
        textAlign: 'left',
        fontSize: 11,
        textTransform: 'uppercase',
        letterSpacing: '.05em',
        color: 'var(--text-body-subtle)'
      }
    }, /*#__PURE__*/React.createElement("th", {
      style: {
        padding: '8px 8px 8px 0',
        fontWeight: 700
      }
    }, "Integrante"), /*#__PURE__*/React.createElement("th", {
      style: {
        padding: 8,
        fontWeight: 700
      }
    }, "V\xEDnculo"), /*#__PURE__*/React.createElement("th", {
      style: {
        padding: 8,
        fontWeight: 700
      }
    }, "Edad"), /*#__PURE__*/React.createElement("th", {
      style: {
        padding: 8,
        fontWeight: 700
      }
    }, "DNI"))), /*#__PURE__*/React.createElement("tbody", null, M.familia.map((f, i) => /*#__PURE__*/React.createElement("tr", {
      key: i,
      style: {
        borderTop: '1px solid var(--border-light)'
      }
    }, /*#__PURE__*/React.createElement("td", {
      style: {
        padding: '12px 8px 12px 0'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 10
      }
    }, /*#__PURE__*/React.createElement(DS.Avatar, {
      name: f.nombre,
      size: 30
    }), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 13.5,
        fontWeight: 600,
        color: 'var(--text-heading)'
      }
    }, f.nombre))), /*#__PURE__*/React.createElement("td", {
      style: {
        padding: 8
      }
    }, f.rel === 'Titular' ? /*#__PURE__*/React.createElement(DS.Badge, {
      variant: "brand"
    }, f.rel) : /*#__PURE__*/React.createElement(DS.Badge, {
      variant: "neutral"
    }, f.rel)), /*#__PURE__*/React.createElement("td", {
      style: {
        padding: 8,
        fontSize: 13,
        color: 'var(--text-body)'
      }
    }, f.edad, " a\xF1os"), /*#__PURE__*/React.createElement("td", {
      style: {
        padding: 8,
        fontSize: 13,
        color: 'var(--text-body)'
      }
    }, f.dni))))), tab === 'programas' && /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        flexDirection: 'column',
        gap: 12
      }
    }, /*#__PURE__*/React.createElement(DS.Alert, {
      variant: "success",
      title: "Inscripci\xF3n activa"
    }, l.programa, " \u2014 alta el 02/2024, cobro mensual al d\xEDa."), /*#__PURE__*/React.createElement(DS.Alert, {
      variant: "info"
    }, "Becas Progresar \u2014 en evaluaci\xF3n. Documentaci\xF3n presentada el 05/06.")), tab === 'archivos' && /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'grid',
        gridTemplateColumns: 'repeat(3, 1fr)',
        gap: 12
      }
    }, ['DNI frente.pdf', 'DNI dorso.pdf', 'Certificado de domicilio.pdf', 'Recibo de servicios.jpg', 'Declaración jurada.pdf', 'Foto carnet.png'].map(f => /*#__PURE__*/React.createElement("div", {
      key: f,
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: 12,
        border: '1px solid var(--border-base)',
        borderRadius: 'var(--radius-lg)'
      }
    }, /*#__PURE__*/React.createElement("i", {
      className: "fas fa-file-lines",
      style: {
        color: 'var(--text-fg-brand)',
        fontSize: 18
      }
    }), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 12.5,
        color: 'var(--text-heading)',
        fontWeight: 600,
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap'
      }
    }, f)))))));
  }
  window.LegajoDetail = LegajoDetail;
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/backoffice/LegajoDetail.jsx", error: String((e && e.message) || e) }); }

// ui_kits/backoffice/Legajos.jsx
try { (() => {
// Legajos list screen with filter bar + table + pagination.
(function () {
  const DS = window.ChacoNODODesignSystem_dc2a68;
  function Legajos({
    onOpenLegajo
  }) {
    const M = window.MOCK;
    const [q, setQ] = React.useState('');
    const rows = M.legajos.filter(l => (l.nombre + l.dni + l.localidad + l.programa).toLowerCase().includes(q.toLowerCase()));
    return /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        flexDirection: 'column',
        gap: 18
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'flex-end',
        gap: 12,
        flexWrap: 'wrap'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1,
        minWidth: 220
      }
    }, /*#__PURE__*/React.createElement(DS.Input, {
      placeholder: "Buscar por nombre, DNI o localidad\u2026",
      icon: "fas fa-magnifying-glass",
      value: q,
      onChange: e => setQ(e.target.value)
    })), /*#__PURE__*/React.createElement("div", {
      style: {
        width: 190
      }
    }, /*#__PURE__*/React.createElement(DS.Select, {
      placeholder: "Todos los programas",
      options: ['Tarjeta Alimentar', 'Potenciar Trabajo', 'Becas Progresar', 'Pensión no contributiva']
    })), /*#__PURE__*/React.createElement("div", {
      style: {
        width: 160
      }
    }, /*#__PURE__*/React.createElement(DS.Select, {
      placeholder: "Todos los estados",
      options: ['Activo', 'Pendiente', 'En revisión', 'Vencido']
    })), /*#__PURE__*/React.createElement(DS.Button, {
      variant: "brand",
      icon: "fas fa-plus"
    }, "Nuevo legajo")), /*#__PURE__*/React.createElement(DS.Card, {
      padding: 0
    }, /*#__PURE__*/React.createElement("table", {
      style: {
        width: '100%',
        borderCollapse: 'collapse',
        fontFamily: 'var(--font-sans)'
      }
    }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", {
      style: {
        textAlign: 'left',
        fontSize: 11,
        textTransform: 'uppercase',
        letterSpacing: '.05em',
        color: 'var(--text-body-subtle)',
        background: 'var(--bg-secondary)'
      }
    }, /*#__PURE__*/React.createElement("th", {
      style: {
        padding: '12px 20px',
        fontWeight: 700
      }
    }, "Ciudadano"), /*#__PURE__*/React.createElement("th", {
      style: {
        padding: '12px',
        fontWeight: 700
      }
    }, "Localidad"), /*#__PURE__*/React.createElement("th", {
      style: {
        padding: '12px',
        fontWeight: 700
      }
    }, "Programa"), /*#__PURE__*/React.createElement("th", {
      style: {
        padding: '12px',
        fontWeight: 700,
        textAlign: 'center'
      }
    }, "Integrantes"), /*#__PURE__*/React.createElement("th", {
      style: {
        padding: '12px',
        fontWeight: 700
      }
    }, "Estado"), /*#__PURE__*/React.createElement("th", {
      style: {
        padding: '12px 20px',
        fontWeight: 700,
        textAlign: 'right'
      }
    }))), /*#__PURE__*/React.createElement("tbody", null, rows.map(l => {
      const e = M.estados[l.estado];
      return /*#__PURE__*/React.createElement("tr", {
        key: l.id,
        onClick: () => onOpenLegajo(l),
        style: {
          cursor: 'pointer',
          borderTop: '1px solid var(--border-light)'
        },
        onMouseEnter: ev => ev.currentTarget.style.background = 'var(--bg-secondary)',
        onMouseLeave: ev => ev.currentTarget.style.background = 'transparent'
      }, /*#__PURE__*/React.createElement("td", {
        style: {
          padding: '12px 20px'
        }
      }, /*#__PURE__*/React.createElement("div", {
        style: {
          display: 'flex',
          alignItems: 'center',
          gap: 10
        }
      }, /*#__PURE__*/React.createElement(DS.Avatar, {
        name: l.nombre,
        size: 34
      }), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
        style: {
          fontSize: 13.5,
          fontWeight: 700,
          color: 'var(--text-heading)'
        }
      }, l.nombre), /*#__PURE__*/React.createElement("div", {
        style: {
          fontSize: 11.5,
          color: 'var(--text-body-subtle)'
        }
      }, "DNI ", l.dni)))), /*#__PURE__*/React.createElement("td", {
        style: {
          padding: '12px',
          fontSize: 13,
          color: 'var(--text-body)'
        }
      }, l.localidad), /*#__PURE__*/React.createElement("td", {
        style: {
          padding: '12px',
          fontSize: 13,
          color: 'var(--text-body)'
        }
      }, l.programa), /*#__PURE__*/React.createElement("td", {
        style: {
          padding: '12px',
          fontSize: 13,
          color: 'var(--text-body)',
          textAlign: 'center'
        }
      }, l.integrantes), /*#__PURE__*/React.createElement("td", {
        style: {
          padding: '12px'
        }
      }, /*#__PURE__*/React.createElement(DS.Badge, {
        variant: e.variant,
        dot: e.dot
      }, e.label)), /*#__PURE__*/React.createElement("td", {
        style: {
          padding: '12px 20px',
          textAlign: 'right',
          color: 'var(--text-body-subtle)'
        }
      }, /*#__PURE__*/React.createElement("i", {
        className: "fas fa-chevron-right"
      })));
    }))), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '12px 20px',
        borderTop: '1px solid var(--border-light)',
        background: 'var(--bg-secondary)'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 12.5,
        color: 'var(--text-body-subtle)'
      }
    }, "Mostrando ", rows.length, " de 1.284 legajos"), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        gap: 6
      }
    }, /*#__PURE__*/React.createElement(DS.Button, {
      size: "sm",
      variant: "secondary",
      icon: "fas fa-chevron-left",
      disabled: true
    }, "Anterior"), /*#__PURE__*/React.createElement(DS.Button, {
      size: "sm",
      variant: "secondary",
      iconRight: "fas fa-chevron-right"
    }, "Siguiente")))));
  }
  window.Legajos = Legajos;
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/backoffice/Legajos.jsx", error: String((e && e.message) || e) }); }

// ui_kits/backoffice/Shell.jsx
try { (() => {
// Backoffice shell: fixed white sidebar + sticky topbar.
const DS = window.ChacoNODODesignSystem_dc2a68;
function Sidebar({
  active,
  onNavigate,
  collapsed
}) {
  const {
    nav
  } = window.MOCK;
  return /*#__PURE__*/React.createElement("aside", {
    style: {
      width: collapsed ? 80 : 264,
      flexShrink: 0,
      background: 'var(--bg-white)',
      borderRight: '1px solid var(--border-base)',
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      transition: 'width var(--duration-normal) var(--ease-standard)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      height: 64,
      display: 'flex',
      alignItems: 'center',
      padding: collapsed ? 0 : '0 20px',
      justifyContent: collapsed ? 'center' : 'flex-start',
      borderBottom: '1px solid var(--border-base)'
    }
  }, collapsed ? /*#__PURE__*/React.createElement("img", {
    src: "../../assets/logo-mark.png",
    alt: "Chaco",
    style: {
      width: 36,
      height: 36
    }
  }) : /*#__PURE__*/React.createElement("img", {
    src: "../../assets/logo-chaco-horizontal.png",
    alt: "Gobierno del Chaco",
    style: {
      height: 30
    }
  })), /*#__PURE__*/React.createElement("nav", {
    style: {
      flex: 1,
      padding: 12,
      display: 'flex',
      flexDirection: 'column',
      gap: 2,
      overflowY: 'auto'
    }
  }, nav.map(item => {
    const on = item.id === active;
    return /*#__PURE__*/React.createElement("button", {
      key: item.id,
      onClick: () => onNavigate(item.id),
      title: item.label,
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: collapsed ? '11px 0' : '11px 14px',
        justifyContent: collapsed ? 'center' : 'flex-start',
        borderRadius: 'var(--radius-lg)',
        border: 'none',
        cursor: 'pointer',
        background: on ? 'var(--bg-brand-soft)' : 'transparent',
        color: on ? 'var(--text-fg-brand-strong)' : 'var(--text-body)',
        fontFamily: 'var(--font-sans)',
        fontSize: 14,
        fontWeight: on ? 700 : 500,
        position: 'relative',
        transition: 'background var(--duration-fast) var(--ease-standard)'
      },
      onMouseEnter: e => {
        if (!on) e.currentTarget.style.background = 'var(--bg-secondary)';
      },
      onMouseLeave: e => {
        if (!on) e.currentTarget.style.background = 'transparent';
      }
    }, /*#__PURE__*/React.createElement("i", {
      className: item.icon,
      style: {
        width: 18,
        textAlign: 'center',
        fontSize: 16,
        color: on ? 'var(--text-fg-brand)' : 'var(--text-body-subtle)'
      }
    }), !collapsed && /*#__PURE__*/React.createElement("span", {
      style: {
        flex: 1,
        textAlign: 'left'
      }
    }, item.label), !collapsed && item.count != null && /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 11,
        fontWeight: 700,
        padding: '1px 8px',
        borderRadius: 'var(--radius-full)',
        background: on ? 'var(--bg-white)' : 'var(--bg-tertiary)',
        color: on ? 'var(--text-fg-brand)' : 'var(--text-body-subtle)'
      }
    }, item.count > 999 ? '999+' : item.count));
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 12,
      borderTop: '1px solid var(--border-base)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      padding: collapsed ? 0 : '8px 10px',
      justifyContent: collapsed ? 'center' : 'flex-start'
    }
  }, /*#__PURE__*/React.createElement(DS.Avatar, {
    name: window.MOCK.user.name,
    size: 36
  }), !collapsed && /*#__PURE__*/React.createElement("div", {
    style: {
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 13,
      fontWeight: 700,
      color: 'var(--text-heading)',
      whiteSpace: 'nowrap',
      overflow: 'hidden',
      textOverflow: 'ellipsis'
    }
  }, window.MOCK.user.name), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: 'var(--text-body-subtle)'
    }
  }, window.MOCK.user.role)))));
}
function Topbar({
  title,
  onToggle,
  onAlerts
}) {
  return /*#__PURE__*/React.createElement("header", {
    style: {
      height: 64,
      flexShrink: 0,
      display: 'flex',
      alignItems: 'center',
      gap: 16,
      padding: '0 24px',
      background: 'var(--bg-white)',
      borderBottom: '1px solid var(--border-base)',
      boxShadow: 'var(--shadow-xs)',
      position: 'sticky',
      top: 0,
      zIndex: 20
    }
  }, /*#__PURE__*/React.createElement("button", {
    onClick: onToggle,
    "aria-label": "Men\xFA",
    style: {
      background: 'none',
      border: 'none',
      cursor: 'pointer',
      color: 'var(--text-body)',
      fontSize: 18,
      padding: 6
    }
  }, /*#__PURE__*/React.createElement("i", {
    className: "fas fa-bars"
  })), /*#__PURE__*/React.createElement("h1", {
    style: {
      margin: 0,
      fontSize: 20,
      fontWeight: 800,
      color: 'var(--text-heading)',
      letterSpacing: '-0.3px'
    }
  }, title), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'relative',
      width: 280,
      maxWidth: '32vw'
    }
  }, /*#__PURE__*/React.createElement("i", {
    className: "fas fa-magnifying-glass",
    style: {
      position: 'absolute',
      left: 14,
      top: '50%',
      transform: 'translateY(-50%)',
      color: 'var(--text-body-subtle)',
      fontSize: 13
    }
  }), /*#__PURE__*/React.createElement("input", {
    placeholder: "Buscar legajo, DNI, consulta\u2026",
    style: {
      width: '100%',
      height: 40,
      padding: '0 14px 0 38px',
      fontFamily: 'var(--font-sans)',
      fontSize: 13.5,
      border: '1px solid var(--border-base)',
      borderRadius: 'var(--radius-full)',
      background: 'var(--bg-secondary)',
      outline: 'none',
      color: 'var(--text-heading)'
    }
  })), /*#__PURE__*/React.createElement("button", {
    onClick: onAlerts,
    "aria-label": "Alertas",
    style: {
      position: 'relative',
      background: 'none',
      border: 'none',
      cursor: 'pointer',
      color: 'var(--text-body)',
      fontSize: 18,
      padding: 6
    }
  }, /*#__PURE__*/React.createElement("i", {
    className: "fas fa-bell"
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      position: 'absolute',
      top: 0,
      right: 0,
      minWidth: 16,
      height: 16,
      padding: '0 4px',
      borderRadius: 'var(--radius-full)',
      background: 'var(--bg-danger)',
      color: '#fff',
      fontSize: 10,
      fontWeight: 700,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center'
    }
  }, "4")), /*#__PURE__*/React.createElement("span", {
    title: "Conectado",
    style: {
      width: 9,
      height: 9,
      borderRadius: '50%',
      background: 'var(--bg-success)',
      boxShadow: '0 0 0 3px var(--bg-success-soft)'
    }
  }), /*#__PURE__*/React.createElement(DS.Avatar, {
    name: window.MOCK.user.name,
    size: 36
  }));
}
Object.assign(window, {
  Sidebar,
  Topbar
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/backoffice/Shell.jsx", error: String((e && e.message) || e) }); }

// ui_kits/backoffice/data.js
try { (() => {
// Mock data for the Chaco / NODO backoffice UI kit (all fictional).
window.MOCK = {
  user: {
    name: 'María González',
    role: 'Trabajadora social'
  },
  nav: [{
    id: 'inicio',
    label: 'Inicio',
    icon: 'fas fa-house'
  }, {
    id: 'legajos',
    label: 'Legajos',
    icon: 'fas fa-folder-open',
    count: 1284
  }, {
    id: 'programas',
    label: 'Programas',
    icon: 'fas fa-hand-holding-heart'
  }, {
    id: 'conversaciones',
    label: 'Conversaciones',
    icon: 'fas fa-comments',
    count: 6
  }, {
    id: 'tableros',
    label: 'Tableros',
    icon: 'fas fa-chart-line'
  }, {
    id: 'configuracion',
    label: 'Configuración',
    icon: 'fas fa-gear'
  }],
  stats: [{
    label: 'Legajos activos',
    value: '1.284',
    icon: 'fas fa-folder-open',
    tone: 'brand',
    change: '8%',
    changeDir: 'up',
    footnote: 'vs. mes anterior'
  }, {
    label: 'Consultas abiertas',
    value: '37',
    icon: 'fas fa-comments',
    tone: 'warning',
    change: '3',
    changeDir: 'down',
    footnote: 'sin asignar: 6'
  }, {
    label: 'Beneficios entregados',
    value: '9.512',
    icon: 'fas fa-hand-holding-heart',
    tone: 'olive',
    change: '12%',
    changeDir: 'up',
    footnote: 'en el trimestre'
  }, {
    label: 'Alertas críticas',
    value: '4',
    icon: 'fas fa-triangle-exclamation',
    tone: 'danger',
    change: '2',
    changeDir: 'up',
    footnote: 'requieren acción'
  }],
  legajos: [{
    id: 1,
    nombre: 'González, María Belén',
    dni: '28.450.110',
    localidad: 'Resistencia',
    programa: 'Tarjeta Alimentar',
    integrantes: 4,
    estado: 'activo',
    actualizado: 'Hoy'
  }, {
    id: 2,
    nombre: 'Romero, Juan Carlos',
    dni: '30.118.902',
    localidad: 'Barranqueras',
    programa: 'Potenciar Trabajo',
    integrantes: 2,
    estado: 'pendiente',
    actualizado: 'Ayer'
  }, {
    id: 3,
    nombre: 'Fernández, Lucía',
    dni: '35.902.441',
    localidad: 'Sáenz Peña',
    programa: 'Becas Progresar',
    integrantes: 1,
    estado: 'activo',
    actualizado: 'Hace 2 días'
  }, {
    id: 4,
    nombre: 'Sosa, Ramón Alberto',
    dni: '22.105.778',
    localidad: 'Resistencia',
    programa: 'Tarjeta Alimentar',
    integrantes: 6,
    estado: 'vencido',
    actualizado: 'Hace 5 días'
  }, {
    id: 5,
    nombre: 'Ibarra, Daniela',
    dni: '40.553.219',
    localidad: 'Villa Ángela',
    programa: 'Potenciar Trabajo',
    integrantes: 3,
    estado: 'activo',
    actualizado: 'Hace 1 sem.'
  }, {
    id: 6,
    nombre: 'Ojeda, Marta Susana',
    dni: '18.774.300',
    localidad: 'Charata',
    programa: 'Pensión no contributiva',
    integrantes: 2,
    estado: 'revision',
    actualizado: 'Hace 1 sem.'
  }, {
    id: 7,
    nombre: 'Benítez, Carlos',
    dni: '33.660.155',
    localidad: 'Resistencia',
    programa: 'Becas Progresar',
    integrantes: 5,
    estado: 'activo',
    actualizado: 'Hace 2 sem.'
  }],
  estados: {
    activo: {
      label: 'Activo',
      variant: 'success',
      dot: true
    },
    pendiente: {
      label: 'Pendiente',
      variant: 'warning'
    },
    vencido: {
      label: 'Vencido',
      variant: 'danger'
    },
    revision: {
      label: 'En revisión',
      variant: 'info'
    }
  },
  familia: [{
    nombre: 'González, María Belén',
    rel: 'Titular',
    edad: 38,
    dni: '28.450.110'
  }, {
    nombre: 'Acosta, Diego',
    rel: 'Cónyuge',
    edad: 41,
    dni: '27.900.221'
  }, {
    nombre: 'Acosta González, Mateo',
    rel: 'Hijo/a',
    edad: 12,
    dni: '49.110.330'
  }, {
    nombre: 'Acosta González, Valentina',
    rel: 'Hijo/a',
    edad: 7,
    dni: '52.880.441'
  }],
  actividad: [{
    icon: 'fas fa-pen',
    text: 'Se actualizó la dimensión Vivienda del legajo #1',
    time: 'hace 20 min',
    tone: 'brand'
  }, {
    icon: 'fas fa-circle-check',
    text: 'Consulta #4821 resuelta por J. Romero',
    time: 'hace 1 h',
    tone: 'success'
  }, {
    icon: 'fas fa-folder-plus',
    text: 'Nuevo legajo creado: Ibarra, Daniela',
    time: 'hace 3 h',
    tone: 'olive'
  }, {
    icon: 'fas fa-triangle-exclamation',
    text: 'Alerta de vencimiento en legajo #4',
    time: 'hace 5 h',
    tone: 'danger'
  }],
  consultas: [{
    id: 4821,
    asunto: 'Solicitud de turno — Tarjeta Alimentar',
    ciudadano: 'Romero, Juan',
    estado: 'pendiente',
    time: '10:24'
  }, {
    id: 4819,
    asunto: 'Actualización de domicilio',
    ciudadano: 'Fernández, Lucía',
    estado: 'revision',
    time: 'Ayer'
  }, {
    id: 4815,
    asunto: 'Consulta por estado de beca',
    ciudadano: 'Benítez, Carlos',
    estado: 'activo',
    time: 'Ayer'
  }]
};
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/backoffice/data.js", error: String((e && e.message) || e) }); }

// ui_kits/inicio/data.js
try { (() => {
// /inicio/ — datos mock del panel de inicio (ficticios). Chaco / NODO backoffice.
window.INICIO = {
  user: {
    name: 'María González',
    role: 'Coordinadora — Nivel Superior'
  },
  saludo: 'Buenas tardes',
  stats: [{
    label: 'Legajos activos',
    value: '1.284',
    icon: 'folderOpen',
    tone: 'brand',
    gradient: true,
    change: '8%',
    dir: 'up',
    foot: 'vs. mes anterior'
  }, {
    label: 'Relevamientos en curso',
    value: '37',
    icon: 'clipboardList',
    tone: 'warning',
    change: '5',
    dir: 'up',
    foot: '6 sin asignar'
  }, {
    label: 'Formularios por revisar',
    value: '24',
    icon: 'clipboardCheck',
    tone: 'brand',
    change: '3',
    dir: 'down',
    foot: 'pendientes hoy'
  }, {
    label: 'Beneficiarios con cupo',
    value: '9.512',
    icon: 'usersGroup',
    tone: 'success',
    change: '12%',
    dir: 'up',
    foot: 'en el trimestre'
  }],
  accesos: [{
    label: 'Nuevo legajo',
    icon: 'identification',
    tone: 'brand'
  }, {
    label: 'Nueva convocatoria',
    icon: 'megaphone',
    tone: 'olive'
  }, {
    label: 'Asignar relevamiento',
    icon: 'folderOpen',
    tone: 'pink'
  }, {
    label: 'Revisar formularios',
    icon: 'clipboardCheck',
    tone: 'brand'
  }],
  pendientes: [{
    titulo: 'Formularios en revisión',
    desc: 'Becas Superior 2026 — Universitario',
    n: 18,
    tone: 'brand',
    icon: 'clipboardCheck'
  }, {
    titulo: 'Relevamientos vencidos',
    desc: 'Requieren reprogramación',
    n: 2,
    tone: 'danger',
    icon: 'clock'
  }, {
    titulo: 'RENAPER pendiente',
    desc: 'Validaciones sin resolver',
    n: 7,
    tone: 'warning',
    icon: 'exclamationCircle'
  }, {
    titulo: 'Lista de espera',
    desc: 'Producción Territorial / Carbón',
    n: 64,
    tone: 'olive',
    icon: 'usersGroup'
  }],
  actividad: [{
    icon: 'pencilSquare',
    text: 'Actualizaste la dimensión Vivienda del legajo #1284',
    time: 'hace 20 min',
    tone: 'brand'
  }, {
    icon: 'checkCircle',
    text: 'Aprobaste el formulario de Acosta, Brenda Sofía',
    time: 'hace 1 h',
    tone: 'success'
  }, {
    icon: 'folderOpen',
    text: 'Se creó el Relevamiento 005 — Charata',
    time: 'hace 3 h',
    tone: 'olive'
  }, {
    icon: 'xCircle',
    text: 'Rechazaste el formulario de Maidana, Pedro',
    time: 'hace 5 h',
    tone: 'danger'
  }, {
    icon: 'megaphone',
    text: 'Se abrió la convocatoria Becas 2026 — Carbón',
    time: 'ayer',
    tone: 'brand'
  }],
  agenda: [{
    hora: '09:30',
    titulo: 'Operativo Resistencia - Zona Norte',
    sub: 'Territorial: Juan Pérez',
    estado: 'En curso',
    tone: 'warning'
  }, {
    hora: '11:00',
    titulo: 'Revisión de cupo — Nivel Superior',
    sub: 'Coordinación',
    estado: 'Hoy',
    tone: 'brand'
  }, {
    hora: '14:00',
    titulo: 'Cierre convocatoria Secundario',
    sub: 'Vence en 3 días',
    estado: 'Próximo',
    tone: 'gray'
  }],
  cobertura: [['Tarjeta Alimentar', 46, 'var(--bg-brand)'], ['Producción Territorial', 28, 'var(--color-olive-500)'], ['Becas Superior', 18, 'var(--bg-pink)'], ['Otros', 8, 'var(--bg-quaternary)']]
};
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/inicio/data.js", error: String((e && e.message) || e) }); }

// ui_kits/inicio/icons.jsx
try { (() => {
// Heroicons v2 (outline) — the icon library for NEW NODO/CHACO templates.
// Icons inherit color from the parent's `color` (never hardcoded). Stroke 1.5.
(function () {
  const P = {
    home: ['m2.25 12 8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.5a.75.75 0 0 0 .75.75h4.5a.75.75 0 0 0 .75-.75V15a.75.75 0 0 1 .75-.75h3a.75.75 0 0 1 .75.75v5.25c0 .414.336.75.75.75h4.5a.75.75 0 0 0 .75-.75V9.75M8.25 21h8.25'],
    squares: ['M3.75 6A2.25 2.25 0 0 1 6 3.75h2.25A2.25 2.25 0 0 1 10.5 6v2.25a2.25 2.25 0 0 1-2.25 2.25H6a2.25 2.25 0 0 1-2.25-2.25V6ZM3.75 15.75A2.25 2.25 0 0 1 6 13.5h2.25a2.25 2.25 0 0 1 2.25 2.25V18a2.25 2.25 0 0 1-2.25 2.25H6A2.25 2.25 0 0 1 3.75 18v-2.25ZM13.5 6a2.25 2.25 0 0 1 2.25-2.25H18A2.25 2.25 0 0 1 20.25 6v2.25A2.25 2.25 0 0 1 18 10.5h-2.25a2.25 2.25 0 0 1-2.25-2.25V6ZM13.5 15.75a2.25 2.25 0 0 1 2.25-2.25H18a2.25 2.25 0 0 1 2.25 2.25V18A2.25 2.25 0 0 1 18 20.25h-2.25A2.25 2.25 0 0 1 13.5 18v-2.25Z'],
    folderOpen: ['M3.75 9.776c.112-.017.227-.026.344-.026h15.812c.117 0 .232.009.344.026m-16.5 0a2.25 2.25 0 0 0-1.883 2.542l.857 6a2.25 2.25 0 0 0 2.227 1.932H19.05a2.25 2.25 0 0 0 2.227-1.932l.857-6a2.25 2.25 0 0 0-1.883-2.542m-16.5 0V6A2.25 2.25 0 0 1 6 3.75h3.879a1.5 1.5 0 0 1 1.06.44l2.122 2.12a1.5 1.5 0 0 0 1.06.44H18A2.25 2.25 0 0 1 20.25 9v.776'],
    clipboardList: ['M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 0 0 2.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 0 0-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 0 0 .75-.75 2.25 2.25 0 0 0-.1-.664m-5.8 0A2.251 2.251 0 0 1 13.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25Z'],
    clipboardCheck: ['M11.35 3.836c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 0 0 .75-.75 2.25 2.25 0 0 0-.1-.664m-5.8 0A2.251 2.251 0 0 1 13.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m8.9-4.414c.376.023.75.05 1.124.08 1.131.094 1.976 1.057 1.976 2.192V16.5A2.25 2.25 0 0 1 18 18.75h-2.25m-7.5-10.5H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V18.75m-7.5-10.5h6.375c.621 0 1.125.504 1.125 1.125v9.375m-8.25-3 1.5 1.5 3-3.75'],
    megaphone: ['M10.34 15.84c-.688-.06-1.386-.09-2.09-.09H7.5a4.5 4.5 0 1 1 0-9h.75c.704 0 1.402-.03 2.09-.09m0 9.18c.253.962.584 1.892.985 2.783.247.55.06 1.21-.463 1.51l-.657.38c-.551.318-1.26.117-1.527-.461a20.845 20.845 0 0 1-1.44-4.282m3.102.069a18.03 18.03 0 0 1-.59-4.59c0-1.586.205-3.124.59-4.59m0 9.18a23.848 23.848 0 0 1 8.835 2.535M10.34 6.66a23.847 23.847 0 0 0 8.835-2.535m0 0A23.74 23.74 0 0 0 18.795 3m.38 1.125a23.91 23.91 0 0 1 1.014 5.395m-1.014 8.855c-.118.38-.245.754-.38 1.125m.38-1.125a23.91 23.91 0 0 0 1.014-5.395m0-3.46c.495.413.811 1.035.811 1.73 0 .695-.316 1.317-.811 1.73m0-3.46a24.347 24.347 0 0 1 0 3.46'],
    usersGroup: ['M15 19.128a9.38 9.38 0 0 0 2.625.372 9.337 9.337 0 0 0 4.121-.952 4.125 4.125 0 0 0-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 0 1 8.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0 1 11.964-3.07M12 6.375a3.375 3.375 0 1 1-6.75 0 3.375 3.375 0 0 1 6.75 0Zm8.25 2.25a2.625 2.625 0 1 1-5.25 0 2.625 2.625 0 0 1 5.25 0Z'],
    chartBar: ['M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z'],
    cog: ['M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.431l-1.003.827c-.293.24-.438.613-.43.992a7.723 7.723 0 0 1 0 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 0 1 0-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.281Z', 'M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z'],
    bell: ['M14.857 17.082a23.848 23.848 0 0 0 5.454-1.31A8.967 8.967 0 0 1 18 9.75V9A6 6 0 0 0 6 9v.75a8.967 8.967 0 0 1-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 0 1-5.714 0m5.714 0a3 3 0 1 1-5.714 0'],
    search: ['m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z'],
    plus: ['M12 4.5v15m7.5-7.5h-15'],
    plusCircle: ['M12 9v6m3-3H9m12 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z'],
    eye: ['M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178Z', 'M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z'],
    pencil: ['m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10'],
    trash: ['m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0'],
    chevronRight: ['m8.25 4.5 7.5 7.5-7.5 7.5'],
    chevronDown: ['m19.5 8.25-7.5 7.5-7.5-7.5'],
    chevronLeft: ['M15.75 19.5 8.25 12l7.5-7.5'],
    arrowLeft: ['M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18'],
    download: ['M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3'],
    check: ['m4.5 12.75 6 6 9-13.5'],
    checkCircle: ['M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z'],
    xCircle: ['m9.75 9.75 4.5 4.5m0-4.5-4.5 4.5M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z'],
    xMark: ['M6 18 18 6M6 6l12 12'],
    warning: ['M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z'],
    exclamationCircle: ['M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z'],
    clock: ['M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z'],
    funnel: ['M12 3c2.755 0 5.455.232 8.083.678.533.09.917.556.917 1.096v1.044a2.25 2.25 0 0 1-.659 1.591l-5.432 5.432a2.25 2.25 0 0 0-.659 1.591v2.927a2.25 2.25 0 0 1-1.244 2.013L9.75 21v-6.568a2.25 2.25 0 0 0-.659-1.591L3.659 7.409A2.25 2.25 0 0 1 3 5.818V4.774c0-.54.384-1.006.917-1.096A48.32 48.32 0 0 1 12 3Z'],
    identification: ['M15 9h3.75M15 12h3.75M15 15h3.75M4.5 19.5h15a2.25 2.25 0 0 0 2.25-2.25V6.75A2.25 2.25 0 0 0 19.5 4.5h-15a2.25 2.25 0 0 0-2.25 2.25v10.5A2.25 2.25 0 0 0 4.5 19.5Zm6-10.125a1.875 1.875 0 1 1-3.75 0 1.875 1.875 0 0 1 3.75 0ZM10.5 15.75a3 3 0 0 0-6 0v.75c0 .414.336.75.75.75h4.5a.75.75 0 0 0 .75-.75v-.75Z'],
    academicCap: ['M4.26 10.147a60.438 60.438 0 0 0-.491 6.347A48.62 48.62 0 0 1 12 20.904a48.62 48.62 0 0 1 8.232-4.41 60.46 60.46 0 0 0-.491-6.347m-15.482 0a50.636 50.636 0 0 0-2.658-.813A59.906 59.906 0 0 1 12 3.493a59.903 59.903 0 0 1 10.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.717 50.717 0 0 1 12 13.489a50.702 50.702 0 0 1 7.74-3.342M6.75 15a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Zm0 0v-3.675A55.378 55.378 0 0 1 12 8.443m-7.007 11.55A5.981 5.981 0 0 0 6.75 15.75v-1.5'],
    briefcase: ['M20.25 14.15v4.073a2.25 2.25 0 0 1-1.632 2.163l-1.32.377a9.797 9.797 0 0 1-5.396 0l-1.32-.377a2.25 2.25 0 0 1-1.632-2.163V14.15M20.25 14.15a48.7 48.7 0 0 0-16.5 0m16.5 0a2.25 2.25 0 0 0 1.5-2.122V8.706a2.25 2.25 0 0 0-1.883-2.221 48.422 48.422 0 0 0-1.117-.165M3.75 14.15a2.25 2.25 0 0 1-1.5-2.122V8.706a2.25 2.25 0 0 1 1.883-2.221c.37-.058.74-.113 1.117-.165m12.75 0V5.625a2.25 2.25 0 0 0-2.25-2.25h-3a2.25 2.25 0 0 0-2.25 2.25v.741m7.5 0a49.16 49.16 0 0 0-7.5 0'],
    documentText: ['M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z'],
    userPlus: ['M19 7.5v3m0 0v3m0-3h3m-3 0h-3m-2.25-4.125a3.375 3.375 0 1 1-6.75 0 3.375 3.375 0 0 1 6.75 0ZM4 19.235v-.11a6.375 6.375 0 0 1 12.75 0v.109A12.318 12.318 0 0 1 10.374 21c-2.331 0-4.512-.645-6.374-1.766Z'],
    mapPin: ['M15 10.5a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z', 'M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1 1 15 0Z'],
    adjustments: ['M10.5 6h9.75M10.5 6a1.5 1.5 0 1 1-3 0m3 0a1.5 1.5 0 1 0-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m-9.75 0h9.75'],
    dotsVertical: ['M12 6.75a.75.75 0 1 1 0-1.5.75.75 0 0 1 0 1.5ZM12 12.75a.75.75 0 1 1 0-1.5.75.75 0 0 1 0 1.5ZM12 18.75a.75.75 0 1 1 0-1.5.75.75 0 0 1 0 1.5Z'],
    userCircle: ['M17.982 18.725A7.488 7.488 0 0 0 12 15.75a7.488 7.488 0 0 0-5.982 2.975m11.963 0a9 9 0 1 0-11.963 0m11.963 0A8.966 8.966 0 0 1 12 21a8.966 8.966 0 0 1-5.982-2.275M15 9.75a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z'],
    arrowPath: ['M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99'],
    listBullet: ['M8.25 6.75h12M8.25 12h12m-12 5.25h12M3.75 6.75h.007v.008H3.75V6.75Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0ZM3.75 12h.007v.008H3.75V12Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm-.375 5.25h.007v.008H3.75v-.008Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Z'],
    pencilSquare: ['m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10']
  };
  function Icon({
    name,
    size = 24,
    style,
    ...rest
  }) {
    const d = P[name] || P.squares;
    return React.createElement('svg', {
      viewBox: '0 0 24 24',
      fill: 'none',
      stroke: 'currentColor',
      strokeWidth: 1.5,
      width: size,
      height: size,
      'aria-hidden': true,
      style: {
        display: 'inline-block',
        flexShrink: 0,
        ...style
      },
      ...rest
    }, d.map((path, i) => React.createElement('path', {
      key: i,
      d: path,
      strokeLinecap: 'round',
      strokeLinejoin: 'round'
    })));
  }
  window.Icon = Icon;
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/inicio/icons.jsx", error: String((e && e.message) || e) }); }

// ui_kits/portal-ciudadano/PortalShell.jsx
try { (() => {
// Portal Ciudadano shell: white header (logo + contact), navy footer, chat FAB.
(function () {
  const DS = window.ChacoNODODesignSystem_dc2a68;
  function Header({
    authed,
    onHome,
    onLogin,
    onLogout
  }) {
    const P = window.PORTAL;
    return /*#__PURE__*/React.createElement("header", {
      style: {
        background: 'var(--bg-white)',
        borderBottom: '1px solid var(--border-base)',
        position: 'sticky',
        top: 0,
        zIndex: 30,
        boxShadow: 'var(--shadow-xs)'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        maxWidth: 1120,
        margin: '0 auto',
        padding: '12px 24px',
        display: 'flex',
        alignItems: 'center',
        gap: 16
      }
    }, /*#__PURE__*/React.createElement("img", {
      src: "../../assets/logo-chaco-horizontal.png",
      alt: "Gobierno del Chaco",
      style: {
        height: 38,
        cursor: 'pointer'
      },
      onClick: onHome
    }), /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1
      }
    }), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 20
      },
      className: "contact"
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        fontSize: 13,
        color: 'var(--text-heading)',
        fontWeight: 600
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        width: 30,
        height: 30,
        borderRadius: 'var(--radius-lg)',
        background: 'var(--bg-brand-soft)',
        color: 'var(--text-fg-brand)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: 13
      }
    }, /*#__PURE__*/React.createElement("i", {
      className: "fas fa-phone"
    })), P.contact.phone), authed ? /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 10
      }
    }, /*#__PURE__*/React.createElement(DS.Avatar, {
      name: P.ciudadano.name,
      size: 34
    }), /*#__PURE__*/React.createElement(DS.Button, {
      size: "sm",
      variant: "secondary",
      icon: "fas fa-right-from-bracket",
      onClick: onLogout
    }, "Salir")) : /*#__PURE__*/React.createElement(DS.Button, {
      size: "sm",
      variant: "brand",
      icon: "fas fa-right-to-bracket",
      onClick: onLogin
    }, "Ingresar"))));
  }
  function Footer() {
    const P = window.PORTAL;
    return /*#__PURE__*/React.createElement("footer", {
      style: {
        background: 'var(--bg-navy)',
        color: '#fff',
        marginTop: 56
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        maxWidth: 1120,
        margin: '0 auto',
        padding: '44px 24px 28px',
        display: 'grid',
        gridTemplateColumns: 'repeat(3, 1fr)',
        gap: 32
      }
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("img", {
      src: "../../assets/logo-chaco-horizontal.png",
      alt: "Gobierno del Chaco",
      style: {
        height: 34,
        filter: 'brightness(0) invert(1)',
        marginBottom: 12
      }
    }), /*#__PURE__*/React.createElement("p", {
      style: {
        color: '#cbd5e1',
        fontSize: 13,
        lineHeight: 1.6,
        margin: 0,
        maxWidth: 280
      }
    }, "Portal de programas y tr\xE1mites sociales del Gobierno de la Provincia del Chaco.")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("h4", {
      style: {
        color: '#fff',
        fontSize: 15,
        margin: '0 0 12px'
      }
    }, "Contacto"), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        fontSize: 13,
        color: '#cbd5e1'
      }
    }, /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("i", {
      className: "fas fa-phone",
      style: {
        width: 18
      }
    }), " ", P.contact.phone), /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("i", {
      className: "fas fa-envelope",
      style: {
        width: 18
      }
    }), " ", P.contact.email))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("h4", {
      style: {
        color: '#fff',
        fontSize: 15,
        margin: '0 0 12px'
      }
    }, "Horarios de atenci\xF3n"), /*#__PURE__*/React.createElement("p", {
      style: {
        color: '#cbd5e1',
        fontSize: 13,
        margin: 0,
        lineHeight: 1.6
      }
    }, "Lunes a Viernes", /*#__PURE__*/React.createElement("br", null), "9:00 \u2014 17:00 hs"))), /*#__PURE__*/React.createElement("div", {
      style: {
        borderTop: '1px solid rgba(255,255,255,.12)',
        padding: '16px 24px',
        textAlign: 'center'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        color: '#94a3b8',
        fontSize: 12.5
      }
    }, "\xA9 2026 Gobierno del Chaco \xB7 Plataforma NODO \u2014 Todos los derechos reservados")));
  }
  function ChatFab() {
    const [open, setOpen] = React.useState(false);
    return /*#__PURE__*/React.createElement("div", {
      style: {
        position: 'fixed',
        bottom: 24,
        right: 24,
        zIndex: 40
      }
    }, open && /*#__PURE__*/React.createElement("div", {
      style: {
        position: 'absolute',
        bottom: 70,
        right: 0,
        width: 300,
        background: 'var(--bg-white)',
        borderRadius: 'var(--radius-xl)',
        boxShadow: 'var(--shadow-xl)',
        border: '1px solid var(--border-base)',
        overflow: 'hidden'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        background: 'var(--gradient-brand)',
        color: '#fff',
        padding: 14,
        display: 'flex',
        alignItems: 'center',
        gap: 8
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        width: 8,
        height: 8,
        borderRadius: '50%',
        background: '#fff'
      }
    }), /*#__PURE__*/React.createElement("strong", {
      style: {
        fontSize: 14
      }
    }, "Mesa de Ayuda")), /*#__PURE__*/React.createElement("div", {
      style: {
        padding: 22,
        textAlign: 'center',
        color: 'var(--text-body-subtle)'
      }
    }, /*#__PURE__*/React.createElement("i", {
      className: "fas fa-headset",
      style: {
        fontSize: 30,
        color: 'var(--text-fg-brand)',
        marginBottom: 10,
        display: 'block'
      }
    }), /*#__PURE__*/React.createElement("div", {
      style: {
        fontWeight: 700,
        color: 'var(--text-heading)',
        marginBottom: 2
      }
    }, "Asistencia t\xE9cnica"), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 13
      }
    }, "Lun a Vie, 9 a 17 hs"))), /*#__PURE__*/React.createElement("button", {
      onClick: () => setOpen(o => !o),
      "aria-label": "Ayuda",
      style: {
        width: 56,
        height: 56,
        borderRadius: '50%',
        border: 'none',
        cursor: 'pointer',
        background: 'var(--gradient-brand)',
        color: '#fff',
        fontSize: 20,
        boxShadow: 'var(--shadow-lg)'
      }
    }, /*#__PURE__*/React.createElement("i", {
      className: open ? 'fas fa-xmark' : 'fas fa-comments'
    })));
  }
  Object.assign(window, {
    PortalHeader: Header,
    PortalFooter: Footer,
    ChatFab
  });
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/portal-ciudadano/PortalShell.jsx", error: String((e && e.message) || e) }); }

// ui_kits/portal-ciudadano/data.js
try { (() => {
// Mock data for the Portal Ciudadano UI kit (all fictional).
window.PORTAL = {
  contact: {
    phone: '0800-222-1133',
    email: 'ayuda@chaco.gob.ar'
  },
  ciudadano: {
    name: 'Juan Carlos Romero',
    dni: '30.118.902'
  },
  programas: [{
    id: 'alimentar',
    nombre: 'Tarjeta Alimentar',
    icon: 'fas fa-cart-shopping',
    desc: 'Asistencia para la compra de alimentos de la canasta básica familiar.',
    tone: 'brand'
  }, {
    id: 'progresar',
    nombre: 'Becas Progresar',
    icon: 'fas fa-graduation-cap',
    desc: 'Apoyo económico para estudiantes que continúan sus estudios.',
    tone: 'olive'
  }, {
    id: 'potenciar',
    nombre: 'Potenciar Trabajo',
    icon: 'fas fa-briefcase',
    desc: 'Acompañamiento para la inclusión socioproductiva y el empleo.',
    tone: 'pink'
  }, {
    id: 'salud',
    nombre: 'Salud Comunitaria',
    icon: 'fas fa-heart-pulse',
    desc: 'Turnos, libreta sanitaria y campañas de salud en tu localidad.',
    tone: 'brand'
  }],
  misProgramas: [{
    nombre: 'Tarjeta Alimentar',
    estado: 'activo',
    detalle: 'Cobro mensual al día · próximo: 10/07'
  }, {
    nombre: 'Becas Progresar',
    estado: 'revision',
    detalle: 'Documentación en evaluación'
  }],
  misConsultas: [{
    id: 4821,
    asunto: 'Solicitud de turno — Tarjeta Alimentar',
    estado: 'pendiente',
    fecha: 'Hoy, 10:24'
  }, {
    id: 4720,
    asunto: 'Actualización de domicilio',
    estado: 'activo',
    fecha: '02/06/2026'
  }, {
    id: 4610,
    asunto: 'Consulta por estado de beca',
    estado: 'cerrado',
    fecha: '21/05/2026'
  }],
  estados: {
    activo: {
      label: 'Activo',
      variant: 'success',
      dot: true
    },
    revision: {
      label: 'En revisión',
      variant: 'info'
    },
    pendiente: {
      label: 'Pendiente',
      variant: 'warning'
    },
    cerrado: {
      label: 'Resuelto',
      variant: 'neutral'
    }
  }
};
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/portal-ciudadano/data.js", error: String((e && e.message) || e) }); }

// ui_kits/programa-becas/data.js
try { (() => {
// Programa Becas — mock domain data (fictional). Chaco / NODO backoffice.
// Domain: Segmento → Subsegmento → Convocatoria → Relevamiento → Formulario.
window.BECAS = {
  user: {
    name: 'María González',
    role: 'Coordinadora — Nivel Superior'
  },
  // Relevamiento workflow states (canonical)
  relevEstados: {
    ASIGNADO: {
      label: 'Asignado',
      variant: 'gray'
    },
    EN_CURSO: {
      label: 'En curso',
      variant: 'warning'
    },
    FINALIZANDO: {
      label: 'Finalizando',
      variant: 'warning'
    },
    FINALIZADO: {
      label: 'Finalizado',
      variant: 'brand'
    },
    EN_REVISION: {
      label: 'En revisión',
      variant: 'brand'
    },
    TERMINADO: {
      label: 'Terminado',
      variant: 'success'
    },
    VENCIDO: {
      label: 'Vencido',
      variant: 'danger'
    }
  },
  // Tipos de campo de un requisito (parametría)
  tiposRequisito: ['STRING', 'INT', 'SELECTOR', 'SELECTOR_MULTIPLE', 'DATE', 'ARCHIVO', 'GPS'],
  // Modelo: Segmento { cupoTotal, coordinador, requisitos[], subsegmentos[ { cupoMax, ocupado, requisitos[] } ] }
  // cupoOcupado del segmento = Σ subsegmentos.ocupado · disponible del subsegmento = cupoMax − ocupado
  segmentos: [{
    id: 1,
    nombre: 'Producción Territorial / Fuego y Barro',
    desc: 'Productores de ladrillo y carbón vegetal del territorio provincial.',
    cupoTotal: 500,
    coordinador: 'Laura Méndez',
    estado: 'activo',
    requisitos: [{
      id: 11,
      pregunta: '¿Lugar de trabajo / producción?',
      tipo: 'STRING',
      obligatorio: true,
      orden: 1
    }, {
      id: 12,
      pregunta: 'Fotos del lugar',
      tipo: 'ARCHIVO',
      obligatorio: true,
      orden: 2
    }, {
      id: 13,
      pregunta: 'Ubicación GPS del predio',
      tipo: 'GPS',
      obligatorio: true,
      orden: 3
    }],
    subsegmentos: [{
      id: 101,
      nombre: 'Ladrillo',
      desc: 'Producción de ladrillos artesanales.',
      cupoMax: 200,
      ocupado: 50,
      requisitos: [{
        id: 1101,
        pregunta: 'Cantidad de hornos',
        tipo: 'INT',
        obligatorio: true,
        orden: 1
      }, {
        id: 1102,
        pregunta: 'Tipo de horno',
        tipo: 'SELECTOR',
        obligatorio: false,
        orden: 2
      }]
    }, {
      id: 102,
      nombre: 'Carbón',
      desc: 'Producción de carbón vegetal.',
      cupoMax: 300,
      ocupado: 100,
      requisitos: [{
        id: 1201,
        pregunta: 'Método de producción',
        tipo: 'SELECTOR',
        obligatorio: true,
        orden: 1
      }]
    }]
  }, {
    id: 2,
    nombre: 'Nivel Superior',
    desc: 'Terciario y universitario, instituciones públicas y privadas.',
    cupoTotal: 1500,
    coordinador: 'María González',
    estado: 'activo',
    requisitos: [{
      id: 21,
      pregunta: 'Certificado de alumno regular',
      tipo: 'ARCHIVO',
      obligatorio: true,
      orden: 1
    }, {
      id: 22,
      pregunta: 'Promedio del último período',
      tipo: 'INT',
      obligatorio: true,
      orden: 2
    }, {
      id: 23,
      pregunta: 'Institución educativa',
      tipo: 'STRING',
      obligatorio: true,
      orden: 3
    }],
    subsegmentos: [{
      id: 201,
      nombre: 'Terciario',
      desc: 'Institutos de formación terciaria.',
      cupoMax: 700,
      ocupado: 512,
      requisitos: []
    }, {
      id: 202,
      nombre: 'Universitario',
      desc: 'Carreras de grado universitarias.',
      cupoMax: 800,
      ocupado: 700,
      requisitos: [{
        id: 2201,
        pregunta: 'Carrera / Especialidad',
        tipo: 'STRING',
        obligatorio: true,
        orden: 1
      }]
    }]
  }, {
    id: 3,
    nombre: 'Nivel Secundario',
    desc: 'Estudiantes de escuelas secundarias de la provincia.',
    cupoTotal: 2000,
    coordinador: 'Laura Méndez',
    estado: 'activo',
    requisitos: [{
      id: 31,
      pregunta: 'Constancia de inscripción',
      tipo: 'ARCHIVO',
      obligatorio: true,
      orden: 1
    }],
    subsegmentos: [{
      id: 301,
      nombre: 'Ciclo Básico',
      desc: '1º a 3º año.',
      cupoMax: 1000,
      ocupado: 820,
      requisitos: []
    }, {
      id: 302,
      nombre: 'Ciclo Orientado',
      desc: '4º a 6º año.',
      cupoMax: 1000,
      ocupado: 980,
      requisitos: []
    }]
  }, {
    id: 4,
    nombre: 'Posgrado e Investigación',
    desc: 'Maestrías, doctorados y proyectos de investigación.',
    cupoTotal: 120,
    coordinador: 'Diego Ferreyra',
    estado: 'inactivo',
    requisitos: [],
    subsegmentos: []
  }],
  coordinadores: [{
    nombre: 'María González',
    segmentos: ['Nivel Superior'],
    legajos: 1212
  }, {
    nombre: 'Laura Méndez',
    segmentos: ['Nivel Secundario'],
    legajos: 1840
  }, {
    nombre: 'Diego Ferreyra',
    segmentos: ['Nivel Superior', 'Posgrado e Investigación'],
    legajos: 1308
  }, {
    nombre: 'Sofía Aguirre',
    segmentos: ['Formación Profesional'],
    legajos: 530
  }],
  // Requisitos nativos (per segmento/subsegmento) — build the territorial's dynamic form
  requisitos: [{
    id: 1,
    nombre: 'Certificado de alumno regular',
    tipo: 'Archivo',
    segmento: 'Nivel Superior',
    obligatorio: true
  }, {
    id: 2,
    nombre: 'Promedio del último período',
    tipo: 'Número',
    segmento: 'Nivel Superior',
    obligatorio: true
  }, {
    id: 3,
    nombre: 'Institución educativa',
    tipo: 'Texto',
    segmento: 'Nivel Superior',
    obligatorio: true
  }, {
    id: 4,
    nombre: 'Carrera / Especialidad',
    tipo: 'Texto',
    segmento: 'Nivel Superior',
    obligatorio: true
  }, {
    id: 5,
    nombre: 'Año que cursa',
    tipo: 'Selección',
    segmento: 'Nivel Superior',
    obligatorio: true
  }, {
    id: 6,
    nombre: '¿Percibe otra beca?',
    tipo: 'Sí / No',
    segmento: 'Nivel Superior',
    obligatorio: false
  }, {
    id: 7,
    nombre: 'Constancia de CBU',
    tipo: 'Archivo',
    segmento: 'Nivel Superior',
    obligatorio: true
  }],
  // 13 preguntas globales del programa (se muestran informativas en la convocatoria)
  requisitosGenerales: ['Apellido y nombre', 'DNI', 'Fecha de nacimiento', 'Sexo', 'Domicilio', 'Localidad', 'Teléfono de contacto', 'Correo electrónico', 'Estado civil', 'Composición del grupo familiar', 'Situación habitacional', 'Ingreso mensual del hogar', 'Cobertura de salud'],
  // Usuarios con rol Territorial
  territoriales: ['Juan Pérez', 'María López', 'Carlos Gómez', 'Paula Vega', 'Marta Ojeda'],
  // Convocatorias — segmento/subsegmento por id; cupo se toma del subsegmento si tiene, si no del segmento.
  convocatorias: [{
    id: 1,
    nombre: 'Convocatoria Becas 2026 — Carbón',
    desc: 'Relevamiento de productores de carbón vegetal del territorio.',
    segmentoId: 1,
    subsegmentoId: 102,
    desde: '01/03/2026',
    hasta: '30/04/2026',
    estado: 'activa',
    creada: '12/02/2026',
    creadoPor: 'Admin — D. Ferreyra',
    relevamientos: [{
      id: 1,
      nombre: 'Relevamiento 001',
      territorial: 'Juan Pérez',
      zona: 'Resistencia - Zona Norte',
      plazo: '15/03/2026',
      estado: 'ASIGNADO',
      formularios: 0
    }, {
      id: 2,
      nombre: 'Relevamiento 002',
      territorial: 'María López',
      zona: 'Pcia. Roque Sáenz Peña',
      plazo: '20/03/2026',
      estado: 'EN_CURSO',
      formularios: 12
    }, {
      id: 3,
      nombre: 'Relevamiento 003',
      territorial: 'Carlos Gómez',
      zona: 'Villa Ángela',
      plazo: '18/03/2026',
      estado: 'FINALIZADO',
      formularios: 25
    }, {
      id: 4,
      nombre: 'Relevamiento 004',
      territorial: 'Paula Vega',
      zona: 'Charata',
      plazo: '22/03/2026',
      estado: 'EN_REVISION',
      formularios: 18
    }],
    beneficiarios: [{
      dni: '12.345.678',
      nombre: 'Juan Pérez',
      estado: 'cupo',
      fecha: '20/03/2026'
    }, {
      dni: '87.654.321',
      nombre: 'María López',
      estado: 'espera',
      fecha: '22/03/2026'
    }, {
      dni: '33.221.998',
      nombre: 'Ramón Acosta',
      estado: 'cupo',
      fecha: '21/03/2026'
    }, {
      dni: '40.552.117',
      nombre: 'Lucía Sosa',
      estado: 'rechazado',
      fecha: '23/03/2026'
    }]
  }, {
    id: 2,
    nombre: 'Becas Superior 2026 — Universitario',
    desc: 'Becas para estudiantes universitarios de grado.',
    segmentoId: 2,
    subsegmentoId: 202,
    desde: '01/03/2026',
    hasta: '15/05/2026',
    estado: 'activa',
    creada: '10/02/2026',
    creadoPor: 'Admin — M. González',
    relevamientos: [{
      id: 1,
      nombre: 'Relevamiento 001',
      territorial: 'Paula Vega',
      zona: 'Resistencia - Centro',
      plazo: '12/03/2026',
      estado: 'EN_CURSO',
      formularios: 30
    }, {
      id: 2,
      nombre: 'Relevamiento 002',
      territorial: 'Marta Ojeda',
      zona: 'Barranqueras',
      plazo: '14/03/2026',
      estado: 'TERMINADO',
      formularios: 41
    }],
    beneficiarios: [{
      dni: '45.880.214',
      nombre: 'Acosta, Brenda Sofía',
      estado: 'cupo',
      fecha: '15/03/2026'
    }, {
      dni: '46.112.907',
      nombre: 'Benítez, Tomás',
      estado: 'espera',
      fecha: '16/03/2026'
    }]
  }, {
    id: 3,
    nombre: 'Convocatoria Becas 2026 — Ladrillo',
    desc: 'Relevamiento de productores de ladrillo artesanal.',
    segmentoId: 1,
    subsegmentoId: 101,
    desde: '01/04/2026',
    hasta: '20/05/2026',
    estado: 'inactiva',
    creada: '05/03/2026',
    creadoPor: 'Admin — D. Ferreyra',
    relevamientos: [],
    beneficiarios: []
  }, {
    id: 4,
    nombre: 'Becas Secundario 2025',
    desc: 'Convocatoria del ciclo lectivo anterior.',
    segmentoId: 3,
    subsegmentoId: 302,
    desde: '15/02/2025',
    hasta: '15/03/2025',
    estado: 'finalizada',
    creada: '20/01/2025',
    creadoPor: 'Admin — L. Méndez',
    relevamientos: [{
      id: 1,
      nombre: 'Relevamiento 001',
      territorial: 'Carlos Gómez',
      zona: 'Sáenz Peña',
      plazo: '01/03/2025',
      estado: 'TERMINADO',
      formularios: 60
    }],
    beneficiarios: []
  }],
  convEstados: {
    activa: {
      label: 'Activa',
      variant: 'success',
      dot: true
    },
    inactiva: {
      label: 'Inactiva',
      variant: 'gray'
    },
    finalizada: {
      label: 'Finalizada',
      variant: 'brand'
    }
  },
  benefEstados: {
    cupo: {
      label: 'Con cupo',
      variant: 'success',
      dot: true
    },
    espera: {
      label: 'En lista de espera',
      variant: 'warning'
    },
    rechazado: {
      label: 'Validado-Rechazado',
      variant: 'danger'
    }
  },
  // Estado del formulario / persona relevada (dentro de un operativo)
  personaEstados: {
    PENDIENTE: {
      label: 'Pendiente',
      variant: 'warning'
    },
    APROBADO: {
      label: 'Aprobado',
      variant: 'success',
      dot: true
    },
    RECHAZADO: {
      label: 'Rechazado',
      variant: 'danger'
    },
    VALIDADO_SIS: {
      label: 'Validado SIS',
      variant: 'success',
      dot: true
    },
    RECHAZADO_SIS: {
      label: 'Rechazado SIS',
      variant: 'danger'
    }
  },
  renaperRes: {
    validado: {
      label: 'Validado',
      variant: 'success',
      icon: 'checkCircle'
    },
    no_validado: {
      label: 'No validado',
      variant: 'danger',
      icon: 'xCircle'
    },
    pendiente: {
      label: 'Pendiente',
      variant: 'warning',
      icon: 'clock'
    }
  },
  sisRes: {
    oka: {
      label: 'OKA',
      variant: 'success',
      icon: 'checkCircle'
    },
    rechazado: {
      label: 'Rechazado',
      variant: 'danger',
      icon: 'xCircle'
    },
    pendiente: {
      label: 'Pendiente',
      variant: 'warning',
      icon: 'clock'
    }
  },
  // OPERATIVOS de relevamiento. Las personas relevadas viven DENTRO de cada operativo.
  relevamientos: [{
    id: 1,
    nombre: 'Relevamiento 001',
    convocatoria: 'Convocatoria Becas 2026 — Carbón',
    segmento: 'Producción Territorial',
    subsegmento: 'Carbón',
    territorial: 'Juan Pérez',
    zona: 'Resistencia - Zona Norte',
    fecha: '15/03/2026',
    estado: 'EN_CURSO',
    observaciones: 'Acceso por camino vecinal; coordinar con referente local.',
    personas: [{
      dni: '12.345.678',
      nombre: 'Juan Pérez',
      fechaCarga: '12/03/2026',
      estado: 'APROBADO',
      renaper: 'validado',
      sis: 'oka'
    }, {
      dni: '23.456.789',
      nombre: 'Marta Giménez',
      fechaCarga: '12/03/2026',
      estado: 'PENDIENTE',
      renaper: 'validado',
      sis: 'pendiente'
    }, {
      dni: '34.567.890',
      nombre: 'Ramón Acosta',
      fechaCarga: '13/03/2026',
      estado: 'VALIDADO_SIS',
      renaper: 'validado',
      sis: 'oka'
    }, {
      dni: '45.678.901',
      nombre: 'Lucía Sosa',
      fechaCarga: '13/03/2026',
      estado: 'RECHAZADO_SIS',
      renaper: 'validado',
      sis: 'rechazado'
    }, {
      dni: '56.789.012',
      nombre: 'Pedro Maidana',
      fechaCarga: '14/03/2026',
      estado: 'RECHAZADO',
      renaper: 'no_validado',
      sis: 'pendiente'
    }]
  }, {
    id: 2,
    nombre: 'Relevamiento 002',
    convocatoria: 'Convocatoria Becas 2026 — Carbón',
    segmento: 'Producción Territorial',
    subsegmento: 'Carbón',
    territorial: 'María López',
    zona: 'Pcia. Roque Sáenz Peña',
    fecha: '20/03/2026',
    estado: 'ASIGNADO',
    observaciones: '',
    personas: []
  }, {
    id: 3,
    nombre: 'Relevamiento 003',
    convocatoria: 'Convocatoria Becas 2026 — Carbón',
    segmento: 'Producción Territorial',
    subsegmento: 'Carbón',
    territorial: 'Carlos Gómez',
    zona: 'Villa Ángela',
    fecha: '18/03/2026',
    estado: 'EN_REVISION',
    observaciones: 'Operativo conjunto con Desarrollo Social.',
    personas: [{
      dni: '67.890.123',
      nombre: 'Ana Benítez',
      fechaCarga: '16/03/2026',
      estado: 'PENDIENTE',
      renaper: 'validado',
      sis: 'pendiente'
    }, {
      dni: '78.901.234',
      nombre: 'Diego Cabrera',
      fechaCarga: '16/03/2026',
      estado: 'APROBADO',
      renaper: 'validado',
      sis: 'oka'
    }, {
      dni: '89.012.345',
      nombre: 'Sofía Ledesma',
      fechaCarga: '17/03/2026',
      estado: 'PENDIENTE',
      renaper: 'pendiente',
      sis: 'pendiente'
    }]
  }, {
    id: 4,
    nombre: 'Relevamiento 004',
    convocatoria: 'Becas Superior 2026 — Universitario',
    segmento: 'Nivel Superior',
    subsegmento: 'Universitario',
    territorial: 'Paula Vega',
    zona: 'Resistencia - Centro',
    fecha: '12/03/2026',
    estado: 'TERMINADO',
    observaciones: '',
    personas: [{
      dni: '45.880.214',
      nombre: 'Acosta, Brenda Sofía',
      fechaCarga: '10/03/2026',
      estado: 'APROBADO',
      renaper: 'validado',
      sis: 'oka'
    }, {
      dni: '46.112.907',
      nombre: 'Benítez, Tomás',
      fechaCarga: '10/03/2026',
      estado: 'VALIDADO_SIS',
      renaper: 'validado',
      sis: 'oka'
    }]
  }, {
    id: 5,
    nombre: 'Relevamiento 005',
    convocatoria: 'Convocatoria Becas 2026 — Ladrillo',
    segmento: 'Producción Territorial',
    subsegmento: 'Ladrillo',
    territorial: 'Marta Ojeda',
    zona: 'Charata',
    fecha: '08/03/2026',
    estado: 'VENCIDO',
    observaciones: 'Sin avances; reprogramar.',
    personas: []
  }],
  // Form under review (caso a caso)
  formulario: {
    ciudadano: 'Acosta, Brenda Sofía',
    dni: '45.880.214',
    edad: 19,
    convocatoria: 'Becas Superior 2026 — 1er cuatrimestre',
    segmento: 'Nivel Superior · Universitario',
    territorial: 'Carlos Ruiz',
    presentado: '18/06/2026',
    social: [{
      p: 'Composición del grupo familiar',
      r: '4 integrantes (madre, 2 hermanos menores)'
    }, {
      p: 'Ingreso mensual del hogar',
      r: '$ 410.000'
    }, {
      p: 'Situación habitacional',
      r: 'Vivienda alquilada'
    }, {
      p: 'Cobertura de salud',
      r: 'Hospital público'
    }, {
      p: '¿Trabaja actualmente?',
      r: 'No'
    }],
    requisitos: [{
      nombre: 'Certificado de alumno regular',
      tipo: 'Archivo',
      valor: 'cert-regular.pdf',
      ok: true
    }, {
      nombre: 'Promedio del último período',
      tipo: 'Número',
      valor: '8,40',
      ok: true
    }, {
      nombre: 'Institución educativa',
      tipo: 'Texto',
      valor: 'UNNE — Facultad de Medicina',
      ok: true
    }, {
      nombre: 'Carrera / Especialidad',
      tipo: 'Texto',
      valor: 'Medicina',
      ok: true
    }, {
      nombre: 'Año que cursa',
      tipo: 'Selección',
      valor: '2º año',
      ok: true
    }, {
      nombre: 'Constancia de CBU',
      tipo: 'Archivo',
      valor: '— sin adjuntar —',
      ok: false
    }],
    historial: [{
      quien: 'Carlos Ruiz (Territorial)',
      accion: 'Presentó el formulario',
      cuando: '18/06 · 09:12'
    }, {
      quien: 'Sistema',
      accion: 'Validación RENAPER correcta',
      cuando: '18/06 · 09:12'
    }, {
      quien: 'María González (Coordinadora)',
      accion: 'Tomó el caso para revisión',
      cuando: '18/06 · 11:40'
    }]
  },
  // Cupo y lista de espera
  espera: [{
    id: 7701,
    ciudadano: 'Gómez, Valentina',
    dni: '47.553.901',
    convocatoria: 'Becas Superior 2026 — 1er cuatr.',
    desde: '12/06/2026',
    prioridad: 'Alta'
  }, {
    id: 7702,
    ciudadano: 'Herrera, Nicolás',
    dni: '46.220.114',
    convocatoria: 'Becas Superior 2026 — 1er cuatr.',
    desde: '12/06/2026',
    prioridad: 'Media'
  }, {
    id: 7703,
    ciudadano: 'Ibáñez, Camila',
    dni: '48.001.226',
    convocatoria: 'Becas Superior 2026 — 1er cuatr.',
    desde: '13/06/2026',
    prioridad: 'Media'
  }, {
    id: 7704,
    ciudadano: 'Juárez, Lautaro',
    dni: '47.889.330',
    convocatoria: 'Becas Superior 2026 — 1er cuatr.',
    desde: '14/06/2026',
    prioridad: 'Baja'
  }],
  prioridades: {
    Alta: 'danger',
    Media: 'warning',
    Baja: 'gray'
  },
  // Formularios cargados dentro de un relevamiento (lista caso a caso)
  formEstados: {
    BORRADOR: {
      label: 'Borrador',
      variant: 'gray'
    },
    PRESENTADO: {
      label: 'Presentado',
      variant: 'warning'
    },
    EN_REVISION: {
      label: 'En revisión',
      variant: 'brand'
    },
    APROBADO: {
      label: 'Aprobado',
      variant: 'success',
      dot: true
    },
    RECHAZADO: {
      label: 'Rechazado',
      variant: 'danger'
    }
  },
  formularios: [{
    id: 9001,
    ciudadano: 'Acosta, Brenda Sofía',
    dni: '45.880.214',
    renaper: 'ok',
    estado: 'EN_REVISION',
    completo: 92,
    presentado: '18/06/2026'
  }, {
    id: 9002,
    ciudadano: 'Benítez, Tomás',
    dni: '46.112.907',
    renaper: 'ok',
    estado: 'PRESENTADO',
    completo: 100,
    presentado: '18/06/2026'
  }, {
    id: 9003,
    ciudadano: 'Coronel, Ailén',
    dni: '44.503.118',
    renaper: 'pendiente',
    estado: 'BORRADOR',
    completo: 60,
    presentado: '—'
  }, {
    id: 9004,
    ciudadano: 'Duarte, Mateo',
    dni: '47.220.661',
    renaper: 'ok',
    estado: 'APROBADO',
    completo: 100,
    presentado: '15/06/2026'
  }, {
    id: 9005,
    ciudadano: 'Escobar, Lucía',
    dni: '45.009.473',
    renaper: 'observado',
    estado: 'RECHAZADO',
    completo: 80,
    presentado: '14/06/2026'
  }],
  renaperEstados: {
    ok: {
      label: 'RENAPER validado',
      variant: 'success',
      icon: 'checkCircle'
    },
    pendiente: {
      label: 'RENAPER pendiente',
      variant: 'warning',
      icon: 'clock'
    },
    observado: {
      label: 'RENAPER observado',
      variant: 'danger',
      icon: 'exclamationCircle'
    }
  }
};
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/programa-becas/data.js", error: String((e && e.message) || e) }); }

// ui_kits/programa-becas/icons.jsx
try { (() => {
// Heroicons v2 (outline) — the icon library for NEW NODO/CHACO templates.
// Icons inherit color from the parent's `color` (never hardcoded). Stroke 1.5.
(function () {
  const P = {
    home: ['m2.25 12 8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.5a.75.75 0 0 0 .75.75h4.5a.75.75 0 0 0 .75-.75V15a.75.75 0 0 1 .75-.75h3a.75.75 0 0 1 .75.75v5.25c0 .414.336.75.75.75h4.5a.75.75 0 0 0 .75-.75V9.75M8.25 21h8.25'],
    squares: ['M3.75 6A2.25 2.25 0 0 1 6 3.75h2.25A2.25 2.25 0 0 1 10.5 6v2.25a2.25 2.25 0 0 1-2.25 2.25H6a2.25 2.25 0 0 1-2.25-2.25V6ZM3.75 15.75A2.25 2.25 0 0 1 6 13.5h2.25a2.25 2.25 0 0 1 2.25 2.25V18a2.25 2.25 0 0 1-2.25 2.25H6A2.25 2.25 0 0 1 3.75 18v-2.25ZM13.5 6a2.25 2.25 0 0 1 2.25-2.25H18A2.25 2.25 0 0 1 20.25 6v2.25A2.25 2.25 0 0 1 18 10.5h-2.25a2.25 2.25 0 0 1-2.25-2.25V6ZM13.5 15.75a2.25 2.25 0 0 1 2.25-2.25H18a2.25 2.25 0 0 1 2.25 2.25V18A2.25 2.25 0 0 1 18 20.25h-2.25A2.25 2.25 0 0 1 13.5 18v-2.25Z'],
    folderOpen: ['M3.75 9.776c.112-.017.227-.026.344-.026h15.812c.117 0 .232.009.344.026m-16.5 0a2.25 2.25 0 0 0-1.883 2.542l.857 6a2.25 2.25 0 0 0 2.227 1.932H19.05a2.25 2.25 0 0 0 2.227-1.932l.857-6a2.25 2.25 0 0 0-1.883-2.542m-16.5 0V6A2.25 2.25 0 0 1 6 3.75h3.879a1.5 1.5 0 0 1 1.06.44l2.122 2.12a1.5 1.5 0 0 0 1.06.44H18A2.25 2.25 0 0 1 20.25 9v.776'],
    clipboardList: ['M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 0 0 2.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 0 0-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 0 0 .75-.75 2.25 2.25 0 0 0-.1-.664m-5.8 0A2.251 2.251 0 0 1 13.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25Z'],
    clipboardCheck: ['M11.35 3.836c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 0 0 .75-.75 2.25 2.25 0 0 0-.1-.664m-5.8 0A2.251 2.251 0 0 1 13.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m8.9-4.414c.376.023.75.05 1.124.08 1.131.094 1.976 1.057 1.976 2.192V16.5A2.25 2.25 0 0 1 18 18.75h-2.25m-7.5-10.5H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V18.75m-7.5-10.5h6.375c.621 0 1.125.504 1.125 1.125v9.375m-8.25-3 1.5 1.5 3-3.75'],
    megaphone: ['M10.34 15.84c-.688-.06-1.386-.09-2.09-.09H7.5a4.5 4.5 0 1 1 0-9h.75c.704 0 1.402-.03 2.09-.09m0 9.18c.253.962.584 1.892.985 2.783.247.55.06 1.21-.463 1.51l-.657.38c-.551.318-1.26.117-1.527-.461a20.845 20.845 0 0 1-1.44-4.282m3.102.069a18.03 18.03 0 0 1-.59-4.59c0-1.586.205-3.124.59-4.59m0 9.18a23.848 23.848 0 0 1 8.835 2.535M10.34 6.66a23.847 23.847 0 0 0 8.835-2.535m0 0A23.74 23.74 0 0 0 18.795 3m.38 1.125a23.91 23.91 0 0 1 1.014 5.395m-1.014 8.855c-.118.38-.245.754-.38 1.125m.38-1.125a23.91 23.91 0 0 0 1.014-5.395m0-3.46c.495.413.811 1.035.811 1.73 0 .695-.316 1.317-.811 1.73m0-3.46a24.347 24.347 0 0 1 0 3.46'],
    usersGroup: ['M15 19.128a9.38 9.38 0 0 0 2.625.372 9.337 9.337 0 0 0 4.121-.952 4.125 4.125 0 0 0-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 0 1 8.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0 1 11.964-3.07M12 6.375a3.375 3.375 0 1 1-6.75 0 3.375 3.375 0 0 1 6.75 0Zm8.25 2.25a2.625 2.625 0 1 1-5.25 0 2.625 2.625 0 0 1 5.25 0Z'],
    chartBar: ['M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z'],
    cog: ['M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.431l-1.003.827c-.293.24-.438.613-.43.992a7.723 7.723 0 0 1 0 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 0 1 0-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.281Z', 'M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z'],
    bell: ['M14.857 17.082a23.848 23.848 0 0 0 5.454-1.31A8.967 8.967 0 0 1 18 9.75V9A6 6 0 0 0 6 9v.75a8.967 8.967 0 0 1-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 0 1-5.714 0m5.714 0a3 3 0 1 1-5.714 0'],
    search: ['m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z'],
    plus: ['M12 4.5v15m7.5-7.5h-15'],
    plusCircle: ['M12 9v6m3-3H9m12 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z'],
    eye: ['M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178Z', 'M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z'],
    pencil: ['m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10'],
    trash: ['m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0'],
    chevronRight: ['m8.25 4.5 7.5 7.5-7.5 7.5'],
    chevronDown: ['m19.5 8.25-7.5 7.5-7.5-7.5'],
    chevronLeft: ['M15.75 19.5 8.25 12l7.5-7.5'],
    arrowLeft: ['M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18'],
    download: ['M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3'],
    check: ['m4.5 12.75 6 6 9-13.5'],
    checkCircle: ['M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z'],
    xCircle: ['m9.75 9.75 4.5 4.5m0-4.5-4.5 4.5M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z'],
    xMark: ['M6 18 18 6M6 6l12 12'],
    warning: ['M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z'],
    exclamationCircle: ['M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z'],
    clock: ['M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z'],
    funnel: ['M12 3c2.755 0 5.455.232 8.083.678.533.09.917.556.917 1.096v1.044a2.25 2.25 0 0 1-.659 1.591l-5.432 5.432a2.25 2.25 0 0 0-.659 1.591v2.927a2.25 2.25 0 0 1-1.244 2.013L9.75 21v-6.568a2.25 2.25 0 0 0-.659-1.591L3.659 7.409A2.25 2.25 0 0 1 3 5.818V4.774c0-.54.384-1.006.917-1.096A48.32 48.32 0 0 1 12 3Z'],
    identification: ['M15 9h3.75M15 12h3.75M15 15h3.75M4.5 19.5h15a2.25 2.25 0 0 0 2.25-2.25V6.75A2.25 2.25 0 0 0 19.5 4.5h-15a2.25 2.25 0 0 0-2.25 2.25v10.5A2.25 2.25 0 0 0 4.5 19.5Zm6-10.125a1.875 1.875 0 1 1-3.75 0 1.875 1.875 0 0 1 3.75 0ZM10.5 15.75a3 3 0 0 0-6 0v.75c0 .414.336.75.75.75h4.5a.75.75 0 0 0 .75-.75v-.75Z'],
    academicCap: ['M4.26 10.147a60.438 60.438 0 0 0-.491 6.347A48.62 48.62 0 0 1 12 20.904a48.62 48.62 0 0 1 8.232-4.41 60.46 60.46 0 0 0-.491-6.347m-15.482 0a50.636 50.636 0 0 0-2.658-.813A59.906 59.906 0 0 1 12 3.493a59.903 59.903 0 0 1 10.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.717 50.717 0 0 1 12 13.489a50.702 50.702 0 0 1 7.74-3.342M6.75 15a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Zm0 0v-3.675A55.378 55.378 0 0 1 12 8.443m-7.007 11.55A5.981 5.981 0 0 0 6.75 15.75v-1.5'],
    briefcase: ['M20.25 14.15v4.073a2.25 2.25 0 0 1-1.632 2.163l-1.32.377a9.797 9.797 0 0 1-5.396 0l-1.32-.377a2.25 2.25 0 0 1-1.632-2.163V14.15M20.25 14.15a48.7 48.7 0 0 0-16.5 0m16.5 0a2.25 2.25 0 0 0 1.5-2.122V8.706a2.25 2.25 0 0 0-1.883-2.221 48.422 48.422 0 0 0-1.117-.165M3.75 14.15a2.25 2.25 0 0 1-1.5-2.122V8.706a2.25 2.25 0 0 1 1.883-2.221c.37-.058.74-.113 1.117-.165m12.75 0V5.625a2.25 2.25 0 0 0-2.25-2.25h-3a2.25 2.25 0 0 0-2.25 2.25v.741m7.5 0a49.16 49.16 0 0 0-7.5 0'],
    documentText: ['M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z'],
    userPlus: ['M19 7.5v3m0 0v3m0-3h3m-3 0h-3m-2.25-4.125a3.375 3.375 0 1 1-6.75 0 3.375 3.375 0 0 1 6.75 0ZM4 19.235v-.11a6.375 6.375 0 0 1 12.75 0v.109A12.318 12.318 0 0 1 10.374 21c-2.331 0-4.512-.645-6.374-1.766Z'],
    mapPin: ['M15 10.5a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z', 'M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1 1 15 0Z'],
    adjustments: ['M10.5 6h9.75M10.5 6a1.5 1.5 0 1 1-3 0m3 0a1.5 1.5 0 1 0-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m-9.75 0h9.75'],
    dotsVertical: ['M12 6.75a.75.75 0 1 1 0-1.5.75.75 0 0 1 0 1.5ZM12 12.75a.75.75 0 1 1 0-1.5.75.75 0 0 1 0 1.5ZM12 18.75a.75.75 0 1 1 0-1.5.75.75 0 0 1 0 1.5Z'],
    userCircle: ['M17.982 18.725A7.488 7.488 0 0 0 12 15.75a7.488 7.488 0 0 0-5.982 2.975m11.963 0a9 9 0 1 0-11.963 0m11.963 0A8.966 8.966 0 0 1 12 21a8.966 8.966 0 0 1-5.982-2.275M15 9.75a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z'],
    arrowPath: ['M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99'],
    listBullet: ['M8.25 6.75h12M8.25 12h12m-12 5.25h12M3.75 6.75h.007v.008H3.75V6.75Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0ZM3.75 12h.007v.008H3.75V12Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm-.375 5.25h.007v.008H3.75v-.008Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Z'],
    pencilSquare: ['m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10']
  };
  function Icon({
    name,
    size = 24,
    style,
    ...rest
  }) {
    const d = P[name] || P.squares;
    return React.createElement('svg', {
      viewBox: '0 0 24 24',
      fill: 'none',
      stroke: 'currentColor',
      strokeWidth: 1.5,
      width: size,
      height: size,
      'aria-hidden': true,
      style: {
        display: 'inline-block',
        flexShrink: 0,
        ...style
      },
      ...rest
    }, d.map((path, i) => React.createElement('path', {
      key: i,
      d: path,
      strokeLinecap: 'round',
      strokeLinejoin: 'round'
    })));
  }
  window.Icon = Icon;
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/programa-becas/icons.jsx", error: String((e && e.message) || e) }); }

// ui_kits/programa-becas/inicio-data.js
try { (() => {
// /inicio/ — datos mock del panel de inicio (ficticios). Chaco / NODO backoffice.
window.INICIO = {
  user: {
    name: 'María González',
    role: 'Coordinadora — Nivel Superior'
  },
  saludo: 'Buenas tardes',
  stats: [{
    label: 'Legajos activos',
    value: '1.284',
    icon: 'folderOpen',
    tone: 'brand',
    gradient: true,
    change: '8%',
    dir: 'up',
    foot: 'vs. mes anterior'
  }, {
    label: 'Relevamientos en curso',
    value: '37',
    icon: 'clipboardList',
    tone: 'warning',
    change: '5',
    dir: 'up',
    foot: '6 sin asignar'
  }, {
    label: 'Formularios por revisar',
    value: '24',
    icon: 'clipboardCheck',
    tone: 'brand',
    change: '3',
    dir: 'down',
    foot: 'pendientes hoy'
  }, {
    label: 'Beneficiarios con cupo',
    value: '9.512',
    icon: 'usersGroup',
    tone: 'success',
    change: '12%',
    dir: 'up',
    foot: 'en el trimestre'
  }],
  accesos: [{
    label: 'Nuevo legajo',
    icon: 'identification',
    tone: 'brand'
  }, {
    label: 'Nueva convocatoria',
    icon: 'megaphone',
    tone: 'olive'
  }, {
    label: 'Asignar relevamiento',
    icon: 'folderOpen',
    tone: 'pink'
  }, {
    label: 'Revisar formularios',
    icon: 'clipboardCheck',
    tone: 'brand'
  }],
  pendientes: [{
    titulo: 'Formularios en revisión',
    desc: 'Becas Superior 2026 — Universitario',
    n: 18,
    tone: 'brand',
    icon: 'clipboardCheck'
  }, {
    titulo: 'Relevamientos vencidos',
    desc: 'Requieren reprogramación',
    n: 2,
    tone: 'danger',
    icon: 'clock'
  }, {
    titulo: 'RENAPER pendiente',
    desc: 'Validaciones sin resolver',
    n: 7,
    tone: 'warning',
    icon: 'exclamationCircle'
  }, {
    titulo: 'Lista de espera',
    desc: 'Producción Territorial / Carbón',
    n: 64,
    tone: 'olive',
    icon: 'usersGroup'
  }],
  actividad: [{
    icon: 'pencilSquare',
    text: 'Actualizaste la dimensión Vivienda del legajo #1284',
    time: 'hace 20 min',
    tone: 'brand'
  }, {
    icon: 'checkCircle',
    text: 'Aprobaste el formulario de Acosta, Brenda Sofía',
    time: 'hace 1 h',
    tone: 'success'
  }, {
    icon: 'folderOpen',
    text: 'Se creó el Relevamiento 005 — Charata',
    time: 'hace 3 h',
    tone: 'olive'
  }, {
    icon: 'xCircle',
    text: 'Rechazaste el formulario de Maidana, Pedro',
    time: 'hace 5 h',
    tone: 'danger'
  }, {
    icon: 'megaphone',
    text: 'Se abrió la convocatoria Becas 2026 — Carbón',
    time: 'ayer',
    tone: 'brand'
  }],
  agenda: [{
    hora: '09:30',
    titulo: 'Operativo Resistencia - Zona Norte',
    sub: 'Territorial: Juan Pérez',
    estado: 'En curso',
    tone: 'warning'
  }, {
    hora: '11:00',
    titulo: 'Revisión de cupo — Nivel Superior',
    sub: 'Coordinación',
    estado: 'Hoy',
    tone: 'brand'
  }, {
    hora: '14:00',
    titulo: 'Cierre convocatoria Secundario',
    sub: 'Vence en 3 días',
    estado: 'Próximo',
    tone: 'gray'
  }],
  cobertura: [['Tarjeta Alimentar', 46, 'var(--bg-brand)'], ['Producción Territorial', 28, 'var(--color-olive-500)'], ['Becas Superior', 18, 'var(--bg-pink)'], ['Otros', 8, 'var(--bg-quaternary)']]
};
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/programa-becas/inicio-data.js", error: String((e && e.message) || e) }); }

__ds_ns.Avatar = __ds_scope.Avatar;

__ds_ns.Badge = __ds_scope.Badge;

__ds_ns.Button = __ds_scope.Button;

__ds_ns.Card = __ds_scope.Card;

__ds_ns.StatCard = __ds_scope.StatCard;

__ds_ns.Alert = __ds_scope.Alert;

__ds_ns.Modal = __ds_scope.Modal;

__ds_ns.Input = __ds_scope.Input;

__ds_ns.Select = __ds_scope.Select;

__ds_ns.Tabs = __ds_scope.Tabs;

})();
