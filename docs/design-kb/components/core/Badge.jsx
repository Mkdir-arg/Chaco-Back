import React from 'react';

/**
 * Badge — compact status pill. Soft tinted background + colored text,
 * matching the app's .badge-* rules (success/warning/danger/brand).
 */
export function Badge({ children, variant = 'neutral', size = 'sm', dot = false, icon, style, ...rest }) {
  const variants = {
    neutral: { background: 'var(--bg-tertiary)',     color: 'var(--color-gray-600)',    border: 'var(--border-base)' },
    brand:   { background: 'var(--bg-brand-soft)',    color: 'var(--color-pink-900)',    border: 'var(--border-brand-subtle)' },
    info:    { background: 'var(--bg-info-soft)',     color: 'var(--text-fg-info)',      border: 'var(--color-brand-200)' },
    success: { background: 'var(--bg-success-soft)',  color: 'var(--text-fg-success)',   border: 'var(--border-success-subtle)' },
    warning: { background: 'var(--bg-warning-soft)',  color: 'var(--text-fg-warning)',   border: 'var(--border-warning-subtle)' },
    danger:  { background: 'var(--bg-danger-soft)',   color: 'var(--text-fg-danger)',    border: 'var(--border-danger-subtle)' },
    solid:   { background: 'var(--bg-brand)',         color: '#ffffff',                  border: 'transparent' },
  };
  const sizes = {
    xs: { fontSize: 11, padding: '2px 8px',  gap: 4 },
    sm: { fontSize: 12, padding: '4px 12px', gap: 5 },
    md: { fontSize: 14, padding: '6px 14px', gap: 6 },
  };
  const vr = variants[variant] || variants.neutral;
  const sz = sizes[size] || sizes.sm;
  return (
    <span
      style={{
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
        ...style,
      }}
      {...rest}
    >
      {dot && (
        <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'currentColor', flexShrink: 0 }} />
      )}
      {icon && <i className={icon} aria-hidden="true" />}
      {children}
    </span>
  );
}
