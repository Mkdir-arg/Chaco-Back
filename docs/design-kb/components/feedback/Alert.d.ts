import * as React from 'react';

export interface AlertProps {
  children?: React.ReactNode;
  variant?: 'info' | 'success' | 'warning' | 'danger';
  /** Bold title line above the body */
  title?: React.ReactNode;
  /** Override the default Font Awesome icon */
  icon?: string;
  /** When provided, shows a dismiss button */
  onClose?: () => void;
  style?: React.CSSProperties;
}

/**
 * Inline message banner — soft tinted background, leading icon, optional
 * title and dismiss. The portal/backoffice notification style.
 *
 * @startingPoint section="Feedback" subtitle="Inline message banners" viewport="700x260"
 */
export function Alert(props: AlertProps): JSX.Element;
