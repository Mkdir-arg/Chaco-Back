# Componente · Lista de tarjetas para móvil (`components/_lista_tarjetas.html`)

**Clasificación:** Canónico reutilizable. La alternativa de una tabla densa a menos de `md` (768 px): una
tarjeta por registro, con las mismas acciones que la fila.
**Evidencia:** `templates/components/_lista_tarjetas.html`, `core/tests/test_nodo_ui_piezas.py`
(`ListaTarjetasTest`), `programas/tests/test_dispositivos_relevamientos_listado.py` (`TarjetasMovilTests`).
**Consumidor de referencia:** `programas/templates/programas/dispositivos/relevamientos/list.html` (P21, las
cuatro solapas). Solo usa clases y tokens que ya existen; las utilidades `md:hidden` y `hidden md:block` son
las únicas que entraron al CSS compilado.

## Cuándo usarla

- Una tabla de la lista que a 390 px obliga a desplazar de costado para leer el registro o llegar a su acción.
- **No** reemplaza a la tabla: en escritorio la tabla no cambia. Los dos bloques conviven y el CSS decide cuál
  se ve (`hidden md:block` en el wrapper de la tabla, `md:hidden` en la lista), sin JS.
- No es una grilla de tarjetas decorativa: es la misma lista, con otra forma, y sigue dentro de la card del listado.

## Invocación

```django
<div class="hidden md:block overflow-x-auto mt-3"> … la tabla de siempre … </div>
{% include "components/_lista_tarjetas.html" with tarjetas=solapa.tarjetas nombre="Relevamientos en curso" %}
{% include "components/_paginacion.html" … %}
```

| Parámetro | Efecto |
|---|---|
| `nombre` | Obligatorio. Nombre accesible de la lista (`aria-label` del `<ul>`) |
| `tarjetas` | Lista de dicts armada **en la vista** (nunca un queryset), uno por registro |

Cada tarjeta:

| Clave | Efecto |
|---|---|
| `titulo` | Obligatorio. `h3 text-sm font-bold text-heading` |
| `subtitulo` | Opcional, una línea `text-xs text-body-subtle` |
| `badges` | Lista de `{texto, tono}`; el primero es el estado (`badge-dot`). Tonos: `success`, `info`, `warning`, `danger`, `brand`; otro valor, badge neutro |
| `pares` | 2 a 4 `{etiqueta, valor, nota}` en una grilla de dos columnas; valor vacío se lee «—» |
| `accion` | Opcional, la acción principal visible: `{texto, url, icono, etiqueta, variante}` (`brand` o `secondary`). Solo navega |
| `menu`, `menu_id`, `menu_etiqueta` | Opcionales. Las demás acciones en «⋮» (`{% menu_fila %}`); cada ítem con las claves de `_menu_fila_item.html` (`texto`, `icono`, `url`, `confirm_url`, `confirm_title`, `confirm_text`, `confirm_ok`, `peligro`, `motivo`). Sin ítems no se dibuja el ⋮ |

## Reglas

- **Mismas acciones que la tabla, de una sola fuente.** La vista arma las acciones de la fila **una vez** (en
  Relevamientos, `_preparar_fila`): `accion_visible` (dict o `None`: lo que en la tabla es el botón de ícono) y
  `acciones_menu` (lista de dicts con las claves de `_menu_fila_item.html`, con `motivo` si está bloqueada). La
  tabla recorre esas listas con el include `only` y la tarjeta las reusa tal cual: no se vuelven a escribir los
  textos, íconos ni `confirm_*` en otro lado. Lo único propio de la tarjeta, explícito en la vista: **si la fila no
  tiene acción visible, la primera acción del menú que solo navega (con `url` y sin `motivo`) pasa a principal** y
  sale del menú. Una acción que muta nunca es la principal: confirma desde el menú con `ModernModal`. Un ítem
  bloqueado conserva su `motivo`, no se omite. Un test compara las listas de dicts y el HTML de los dos bloques.
- `menu_id` tiene que ser distinto del de la tabla (`tarjeta-` + el id de la fila): los dos bloques están en el
  DOM aunque uno esté oculto.
- El estado, el tono, las etiquetas y los permisos los decide la vista; el template solo traduce `tono` a la
  variante de badge. El color nunca es el único portador: el badge lleva texto.
- Los datos de otros alcances no se nombran: lo que la tabla oculta por privacidad, la tarjeta también.
- Los pares son lo mínimo para decidir sin abrir el registro; el detalle completo sigue en la pantalla del registro.
- Autoescape siempre: ningún `|safe`.

## Prohibido

- Mostrar las dos formas a la vez (la tabla a menos de `md` o la lista de `md` para arriba).
- Una acción en la tarjeta que no exista en la tabla, o con otra URL.
- Pasar un queryset o resolver reglas de dominio en el template.
- Más de 4 pares, o acciones principales múltiples: lo demás va al «⋮».
