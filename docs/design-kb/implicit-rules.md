# Implicit Rules
**Inferred Design Principles — NODO Design System**

Each rule includes confidence level, evidence, and rationale.

---

## Spacing Behavior

### IR-S01: Base unit is 4px
**Confidence:** HIGH
**Evidence:** Component spacing values (2px, 4px, 6px, 8px, 10px, 12px, 16px, 20px, 24px, 28px, 32px) are all multiples of 4px.
**Rationale:** A 4px base grid is the most common convention in modern design systems. The badge padding (2px/4px/6px) and button padding (6px/8px/10px/12px/14px) confirm the 4px step pattern.
**How to apply:** When choosing a spacing value not documented, default to the nearest 4px multiple.

### IR-S02: Form spacing follows an 8px rhythm
**Confidence:** MEDIUM
**Evidence:** Field gap 20px (5×4), section gap 32px (8×4). These are larger 4px multiples.
**Rationale:** Forms use wider spacing for clarity between elements to prevent visual crowding on data-dense screens.
**How to apply:** Between form fields: 20px. Between form sections: 32px. These are non-negotiable.

### IR-S03: Internal card padding is ~20px
**Confidence:** MEDIUM
**Evidence:** Module card spec (15px/28px padding) and stat card spec (~20px padding).
**Rationale:** Cards need enough breathing room for content hierarchy without wasting space.
**How to apply:** Default card padding: 20–24px on all sides.

---

## Layout Behavior

### IR-L01: Content hierarchy flows top-to-bottom, left-to-right
**Confidence:** HIGH
**Evidence:** Every documented screen (home, list view, detail view) follows: heading → context (stat cards) → search/filter → detail (table/charts) → actions.
**Rationale:** Users scan top-to-bottom. Overview first, detail second. Context before interaction.
**How to apply:** Never place search or filters above the summary/stat cards. Actions go at the end of a flow.

### IR-L02: Right-alignment signals primary action
**Confidence:** HIGH
**Evidence:** All primary CTAs (⊕ Nuevo legajo, Crear Ciudadano, Export) are right-aligned on their row. Cancel/back buttons are left of primary.
**Rationale:** Users read left-to-right. Heading/context on the left; the thing they need to "do" on the right.
**How to apply:** Section heading + right-aligned Brand CTA is the default pattern. Never center the primary CTA.

### IR-L03: Forms have a maximum width and are centered
**Confidence:** HIGH
**Evidence:** New Citizen form "~700px centered". Confirm Data form uses two columns within a limited width.
**Rationale:** Wide forms are hard to scan. The eye needs to travel too far between label and input.
**How to apply:** max-width ~700px for single-column forms. Multi-column forms may be slightly wider.

### IR-L04: The sidebar is never hidden on desktop
**Confidence:** HIGH
**Evidence:** All authenticated screens show sidebar + content layout. No documented exception for internal screens.
**Rationale:** The sidebar provides persistent navigation orientation. Hiding it creates disorientation.
**How to apply:** Sidebar appears on all authenticated (post-login) screens. Never hide it programmatically on desktop.

---

## Hierarchy Behavior

### IR-H01: One brand gradient element per visible area
**Confidence:** HIGH
**Evidence:** "One Brand button per section" rule. The gradient is visually dominant — its power comes from exclusivity.
**Rationale:** The brand gradient is attention-commanding. Using it multiple times in the same view dilutes its impact and creates visual noise.
**How to apply:** One gradient button per section. One gradient background element (total banner, sidebar logo). Multiple gradients = no gradient.

### IR-H02: Text hierarchy: Heading → Body → Subtle — never mixed
**Confidence:** HIGH
**Evidence:** Explicit token mapping: `text-heading` for H1–H3, `text-body` for paragraphs, `text-body-subtle` for optional/secondary text.
**Rationale:** Three levels of text contrast create a clear scanning hierarchy. Mixing them creates ambiguity.
**How to apply:** Never use `text-body-subtle` for content that the user must read. Never use `text-heading` for helper/optional text.

### IR-H03: State badges use both color AND text label
**Confidence:** HIGH
**Evidence:** Badges always show text ("BAJO", "ALTO", "Completa") alongside color coding.
**Rationale:** Color alone fails accessibility requirements and is ambiguous for users with color vision deficiency.
**How to apply:** Every status indicator must have a text label. Color reinforces, never replaces, the label.

---

## Visual Rhythm

### IR-VR01: Border radius scales with element prominence
**Confidence:** MEDIUM
**Evidence:** Buttons: rounded-full (pills). Cards/modals: rounded-xl (12px). Inputs: rounded-lg (8px). Badges: rounded-md (6px) or rounded-full.
**Rationale:** More prominent interactive elements (buttons) get maximum softness (pill). Containers get a significant but controlled radius. Small elements get proportional radius.
**How to apply:** Interactive: rounded-full. Card containers: rounded-xl. Form inputs: rounded-lg. Small tags/badges: rounded-md to rounded-full.

### IR-VR02: Shadow intensity scales with content importance
**Confidence:** MEDIUM
**Evidence:** Cards: sombra-sm default → sombra-md on hover. Modals/dropdowns: sombra-lg. The system deliberately avoids heavy shadows.
**Rationale:** Minimal shadows keep the aesthetic clean. Shadow escalation on hover provides subtle affordance cues.
**How to apply:** Resting surfaces: no shadow or sombra-sm. Hovered/active surfaces: sombra-md. Floating/overlay surfaces: sombra-lg or sombra-xl.

---

## Responsiveness Logic

### IR-R01: The CSS files suggest mobile is a secondary concern
**Confidence:** MEDIUM
**Evidence:** Dedicated CSS files exist (mobile-forms.css, mobile-tables.css, mobile-modals.css) suggesting mobile was retrofitted rather than mobile-first. The sidebar behavior on mobile is undocumented.
**Rationale:** The backoffice is primarily a desktop tool for government workers. Mobile is needed but not the primary use case.
**How to apply:** Desktop design is primary. Mobile adaptations should be tested but the core experience assumes desktop.

### IR-R02: New templates use Tailwind; legacy templates use Bootstrap
**Confidence:** HIGH
**Evidence:** NODO DS.md explicitly states: "Templates nuevos → Tailwind CSS. Templates legacy → Bootstrap 5.3.2 + AdminLTE."
**Rationale:** The project is migrating from Bootstrap/AdminLTE to Tailwind incrementally. Both coexist.
**How to apply:** NEVER mix Tailwind and Bootstrap classes in the same component. Check if the template is "new" or "legacy" before choosing the CSS approach.

---

## Consistency Patterns

### IR-CP01: Every interactive element has three minimum states
**Confidence:** HIGH
**Evidence:** All documented components (button, input, sidebar item, table row) explicitly show default, hover, and focus states.
**Rationale:** Accessibility requires visible focus. UX requires hover feedback. These are non-negotiable.
**How to apply:** When creating any clickable or focusable element, define all three states before shipping.

### IR-CP02: Brand gradient always goes purple→pink, never reversed
**Confidence:** HIGH
**Evidence:** All documented gradients: `linear-gradient(45deg, #7928CA, #FF0080)` or `linear-gradient(45deg, #5059BC, #F26DF9)`.
**Rationale:** Direction encodes brand identity. Reversing it would be inconsistent.
**How to apply:** Always purple/jacaranda as the start color, pink/rosa as the end color. Never reversed.

### IR-CP03: Icon color always inherits from text token, never hardcoded
**Confidence:** HIGH
**Evidence:** Icon section states "Icons never have their own color — they inherit via text color tokens."
**Rationale:** This allows icons to automatically adapt to dark mode and state changes.
**How to apply:** Apply `text-[token]` class to the icon element. Never use `fill` or `stroke` with hardcoded values.

### IR-CP04: The brand color in NODO DS.md is magenta (#FF0080) while the final design tokens use Jacaranda (#5059BC) as brand
**Confidence:** HIGH
**Evidence:** NODO DS.md §1 states brand color = `#FF0080`. chaco-tokens.json/css uses `--color-brand-*` as Jacaranda/purple (`#5059BC`). The button gradient uses both.
**Rationale:** There appear to be two versions of the design system — an earlier one (NODO DS.md, magenta-first) and a newer one (chaco-tokens.json, Jacaranda/purple-first). The newer token system should be considered authoritative.
**How to apply:** Use `chaco-tokens.json` / `chaco-tokens.css` tokens as the source of truth. The gradient button in both versions uses the purple→pink combination, so both systems are consistent on that.
