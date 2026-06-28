import * as React from 'react';

export interface TabItem {
  value: string;
  label: string;
  /** Font Awesome icon class */
  icon?: string;
  /** Optional count chip */
  count?: number;
}

export interface TabsProps {
  /** Tabs as strings or {value,label,icon,count} objects */
  tabs: (string | TabItem)[];
  /** Controlled active value */
  value?: string;
  /** Uncontrolled initial value */
  defaultValue?: string;
  onChange?: (value: string) => void;
  style?: React.CSSProperties;
}

/**
 * Horizontal tab bar with an underline indicator on the active item.
 * Works controlled or uncontrolled; supports per-tab icons and count chips.
 *
 * @startingPoint section="Navigation" subtitle="Underline tab bar" viewport="700x120"
 */
export function Tabs(props: TabsProps): JSX.Element;
