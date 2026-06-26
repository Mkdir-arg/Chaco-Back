---
name: chaco-nodo-design
description: Use this skill to generate well-branded interfaces and assets for the Gobierno del Chaco / NODO social-services platform (backoffice + portal ciudadano), either for production or throwaway prototypes/mocks. Contains essential design guidelines, colors, type, fonts, assets, and UI kit components for prototyping. Spanish (es-AR) product.
user-invocable: true
---

Read the `readme.md` file within this skill, and explore the other available files.

If creating visual artifacts (slides, mocks, throwaway prototypes, etc), copy assets out and create
static HTML files for the user to view. If working on production code, you can copy assets and read
the rules here to become an expert in designing with this brand.

If the user invokes this skill without any other guidance, ask them what they want to build or design,
ask some questions, and act as an expert designer who outputs HTML artifacts _or_ production code,
depending on the need.

## Quick reference
- **Language:** Spanish, Argentine *voseo* ("ingresá", "tu legajo"). No emoji.
- **Brand color:** Jacarandá `#5059BC`. **Accent:** pink `#F98DFF`. **Gradient:** `linear-gradient(45deg,#5059BC,#F98DFF)` — never reversed, one brand action per section.
- **Type:** Manrope (UI/body). Display = Fredoka (substitute for "Gellat").
- **Radii:** buttons = pill, cards/modals = 12–16px, inputs = 8px.
- **Icons:** Heroicons v2 outline for new screens (see `ui_kits/programa-becas/icons.jsx`); Font Awesome 6 solid in legacy.
- **Tokens:** link `styles.css`; everything is a CSS custom property.

## Where things are
- `tokens/` — colors, typography, spacing/radius/shadow, fonts.
- `components/` — React primitives: Button, Badge, Card, StatCard, Avatar, Input, Select, Alert, Modal, Tabs.
- `ui_kits/programa-becas/` — full 8-screen backoffice module to copy patterns from.
- `guidelines/` — foundation specimen cards.
- `assets/` — logos, illustration, icons.
