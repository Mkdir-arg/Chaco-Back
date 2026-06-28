import React from 'react';

/**
 * Select — labelled native dropdown styled to match Input.
 */
export function Select({ label, value, defaultValue, options = [], placeholder, error, helper, required = false, disabled = false, onChange, id, style, ...rest }) {
  const [focused, setFocused] = React.useState(false);
  const fieldId = id || (label ? `sel-${String(label).replace(/\s+/g, '-').toLowerCase()}` : undefined);
  const borderColor = error ? 'var(--border-danger)' : focused ? 'var(--border-brand)' : 'var(--border-base)';
  const norm = options.map((o) => (typeof o === 'string' ? { value: o, label: o } : o));
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, ...style }}>
      {label && (
        <label htmlFor={fieldId} style={{ fontFamily: 'var(--font-sans)', fontSize: 13, fontWeight: 600, color: 'var(--text-heading)' }}>
          {label}{required && <span style={{ color: 'var(--text-fg-danger)', marginLeft: 3 }}>*</span>}
        </label>
      )}
      <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
        <select
          id={fieldId}
          value={value}
          defaultValue={defaultValue}
          required={required}
          disabled={disabled}
          onChange={onChange}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          style={{
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
            transition: 'border-color var(--duration-fast) var(--ease-standard), box-shadow var(--duration-fast) var(--ease-standard)',
          }}
          {...rest}
        >
          {placeholder && <option value="" disabled>{placeholder}</option>}
          {norm.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <i className="fas fa-chevron-down" aria-hidden="true" style={{ position: 'absolute', right: 14, color: 'var(--text-body-subtle)', fontSize: 12, pointerEvents: 'none' }} />
      </div>
      {(error || helper) && (
        <div style={{ fontSize: 12, color: error ? 'var(--text-fg-danger)' : 'var(--text-body-subtle)' }}>{error || helper}</div>
      )}
    </div>
  );
}
