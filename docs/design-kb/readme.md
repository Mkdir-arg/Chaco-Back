# Chaco / NODO — Design System

A design system for the **Gobierno de la Provincia del Chaco** (Argentina) social-services
platform, built on the **NODO** platform engine. The system serves two products:

1. **Backoffice** — the staff console used by social workers, coordinators and administrators
   to manage *legajos* (citizen case files), social programs, surveys (*relevamientos*) and
   conversations.
2. **Portal Ciudadano** — the public-facing portal where citizens discover programs, check the
   status of their benefits and open support requests.

Everything here is in **Spanish (es-AR)** — the platform's only language. Copy uses Argentine
*voseo* ("ingresá", "seleccioná", "tu legajo").

> ⚠️ All names, DNIs, addresses and figures in the UI kits are **fictional sample data**.

---

## Sources

This system was reverse-engineered from the product's own repository and its in-repo design
knowledge base. If you have access, explore them to build more faithfully:

- **Code + design-kb:** https://github.com/Mkdir-arg/Chaco
  - `static/custom/css/chaco-tokens.css` — the Figma-derived v1.0/v1.1 token set (source of truth for color + type).
  - `static/custom/css/nodo-brand.css`, `paleta-unificada.css`, `portal-modern.css` — brand + portal styling.
  - `docs/design-kb/` — the authoritative **design knowledge base**: `design-constitution.md`,
    `implicit-rules.md`, `foundations/` (colors, typography, iconography, spacing), 13 component
    specs under `components/*.yaml`, and 5 patterns under `patterns/*.md`. **Read this first** when
    extending the system.
  - `docs/internal/analisis/003-programa-becas-relevamiento-propuesta.md` — functional analysis
    behind the **Programa Becas** UI kit (domain: Segmento → Subsegmento → Convocatoria →
    Relevamiento → Formulario; roles Admin / Coordinador / Territorial; RENAPER; cupo + lista de espera).
- **Brand assets** (logos, illustration) were imported from `static/custom/branding/chaco/` and live in `assets/`.

---

## CONTENT FUNDAMENTALS

**Language & person.** Spanish, Argentine *voseo*. The system speaks **to** the citizen/staffer
informally with second person: "Ingresá", "Buscá", "Seleccioná", "tu legajo", "Recibirás una
respuesta". Never the Spanish-from-Spain *vosotros* or formal *usted* in UI copy.

**Tone.** Institutional but warm and plain. It is a government social-services platform — clarity
and dignity over cleverness. No marketing hype, no exclamation overload. Microcopy is short,
action-first ("Nuevo legajo", "Asignar territorial", "Dar de baja").

**Casing.** Sentence case for headings and buttons ("Nuevo segmento", not "Nuevo Segmento" or
"NUEVO SEGMENTO"). UPPERCASE is reserved for tiny table-header/eyebrow labels with letter-spacing.
Proper nouns of programs keep their official casing ("Tarjeta Alimentar", "Becas Progresar",
"Potenciar Trabajo").

**Domain vocabulary (use verbatim).** *Legajo* (case file), *ciudadano*, *programa*, *relevamiento*
(field survey), *convocatoria* (call/intake period), *segmento / subsegmento*, *coordinador*,
*territorial* (field worker), *cupo* (quota), *lista de espera*. Workflow states are uppercase
constants from the backend: `ASIGNADO`, `EN_CURSO`, `FINALIZANDO`, `FINALIZADO`, `EN_REVISION`,
`TERMINADO`.

**Numbers & dates.** Argentine format: thousands with a dot (`1.284`), decimals with a comma
(`8,40`), currency `$ 410.000`, dates `dd/mm/aaaa`.

**Emoji.** Not used anywhere in the product. Status and meaning are carried by icons + colored
badges, never emoji.

**Examples**
- Empty state: *"Este segmento todavía no tiene requisitos nativos cargados."*
- Confirmation: *"¿Querés dar de baja este legajo? Esta acción no se puede deshacer."*
- Success toast: *"Formulario aprobado · estado TERMINADO"*

---

## VISUAL FOUNDATIONS

**Color.** The brand color is **Jacarandá purple `#5059BC`** (the jacaranda tree, emblematic of the
region). The accent is a **pink blossom `#F98DFF` / `#FFB9DC`**. Field-greens (`#8A9A5B` and lighter
sages) come straight from the leaf-and-furrow logo mark and appear as a tertiary/olive accent.
Neutrals are a cool gray ramp; institutional headings use a near-black **navy `#001224 / #252F40`**
(the wordmark color). Semantic colors: emerald success, rose danger, orange warning, jacaranda used
as "info". Each is provided as a **soft tint + a solid** pair. Full tokens in `tokens/colors.css`.

**Signature gradient.** `linear-gradient(45deg, #5059BC, #F98DFF)` — Jacarandá → BG Pink, **always in
that direction, never reversed** (design-kb implicit rule). It marks the single most important action
per view (the Brand button), gradient-initial avatars, and small brand moments. Use it sparingly —
**one brand-gradient action per section.** (A legacy parent-NODO magenta→purple gradient
`--gradient-nodo-legacy` exists for old marketing surfaces; avoid it in CHACO product UI.)

**Type.** **Manrope is the only typeface** (Google Fonts) — UI, body *and* headings — at weights
400–800; headings are 700–800 with slightly negative tracking. There is **no separate display face**:
the brand originally specified a rounded display (*Gellat*), but in CHACO the font tokens
(`--font-sans` / `--font-display`) all resolve to Manrope, so **Gellat/Fredoka are not used**. Scale and
weights in `tokens/typography.css`.

**Spacing & layout.** 4px base grid; **20px** is the canonical gap between cards/fields, **32px**
between form sections. Forms are centered, ~700px max-width. The backoffice is a **fixed 276px white
sidebar** + sticky 64px topbar + scrolling canvas on `--bg-secondary` (#f9fafb). Content max-width ~1180px.

**Corner radii.** Buttons are **fully rounded pills** (`rounded-full`). Cards and modals are
`rounded-xl` (12px) / `rounded-2xl` (16px). Inputs and selects are `rounded-lg` (8px). Badges are
pills. (Radii in `tokens/spacing.css`.)

**Cards.** White surface, **1px hairline border `#E5E7EB`**, soft `shadow-sm`, 12px radius. On hover
(when interactive) they lift 2px and deepen to `shadow-lg`. No heavy borders, no colored left-border
accents.

**Elevation.** Soft, low-contrast, neutral shadows (xs→xl) — institutional, not flashy. A single
brand-tinted glow (`--shadow-brand`) is available for focus/hero CTAs.

**Borders & focus.** Default border `--border-base` (#E5E7EB). Inputs show a **brand focus ring**
(`0 0 0 3px rgba(80,89,188,.35)`); errors switch border + ring to rose.

**Badges.** Always **color + text together** (never color alone) for accessibility; an optional
leading dot. Six tones: gray, white, brand (pink fill / wine text), danger, warning, success.

**Buttons.** Pill shaped. **Brand** = gradient (primary). **Secondary** = neutral gray bordered.
**Tertiary** = white with brand outline, hover fills `#DEE1FF`. **Danger** = solid rose. One brand
button per section.

**Imagery.** Flat-vector illustrations of **people** (diverse, warm) on sage→jacaranda gradient
panels — used for login, welcome and empty states. No stock photos, no abstract 3D blobs.

**Motion.** Restrained. Standard easing `cubic-bezier(0.4,0,0.2,1)`; fast 150ms for hovers, 300ms for
panels. Hover = brightness/background shift (no bounce); press = subtle. Respect reduced-motion.

**Transparency & blur.** Used only for overlays: modal backdrop is `rgba(0,0,0,.5)` + `backdrop-blur(4px)`.

---

## ICONOGRAPHY

Two icon systems coexist, by era:

- **New templates → Heroicons v2 (outline), stroke 1.5, 24×24, `currentColor`.** This is the
  forward-looking standard set in the design-kb constitution. The **Programa Becas** UI kit ships a
  self-contained Heroicons subset in `ui_kits/programa-becas/icons.jsx` (`<Icon name="…" />`) — copy
  that file (or pull Heroicons from a CDN/npm) when building new screens. Icons inherit color from the
  parent; never hardcode an icon color.
- **Legacy templates → Font Awesome 6 (solid).** The existing app and the foundation/component
  specimen cards use Font Awesome via CDN (`fas fa-*`). The reusable React components accept **either**
  a Font Awesome class (`icon="fas fa-plus"`) **or** a rendered SVG node (`iconNode={<Icon name="plus"/>}`),
  so they bridge both worlds.

The app's original sidebar SVGs (`legajos`, `inicio`, `tableros`, `administracion`) were imported into
`assets/icons/` for reference. **No emoji and no Unicode-glyph icons** are used anywhere.

---

## INDEX / MANIFEST

**Root**
- `styles.css` — global entry point (consumers link this one file). `@import`s only.
- `readme.md` — this guide.
- `SKILL.md` — Agent-Skills-compatible front-matter so the system can be used in Claude Code.

**`tokens/`** — CSS custom properties + fonts (all reached from `styles.css`)
- `colors.css` · `typography.css` · `spacing.css` (radius/shadow/motion/layout) · `fonts.css` · `base.css`

**`components/`** — reusable React primitives (`window.ChacoNODODesignSystem_dc2a68.<Name>`)
- `core/` — **Button, Badge, Card, StatCard, Avatar**
- `forms/` — **Input, Select**
- `feedback/` — **Alert, Modal**
- `navigation/` — **Tabs**
- Each has `<Name>.jsx`, `<Name>.d.ts`, `<Name>.prompt.md`, and a directory `*.card.html` specimen.

**`ui_kits/`** — full-screen product recreations
- `programa-becas/` — **Programa Becas backoffice module, 8 interactive screens** (segmentos,
  requisitos, convocatorias, relevamientos, revisión de formularios, cupo y lista de espera, solapa
  Becas en legajo, reportes). Entry: `index.html`. Ships `icons.jsx` (Heroicons) + `data.js`.
- `backoffice/` — generic staff console (dashboard, legajos list + detail).
- `portal-ciudadano/` — citizen portal shell (header, footer, chat).

**`guidelines/`** — foundation specimen cards (rendered in the Design System tab): Colors (7), Type (3),
Spacing (3), Brand (4).

**`assets/`** — `logo-chaco-horizontal.*`, `logo-mark.png`, `favicon.png`, `illustration-login.*`,
`login-background.png`, `icons/` (original sidebar SVGs).

---

## CAVEATS

- **Manrope única (no display face).** The brand originally specified a rounded display (*Gellat*),
  not shipped and not on Google Fonts. CHACO decided **Manrope for everything**: the font tokens
  resolve to Manrope and **Gellat/Fredoka are not used**. (Revisit only if real Gellat files are adopted.)
- **Webfonts via Google Fonts `@import`** (Manrope only), not self-hosted `@font-face` — so the
  compiler reports zero shipped font binaries. That's expected; consumers load it from the CDN.
- Color tokens follow the **current** `chaco-tokens.css` (Jacarandá/pink). The older institutional-blue
  SISOC palette and the magenta NODO brand are kept only as legacy references.
