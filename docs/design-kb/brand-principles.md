# NODO Brand Principles
**Gobierno del Chaco — Sistema Integral**

---

## Visual Personality

NODO presents as a **modern, trustworthy, and energetic government platform**. The visual identity balances institutional seriousness with the accessibility and approachability of modern SaaS products.

The brand communicates capability and care simultaneously: capable enough for complex social management work, approachable enough for daily use by social workers and public servants.

**Core visual character:**
- Bold, gradient-driven brand colors (Jacaranda purple → Rosa pink at 45°) signal modernity and forward motion
- Clean neutral surfaces (white, gray-50, gray-100) provide breathing room and professional calm
- Flat illustration style with bright magenta accents creates warmth without whimsy
- Wavy line textures on access screens evoke fluidity and openness

---

## Emotional Goals

The system aims to evoke:

1. **Confidence** — The platform handles sensitive citizen data; users must trust it implicitly
2. **Clarity** — Complex social case data must be scannable and digestible at a glance
3. **Efficiency** — Every second a social worker spends navigating the UI is a second not spent helping citizens
4. **Pride** — Public servants should feel they are using a professional-grade tool

---

## Trust Signals

| Signal | Implementation |
|--------|---------------|
| Institutional identity | Government logo visible in sidebar and all access screens |
| Data accuracy | RENAPER integration with clearly labeled read-only vs. editable fields |
| System status | Always-visible system health indicators on the dashboard |
| Role clarity | User name, role, and group always shown in sidebar user card |
| Destructive action gates | SweetAlert2 confirmation for all delete/destructive actions |
| Accessible states | Every interactive element has visible focus, hover, and disabled states |
| Error clarity | Error messages are descriptive ("El email no es válido"), never generic |

---

## Hierarchy Philosophy

Visual hierarchy in NODO is intentional and strict:

1. **One primary action per screen** — A single Brand button is the CTA. Never two Brand buttons in the same section.
2. **Content before chrome** — The content area dominates; sidebar and topbar are recessive
3. **Data over decoration** — Charts, tables, and metrics are the heroes of the interface
4. **State before style** — Every component's visual appearance communicates its interactive state
5. **Heading → Body → Subtle** — Three text levels establish hierarchy; never use heading color on body copy or vice versa

---

## Content Philosophy

- **Labels describe, they do not decorate** — Every label, heading, and helper text exists to reduce cognitive load, not add visual weight
- **Required fields are marked** — The asterisk in `text-fg-danger` communicates clearly what the user must provide
- **Errors explain, not accuse** — Error messages say what went wrong and how to fix it
- **Empty states have purpose** — Empty states show an illustration with a contextual action, never a blank space
- **Plurals and zeros are handled** — "0 ciudadanos", "3 Alertas" — the system always renders quantity correctly
- **IDs and stack traces are hidden** — Never expose technical identifiers or error details to end users

---

## Interaction Philosophy

- **Keyboard accessibility is non-negotiable** — Focus states are always visible (`outline: 2px solid` on focus)
- **Destructive actions require confirmation** — SweetAlert2 modal before any delete or irreversible operation
- **State changes are animated** — 150ms transitions on all interactive state changes prevent jarring shifts
- **Loading states preserve layout** — Spinner replaces label in buttons; card skeletons replace content during load
- **One active nav item at a time** — The sidebar pill indicator is singular and unambiguous
- **Dark mode is a first-class citizen** — All tokens have light and dark variants; themes switch via `data-theme="dark"` or `.dark` class

---

## Logo Usage

The NODO logo is composed of:
1. **Isologo** — Stylized shield with olive green (`#8A9A46`/`#C8D29C`) and Jacaranda blue (`#5059BC`) stripes, crowned by three rosa pink (`#F26DF9`) dots
2. **Wordmark** — "Gobierno del CHACO" with "CHACO" in extra bold. Color: Azul Principal `#00203A`

**Usage rules:**
- Isologo + Wordmark: sidebar header, all access screens
- Isologo alone: favicon and app icons only
- Always on light backgrounds (`bg-white`, `bg-primary`)
- Dark background variant: only with design team approval
- Never change logo colors, crop, distort, or rotate

---

## Brand Color Gradient

The signature gradient — **Jacaranda → Azul Claro at 45°** — es el elemento de marca más distintivo del sistema.

| Format | Value |
|--------|-------|
| CSS | `linear-gradient(45deg, #5059BC, #598DFF)` |
| CSS variable approach | `linear-gradient(45deg, var(--color-brand-700), #598DFF)` |

Used on: primary Brand buttons, sidebar logo badge, metric card icon shapes, total/summary banner backgrounds.
