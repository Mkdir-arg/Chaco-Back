import React from 'react';

/**
 * StatCard — KPI tile with a tinted icon square, value and label, plus an
 * optional trend indicator. Mirrors the dashboard stat cards.
 */
export function StatCard({ label, value, icon, iconNode, tone = 'brand', change, changeDir = 'up', footnote, gradientIcon = false, alert = false, style, ...rest }) {
  const tones = {
    brand:   { bg: 'var(--bg-brand-soft)',   fg: 'var(--text-fg-brand)' },
    success: { bg: 'var(--bg-success-soft)', fg: 'var(--text-fg-success)' },
    warning: { bg: 'var(--bg-warning-soft)', fg: 'var(--text-fg-warning)' },
    danger:  { bg: 'var(--bg-danger-soft)',  fg: 'var(--text-fg-danger)' },
    olive:   { bg: 'var(--color-olive-200)', fg: 'var(--color-olive-700)' },
    neutral: { bg: 'var(--bg-tertiary)',     fg: 'var(--color-gray-600)' },
  };
  const t = tones[tone] || tones.brand;
  const trend = {
    up:   { color: 'var(--text-fg-success)', icon: 'fas fa-arrow-up' },
    down: { color: 'var(--text-fg-danger)',  icon: 'fas fa-arrow-down' },
    flat: { color: 'var(--text-body-subtle)', icon: 'fas fa-minus' },
  }[changeDir] || {};

  return (
    <div
      style={{
        background: 'var(--bg-primary)',
        border: '1px solid var(--border-base)',
        borderRadius: 'var(--radius-xl)',
        boxShadow: 'var(--shadow-sm)',
        padding: 20,
        display: 'flex',
        flexDirection: 'column',
        gap: 14,
        ...style,
      }}
      {...rest}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-body-subtle)' }}>{label}</div>
        {(icon || iconNode) && (
          <div style={{
            width: 44, height: 44, flexShrink: 0, borderRadius: 'var(--radius-lg)',
            background: gradientIcon ? 'var(--gradient-brand)' : t.bg, color: gradientIcon ? '#fff' : t.fg,
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18, position: 'relative',
          }}>
            {iconNode || <i className={icon} aria-hidden="true" />}
            {alert && <span style={{ position: 'absolute', top: -2, right: -2, width: 10, height: 10, borderRadius: '50%', background: 'var(--bg-danger)', border: '2px solid var(--bg-primary)' }} />}
          </div>
        )}
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
        <div style={{ fontFamily: 'var(--font-sans)', fontSize: 32, fontWeight: 800, color: 'var(--text-heading)', lineHeight: 1 }}>{value}</div>
        {change != null && (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 13, fontWeight: 600, color: trend.color }}>
            <i className={trend.icon} aria-hidden="true" />{change}
          </span>
        )}
      </div>
      {footnote && <div style={{ fontSize: 12, color: 'var(--text-body-subtle)' }}>{footnote}</div>}
    </div>
  );
}
