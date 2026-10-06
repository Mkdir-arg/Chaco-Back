# Componente · Tabla densa y acción de fila

**Clasificación:** Canónico reutilizable.
**Evidencia:** `static/custom/css/nodo-tables.css` y `static/custom/css/nodo-buttons.css`
(cargadas desde `templates/includes/base.html`), `static/custom/js/nodo-tooltips.js`.
**Consumidores de referencia:** `programas/templates/programas/becas/revision/personas_list.html`
(primer consumidor de las clases de tabla y del botón de ícono),
`programas/templates/programas/becas/_resumen_ciudadano.html` (resumen de Becas del ciudadano,
reusado por la solapa del legajo), `programas/templates/programas/becas/reportes/reporte.html`.

## Contrato

```django
<div class="overflow-x-auto">
  <table class="w-full border-collapse">
    <thead>
      <tr class="nodo-thead-row">
        <th class="nodo-th">Columna</th>
        <th class="nodo-th text-center">Centrada</th>
        <th class="nodo-th text-right w-28"><span class="sr-only">Acciones</span></th>
      </tr>
    </thead>
    <tbody>
      <tr class="hover:bg-secondary">
        <td class="nodo-td text-heading font-medium">…</td>
        <td class="nodo-td text-center">…</td>
        <td class="nodo-td text-right">…</td>
      </tr>
    </tbody>
  </table>
</div>
```

- Fila de encabezado `<tr class="nodo-thead-row">`: fondo `--bg-secondary` y borde inferior
  `--border-base`.
- `<th class="nodo-th">`: 11 px, bold, mayúsculas, tracking .05em, `--text-body-subtle`,
  padding 11px 16px, alineado a la izquierda.
- `<td class="nodo-td">`: `--font-size-sm`, padding 13px 16px, borde superior `--border-light`.
- Padding, tamaño, color y alineación de `th` y `td` están en `:where()` (especificidad cero):
  una utilidad en el mismo elemento los reemplaza (`text-center`, `text-right`, `px-3`,
  `text-body`, `text-heading font-medium`). Peso, mayúsculas, tracking y bordes quedan en la clase.
- Wrapper `overflow-x-auto`; tabla `w-full border-collapse`; filas `hover:bg-secondary`
  (opcionalmente `transition`); links de entidad `text-fg-brand hover:underline`.
- La columna de acciones **no lleva el `<th>` vacío**:
  `<th class="nodo-th text-right"><span class="sr-only">Acciones</span></th>`, porque una columna
  sin nombre no se anuncia.
- Iniciales de una persona en la fila:
  `w-8 h-8 rounded-full bg-brand-soft text-fg-brand flex items-center justify-center text-xs font-bold flex-shrink-0`
  con `aria-hidden="true"`. Nunca `var(--gradient-brand)`: un solo acento por bloque.

## Acción de fila (`.nodo-icon-btn`)

```django
<a href="{% url '<app>:<detalle>' obj.pk %}?next={{ request.get_full_path|urlencode }}"
   class="nodo-icon-btn" aria-label="Ver <entidad> de {{ obj.nombre }} {{ obj.apellido }}">
  <i class="fas fa-eye" aria-hidden="true"></i>
</a>
```

- `inline-flex`, padding 6px, `rounded-lg`, gris `--text-body-subtle` en reposo; al pasar, fondo
  `--bg-secondary` y color `--text-fg-brand`. `.nodo-icon-btn--danger` pasa a `--text-fg-danger`
  para lo destructivo.
- Foco de teclado con el anillo de marca (`outline 2px var(--border-brand)`, offset 2px), no el
  del navegador.
- Solo ícono Font Awesome con `aria-hidden="true"`; **`aria-label` obligatorio y con el
  registro** («Ver caso de Ana Pérez», no «Ver»), que `static/custom/js/nodo-tooltips.js` muestra
  al pasar el mouse o con el foco.
- Deshabilitado: `disabled` en `<button>`, `aria-disabled="true"` en `<a>`; el ícono queda
  `--text-fg-disabled` sin caja, con un selector que le gana al `button:disabled` de
  `static/custom/css/nodo-brand.css`. En `.btn-nodo` y `.btn-tertiary`, `aria-disabled="true"`
  tiene el mismo aspecto que `:disabled` pero sigue alcanzable por teclado, para que se anuncie
  su `aria-describedby`; el bloqueo del click va en el handler.
- Sirve en `<a>` y en `<button type="button">`: el color resuelve por variable y le gana a la
  cascada de `static/custom/css/nodo-brand.css`.
- Ver = `fa-eye`. Varias acciones en la misma celda: `<div class="inline-flex items-center gap-1">`.

## Prohibido

- `<thead style=…>`, `th` con `style="font-size:11px"` o con la lista de utilidades por celda.
- `divide-y`, `hover:bg-tertiary`, bordes propios por fila.
- Cards repetidas por registro cuando el usuario compara filas.
- «Ver detalle» como botón con texto dentro de la fila.
- `aria-label` genérico en el botón de ícono.
- Mapear estado a color dentro de la pantalla: va en el parcial de badges del módulo.

## Deuda conocida

`programas/templates/programas/becas/config/_segmentos_table.html` sigue con las utilidades en
línea (mismo resultado visual): se migra al tocarla, no se copia.
