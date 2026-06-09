# Prompt de Implementación — CHACO NODO Design System
**Copiar y pegar completo en una nueva sesión de Claude**

---

## Contexto

Sos un Senior Frontend Engineer implementando el Design System de NODO para el Gobierno del Chaco. El sistema fue completamente especificado por la diseñadora y documentado en `docs/design-kb/`. Tu trabajo es implementar ese diseño en el código Django existente.

**Stack:**
- Python 3.12, Django 4.2, MySQL 8
- CSS nuevos → Tailwind CSS (Play CDN, sin build step)
- CSS legacy → Bootstrap 5.3.2 + AdminLTE
- Íconos nuevos → Heroicons (SVG inline)
- Íconos legacy → Font Awesome 6.4.0
- JS → Alpine.js 3.14.1, jQuery 3.6.0, SweetAlert2, Toastr, ApexCharts
- Branding dinámico → `config/branding.py` genera CSS variables inyectadas en templates

**Regla de fuentes:** CHACO siempre gana sobre NODO. La fuente de verdad es `docs/design-kb/`.

---

## Lo que ya está hecho — NO repetir

- `static/custom/css/chaco-tokens.css` → copiado al repo ✅
- `static/custom/js/chaco-tailwind.config.js` → copiado al repo ✅
- `docs/design-kb/tokens/chaco-tokens.json` → copiado al repo ✅
- `templates/includes/base.html` → chaco-tokens.css wired como primer import, tailwind.config extendido con todos los semantic tokens, Inter agregado a Google Fonts ✅
- `portal/templates/portal/base.html` → chaco-tokens.css wired ✅
- `docs/design-kb/` → Knowledge Base completo (foundations, tokens, 13 components, 5 patterns, constitution) ✅

---

## Lo que falta — ejecutar en orden

### FASE 1 (incompleta) — Completar integración de tokens

**1a. Reconciliar `config/branding.py` con chaco-tokens.css**

Lee `config/branding.py`. Identifica qué variables CSS genera y mapéalas contra las variables de `chaco-tokens.css`. Donde haya valores duplicados:
- Si branding.py genera `--color-primario: #5059BC` y chaco-tokens.css ya define `--bg-brand: #5059bc`, actualiza branding.py para que use `--bg-brand` como referencia en lugar de definir un valor propio.
- Mantén la compatibilidad: los templates existentes usan `{{ branding.css_variables }}`.

**1b. Auditar valores hex crudos en CSS existentes**

Busca en `static/custom/css/paleta-unificada.css`, `nodo-brand.css` y `nodo-buttons.css` valores hex que ahora tienen equivalente en token:
- `#5059bc` o `#5059BC` → `var(--bg-brand)`
- `#c70036` → `var(--bg-danger)`
- `#f9fafb` → `var(--bg-secondary-soft)`
- `#e5e7eb` → `var(--border-base)`
- `#111827` → `var(--text-heading)`
- `#4b5563` → `var(--text-body)`
- `#6b7280` → `var(--text-body-subtle)`

No reemplazar todos los hex de una vez — reemplazar solo los que corresponden exactamente a un semantic token. Los valores únicos/específicos de componentes legacy pueden quedarse.

---

### FASE 2 — Componentes CSS

Lee primero: `docs/design-kb/components/button.yaml`, `badge.yaml`, `input.yaml`, `sidebar.yaml`, `data-table.yaml`

**2a. `static/custom/css/nodo-buttons.css`**

Implementar o verificar los 3 variantes × 5 tamaños × 4 estados:

```css
/* Brand button — gradiente Jacaranda → BG Pink */
.btn-brand {
  background: linear-gradient(45deg, var(--bg-brand), var(--bg-pink));
  color: var(--text-white);
  border: none;
  border-radius: var(--rounded-full);
  font-family: var(--font-family-base);
  font-weight: var(--font-weight-medium);
  cursor: pointer;
  transition: filter 150ms ease;
}
.btn-brand:hover { filter: brightness(0.92); }
.btn-brand:focus { outline: 2px solid var(--bg-brand); outline-offset: 2px; }
.btn-brand:disabled {
  background: var(--bg-disabled);
  border: 1px solid var(--border-base);
  color: var(--text-fg-disabled);
  cursor: not-allowed;
}

/* Secondary button */
.btn-secondary {
  background: var(--bg-secondary-soft);
  border: 1px solid var(--border-base);
  color: var(--text-body);
  border-radius: var(--rounded-full);
}
.btn-secondary:hover { background: var(--bg-tertiary); color: var(--text-heading); }
.btn-secondary:disabled { background: var(--bg-disabled); color: var(--text-fg-disabled); cursor: not-allowed; }

/* Tertiary button — outlined brand */
.btn-tertiary {
  background: var(--bg-white);
  border: 1px solid var(--border-brand);
  color: var(--text-fg-brand);
  border-radius: var(--rounded-full);
}
.btn-tertiary:hover { background: #DEE1FF; }
.btn-tertiary:disabled { background: #F0F2FF; cursor: not-allowed; }

/* Danger button */
.btn-danger {
  background: var(--bg-danger);
  color: var(--text-white);
  border: none;
  border-radius: var(--rounded-full);
}

/* Sizes */
.btn-xs   { font-size: var(--font-size-xs);  padding: 6px 12px;  height: 32px; }
.btn-sm   { font-size: var(--font-size-sm);  padding: 8px 12px;  height: 36px; }
.btn-base { font-size: var(--font-size-sm);  padding: 10px 16px; height: 40px; }
.btn-l    { font-size: var(--font-size-base); padding: 12px 20px; height: 48px; }
.btn-xl   { font-size: var(--font-size-base); padding: 14px 24px; height: 52px; }

/* Loading state */
.btn-loading { position: relative; color: transparent; pointer-events: none; }
.btn-loading::after {
  content: '';
  position: absolute;
  width: 16px; height: 16px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
```

**2b. Badge component** — ver `docs/design-kb/components/badge.yaml`

6 variantes (gray, white, brand, danger, warning, success) × 2 tamaños (sm: 20px, lg: 24px). Border-radius: 6px. Implementar en `static/custom/css/nodo-brand.css` o crear `static/custom/css/nodo-badges.css`.

**2c. Input / Form fields** — ver `docs/design-kb/components/input.yaml`

4 estados: default, focus (border-brand 1.5px), error (border-danger + bg-danger-soft), disabled (bg-disabled).

**2d. Avatar** — ver `docs/design-kb/components/avatar.yaml`

31×31px, rounded-full, bg-brand-medium, text-white font-semibold. Clase `.avatar-initials`.

---

### FASE 3 — Django template fragments

Crear en `templates/includes/ds/`:

| Archivo | Params |
|---------|--------|
| `stat-card.html` | `number`, `label`, `icon_svg`, `alert_dot` (bool) |
| `badge.html` | `variant`, `size`, `text`, `dismissible` (bool) |
| `empty-state.html` | `title`, `message`, `cta_url`, `cta_label` |
| `breadcrumb.html` | `steps` (list de `{label, url, active}`) |
| `alert-panel.html` | `alerts` (list) |

Cada template:
- Solo clases Tailwind o CSS variables (ningún hex crudo)
- `{% load static %}` si necesita imágenes
- Aria attributes para accesibilidad

Ejemplo stat-card.html:
```html
<div class="bg-bg-primary border border-bg-quaternary rounded-xl p-5 cursor-default"
     style="box-shadow: var(--sombra-sm)">
  <div class="flex items-center justify-between mb-2">
    <div class="w-10 h-10 rounded-xl flex items-center justify-center"
         style="background: linear-gradient(45deg, var(--bg-brand), var(--bg-pink))">
      {{ icon_svg }}
    </div>
    {% if alert_dot %}
    <span class="w-2.5 h-2.5 rounded-full bg-bg-danger" aria-label="Alerta activa"></span>
    {% endif %}
  </div>
  <p class="text-3xl font-bold" style="color: var(--text-heading)">{{ number }}</p>
  <p class="text-xs font-medium uppercase tracking-wide mt-1"
     style="color: var(--text-body-subtle)">{{ label }}</p>
</div>
```

---

### FASE 4 — Dark mode toggle (backoffice únicamente)

Agregar al topbar del backoffice un toggle que:
```javascript
// Alpine.js component
function darkModeToggle() {
  return {
    dark: localStorage.getItem('theme') === 'dark',
    toggle() {
      this.dark = !this.dark
      document.documentElement.setAttribute('data-theme', this.dark ? 'dark' : 'light')
      localStorage.setItem('theme', this.dark ? 'dark' : 'light')
    },
    init() {
      const saved = localStorage.getItem('theme') || 'light'
      document.documentElement.setAttribute('data-theme', saved)
      this.dark = saved === 'dark'
    }
  }
}
```

El portal ciudadano NO tiene dark mode (Amendment III de la Design Constitution).

---

### FASE 5 — Auditoría de accesibilidad

Para cada componente implementado verificar:
1. `outline: 2px solid` en focus — NUNCA `outline: none`
2. Botones icon-only: `aria-label` requerido
3. Badges de estado: texto + color (nunca solo color)
4. Campos requeridos: `*` en `text-fg-danger` + atributo HTML `required`
5. `window.confirm()` → reemplazar por SweetAlert2 donde quede

Buscar: `grep -r "outline: none" static/custom/css/`
Buscar: `grep -r "window.confirm" . --include="*.html" --include="*.js"`

---

### FASE 6 — Página de documentación del sistema

Crear vista Django en `/configuracion/design-system/` (staff-only):
- App: `configuracion`
- View: `DesignSystemView` (LoginRequired + staff check)
- Template: `configuracion/design-system.html`
- URL: `path('design-system/', views.DesignSystemView.as_view())`

La página muestra en vivo:
- Swatches de todos los semantic tokens de color
- Escala tipográfica
- Matriz: variantes × tamaños × estados de botones
- Todos los badge variants
- Ejemplos de inputs (default, focus, error, disabled)
- Stat card demo
- Empty state demo

---

## Decisiones clave — no re-consultar

| Qué | Valor |
|-----|-------|
| Brand primary | `#5059BC` Jacaranda → `var(--bg-brand)` |
| Gradiente Brand | `linear-gradient(45deg, var(--bg-brand), var(--bg-pink))` |
| Sidebar width | `288px` (Tailwind `w-72`) |
| Form max-width | `768px` fijo (`max-w-3xl`) — todos los formularios |
| Avatar size | `31×31px`, circular, iniciales 2 chars |
| Toast | Centrado, `rgba(75,85,99,0.7)`, 10 segundos |
| Modal backdrop | `rgba(209,213,219,0.7)` (gray-300 al 70%) |
| Modal confirm btn | Brand gradient (NO rojo, incluso en acciones destructivas) |
| Button border-radius | `rounded-full` (9999px) — todas las variantes y tamaños |
| Table headers | `text-xs font-semibold uppercase text-body-subtle` |
| Dark mode | Backoffice únicamente — portal usa light mode |
| Stat cards | Visual only — `cursor: default`, no son links |
| Asterisco requerido | `text-fg-danger` (#c70036) |
| Íconos (nuevos templates) | Heroicons outline (default) / solid (active) |
| Íconos (legacy templates) | Font Awesome 6.4.0 |
| CSS (nuevos) | Tailwind — NUNCA mezclar con Bootstrap en el mismo componente |
| CSS (legacy) | Bootstrap 5.3.2 + AdminLTE |
| Confirmaciones destructivas | SweetAlert2 obligatorio — `window.confirm()` prohibido |

---

## Archivos a leer antes de empezar

```
docs/design-kb/design-constitution.md       ← ley suprema
docs/design-kb/foundations/colors.yaml      ← todos los color tokens
docs/design-kb/foundations/typography.yaml  ← reglas de fuente
docs/design-kb/tokens/design-tokens.yaml    ← inventario completo
docs/design-kb/anti-patterns.md             ← qué NO hacer
docs/design-kb/components/button.yaml
docs/design-kb/components/badge.yaml
docs/design-kb/components/input.yaml
docs/design-kb/components/sidebar.yaml
docs/design-kb/components/data-table.yaml
docs/design-kb/components/toast.yaml
docs/design-kb/components/modal.yaml
docs/design-kb/components/avatar.yaml
docs/design-kb/components/select.yaml
static/custom/css/chaco-tokens.css          ← CSS variables (fuente de verdad)
static/custom/css/nodo-buttons.css          ← implementación actual de botones
static/custom/css/paleta-unificada.css      ← sombras, transiciones
config/branding.py                          ← generador dinámico de CSS vars
templates/includes/base.html               ← template base backoffice
```

---

## Verificación al final de cada fase

- [ ] `python manage.py check` sin errores
- [ ] No hay valores hex crudos en CSS de componentes (solo CSS vars)
- [ ] Los 3 variantes de botón tienen los 4 estados (default, hover, focus, disabled)
- [ ] Todas las tablas tienen empty state definido
- [ ] SweetAlert2 usado en todas las acciones destructivas
- [ ] No quedan `window.confirm()` en el código
- [ ] Focus ring visible en todos los elementos interactivos
- [ ] Dark mode toggle persiste en localStorage (solo backoffice)
