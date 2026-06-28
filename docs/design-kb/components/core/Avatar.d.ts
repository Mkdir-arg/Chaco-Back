import * as React from 'react';

export interface AvatarProps {
  /** Full name — used for initials and tooltip */
  name?: string;
  /** Optional image URL; when set, replaces the gradient initials */
  src?: string;
  /** Diameter in px */
  size?: number;
  /** Rounded square instead of circle */
  square?: boolean;
  style?: React.CSSProperties;
}

/**
 * Circular user marker. With no image it renders gradient initials —
 * the navbar/user-menu avatar pattern.
 */
export function Avatar(props: AvatarProps): JSX.Element;
