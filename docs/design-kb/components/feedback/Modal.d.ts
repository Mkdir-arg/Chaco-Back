import * as React from 'react';

export interface ModalProps {
  /** Controls visibility (default true) */
  open?: boolean;
  title?: React.ReactNode;
  /** Override the tone's default Font Awesome icon */
  icon?: string;
  /** Header icon tone */
  tone?: 'info' | 'success' | 'warning' | 'danger' | 'brand';
  children?: React.ReactNode;
  /** Footer slot — typically a pair of Buttons */
  footer?: React.ReactNode;
  /** Called on backdrop click / close button */
  onClose?: () => void;
  /** Max width in px */
  width?: number;
  style?: React.CSSProperties;
}

/**
 * Centered dialog over a dimmed, blurred backdrop. Header with tinted icon,
 * body, and an action footer — the app's ModernModal pattern.
 */
export function Modal(props: ModalProps): JSX.Element | null;
