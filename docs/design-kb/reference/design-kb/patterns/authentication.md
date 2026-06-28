# Pattern: Authentication
**Source: CHACO_NODO_Design_Manual.md §13.1, §13.2**

---

## Overview

Authentication screens (login, password recovery) use the **split-screen pattern** — the only place in the system where this layout is permitted.

---

## Login Screen

**Layout:** Split screen
- **Left (60%):** Decorative illustration area
  - Background: wavy line texture in Jacaranda blue at low opacity
  - Flat illustration: people working with development blocks (pink/magenta accents, black silhouettes)
- **Right (40%):** Authentication form

**Form content (top to bottom):**
1. Heading: "Bienvenido a Nodo, tu Sistema Integral" — Gellat Extra Bold, `text-heading (#00203A)`
2. Subheading: "Inicia Sesion" — Manrope, smaller size
3. Email field: input with EnvelopeIcon prefix, label "Email institucional"
4. Password field: input with LockClosedIcon prefix, label "Contraseña"
5. "¿Olvidaste tu contraseña?" link — `text-fg-brand`, `text-sm`
6. "Recordarme" checkbox
7. Primary CTA: Brand button — "Create account" (or localized equivalent) → arrow right
8. "¿No estas registrado? Crear cuenta" — `text-body` with `text-fg-brand` link
9. NODO logo + "Powered by ICom" text below

---

## Password Recovery Screen

**Layout:** Centered on screen (not split-screen), with wavy texture on both sides

**Content (top to bottom):**
1. Heading: "Restablecer Contraseña" — Gellat Extra Bold, `text-heading`
2. Email field: input with icon prefix
3. reCAPTCHA widget (embedded)
4. Instructional helper text: `text-body`, `text-sm`
5. Primary CTA: Brand button — "Reestablecer contraseña"
6. NODO logo below

---

## Rules

- The split-screen layout is **exclusively for authentication screens**
- Never apply split-screen layout to authenticated/internal screens
- The Gellat font is **only for hero headings** on these screens
- The NODO logo always appears on authentication screens
- Password field must have toggle visibility option (UNKNOWN — not confirmed in specs)

---

## States

- **Default:** Empty form, placeholder text visible
- **Validation error:** Inline error below field, `border-danger`, `bg-danger-soft`
- **Success:** Redirect to home or confirmation message
- **CAPTCHA:** Embedded reCAPTCHA on recovery screen

---

## Accessibility

- Form fields have visible labels (not just placeholders)
- Required fields marked with `*` in `text-fg-danger`
- Focus states visible on all inputs
- CTA button announces action clearly
