import React from 'react';

/**
 * Card — the base white surface used everywhere in the backoffice and portal.
 * 12px radius, hairline border, soft shadow. Optional header / footer slots.
 */
export function Card({ children, title, subtitle, headerRight, footer, padding = 24, hover = false, accent, style, ...rest }) {
  return (
    <div
      style={{
        background: 'var(--bg-primary)',
        border: '1px solid var(--border-base)',
        borderRadius: 'var(--radius-xl)',
        boxShadow: 'var(--shadow-sm)',
        overflow: 'hidden',
        transition: 'box-shadow var(--duration-normal) var(--ease-standard), transform var(--duration-normal) var(--ease-standard)',
        ...(accent ? { borderTop: `3px solid ${accent}` } : null),
        ...style,
      }}
      onMouseEnter={(e) => { if (hover) { e.currentTarget.style.boxShadow = 'var(--shadow-lg)'; e.currentTarget.style.transform = 'translateY(-2px)'; } }}
      onMouseLeave={(e) => { if (hover) { e.currentTarget.style.boxShadow = 'var(--shadow-sm)'; e.currentTarget.style.transform = 'none'; } }}
      {...rest}
    >
      {(title || headerRight) && (
        <div style={{
          display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between',
          gap: 16, padding: '16px 20px', borderBottom: '1px solid var(--border-light)',
        }}>
          <div>
            {title && <div style={{ fontFamily: 'var(--font-sans)', fontSize: 16, fontWeight: 700, color: 'var(--text-heading)' }}>{title}</div>}
            {subtitle && <div style={{ fontSize: 13, color: 'var(--text-body-subtle)', marginTop: 2 }}>{subtitle}</div>}
          </div>
          {headerRight && <div style={{ flexShrink: 0 }}>{headerRight}</div>}
        </div>
      )}
      <div style={{ padding }}>{children}</div>
      {footer && (
        <div style={{ padding: '14px 20px', borderTop: '1px solid var(--border-light)', background: 'var(--bg-secondary)' }}>
          {footer}
        </div>
      )}
    </div>
  );
}
