import React from 'react';

/**
 * Tabs — horizontal tab bar with an underline indicator on the active item.
 * Controlled (value/onChange) or uncontrolled (defaultValue).
 */
export function Tabs({ tabs = [], value, defaultValue, onChange, style }) {
  const norm = tabs.map((t) => (typeof t === 'string' ? { value: t, label: t } : t));
  const [internal, setInternal] = React.useState(defaultValue ?? norm[0]?.value);
  const active = value ?? internal;
  const select = (v) => { if (value === undefined) setInternal(v); onChange && onChange(v); };
  return (
    <div style={{ display: 'flex', gap: 4, borderBottom: '1px solid var(--border-base)', fontFamily: 'var(--font-sans)', ...style }}>
      {norm.map((t) => {
        const on = t.value === active;
        return (
          <button
            key={t.value}
            onClick={() => select(t.value)}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 8,
              padding: '12px 16px',
              background: 'none', border: 'none', cursor: 'pointer',
              fontSize: 14, fontWeight: on ? 700 : 500,
              color: on ? 'var(--text-fg-brand)' : 'var(--text-body-subtle)',
              borderBottom: `2px solid ${on ? 'var(--bg-brand)' : 'transparent'}`,
              marginBottom: -1,
              transition: 'color var(--duration-fast) var(--ease-standard)',
              whiteSpace: 'nowrap',
            }}
          >
            {t.iconNode}
            {t.icon && <i className={t.icon} aria-hidden="true" />}
            {t.label}
            {t.count != null && (
              <span style={{
                fontSize: 11, fontWeight: 700, padding: '1px 7px', borderRadius: 'var(--radius-full)',
                background: on ? 'var(--bg-brand-soft)' : 'var(--bg-tertiary)',
                color: on ? 'var(--text-fg-brand)' : 'var(--text-body-subtle)',
              }}>{t.count}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}
