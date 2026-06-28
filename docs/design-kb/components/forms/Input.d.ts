import * as React from 'react';

export interface InputProps {
  /** Field label */
  label?: React.ReactNode;
  value?: string;
  defaultValue?: string;
  placeholder?: string;
  /** HTML input type */
  type?: string;
  /** Font Awesome icon class rendered inside the field */
  icon?: string;
  /** Error message — turns border/ring rose */
  error?: React.ReactNode;
  /** Helper text under the field */
  helper?: React.ReactNode;
  required?: boolean;
  disabled?: boolean;
  onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
  id?: string;
  style?: React.CSSProperties;
}

/**
 * Labelled text field with optional icon, helper and error states.
 * Brand focus ring; rose border + ring on error.
 *
 * @startingPoint section="Forms" subtitle="Text field with label, icon & error" viewport="460x320"
 */
export function Input(props: InputProps): JSX.Element;
