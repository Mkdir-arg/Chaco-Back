# Pattern: Dashboard (Home Screen)
**Source: CHACO_NODO_Design_Manual.md §13.3**

---

## Overview

The home screen is an information-dense dashboard that provides situational awareness at a glance. It follows a strict vertical section order and uses the sidebar + single content area layout.

---

## Layout

```
[TOPBAR — fixed]
[SIDEBAR — fixed left, ~300px]
[CONTENT AREA — scrollable]
  Section 1: Personalized greeting
  Section 2: Banner (reserved)
  Section 3: Critical Alerts (conditional)
  Section 4: Stat Cards grid (4 metrics)
  Section 5: Monthly Trends chart
  Section 6: Case Status chart (donut)
  Section 7: Geographic Distribution (reserved)
  Section 8: Real-Time Activity feed
  Section 9: Quick Access shortcuts
  Section 10: System Status indicators
```

---

## Section Specifications

### Section 1: Greeting
- Personalized salutation + current date
- "Sistema activo" badge: circle dot in `bg-success` (pulsing) + text, badge-success variant
- No CTA

### Section 2: Banner
- Reserved area for announcements and communications
- Empty by default until content is published

### Section 3: Critical Alerts Panel
- **Conditional** — rendered ONLY when alerts exist
- See: `components/alert-panel.yaml`

### Section 4: Stat Cards Grid
- 4 cards in a horizontal row
- See: `components/stat-card.yaml`
- Metrics: Total Ciudadanos, Legajos Activos, Alertas Críticas, Seguimientos
- Cards may have alert dot when category has active critical items

### Section 5: Monthly Trends Chart
- Line chart (Chart.js or ApexCharts)
- Time selector: 7D / 30D / 90D
- Colors: categorical token palette

### Section 6: Case Status Chart
- Donut chart with legend
- Segment colors: categorical token palette

### Section 7: Geographic Distribution
- Map visualization — area reserved
- Shows when map integration is available

### Section 8: Real-Time Activity Feed
- Header badge: "● En vivo" — pulsing green dot (`bg-success`) + text
- Vertical list of recent events
- Each item: circular icon + event name + actor + relative timestamp
- Separator: `border-base` between items

### Section 9: Quick Access Shortcuts
- 4 icon shortcuts in a horizontal row
- Examples: Gestionar Ciudadanos / Nuevo Registro / Reportes / Configuración
- Icon: Heroicons, brand colored, larger size (w-8 h-8)
- Label below icon: `text-xs`, `font-medium`, `text-body`

### Section 10: System Status
- 4 indicators with:
  - Icon/illustration
  - Progress bar: background `bg-quaternary`, fill with brand gradient
  - Percentage text: `text-xs`, `text-body-subtle`
- Examples: Servidor, Seguridad, etc.

---

## Rules

- Section order must not be changed
- Critical alerts section appears ONLY when alerts exist
- Charts must have time selectors when showing temporal data
- Geographic section is reserved — placeholder renders when map is unavailable
- Real-time feed must handle the "no recent activity" empty state
