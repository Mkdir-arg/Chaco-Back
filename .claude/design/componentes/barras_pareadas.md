# Componente · Gráfico de barras pareadas (`components/_barras_pareadas.html`)

**Clasificación:** Canónico reutilizable. Compara dos series por período (casos nuevos y familias alojadas por
día, ingresos y egresos) con dos barras por período, leyenda con totales y tabla equivalente.
**Evidencia:** `templates/components/_barras_pareadas.html`, `static/custom/css/nodo-barras.css` (lo carga el
shell del backoffice), filtro `resumen_barras` de `core/templatetags/nodo_ui.py`,
`core/tests/test_nodo_ui_piezas.py` (`BarrasPareadasTest`).
**Consumidores previstos:** el bloque «Evolución» de la situación de Emergencia (E8) y «Ingresos y egresos» del
tablero de Dispositivos.

## Por qué sin librería

Lo dibuja el servidor con HTML y CSS: funciona sin JS, se imprime y no abre la CSP. Chart.js queda en el
dashboard de Becas (dominio propio, no molde). Una serie temporal de dos valores por período no necesita
interacción: el detalle de cada par está en su `title` y en la tabla.

## Invocación

```django
{% include "components/_barras_pareadas.html" with id="evolucion" titulo="Evolución de los últimos 7 días" serie_a="Casos nuevos" serie_b="Familias alojadas" periodo="Día" periodos=situacion.evolucion only %}
```

| Parámetro | Efecto |
|---|---|
| `periodos` | Lista de dicts armada **en la vista o el selector**, en orden: `etiqueta` (fila de la tabla y `title` del par), `a` y `b` (enteros; `None` cuenta 0), `eje` opcional (rótulo corto bajo el par; por defecto `etiqueta`) |
| `serie_a` / `serie_b` | Nombres de las series: leyenda, encabezados de la tabla y descripción de cada par. `a` va en color de marca, `b` en gris neutro |
| `titulo` | Nombre accesible del gráfico (`role="img"` + `aria-label` con los totales) y `caption` de la tabla |
| `id` | Opcional, prefijo de los `id` (por defecto `barras`). Distinto por gráfico si hay más de uno en la página |
| `periodo` | Opcional, encabezado de la primera columna (por defecto «Período») |
| `tabla_abierta` | Opcional, `True` deja la tabla desplegada |

Render: eje Y con tope, medio y 0 (`aria-hidden`); área de 176 px con guías punteadas en el tope y el medio;
un `.nodo-barras__par` por período con dos `.nodo-barras__barra` cuya altura viaja como custom property
(`style="--alto:50%"`), la única forma admitida de pasar un número del servidor; rótulos del eje X; leyenda
`Serie · total`; y `<details class="nodo-barras__tabla">` «Ver la tabla de datos» con la tabla densa canónica
(período, serie A, serie B y fila Total). En impresión la tabla sale desplegada (`::details-content`).

Escala (`resumen_barras`): el tope es el máximo de las dos series redondeado hacia arriba a par, así la guía del
medio es entera. Con todo en cero el tope es 0, las barras quedan vacías y no se divide.

Colores: `--serie-a: var(--bg-brand)` y `--serie-b: var(--color-gray-500)` (contraste ≥ 3:1 sobre blanco),
declarados en `.nodo-barras`. La serie se distingue también por la posición fija (A a la izquierda) y por la
leyenda; los números viajan en texto en la tabla.

## Reglas

- **Todos los períodos de la ventana llegan**: un día sin datos va con `a=0, b=0`. La pieza no rellena huecos.
- Los números llegan contados (agrupados en Python si son fechas: nada de `TruncDate` en ECOM).
- El texto es el portador: la tabla equivalente va siempre; el gráfico la refuerza.
- Va dentro de una surface, debajo de su `h2`; la pieza no trae título visible.

## Prohibido

- Barras con `style="height:…"` o colores en hex: la altura es `--alto` y el color, la clase de la serie.
- Más de dos series o una sola: eso es otra pieza.
- Quitar la tabla equivalente u ocultarla con `hidden`.
