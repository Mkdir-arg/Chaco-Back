import React from 'react';

/**
 * Alert — inline message banner. Soft tinted background, leading icon,
 * optional title and dismiss. Matches the portal/backoffice message style.
 */
export function Alert({ children, variant = 'info', title, icon, onClose, style, ...rest }) {
  const variants = {
    info:    { bg: 'var(--bg-info-soft)',    fg: 'var(--text-fg-info)',    bd: 'var(--color-brand-200)',          ic: 'fas fa-circle-info' },
    success: { bg: 'var(--bg-success-soft)', fg: 'var(--text-fg-success)', bd: 'var(--border-success-subtle)',    ic: 'fas fa-circle-check' },
    warning: { bg: 'var(--bg-warning-soft)', fg: 'var(--text-fg-warning)', bd: 'var(--border-warning-subtle)',    ic: 'fas fa-triangle-exclamation' },
    danger:  { bg: 'var(--bg-danger-soft)',  fg: 'var(--text-fg-danger)',  bd: 'var(--border-danger-subtle)',     ic: 'fas fa-circle-exclamation' },
  };
  const v = variants[variant] || variants.info;
  return (
    <div
      role="alert"
      style={{
        display: 'flex', alignItems: 'flex-start', gap: 12,
        padding: '14px 16px',
        background: v.bg,
        border: `1px solid ${v.bd}`,
        borderRadius: 'var(--radius-xl)',
        color: v.fg,
        fontFamily: 'var(--font-sans)',
        ...style,
      }}
      {...rest}
    >
      <i className={icon || v.ic} aria-hidden="true" style={{ fontSize: 16, marginTop: 2, flexShrink: 0 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        {title && <div style={{ fontWeight: 700, fontSize: 14, marginBottom: children ? 2 : 0 }}>{title}</div>}
        {children && <div style={{ fontSize: 13.5, lineHeight: 1.5, color: 'var(--text-body)' }}>{children}</div>}
      </div>
      {onClose && (
        <button onClick={onClose} aria-label="Cerrar" style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', fontSize: 15, opacity: 0.7, padding: 2, lineHeight: 1 }}>
          <i className="fas fa-xmark" aria-hidden="true" />
        </button>
      )}
    </div>
  );
}
