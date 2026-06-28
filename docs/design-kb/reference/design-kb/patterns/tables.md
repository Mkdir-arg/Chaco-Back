# Pattern: Tables (List Views)
**Source: CHACO_NODO_Design_Manual.md §12.4, §12.7, §13.4, NODO DS.md §9**

---

## Overview

List views follow a consistent pattern: **stat cards → search → filters → table**.
This pattern appears for all entity list screens (Citizens, Organizations, Programs, etc.).

---

## Screen Layout (Ciudadanos en Tratamiento example)

```
[Heading] [Subtitle]                    [⊕ Nuevo legajo (Brand →)]

[Stat Card] [Stat Card] [Stat Card] [Stat Card] [Stat Card] [Stat Card]

[🔍 Search input — full width]

[Filter ∨] [Filter ∨] [Toggle] [Toggle]          [↓ Exportar (Tertiary)]

┌─────────────────────────────────────────────────────────────────────┐
│ CIUDADANO │ DNI │ DISPOSITIVO │ RESPONSABLE │ RIESGO │ ESTADO │ ⓘ  │
├───────────┼─────┼─────────────┼─────────────┼────────┼────────┼────┤
│ [avatar]  │     │             │             │ badge  │ badge  │ 👁  │
│ Nombre    │     │             │             │        │        │     │
└─────────────────────────────────────────────────────────────────────┘
│ Mostrando 1-10 of 247              [‹] [1 de 25] [›]               │
```

---

## Section Rules

### Heading Row
- Left: Section H1 + subtitle (smaller, `text-body-subtle`)
- Right: Primary CTA Brand button (e.g., "⊕ Nuevo legajo")
- **CTA always right-aligned** — never centered, never left

### Stat Cards
- 4–6 cards depending on the entity
- Above the search/filter row
- Provide aggregate context before the user interacts with the table

### Search Bar
- Full-width input
- MagnifyingGlassIcon prefix
- Placeholder: descriptive with minimum character hint (e.g., "Buscar por nombre, DNI...")
- Style: Secondary input (bg-secondary-soft, border-base)

### Filter Row
- Horizontal row of filter controls
- Chip/button style (bg-white, border-base, rounded-md)
- Active filter: `border-brand`, `text-fg-brand`
- Export button: right-aligned, Tertiary style + download icon
- Filter examples: "Todos los riesgos ∨", "Todos los estados ∨", "🔔 Con alertas", "📅 Sin plan vigente"

### Data Table
- See: `components/data-table.yaml`
- No alternating row colors
- Hover: `bg-tertiary`
- Status column: badge variants (success/warning/danger)
- Actions column: always last, fixed width

### Pagination
- "Mostrando X-Y of Z" left
- [‹] [Page indicator] [›] — Tertiary buttons, centered or right

---

## Empty State

Every table must have an empty state:
- Illustration (w-12 h-12 or larger, `text-fg-brand` or neutral)
- Message: contextual ("No hay ciudadanos registrados" not "No results")
- Optional CTA: if the user can create a new record, show the Brand button

---

## Loading State

- Skeleton rows while data loads
- Maintains table structure (header visible, rows as skeletons)
- No spinner in place of the entire table

---

## Responsive

- Table scrolls horizontally on small screens (UNKNOWN — dedicated mobile-tables.css exists)
- Stat cards grid collapses (UNKNOWN — exact breakpoint not documented)
