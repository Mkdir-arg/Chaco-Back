# Pattern: Error States & Feedback
**Source: NODO DS.md (general rules), CHACO_NODO_Design_Manual.md**

---

## Overview

Errors in NODO are handled at three layers: inline field validation, toast notifications, and confirmation modals for destructive actions. Each layer has a specific role and must not be substituted.

---

## Layer 1: Inline Field Validation

**When:** Form field has invalid input
**Where:** Immediately below the problematic field

```
[Label]
[Input field — border-danger, bg-danger-soft]
⚠ El email no es válido                          ← text-fg-danger, text-xs, with icon
```

**Rules:**
- Error text is specific: "El email no es válido" not "Error"
- Error icon: `ExclamationCircleIcon` or `fa-circle-exclamation` preceding the message
- Border: `border-danger (#c70036) 1px`
- Background: `bg-danger-soft (#fef0f2)`
- Text: `text-fg-danger (#c70036)`, `text-xs`
- Validation on blur (not on submit for known errors)
- Never use `color: red` or non-tokenized values

---

## Layer 2: Toast Notifications (Toastr)

**When:** Async operations complete (save, delete, network error)
**Position:** Top-right corner, overlaying the interface

| Type | Token | Example |
|------|-------|---------|
| Success | `bg-success` | "Ciudadano creado exitosamente" |
| Error | `bg-danger` | "Error al guardar. Intenta nuevamente." |
| Warning | `bg-warning` | "No se pudo sincronizar con RENAPER" |
| Info | `bg-brand` | "Cambios guardados automáticamente" |

**Rules:**
- Auto-dismiss after a few seconds
- Error toasts should persist until dismissed (never auto-dismiss errors silently)
- Never show IDs, stack traces, or technical details to the user
- Message format: clear, action-oriented, in Spanish

---

## Layer 3: Destructive Action Confirmation (SweetAlert2)

**When:** User triggers a delete, hard reset, or any irreversible action

```
┌────────────────────────────────────┐
│  ¿Estás seguro?                    │
│  Esta acción no se puede deshacer. │
│                                    │
│     [Cancelar]    [Eliminar]       │
│     (Secondary)   (Danger/Brand)   │
└────────────────────────────────────┘
```

**Rules:**
- **Always** use SweetAlert2 — never `window.confirm()`
- **Always** use for: delete, deactivate, archive, bulk operations
- Secondary button: "Cancelar" — cancels the action
- Primary confirm button: "Eliminar" or action-specific label — proceeds
- The confirm button style for destructive actions: Danger-styled (bg-danger or equivalent) NOT Brand button
- Dialog title is always a question format

---

## Layer 4: System-Level Errors (Future)

For network errors, server errors, or unavailable features:
- Empty state with error illustration
- Clear message: "No se pudo cargar la información. Intenta más tarde."
- Retry CTA if applicable
- Never show technical HTTP status codes or stack traces

---

## What Never to Do

- Show `window.confirm()` for destructive actions
- Show error messages only through color change
- Use generic "Error" as the full error message
- Show technical IDs or stack traces in user-facing messages
- Allow destructive actions to proceed without confirmation
- Auto-dismiss error toast notifications
