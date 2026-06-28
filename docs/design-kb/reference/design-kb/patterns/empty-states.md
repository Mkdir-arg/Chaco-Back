# Pattern: Empty States
**Source: NODO DS.md (pending documentation), CHACO_NODO_Design_Manual.md**

---

## Overview

Empty states communicate the absence of data with context and (when applicable) a path forward. A blank space is never an acceptable empty state.

---

## When Empty States Are Required

- Every data table with zero results
- Every list view with no records
- Real-time activity feed with no recent events
- Search with no matching results
- Notification panel with no notifications

---

## Structure

```
┌────────────────────────────┐
│                            │
│    [Illustration]          │
│    w-12 h-12 or larger     │
│                            │
│    [Primary message]       │   ← text-heading, font-semibold, text-center
│    No hay X registrados    │
│                            │
│    [Secondary message]     │   ← text-body, text-sm, text-center (optional)
│    Crea el primero para    │
│    empezar.                │
│                            │
│    [CTA (optional)]        │   ← Brand button if user can create
│    ⊕ Nuevo X               │
│                            │
└────────────────────────────┘
```

---

## Specifications

| Element | Value |
|---------|-------|
| Illustration | Heroicons w-12 h-12, `text-fg-brand` or `text-body-subtle` |
| Illustration alternative | Full illustrated SVG (larger, for prominent empty states) |
| Primary message font | `text-base` or `text-lg`, `font-semibold`, `text-heading` |
| Secondary message font | `text-sm`, `text-body` |
| CTA | Brand button, only when creation is possible |
| Container | centered vertically and horizontally within the table/list area |

---

## Specific Cases

### Search empty state
- Message: "Sin resultados para '[query]'"
- No CTA (can't create from search)
- Secondary: "Intenta con otros términos"

### Filter empty state
- Message: "No hay [entity] con estos filtros"
- CTA: "Limpiar filtros" (Tertiary button, not Brand)

### New entity (no records yet)
- Message: "No hay [entity] registrados"
- CTA: "⊕ Nuevo [entity]" — Brand button

### Observations panel (citizen detail)
- Shows illustration when no observations exist
- No CTA unless user can add observations

---

## Rules

- **Never** show a blank white area where content should be
- **Never** show generic "No results" — always contextualize
- **Never** show a CTA that the user doesn't have permission to use
- Empty state illustrations use system icon colors (`text-fg-brand` or `text-body-subtle`)
- Empty states should maintain the table/list structure (header visible, body replaced)
