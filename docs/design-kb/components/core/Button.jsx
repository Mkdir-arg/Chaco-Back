import React from 'react';

/**
 * Button — the primary interactive control for Chaco / NODO surfaces.
 * Variants map 1:1 to the app's nodo-buttons.css (.btn-brand / .btn-secondary / .btn-tertiary).
 */
export function Button({
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
    xs:   { height: 32, padding: '6px 12px',  fontSize: 12 },
    sm:   { height: 36, padding: '8px 14px',  fontSize: 14 },
    base: { height: 40, padding: '10px 16px', fontSize: 14 },
    lg:   { height: 48, padding: '12px 20px', fontSize: 16 },
    xl:   { height: 52, padding: '14px 24px', fontSize: 16 },
  };

  const variants = {
    brand: {
      background: 'var(--gradient-brand)',
      color: '#ffffff',
      border: '1px solid transparent',
    },
    primary: {
      background: 'var(--bg-brand)',
      color: '#ffffff',
      border: '1px solid transparent',
    },
    secondary: {
      background: 'var(--bg-secondary)',
      color: 'var(--color-gray-600)',
      border: '1px solid var(--border-base)',
    },
    tertiary: {
      background: 'var(--bg-white)',
      color: 'var(--text-fg-brand)',
      border: '1px solid var(--border-brand)',
    },
    ghost: {
      background: 'transparent',
      color: 'var(--text-fg-brand)',
      border: '1px solid transparent',
    },
    danger: {
      background: 'var(--bg-danger)',
      color: '#ffffff',
      border: '1px solid transparent',
    },
  };

  const sz = sizes[size] || sizes.base;
  const vr = variants[variant] || variants.brand;

  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      style={{
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
        ...style,
      }}
      onMouseEnter={(e) => {
        if (disabled) return;
        if (variant === 'tertiary') e.currentTarget.style.background = 'var(--bg-brand-tint)';
        else e.currentTarget.style.filter = 'brightness(0.93)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.filter = 'none';
        if (variant === 'tertiary') e.currentTarget.style.background = 'var(--bg-white)';
      }}
      {...rest}
    >
      {iconNode}
      {icon && <i className={icon} aria-hidden="true" />}
      {children && <span>{children}</span>}
      {iconRight && <i className={iconRight} aria-hidden="true" />}
    </button>
  );
}
