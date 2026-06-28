import React from 'react';

/**
 * Modal — centered dialog over a dimmed, blurred backdrop. Matches the
 * app's ModernModal: header with tinted icon, body, action footer.
 */
export function Modal({ open = true, title, icon, tone = 'info', children, onClose, footer, width = 480, style }) {
  if (!open) return null;
  const tones = {
    info:    { bg: 'var(--bg-info-soft)',    fg: 'var(--text-fg-info)',    ic: 'fas fa-circle-info' },
    success: { bg: 'var(--bg-success-soft)', fg: 'var(--text-fg-success)', ic: 'fas fa-circle-check' },
    warning: { bg: 'var(--bg-warning-soft)', fg: 'var(--text-fg-warning)', ic: 'fas fa-triangle-exclamation' },
    danger:  { bg: 'var(--bg-danger-soft)',  fg: 'var(--text-fg-danger)',  ic: 'fas fa-circle-exclamation' },
    brand:   { bg: 'var(--bg-brand-soft)',   fg: 'var(--text-fg-brand)',   ic: 'fas fa-bell' },
  };
  const t = tones[tone] || tones.info;
  return (
    <div
      onClick={(e) => { if (e.target === e.currentTarget && onClose) onClose(); }}
      style={{
        position: 'fixed', inset: 0, zIndex: 50,
        background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(4px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
      }}
    >
      <div style={{
        width: '100%', maxWidth: width,
        background: 'var(--bg-white)',
        borderRadius: 'var(--radius-2xl)',
        boxShadow: 'var(--shadow-xl)',
        overflow: 'hidden',
        fontFamily: 'var(--font-sans)',
        ...style,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, padding: '20px 24px', borderBottom: '1px solid var(--border-light)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            {(icon || t.ic) && (
              <div style={{ width: 40, height: 40, borderRadius: 'var(--radius-lg)', background: t.bg, color: t.fg, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18 }}>
                <i className={icon || t.ic} aria-hidden="true" />
              </div>
            )}
            <h3 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: 'var(--text-heading)' }}>{title}</h3>
          </div>
          {onClose && (
            <button onClick={onClose} aria-label="Cerrar" style={{ background: 'none', border: 'none', color: 'var(--text-body-subtle)', cursor: 'pointer', fontSize: 18, padding: 4, lineHeight: 1 }}>
              <i className="fas fa-xmark" aria-hidden="true" />
            </button>
          )}
        </div>
        <div style={{ padding: 24, fontSize: 14, lineHeight: 1.6, color: 'var(--text-body)' }}>{children}</div>
        {footer && (
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, padding: '16px 24px', borderTop: '1px solid var(--border-light)', background: 'var(--bg-secondary)' }}>
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}
