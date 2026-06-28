# NODO UX Principles
**Gobierno del Chaco — Sistema Integral**

---

## Navigation Philosophy

NODO uses **hierarchical, sidebar-anchored navigation** designed for power users who manage complex case data daily.

- **Sidebar is always present** in authenticated screens — never hidden by default on desktop
- **Active state is unambiguous** — a branded pill indicator (bg-brand, white text) marks exactly one active item at all times
- **Expandable groups** use chevrons (∨/∧) and show/hide subitems in-place — no page reload, no separate navigation level
- **Subitems inherit the active pill** when selected — the group parent shows active styling when any of its children is active
- **Logo always navigates to home** — never triggers modal or dropdown
- **Collapse is available** but desktop is assumed to be expanded by default

---

## Information Architecture Patterns

The system is organized around **entities** (Ciudadanos, Comedores, Centros de Familia, Instituciones) with consistent IA across each entity type:

1. **List view** — searchable, filterable table with stat cards above
2. **Detail view** — profile header + tabbed or vertically-stacked data panels
3. **Create flow** — multi-step form with RENAPER integration for citizen creation
4. **Edit flow** — pre-filled form distinguishing read-only (RENAPER) from editable fields

Key IA rules:
- Stat cards always appear above the data table — they provide context before detail
- Search and filters always appear between stat cards and the table — progressive refinement
- CTA buttons align to the RIGHT of section headings — never center or left
- Breadcrumbs/steppers appear at the top of multi-step flows

---

## Progressive Disclosure Rules

The system reveals complexity gradually:

1. **Dashboard → List → Detail** — The home screen is an overview. Clicking drills into specifics.
2. **Expandable nav groups** — Submenus are hidden until explicitly opened
3. **Filters default to "All"** — Users see everything first, filter down by intent
4. **Alert panels are opt-in** — Critical alerts appear prominently only when they exist; the panel is absent when there are none
5. **RENAPER data is pre-filled, not asked** — The new citizen flow queries RENAPER automatically to minimize data entry
6. **Confirmation gates for destructive actions** — Complexity (and risk) is revealed only when needed (SweetAlert2 dialog)

---

## Error Handling Philosophy

- **Errors are specific and actionable** — "El email no es válido" not "Error en el formulario"
- **Errors appear inline** — below the field that caused the issue, in `text-fg-danger` with an exclamation icon
- **Required fields are marked upfront** — `*` in `text-fg-danger` before submission, not after failed validation
- **Error state styling is distinct** — border changes to `border-danger`, background to `bg-danger-soft`
- **Success feedback confirms** — Toast notifications (Toastr) confirm successful saves
- **System status is visible** — System health indicators on the dashboard surface problems proactively

---

## Onboarding Philosophy

NODO has no guided onboarding flow currently documented. The system assumes trained government employees. Key assumptions built into the design:

- Users know what RENAPER is and why DNI/Sex is needed for citizen creation
- Users understand the entity hierarchy (Legajos → Ciudadanos → Programs)
- The wavy decoration and illustration on the login screen provide the only "first impression" moment
- Role information in the sidebar user card orients users within the permission model

---

## Decision-Making Philosophy

The design makes decisions on the user's behalf to reduce cognitive load:

| Decision | System's Choice | Rationale |
|----------|-----------------|-----------|
| Required vs optional fields | Required marked with `*` | Users must complete required fields first |
| Which action is primary | Single Brand button per section | Prevents decision paralysis |
| How to show states | Semantic token badges | Users read state from color/label consistently |
| How to confirm destructive actions | SweetAlert2 modal with two buttons | Forces conscious confirmation |
| How to show empty vs loaded | Skeleton + empty state pattern | Distinguishes "loading" from "truly empty" |
| How to handle RENAPER data | Read-only styled fields with helper text | Protects data integrity, explains why fields are locked |

---

## Form UX Rules

- Label always above the field — never use placeholder as label
- Required indicator: `*` in `text-fg-danger` next to the label
- Gap between fields: 20px
- Gap between form sections: 32px
- Related fields appear on the same row (e.g., DNI + Sex)
- Primary CTA: Brand button, right-aligned at the bottom of the form
- Secondary CTA: Tertiary button (← Volver), left of primary button
- Validation: inline, below the field, on blur (not on submit for known errors)

---

## Data Visualization UX

- Charts always have a title and legend
- Time selectors (7D/30D/90D) allow temporal context switching
- Donut charts include a legend with category labels
- Bar charts handle empty months gracefully (no bar, not an error)
- Geographic distribution section is reserved even when map is pending
- Categorical colors for data viz: bg-purple, bg-sky, bg-teal, bg-pink, bg-cyan, bg-fuchsia, bg-indigo, bg-orange
