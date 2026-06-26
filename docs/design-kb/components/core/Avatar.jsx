import React from 'react';

/**
 * Avatar — circular user marker. Falls back to gradient initials (the
 * navbar avatar pattern) when no image is supplied.
 */
export function Avatar({ name = '', src, size = 40, square = false, style, ...rest }) {
  const initials = name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0].toUpperCase())
    .join('');
  return (
    <div
      style={{
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
        ...style,
      }}
      title={name || undefined}
      {...rest}
    >
      {!src && (initials || <i className="fas fa-user" aria-hidden="true" />)}
    </div>
  );
}
