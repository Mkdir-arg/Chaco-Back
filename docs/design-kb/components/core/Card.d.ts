import * as React from 'react';

export interface CardProps {
  children?: React.ReactNode;
  /** Optional header title */
  title?: React.ReactNode;
  /** Smaller text under the title */
  subtitle?: React.ReactNode;
  /** Node pinned to the right of the header (e.g. a Button or Badge) */
  headerRight?: React.ReactNode;
  /** Footer slot, rendered on a tinted bar */
  footer?: React.ReactNode;
  /** Body padding in px */
  padding?: number;
  /** Lift + deepen shadow on hover */
  hover?: boolean;
  /** Color for a 3px top accent stripe (e.g. var(--bg-brand)) */
  accent?: string;
  style?: React.CSSProperties;
}

/**
 * The base white surface for both products: 12px radius, hairline border,
 * soft shadow. Composes optional header/footer slots.
 *
 * @startingPoint section="Core" subtitle="Surface card with header & footer" viewport="700x260"
 */
export function Card(props: CardProps): JSX.Element;
