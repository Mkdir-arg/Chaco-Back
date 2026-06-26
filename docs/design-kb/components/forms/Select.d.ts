import * as React from 'react';

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectProps {
  label?: React.ReactNode;
  value?: string;
  defaultValue?: string;
  /** Options as strings or {value,label} objects */
  options?: (string | SelectOption)[];
  /** Disabled first option shown when empty */
  placeholder?: string;
  error?: React.ReactNode;
  helper?: React.ReactNode;
  required?: boolean;
  disabled?: boolean;
  onChange?: (e: React.ChangeEvent<HTMLSelectElement>) => void;
  id?: string;
  style?: React.CSSProperties;
}

/**
 * Native dropdown styled to match Input — label, brand focus ring, custom chevron.
 */
export function Select(props: SelectProps): JSX.Element;
