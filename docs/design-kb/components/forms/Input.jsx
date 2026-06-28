import React from 'react';

/**
 * Input — labelled text field with optional leading icon, helper / error text.
 * Focus ring uses the brand color; error switches border + ring to rose.
 */
export function Input({
  label, value, defaultValue, placeholder, type = 'text', icon, iconNode, error, helper,
  required = false, disabled = false, onChange, id, style, ...rest
}) {
  const [focused, setFocused] = React.useState(false);
  const fieldId = id || (label ? `inp-${String(label).replace(/\s+/g, '-').toLowerCase()}` : undefined);
  const borderColor = error ? 'var(--border-danger)' : focused ? 'var(--border-brand)' : 'var(--border-base)';
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, ...style }}>
      {label && (
        <label htmlFor={fieldId} style={{ fontFamily: 'var(--font-sans)', fontSize: 13, fontWeight: 600, color: 'var(--text-heading)' }}>
          {label}{required && <span style={{ color: 'var(--text-fg-danger)', marginLeft: 3 }}>*</span>}
        </label>
      )}
      <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
        {icon && (
          <i className={icon} aria-hidden="true" style={{ position: 'absolute', left: 14, color: 'var(--text-body-subtle)', fontSize: 14, pointerEvents: 'none' }} />
        )}
        {iconNode && (
          <span aria-hidden="true" style={{ position: 'absolute', left: 12, color: 'var(--text-body-subtle)', display: 'inline-flex', pointerEvents: 'none' }}>{iconNode}</span>
        )}
        <input
          id={fieldId}
          type={type}
          value={value}
          defaultValue={defaultValue}
          placeholder={placeholder}
          required={required}
          disabled={disabled}
          onChange={onChange}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          style={{
            width: '100%',
            height: 42,
            padding: (icon || iconNode) ? '0 14px 0 40px' : '0 14px',
            fontFamily: 'var(--font-sans)',
            fontSize: 14,
            color: 'var(--text-heading)',
            background: disabled ? 'var(--bg-disabled)' : 'var(--bg-white)',
            border: `1px solid ${borderColor}`,
            borderRadius: 'var(--radius-lg)',
            outline: 'none',
            boxShadow: focused ? (error ? 'var(--ring-danger)' : 'var(--ring-brand)') : 'none',
            transition: 'border-color var(--duration-fast) var(--ease-standard), box-shadow var(--duration-fast) var(--ease-standard)',
          }}
          {...rest}
        />
      </div>
      {(error || helper) && (
        <div style={{ fontSize: 12, color: error ? 'var(--text-fg-danger)' : 'var(--text-body-subtle)' }}>
          {error || helper}
        </div>
      )}
    </div>
  );
}
