# Anexo · Clases usadas que no existen en ningún CSS cargable

Fuente: verificación V5a. Método reproducible: `poc/herramientas/missing_classes.py <raiz_repo>` (con `cssclasses.py`
al lado) sobre el árbol limpio de `origin/development @ 917e583`. Universo declarado: el `tailwind.css` committeado,
todos los `static/custom/css/*.css`, los CSS de Font Awesome y SweetAlert2 de `static/vendor` y los `<style>` inline de
cada template. Resultado: **120 tokens no declarados sobre 1.361 usados**. Tras quitar ruido (literales de comparación
en `:class`) y hooks, quedan las listas de abajo. Es la línea base de la regla **CLASSDEF** (`anexo-agente-diseno.md` §7)
y la lista de trabajo de **FE-06**.

**Causa principal.** `tailwind.config.js` declara `extend.backgroundColor.gray` como string, lo que pisa la escala `gray`
solo para `bg-*` (`text-gray-*` sí existe). `bg-white/NN` no se genera porque `white` es `var(--bg-white)` sin
`<alpha-value>`. **No** agregar la escala `gray` al build: va contra los tokens; reemplazar cada uso por la pieza canónica
(FE-06).

## A. Utilidades Tailwind que el build no genera — bug visual, en alcance y vivas (ERROR de CLASSDEF)

| Clase | Templates o JS (vivos, en alcance) | Reemplazo (FE-06) |
|---|---|---|
| `bg-gray-50` | `templates/includes/base.html` (en `<html>`), `legajos/templates/legajos/ciudadano_confirmar_form.html`, `ciudadano_edit_form.html`, `ciudadano_manual_form.html`, `derivar_programa.html`, `historial_contactos_simple.html`, `templates/legajos/alertas_dashboard.html`, `users/templates/rol/rol_form.html` | quitar del `<html>`; `bg-secondary` en forms |
| `hover:bg-gray-50` | `static/custom/js/alertas_websocket.js` | FE-25 |
| `bg-gray-200` | `configuracion/templates/configuracion/programa_wizard_paso{1,2,3,4}.html`, `secretaria_form.html`, `secretaria_confirm_delete.html`, `subsecretaria_form.html`, `subsecretaria_confirm_delete.html`, `legajos/templates/legajos/historial_contactos_simple.html`, `legajos/templates/legajos/programas/programa_detail.html`, `static/custom/js/alertas_websocket.js` | `btn-nodo btn-tertiary btn-base` |
| `hover:bg-gray-200` | `legajos/templates/legajos/historial_contactos_simple.html` | ídem |
| `bg-gray-300` | `configuracion/templates/configuracion/{localidad,municipio,provincia}_{form,confirm_delete}.html`, `users/templates/rol/rol_form.html` | `btn-nodo btn-tertiary btn-base` |
| `hover:bg-gray-300` | `configuracion/templates/configuracion/programa_wizard_paso{1,2,3,4}.html`, `secretaria_{form,confirm_delete}.html`, `subsecretaria_{form,confirm_delete}.html`, `static/custom/js/alertas_websocket.js` | ídem |
| `bg-gray-400` | `templates/legajos/alertas_dashboard.html` | `badge badge-gray` |
| `hover:bg-gray-400` | `configuracion/templates/configuracion/{localidad,municipio,provincia}_{form,confirm_delete}.html`, `users/templates/rol/rol_form.html` | `btn-nodo btn-tertiary btn-base` |
| `bg-gray-500` | `legajos/templates/legajos/dashboard_contactos_simple.html`, `historial_contactos_simple.html`, `red_contactos_simple.html`, `reportes.html` | `btn-nodo btn-secondary btn-sm` + `fa-arrow-left` o `page_header` con `volver_url` |
| `bg-gray-600` | `templates/legajos/alertas_dashboard.html` | `btn-nodo btn-secondary btn-sm` |
| `hover:bg-gray-600` | `legajos/templates/legajos/dashboard_contactos_simple.html`, `historial_contactos_simple.html`, `red_contactos_simple.html` | ídem |
| `hover:bg-gray-700` | `templates/legajos/alertas_dashboard.html` | ídem |
| `bg-gray-900/80` | `templates/includes/sidebar/base.html` (backdrop móvil) | `bg-black/50` |
| `bg-white/78`, `bg-white/90` | `legajos/templates/legajos/ciudadano_edit_form.html` | `bg-white` o sacar el hero (V5A-NEW-04) |
| `border-fg-brand` | `programas/templates/programas/dispositivos/legajo/detail.html` (`fg-brand` es color de texto) | `border-brand` |
| `divide-border` | `programas/templates/programas/dispositivos/config/_tipo_detail_content.html`, `config/tipo_list.html`, `legajo/list.html` | `divide-y` + `[&>*]:border-light` o `nodo-td` (FE-12). Hoy no rompe: cae al borde por defecto del preflight |
| `mt-px`, `w-40` | `programas/templates/programas/becas/cupo/segmento_detail.html` | **son utilidades válidas: falta regenerar el build** (V5A-NEW-01) |
| `badge-nodo` | `legajos/templates/legajos/programas/programa_detail.html` | `badge` (la clase base) |

## B. Markup Bootstrap/AdminLTE sin CSS, en templates vivos (WARN de CLASSDEF)

| Clase | Template | Se resuelve en |
|---|---|---|
| `app-content`, `app-content-header`, `container-fluid`, `row`, `col-sm-9`, `col-sm-3`, `float-sm-end` | `templates/includes/main.html` | FE-20 (migrar sus 17 consumidores y borrar el shell) |
| `error-page`, `headline`, `error-content`, `align-items-center` | `templates/403.html`, `404.html`, `500.html` | FE-20 (V5A-NEW-03) |

## C. En templates o JS muertos (se van con FE-14, SEC-19 y LEG-06)
- `legajos/templates/legajos/historial_contactos.html`: `row`, `col-*`, `d-flex`, `justify-content-between`, `form-check*`,
  `form-label`, `g-3`, `modal-lg`, `spinner-border*`, `w-100`, `fade`, `align-items-start`.
- `templates/components/widget_contactos.html`: `list-group*`, `btn-outline-primary`, `h-100`, `col-6`, `loading-spinner`.
- `legajos/templates/legajos/dashboard_simple.html`: `row`, `col-12`, `col-md-6`.
- JS huérfanos: `registros_erroneos.js`, `ciudadanosarchivosform.js`, `global_pagination.js`, `custom.js`,
  `configuraciones.js`, `perfilchangepassword.js`, `alertas_conversaciones_simple.js`, `conversaciones_tiempo_real.js`,
  con `btn-success`, `modal-dialog-centered`, `page-item`, `page-link`, `text-muted`, `text-dark`, `list-unstyled`,
  `users-list-*`, `was-validated`, `animate-slide-in`.
- `mobile-enhancements.js` (FE-01): `is-mobile|tablet|desktop`, `touch-friendly`, `lazy`, `scroll-indicator`.

## D. Fuera de alcance (anotado para quien retome)
- Conversaciones: `bg-gray-50/200/600`, `hover:bg-gray-50`, `contador-mensajes`, `evaluacion-btn`,
  `js-cerrar-conversacion`, `notif-conv-lista`, `notificacion-*` (se van con el apagado de conversaciones, G1-01 fase 2).
- Portal ciudadano (`static/custom/js/portal-effects.js`, que carga `portal/base.html`): `bg-gray-200` y un tooltip
  `text-white bg-gray-900`, o sea **invisible**.

## E. Falsos positivos a contemplar en la regla
- `templates/core/performance_dashboard.html` (`row`, `col-*`, `card-outline`, `text-muted`, `text-dark`) carga su propio
  bootstrap y adminlte: CLASSDEF debe sumar al universo los CSS que el template enlaza con `{% static '….css' %}`.

## F. Hooks de JS (allowlist `scripts/design_audit_hooks.txt`, no son bugs)
`tab-content`, `dj-message`, `g-recaptcha`, `grupo-grip`, `item-grip`, `pregunta-grip`, `sortable-placeholder` (el
placeholder de Sortable queda sin estilo: menor), `cap-check`, `cap-item`, `cap-tab-btn`, `cap-tab-panel`,
`contador-modulo`, `tab-select-all-btn`, `roles-panel`, `cons-grupo`, `revealed`.

## Build committeado contra build fresco (V5A-NEW-01)

Build fresco con el `tailwindcss 3.4.19` del repo sobre el árbol limpio, comparado con `static/custom/css/tailwind.css`
(último build `7b22954`, 22-sep; `mt-px` y `w-40` entraron el 30-sep en `aac430c`):

| Qué | Clases |
|---|---|
| Faltan en el committeado | `mt-px` y `w-40` (usos reales). `bg-info-soft` solo aparece en un `{% comment %}` de `segmento_list.html:84` |
| Sobran en el committeado (12, sin uso actual) | `border-[color:var(--border-success-subtle)]`, `bottom-5`, `focus:border-brand`, `focus:ring-1`, `h-[46px]`, `hover:opacity-70`, `hover:text-fg-warning`, `max-w-[1180px]`, `right-5`, `text-[11px]`, `w-[46px]`, `z-[200]` |

Cómo repetir la comparación (worktree limpio): copiar `static/custom/css/tailwind.css` a `tailwind.committeado.css`,
correr `npm ci && npm run build:tailwind` y después
`python poc/herramientas/cssclasses.py tailwind.committeado.css static/custom/css/tailwind.css` (imprime lo que hay
solo en cada uno). Desde la Ola 6 lo hace el gate de CI (`git diff --exit-code static/custom/css/tailwind.css`).
