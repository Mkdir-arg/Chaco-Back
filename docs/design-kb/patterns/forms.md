# Pattern: Forms
**Source: CHACO_NODO_Design_Manual.md §12.1, §13.5, §13.6, NODO DS.md §13**

---

## Overview

Forms in NODO follow a strict set of layout and validation rules to ensure consistency and usability across all data entry screens.

---

## Layout Pattern

```
[Section title / heading]

[Card wrapper — rounded-xl, border-base, bg-white]
  [Form section heading — font-semibold]
  
  [Label *]        [Label *]
  [Input]          [Input]         ← Inline row for related fields
  
  [Label *]
  [Input — full width]
  
  [Helper / error text]
  
  [Label *]
  [Select ∨]

[Action row — right-aligned]
  [← Volver (Tertiary)]   [Submit CTA (Brand)]
```

---

## Field Rules

- Label is **always above** the field — never floating or inside
- Required fields: `*` in `text-fg-brand` next to label text
- Placeholder: only for hint text, never as label replacement
- Gap between fields: **20px**
- Gap between form sections: **32px**

---

## Inline Fields

Related fields appear on the same row:
- Example: DNI + Sex (type/select) — 50/50 split width

---

## Validation Rules

- **Inline validation** — error appears below the field that failed
- **Error style:** `border-danger`, `bg-danger-soft` on field + `text-fg-danger` + exclamation icon below
- **Error message format:** Specific and actionable ("El email no es válido") — never generic ("Error")
- **Required indicator before submission** — marked upfront, not revealed after failure
- **Library:**
  - New templates: HTML5 native validation
  - Legacy templates: `jquery-validate 1.19.5`

---

## Action Row

- Positioned at the **bottom** of the form card
- Right-aligned
- Structure: `[← Volver (Tertiary)]` space `[Primary CTA (Brand)]`
- Tertiary button for going back/canceling
- Brand button for the primary submit action

---

## Multi-Step Forms

Observed in: New Citizen flow (Step 1: DNI query → Step 2: Confirm data)

- Breadcrumb/step indicator at top of page — see `components/breadcrumb.yaml`
- Step 1 (Nuevo Ciudadano):
  - Card: icon + title + subtitle ("Consulta automática con RENAPER")
  - Fields: DNI + Sex (inline row)
  - Actions: `← Volver` (Tertiary) + `Consulta Renaper` (Brand)
  
- Step 2 (Confirmar Datos):
  - Two-column layout (35% RENAPER data / 65% editable form)
  - Left: read-only RENAPER card (see `components/card-renaper.yaml`)
  - Right: editable form with sections (Datos del Ciudadano, Contacto, Domicilio)
  - Actions: `← Volver` (Tertiary) + `⊕ Crear Ciudadano` (Brand)

---

## RENAPER Integration Pattern

Pre-filled data from RENAPER must be visually distinguished:
- Read-only style: `bg-white` with helper text explaining the lock
- Helper text: brief note in `text-xs`, `text-body-subtle` about RENAPER source
- Editable fields: normal input styling
- The user should never confuse locked data for editable data

---

## Form Width

- **Max width: ~700px**
- **Centered** within the content area
- Not full-width — forms that stretch 100% are a design violation

---

## Empty / Pre-filled States

- New entity: all fields empty with placeholder hints
- Edit entity: pre-filled with current values, editable
- RENAPER query result: some fields pre-filled (read-only), user completes the rest
