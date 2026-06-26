import * as React from 'react';

export interface ButtonProps {
  /** Button label / contents */
  children?: React.ReactNode;
  /**
   * Visual style.
   * - `brand`: signature magenta→purple gradient (primary CTA)
   * - `primary`: solid jacaranda purple
   * - `secondary`: neutral gray, bordered
   * - `tertiary`: white with brand (jacaranda) outline
   * - `ghost`: transparent, brand text
   * - `danger`: solid rose for destructive actions
   */
  variant?: 'brand' | 'primary' | 'secondary' | 'tertiary' | 'ghost' | 'danger';
  /** Control height: xs 32 · sm 36 · base 40 · lg 48 · xl 52 (px) */
  size?: 'xs' | 'sm' | 'base' | 'lg' | 'xl';
  /** Font Awesome class for a leading icon, e.g. "fas fa-plus" */
  icon?: string;
  /** Font Awesome class for a trailing icon */
  iconRight?: string;
  /** Stretch to full container width */
  block?: boolean;
  disabled?: boolean;
  type?: 'button' | 'submit' | 'reset';
  onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void;
  style?: React.CSSProperties;
}

/**
 * Primary interactive control for Chaco / NODO. Brand variant carries the
 * signature gradient; use it once per view for the main action.
 *
 * @startingPoint section="Core" subtitle="Buttons in every variant & size" viewport="700x180"
 */
export function Button(props: ButtonProps): JSX.Element;
