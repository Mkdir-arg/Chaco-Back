# Componente · Partes del modal (`becas-modal.js`, `_modal_header`, `_modal_footer`)

**Clasificación:** Canónico reutilizable, **transversal**: las partes viven en Becas pero se
incluyen desde su ruta actual desde cualquier módulo, cargando `becas-modal.js` en `customJS`.
No se copian ni se renombran: `_modal_header.html` y `_modal_footer.html` cierran con
`data-becas-modal-cerrar`, que depende de ese script.
**Evidencia:** `static/custom/js/becas-modal.js`,
`programas/templates/programas/becas/_modal_header.html`,
`programas/templates/programas/becas/_modal_footer.html`,
`programas/tests/test_becas_modal.py`.
**Consumidor de referencia:** el modal «Nuevo programa» de
`programas/templates/programas/becas/config/programa_list.html` (golden del arquetipo Modal).

## Estructura

Overlay `fixed inset-0 z-50 flex items-center justify-center p-4` con `x-show` y
`x-becas-modal="<expr>"`; fondo `absolute inset-0 bg-black/50 backdrop-blur-sm` con el clic
afuera; panel
`relative bg-white rounded-2xl shadow-xl w-full max-w-[560px] max-h-[90vh] flex flex-col overflow-hidden`
con `role="dialog" aria-modal="true" aria-labelledby` apuntando al `id` del título.

Si un `<form>` envuelve cuerpo y pie, lleva `flex flex-col flex-1 min-h-0` (sus atributos, campos
y `data-ajax` no cambian); el cuerpo lleva `overflow-y-auto min-h-0` y el header y el pie
`flex-shrink-0`, así el pie queda siempre a la vista en pantallas bajas.

## `_modal_header.html`

| Parámetro | Efecto |
|---|---|
| `titulo` | Texto del `h3` |
| `titulo_id` | `id` al que apunta el `aria-labelledby` del panel |
| `icono` | Font Awesome |
| `tono` | `brand` (por defecto), `danger`, `warning`, `success` |
| `cerrar` | Expresión Alpine de cierre |
| `titulo_x_text` | Expresión Alpine que reemplaza el texto del `h3` en vivo, sin parpadeo (el modal arranca con `x-cloak`); sirve para alternar Nuevo/Editar |
| `subtitulo` | Línea chica debajo del título |

Render: `flex items-center gap-3 px-6 py-5 border-b border-light`, caja
`w-10 h-10 rounded-lg bg-brand-soft text-fg-brand` (o el par tonal), `h3 text-lg font-bold
text-heading` (envuelto junto al subtítulo en `flex-1 min-w-0`) y la X
`p-1.5 rounded-lg text-body-subtle hover:text-heading hover:bg-secondary` con `aria-label="Cerrar"`.

## `_modal_footer.html`

| Parámetro | Efecto |
|---|---|
| `cancelar` | Expresión Alpine de cierre |
| `cancelar_texto` | Texto del botón de cancelar |
| `accion_texto` | Texto de la acción |
| `accion_icono` | Ícono de la acción |
| `accion_tono` | `brand` (por defecto) o `danger` |
| `form_id` | Apunta con `form=` a un `<form>` de afuera del pie |

Render: `flex justify-end gap-3 px-6 py-4 border-t border-light bg-secondary`, Cancelar
`btn-nodo btn-tertiary btn-base` y acción `btn-nodo btn-brand btn-base` (o `btn-danger`).

## `x-becas-modal` (comportamiento)

El atrapado del foco es un helper propio: **no** se usa `@alpinejs/focus`.


Se registra en `alpine:init`; el script va como `<script>` clásico en `customJS`, que corre antes
que Alpine con `defer`. Al abrir guarda el foco, lo mueve a `[autofocus]`, si no al primer campo,
si no al primer control; atrapa Tab y Shift+Tab dentro del panel; bloquea el scroll del fondo en
`<html>` y `<body>`; Escape hace `<expr> = false`; al cerrar devuelve el foco. Si el foco está en
otro diálogo encima (SweetAlert2, `ModernModal`), no intercepta el teclado.

**Modales sin Alpine:** `window.becasModal.bind(overlay, {onClose})` observa la clase `hidden` o
el `style.display` del overlay; Escape o cualquier `[data-becas-modal-cerrar]` llaman a `onClose`
(sin él, agregan `hidden`).

**Modal anidado:** el de arriba atrapa Tab y Escape; el de abajo queda quieto.

## Prohibido

- Un modal propio sin `role="dialog"`, `aria-modal="true"` y `aria-labelledby`.
- Overlay con `style="backdrop-filter:blur(4px)"`: la clase compilada es `backdrop-blur-sm`.
- Overlay dentro del `space-y-*` de la página (el `margin-top` lo corre y el clic en esa franja
  no cierra).
- Reescribir el header o el pie a mano en vez de incluir las partes.
