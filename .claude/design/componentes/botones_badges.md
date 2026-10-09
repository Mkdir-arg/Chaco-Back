# Componente · Botones y badges NODO

**Clasificación:** Canónico reutilizable.
**Evidencia:** `static/custom/css/nodo-buttons.css`, `static/custom/css/nodo-badges.css`
(las dos cargadas desde `templates/includes/base.html`), `static/custom/js/nodo-tooltips.js`.

## Botones

Siempre **`btn-nodo` + variante + tamaño**.

| Variante | Cuándo |
|---|---|
| `btn-brand` | Acción principal del bloque (guardar, crear, enviar) |
| `btn-secondary` | Acción del encabezado de un detalle, exportes, acciones de apoyo |
| `btn-tertiary` | Cancelar, volver, limpiar, acciones auxiliares |
| `btn-danger` | Destrucción o rechazo |

| Tamaño | Dónde |
|---|---|
| `btn-base` | Acciones del encabezado en **listados y formularios**, pie de formulario y de modal |
| `btn-sm` | Acciones del encabezado en **detalles**, acciones dentro de una fila o de una card |
| `btn-xs`, `btn-lg`, `btn-xl` | Existen; fuera de los dos casos de arriba son novedad |

- Ícono + texto en las acciones visibles; el ícono va `aria-hidden="true"`.
- Deshabilitado: `disabled` en `<button>`; en un `<a>`, `aria-disabled="true"` (mismo aspecto que
  `:disabled` pero sigue alcanzable por teclado para anunciar su `aria-describedby`). El bloqueo
  del click va en el handler.
- `btn-tertiary.btn-back-circle` es el botón circular de volver: lo pone `{% page_header %}`, no
  se escribe a mano.
- **Área táctil:** `@media (pointer: coarse)` lleva `.btn-nodo` y `.nodo-icon-btn` a 44 px de mínimo. Con
  mouse manda el alto del tamaño (`btn-base` 40 px, `btn-sm` 36 px): no se fuerza desde JS ni desde el
  template.
- **`.hidden` gana sobre `btn-nodo`:** la hoja declara `.btn-nodo.hidden, .nodo-icon-btn.hidden
  { display: none }` porque se carga después de Tailwind y, con la misma especificidad, `display:
  inline-flex` le ganaba por orden (el «Cancelar» que `ModernModal` esconde se veía igual).

### Variante `btn-fit` (sin ancho mínimo)

`btn-nodo btn-secondary btn-sm btn-fit`: anula **solo** el `min-width` del tamaño (`btn-xs` 128 px …
`btn-xl` 186 px); el botón mide su contenido más el padding. Alto, padding, radio, tipografía, hover,
disabled y foco son los del tamaño y el tono elegidos, y se combina con cualquiera de los dos.

- **Se usa** en headers densos (3 o más acciones) y en botones dentro de celdas de tabla.
- **No se usa** en formularios ni en la acción principal de una pantalla: ahí manda el `min-width`.
- El `min-width` del sistema no se toca; sin `btn-fit`, ningún botón cambia.
- La regla vive en `nodo-buttons.css`, después de los tamaños (misma especificidad: gana por orden)
  y **antes** del bloque `@media (pointer: coarse)`, que es deliberado: en pantalla táctil ese bloque
  le gana y el botón sigue midiendo 44 px de área táctil (WCAG 2.5.8). Por eso tampoco se sube la
  especificidad a `.btn-nodo.btn-fit`: le ganaría y se perderían esos 44 px.
- Declara `min-width: auto`, **no `0`**. El botón no lleva `white-space: nowrap` ni `flex-shrink: 0`,
  así que con `0` dentro de un header flex sin `flex-wrap` se comprimiría por debajo de su texto: la
  etiqueta se parte en dos líneas y rompe el alto fijo. `auto` anula igual el mínimo del tamaño, pero
  no deja que el contenido se rompa.
- **A 640 px o menos no hace nada**: ahí los cinco tamaños ya valen `min-width: 0` por su propio
  bloque responsive.

### Acción de fila (botón de ícono)

`.nodo-icon-btn` y `.nodo-icon-btn--danger`: contrato completo en la ficha `tabla.md`
(`aria-label` obligatorio y con el registro, ícono con `aria-hidden`, foco con el anillo de
marca).

## Badges

`badge` + variante, **siempre con texto además del color**.

| Variante | Significado habitual |
|---|---|
| `badge-success` | Activo, aprobado, validado |
| `badge-warning` | Pausado, vencido, enviado a la espera de resolución, advertencia |
| `badge-danger` | Rechazado |
| `badge-gray` | Inactivo, dado de baja, contador inactivo de una solapa |
| `badge-info` | Contador de la solapa activa |
| `badge-white` | Chip de alcance sobre fondo de color |
| `badge-brand` | Acento de marca |

- Para estados principales, `badge-dot` agrega el punto: `badge badge-success badge-dot`.
- **Pausado nunca es `danger`** y apagado es gris, no rojo.
- `badge-sm` es solo geometría; en pantalla nueva no hace falta. El alias `badge-nodo` que acompañaba a
  `badge-sm` en plantillas legacy **ya no existe en ningún template** (FE-06): la clase base es `badge`.
- El mapeo estado → variante **no se escribe en la pantalla**: vive en el parcial de badges del
  módulo (ficha `dominio/becas.md`, sección «Mapa de estados»).

## Prohibido

- `btn` de Bootstrap (`btn btn-primary`), botones con utilidades sueltas o sin tamaño.
- Badges con `bg-*`/`text-*` crudos en vez de la variante.
- Color como único indicador de estado.
- Comentarios CSS rotos en `static/custom/css/nodo-badges.css`: un `*/` de más llegó a anular
  `.badge-gray` entera.
