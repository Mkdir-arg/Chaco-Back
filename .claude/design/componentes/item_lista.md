# Componente · Ítem de lista de selección (`components/_item_lista.html`)

**Clasificación:** Canónico reutilizable. Botón de ancho completo con nombre, dato secundario y badge de nivel;
varios, uno bajo otro, son la lista que acompaña a un mapa o a un panel.
**Evidencia:** `templates/components/_item_lista.html`, `static/custom/css/nodo-item-lista.css` (lo carga el
shell) y `core/tests/test_nodo_ui_piezas.py` (`ItemListaTest`).
**Consumidores:** «Localidades con más presión» de la solapa Mapa de la Situación de Emergencia (E8,
`programas/templates/programas/emergencia/situacion/_capas_mapa.html`, con `data-item` que sincroniza
`_mapa_capas.html`); previsto «Más tensionados» del tablero de Dispositivos.

## Por qué no es una tabla ni `lista_tarjetas`

Una tabla es para comparar columnas; acá hay **una sola elección** y el ítem es el control. La lista de tarjetas
(`lista_tarjetas.md`) navega a otra pantalla; esta **selecciona** y deja a la pantalla mostrar el detalle. Es la
alternativa por teclado del mapa, que no es operable sin mouse.

## Invocación

```django
<div role="group" aria-label="Localidades con más presión" class="flex flex-col gap-1">
  {% for l in presion %}
    {% include "components/_item_lista.html" with nombre=l.nombre meta=l.meta dato=l.dato_badge etiqueta=l.etiqueta tono=l.tono clave=l.id only %}
  {% endfor %}
</div>
```

La envoltura es del consumidor (`role="group"` con `aria-label`; el vacío es el estado vacío de la pantalla).

| Parámetro | Efecto |
|---|---|
| `nombre` | Texto principal, una línea; si es largo se recorta con «…» y el `title` lo dice completo |
| `meta` | Opcional, dato secundario bajo el nombre |
| `dato` | Opcional, cifra visible del badge («6,5×»). Con `etiqueta`, el nivel va `sr-only` |
| `etiqueta` | Opcional, nivel en palabras (`Tension.etiqueta`). Sin `dato`, va visible |
| `tono` | Opcional, `Tension.tono`: `success`, `warning`, `danger`; otro o ausente, `gray` |
| `clave` | Opcional, `data-item` para el JS del consumidor |
| `activo` | Opcional, True: seleccionado al cargar |

Sin `dato` ni `etiqueta` no hay badge.

| Tono | Badge | Ícono |
|---|---|---|
| success | `badge-success` | `fa-circle-check` |
| warning | `badge-warning` | `fa-triangle-exclamation` |
| danger | `badge-danger` | `fa-circle-exclamation` |
| otro | `badge-gray` | `fa-circle-minus` |

## Selección y teclado

- Es un `<button type="button" aria-pressed>`: Tab lo recorre, Enter y Espacio lo activan sin JS propio, y el foco
  se ve (`:focus-visible`, contorno de marca).
- El estado seleccionado es **`aria-pressed="true"`**; el CSS pinta `[aria-pressed="true"]`
  (`--bg-info-soft` + borde `--border-info-subtle`). El consumidor, al hacer clic, deja `true` solo en el elegido
  (uno a la vez), abre o llena el panel y centra el mapa; no maneja clases.
- Sin JS la lista se ve completa (nombre, dato y badge); lo que no anda es la selección.
- En alto contraste el seleccionado se marca con un contorno `Highlight` hacia adentro (`outline-offset: -2px`,
  no cambia el tamaño del ítem).

## Reglas

- **El nivel no se calcula en el template.** `tono`, `etiqueta` y `dato` llegan de la vista.
- El color nunca va solo: ícono + cifra o texto en el badge.
- Los nombres llegan escapados por Django; no se marcan `|safe`.

## Prohibido

- Alternar una clase `is-active` o similar: el estado es `aria-pressed`.
- Poner el ítem dentro de un `<a>` o usarlo para navegar (eso es un enlace).
- Estilos propios del ítem en la pantalla.
