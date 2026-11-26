# Componente · Tabla de movimientos de stock (`components/_tabla_movimientos.html`)

**Clasificación:** Canónico reutilizable. Una fila por movimiento de stock, ya en texto.
**Evidencia:** `templates/components/_tabla_movimientos.html`,
`programas/templates/programas/dispositivos/edificios/operativo/_stock.html` (consumidor: panel de la solapa Stock),
`programas/templates/programas/dispositivos/stock/movimientos.html` (consumidor: listado paginado de a 25 con filtros insumo, tipo, desde y hasta),
`programas/services/edificio_stock.py`,
`core/tests/test_nodo_ui_piezas.py` (`TablaMovimientosTest`).

Va dentro de la surface del consumidor; no pone card ni paginación.

## Invocación

```django
{% include "components/_tabla_movimientos.html" with filas=stock.movimientos caption="Últimos movimientos de stock" only %}
```

| Parámetro | Efecto |
|---|---|
| `filas` | Armadas por el servicio (`fila_de_movimiento`): `fecha`, `tipo_texto`, `tipo_tono` (`gray`, `info`, `success`, `warning`, `danger`…), `insumo`, `unidad`, `cantidad_texto`, `suma`, `queda`, `quien`, `detalle` |
| `caption` | Texto para el lector de pantalla (`sr-only`) |

## Reglas

- El signo va en el texto (`cantidad_texto`: «+8» o «−3», con U+2212); el color (`text-fg-success` si `suma`,
  `text-fg-danger` si no) solo lo refuerza.
- El tipo es un `badge badge-dot badge-<tipo_tono>`. Un `detalle` vacío dibuja «—».
- Con `filas` vacío no dibuja nada: el consumidor muestra `_estado_vacio`.
- **Privacidad:** el armado de `detalle` (persona y observación solo con `ciudadano.ver`; otra institución sin
  nombre) vive en `programas/services/edificio_stock.py` (`fila_de_movimiento` y `_detalle`), no en el template.
- El panel que la consume (`contexto_de_la_solapa`) decide cada permiso **una** vez: `puede_ver_stock` está memoizado
  sobre el usuario y sin `stock.ver` no hay botones (Entregar, Ingresar, Traspasar); cada permiso por acción se decide
  una sola vez, aunque dos botones compartan capacidad. Los botones salen del servicio, nunca del template.
- `_url_de_accion` solo hace `reverse(...)`: una ruta mal escrita rompe fuerte, no esconde el botón.
- Cada fila de saldo del panel trae `item_id` y `url_ajustar`, un link GET (`?tab=stock&ajustar=<id>`), no un POST.
  Esa URL la arma **un solo helper**, `url_abrir_ajuste(dispositivo, edificio, item_id)` en
  `programas/services/edificio_stock.py`: lo usan el botón de la fila y el reintento tras `SaldoCambio` / `UuidEnUso`,
  así que los dos abren siempre el mismo modal. Nadie escribe esa URL a mano.
  Claves del contexto de la solapa: `puede_ajustar`, `url_enviar_ajuste` y `url_movimientos` (esta última solo con
  `stock.ver`).

## Prohibido

- Armar las filas en el template.
- Mostrar la cantidad solo con color.
