import * as React from 'react';

export interface BadgeProps {
  children?: React.ReactNode;
  /** Tone of the pill */
  variant?: 'neutral' | 'brand' | 'info' | 'success' | 'warning' | 'danger' | 'solid';
  size?: 'xs' | 'sm' | 'md';
  /** Show a leading status dot in the current color */
  dot?: boolean;
  /** Font Awesome icon class */
  icon?: string;
  style?: React.CSSProperties;
}

/**
 * Compact status pill — soft tinted background with a colored label.
 * Use for record states (Activo, Pendiente), counts and labels.
 *
 * @startingPoint section="Core" subtitle="Status pills in every tone" viewport="700x140"
 */
export function Badge(props: BadgeProps): JSX.Element;
