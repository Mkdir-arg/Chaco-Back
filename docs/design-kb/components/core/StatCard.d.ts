import * as React from 'react';

export interface StatCardProps {
  /** Metric label, e.g. "Legajos activos" */
  label: React.ReactNode;
  /** The big number / value */
  value: React.ReactNode;
  /** Font Awesome icon class for the tinted square */
  icon?: string;
  /** Icon-square tone */
  tone?: 'brand' | 'success' | 'warning' | 'danger' | 'olive' | 'neutral';
  /** Trend value text, e.g. "12%" */
  change?: React.ReactNode;
  /** Trend direction (sets color + arrow) */
  changeDir?: 'up' | 'down' | 'flat';
  /** Small caption under the value */
  footnote?: React.ReactNode;
  style?: React.CSSProperties;
}

/**
 * KPI tile: tinted icon square, large value, label and optional trend.
 * The dashboard stat-card pattern.
 *
 * @startingPoint section="Core" subtitle="Dashboard KPI tile with trend" viewport="700x180"
 */
export function StatCard(props: StatCardProps): JSX.Element;
