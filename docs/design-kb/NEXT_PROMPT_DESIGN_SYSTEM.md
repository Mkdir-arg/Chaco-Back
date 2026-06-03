# NEXT_PROMPT_DESIGN_SYSTEM
**Complete prompt to transform this Design Knowledge Base into a production-grade Design System**

---

## Context

You are working on the **NODO Design System** for the Gobierno del Chaco, a Django-based backoffice and citizen portal (`Chaco` monorepo). The Design Knowledge Base is located at `docs/design-kb/` in this repository.

The tech stack is:
- **Backend:** Python 3.12, Django 4.2
- **CSS (new templates):** Tailwind CSS (Play CDN, no build step)
- **CSS (legacy templates):** Bootstrap 5.3.2 + AdminLTE
- **Custom CSS:** `static/custom/css/` (paleta-unificada.css, nodo-brand.css, nodo-buttons.css)
- **Token files:** `chaco-tokens.css`, `chaco-tailwind.config.js`, `chaco-tokens.json` (in source from design team)
- **JavaScript:** Alpine.js 3.14.1, jQuery 3.6.0, SweetAlert2, Toastr, Chart.js, ApexCharts
- **Icons (new):** Heroicons — `@heroicons/react` or SVG direct
- **Icons (legacy):** Font Awesome 6.4.0
- **Branding config:** `config/branding.py` (generates CSS variables dynamically)

---

## Your Task

Transform the `docs/design-kb/` Design Knowledge Base into a **production-grade, implementable Design System** for the NODO platform. This includes:

---

### Phase 1: Token Integration

1. **Copy `chaco-tokens.css` to `static/custom/css/chaco-tokens.css`** and make it the first CSS import in:
   - `templates/includes/base.html` (backoffice)
   - `portal/templates/portal/base.html` (portal)
   
2. **Reconcile `config/branding.py` with the new tokens.** The branding.py generates CSS variables dynamically. Map the branding.py variables to their equivalent chaco-tokens.css variables. Where they conflict, favor the token file values. Update branding.py to reference token variables where possible instead of raw hex values.

3. **Validate token coverage.** Grep through `static/custom/css/paleta-unificada.css`, `nodo-brand.css`, and `nodo-buttons.css` for any raw hex values that now have token equivalents. Replace each with the corresponding CSS variable from chaco-tokens.css.

4. **Extend the Tailwind config.** If a `tailwind.config.js` does not exist at the root, create one that extends `chaco-tailwind.config.js`. Verify the CDN script tag in `base.html` includes the config extension.

---

### Phase 2: Component Library

For each component in `docs/design-kb/components/`, implement or update the corresponding HTML/CSS:

#### 2a. Button System (`static/custom/css/nodo-buttons.css`)
- Verify all three variants (brand, secondary, tertiary) match specs in `components/button.yaml`
- Verify all five sizes (xs, sm, base, l, xl) match exact measurements
- Verify all states (default, hover, focus, disabled) match token values
- Add loading state: spinner replaces label, width unchanged
- Confirm gradient direction: `linear-gradient(45deg, #5059BC, #F26DF9)` (or NODO variant)

#### 2b. Badge Component
- Implement all six variants (gray, white, brand, danger, warning, success) per `components/badge.yaml`
- Two sizes (sm: 20px height, lg: 24px height)
- Confirm border-radius: 6px (rounded-md)

#### 2c. Input / Form Fields
- Implement all four states (default, focus, error, disabled) per `components/input.yaml`
- Focus border: `border-brand 1.5px`
- Error state: `border-danger 1px` + `bg-danger-soft` background
- Disabled: `bg-disabled` + `text-fg-disabled`
- Label always above field, required `*` in `text-fg-brand`

#### 2d. Sidebar Navigation
- Active item: pill shape (rounded-full or rounded-lg), `bg-brand`, white text
- Hover: `bg-tertiary`
- Chevron rotation transition: 150ms ease
- Logo badge: `linear-gradient(45deg, #7928CA, #FF0080)`, border-radius 12px

#### 2e. Data Table
- No alternating row colors
- Row hover: `bg-tertiary`
- Column headers: `text-xs, font-semibold, uppercase, text-body-subtle` (wait — cross-reference: CHACO_NODO_Design_Manual says `text-xs font-semibold uppercase`, NODO DS says `Inter Medium 13px, text-body` — reconcile and pick one)
- Pagination: Tertiary buttons (outlined brand)
- Empty state: required for every table

---

### Phase 3: Pattern Templates

Create reusable Django template fragments (includes) for:

1. **`templates/includes/ds/stat-card.html`** — takes `number`, `label`, `icon`, `alert_dot` params
2. **`templates/includes/ds/badge.html`** — takes `variant`, `size`, `text`, `dismissible` params
3. **`templates/includes/ds/alert-panel.html`** — takes `alerts` list param
4. **`templates/includes/ds/empty-state.html`** — takes `title`, `message`, `cta_url`, `cta_label` params
5. **`templates/includes/ds/breadcrumb.html`** — takes `steps` list param (each: `label`, `url`, `active`)

Each template must:
- Use only token-based classes (Tailwind or CSS variables)
- Support dark mode via `data-theme` attribute
- Include accessible attributes (aria-labels, roles)

---

### Phase 4: Dark Mode Implementation

1. Verify `[data-theme="dark"]` and `.dark` selectors in `chaco-tokens.css` cover all semantic tokens
2. Add a dark mode toggle to the topbar (Alpine.js or vanilla JS):
   ```javascript
   document.documentElement.setAttribute('data-theme', 'dark') // activate
   document.documentElement.setAttribute('data-theme', 'light') // deactivate
   ```
3. Persist the preference in `localStorage`
4. Test all documented screens in dark mode against the token values in `foundations/colors.yaml`

---

### Phase 5: Accessibility Audit

For each component in `docs/design-kb/components/`:
1. Verify focus states are visible (never `outline: none`)
2. Verify icon-only buttons have `aria-label`
3. Verify status badges have text labels (not only color)
4. Verify required fields have both the `*` indicator and `required` HTML attribute
5. Verify color contrast ratios for key pairs:
   - `text-heading` on `bg-primary` (should be: #111827 on #ffffff = AAA)
   - `text-white` on `bg-brand` (#ffffff on #5059bc — check AA)
   - `text-fg-disabled` on `bg-disabled` (#9ca3af on #f3f4f6 — verify AA)

---

### Phase 6: Documentation Page

Create a live documentation page at `/configuracion/design-system/` (Django view, staff-only):
- Rendered HTML showing all components with their states
- Color swatches for all semantic tokens
- Typography scale samples
- Button variants × sizes × states matrix
- Badge variants
- This page should be self-contained — no external dependencies beyond what's in the project

---

### Verification Checklist

After completing each phase:

- [ ] `manage.py check` passes with no errors
- [ ] Tokens are not duplicated between branding.py and chaco-tokens.css
- [ ] No raw hex values in component CSS (only CSS variables or token-mapped values)
- [ ] All six badge variants render correctly in light and dark mode
- [ ] All three button variants have all four states (default, hover, focus, disabled)
- [ ] All tables have empty states defined
- [ ] SweetAlert2 is wired for all delete actions
- [ ] No `window.confirm()` remains in the codebase
- [ ] Focus rings are visible on all interactive elements
- [ ] Tailwind config is extended with chaco-tokens
- [ ] Dark mode toggle persists preference in localStorage

---

### Files to Read Before Starting

```
docs/design-kb/design-constitution.md          ← Supreme law
docs/design-kb/foundations/colors.yaml         ← All color tokens
docs/design-kb/foundations/typography.yaml     ← Font rules
docs/design-kb/foundations/spacing.yaml        ← Spacing + radius tokens
docs/design-kb/tokens/design-tokens.yaml       ← Full token inventory
docs/design-kb/components/button.yaml          ← Button spec
docs/design-kb/components/badge.yaml           ← Badge spec
docs/design-kb/components/input.yaml           ← Input spec
docs/design-kb/components/sidebar.yaml         ← Sidebar spec
docs/design-kb/components/data-table.yaml      ← Table spec
docs/design-kb/anti-patterns.md                ← What NOT to do
static/custom/css/nodo-buttons.css             ← Current button implementation
static/custom/css/paleta-unificada.css         ← Current token implementation
config/branding.py                             ← Dynamic CSS variable generator
templates/includes/base.html                   ← Main template entry point
```

---

### Source Hierarchy

**CHACO siempre gana sobre NODO.** `NODO DS.md` es la documentación del proyecto padre. En todo conflicto prevalece `CHACO_NODO_Design_Manual.md` + `chaco-tokens.json`. NODO DS.md se usa únicamente como fallback para especificaciones que CHACO no documenta (e.g., alturas exactas de botón, valores hex de badge).

**Decisiones ya resueltas (no requieren consulta):**
- Brand primary: `#5059BC` (Jacaranda), no magenta
- Gradiente Brand button: `linear-gradient(45deg, #5059BC, #598DFF)`
- Botón tertiary: `#5059BC` en border y texto
- Sidebar active: pill `bg-brand (#5059bc)` + texto blanco
- Asterisco requerido: `text-fg-danger` (rojo)
- Headers de tabla: `text-xs, font-semibold, uppercase, text-body-subtle`
- Border-radius botones: `rounded-full` (pill / 9999px)

**Pendientes técnicos (sin conflicto, pero sin valor exacto en fuentes CHACO):**
- Ancho exacto del sidebar: main.css dice 300px, manual dice ~205px — ver pregunta A1
- `#598DFF` como stop final del gradiente no está en chaco-tokens.json — verificar si tiene token

**Coexistencia de stacks:**
- Iconos nuevos → Heroicons. Legacy → Font Awesome. Nunca mezclar en el mismo componente.
- CSS nuevos → Tailwind CSS. Legacy → Bootstrap. Nunca mezclar en el mismo componente.
