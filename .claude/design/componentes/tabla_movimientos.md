# Componente · Tabla de movimientos de stock (`components/_tabla_movimientos.html`)

**Clasificación:** Canónico reutilizable. Una fila por movimiento de stock, ya en texto.
**Evidencia:** `templates/components/_tabla_movimientos.html`,
`programas/templates/programas/dispositivos/edificios/operativo/_stock.html` (consumidor),
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

## Prohibido

- Armar las filas en el template.
- Mostrar la cantidad solo con color.
