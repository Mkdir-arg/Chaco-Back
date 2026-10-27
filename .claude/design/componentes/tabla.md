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
- Posición, padding, tamaño, color y alineación de `th` y `td` están en `:where()` (especificidad cero):
  una utilidad en el mismo elemento los reemplaza (`text-center`, `text-right`, `px-3`,
  `text-body`, `text-heading font-medium`). Peso, mayúsculas, tracking y bordes quedan en la clase.
- Wrapper `overflow-x-auto`; tabla `w-full border-collapse`; filas `hover:bg-secondary`
  (opcionalmente `transition`); links de entidad `text-fg-brand hover:underline`.
- `:where(.overflow-x-auto)` establece `position: relative` en el wrapper compartido:
  contiene el rótulo absoluto `sr-only` de Acciones dentro del scroll, también en tablas
  legacy. Un `th` relativo por sí solo no contiene el desborde con nombres largos:
  evidencia en `dispositivos/legajo/list.html` y `dispositivos/config/tipo_list.html`.
  `:where(.nodo-th)` mantiene su posición relativa sin pisar una utilidad `sticky`.
  La verificación de navegador está en `core/tests/test_nodo_ui_piezas.py`
  (`TablaResponsiveTest`, activada con `CHACO_PLAYWRIGHT=1`).
  `DispositivosResponsiveFDTests` exige wrapper para cada tabla visible cuyo contenido no entra,
  compara capturas con y sin la posición del wrapper a 1440 px y mide ausencia de desborde
  a 390 px con nombres largos en P2, Tipos, Becas, Ciudadanos y Configuración.
- La columna de acciones **no lleva el `<th>` vacío**:
  `<th class="nodo-th text-right"><span class="sr-only">Acciones</span></th>`, porque una columna
  sin nombre no se anuncia.
- Iniciales de una persona en la fila:
  `w-8 h-8 rounded-full bg-brand-soft text-fg-brand flex items-center justify-center text-xs font-bold flex-shrink-0`
  con `aria-hidden="true"`. Nunca `var(--gradient-brand)`: un solo acento por bloque.

## DNI visible

`{% load nodo_ui %}` ofrece `{{ persona.dni|dni }}` para texto visible (por ejemplo,
`12.345.678`). Conserva ceros iniciales; los valores vacíos o no numéricos se devuelven
intactos y siguen escapándose. No se aplica a controles de formularios, atributos de
datos, URLs ni búsquedas. Evidencia: `core/templatetags/nodo_ui.py` y
`core/tests/test_dni_presentacion.py`; consumidores: P4, P6, P7 y la solapa P16.

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
- Mapear estado a color dentro de la pantalla: lo decide el módulo, en su parcial de badges o en
  el servicio/selector que entrega texto y `tono` (`badge badge-dot badge-{{ tono }}`).

## Deuda conocida

`programas/templates/programas/becas/config/_segmentos_table.html` sigue con las utilidades en
línea (mismo resultado visual): se migra al tocarla, no se copia.

## Menú de fila (`{% menu_fila %}`)

**Evidencia:** `core/templatetags/nodo_ui.py` (tag), `templates/components/_menu_fila.html` y
`_menu_fila_item.html`, `static/custom/css/nodo-menu-fila.css`, `static/custom/js/nodo-menu-fila.js`
(el shell carga los dos últimos). Tests: `core/tests/test_nodo_ui_piezas.py` (`MenuFilaTest`).
**Consumidores de referencia:** `programas/templates/programas/dispositivos/relevamientos/list.html`
(P21: ítems con `url`, `motivo` y `confirm_url` preparados en la vista; revisión sin datos con
`_confirm_js.html` y ModernModal; las acciones con formulario abren su modal por
parámetro GET; sus cuatro stat cards llevan `tono` igual al del badge de estado de la tabla). P4 (`dispositivos/legajo/detail.html`) reusa el mismo contrato para cambiar plaza
(o asignarla, si la estadía no tiene: ítem «Asignar plaza», mismo modal) y egresar: un modal por URL y capacidad, sin consultas por fila. Lo van a usar también P12, P20 y P22.

### Cuándo va cada forma

| Situación | Forma |
|---|---|
| 1 o 2 acciones, todas disponibles | `.nodo-icon-btn` sueltos, como arriba |
| 3 o más acciones | `{% menu_fila %}`; la principal («Ver») puede quedar al lado como `.nodo-icon-btn`, en el mismo `inline-flex gap-1` |
| Una acción que el usuario tiene que ver aunque hoy no pueda usarla | `{% menu_fila %}` con el ítem `motivo=`: el ícono suelto deshabilitado no tiene dónde explicar el porqué |
| Acción de una sola fila que casi siempre se usa | `.nodo-icon-btn`: no se esconde en un menú lo que se toca a cada rato |

No se mezclan las dos formas con las mismas acciones en pantallas hermanas de un mismo módulo: si
una tabla de Dispositivos usa el menú para sus acciones secundarias, las demás también.

### Esqueleto

```django
{% load nodo_ui %}
<td class="nodo-td text-right">
  <div class="inline-flex items-center gap-1">
    <a href="{% url '<app>:<detalle>' obj.pk %}" class="nodo-icon-btn" aria-label="Ver <entidad> {{ obj.nombre }}">
      <i class="fas fa-eye" aria-hidden="true"></i>
    </a>
    {% menu_fila id=obj.pk etiqueta="Acciones de <entidad> "|add:obj.nombre %}
      {% include "components/_menu_fila_item.html" with texto="Editar" icono="fa-pen" url=url_editar only %}
      {% include "components/_menu_fila_item.html" with texto="Reasignar" icono="fa-user-pen" motivo=motivo_reasignar only %}
      {% include "components/_menu_fila_item.html" with texto="Dar de baja" icono="fa-ban" peligro=True confirm_url=url_baja confirm_title="¿Dar de baja?" confirm_text="…" confirm_ok="Sí, dar de baja" only %}
    {% endmenu_fila %}
  </div>
</td>
```

El `id` (único en la página: si hay dos tablas con menús, uno de los dos lleva prefijo, p. ej. `id=obj.menu_id` preparado en la vista) y la `etiqueta` (con el registro, nunca
«Acciones» a secas) son obligatorios; el tag falla al compilar sin ellos. Url y `motivo` se
preparan en la vista (`motivo` vacío = acción disponible).

### Ítems (`_menu_fila_item.html`, siempre con `only`)

| Parámetro | Efecto |
|---|---|
| `texto` | Obligatorio. Verbo en infinitivo |
| `icono` | Opcional, Font Awesome sin `fas` |
| `url` | Enlace `<a role="menuitem">` |
| `confirm_url` + `confirm_title`/`confirm_text`/`confirm_ok` | Botón con `data-confirm-url` → `ModernModal` (contrato de `arquetipos/confirmacion.md`; la pantalla carga `_confirm_js.html`). Nunca `confirm()` |
| `peligro=True` | Ítem rojo y `data-confirm-danger="true"` |
| `motivo` | Deshabilita el ítem y muestra el motivo debajo; gana sobre `url` y `confirm_url` |

### Accesibilidad (lo que verifica el JS y lo que no se puede romper)

- El disparador es un `.nodo-icon-btn` de 28 px (44 px con puntero grueso) con `aria-label` con el
  registro, `aria-haspopup="menu"`, `aria-expanded` y `aria-controls` hacia el menú.
- Enter, Espacio o ↓ abren y enfocan el primer ítem (↑ el último). ↑/↓/Home/End mueven; Tab y
  Shift+Tab circulan **dentro** del menú. Enter y Espacio activan.
- Escape cierra y devuelve el foco al disparador. Clic afuera, scroll y resize cierran sin mover
  el foco. Activar un ítem deja el foco en el disparador antes de abrir el `ModernModal`.
- Un ítem deshabilitado lleva `aria-disabled="true"` (no `disabled`): se alcanza por teclado, se
  anuncia con su motivo y no actúa. No se esconde: esconder no es bloquear.
- Con el bloque sin ningún ítem no se dibuja ni el botón.

### Prohibido

- Un `<details>`, un `x-data` o un menú armado a mano para las acciones de fila.
- Ítems sin `only`, `confirm()` nativo, `style=` para posicionarlo (lo calcula el JS).
- `.nodo-icon-btn` deshabilitado suelto para «explicar» por qué una acción no está disponible.
