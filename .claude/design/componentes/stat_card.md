# Componente · Stat card / franja de métricas (`components/_stat_card.html`)

**Clasificación:** Canónico reutilizable. Pieza única.
**Evidencia:** `templates/components/_stat_card.html`, `static/custom/css/nodo-stat-card.css`,
`core/tests/test_nodo_ui_piezas.py`.
**Consumidores de referencia:** `programas/templates/programas/becas/cupo/segmento_detail.html`
(la franja de la golden de detalle),
`programas/templates/programas/becas/relevamientos/convocatoria_detail.html`.

## Invocación

```django
<div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
  {% include "components/_stat_card.html" with etiqueta="Cupo máximo" valor=stats.cupo_maximo icono="fa-users" tono="brand" %}
  {% include "components/_stat_card.html" with etiqueta="Cupo ocupado" valor=stats.cupo_ocupado icono="fa-circle-check" tono="success" %}
  {% include "components/_stat_card.html" with etiqueta="Cupo disponible · sin cupo" valor=stats.cupo_disponible icono="fa-ban" tono="danger" %}
</div>
```

| Parámetro | Efecto |
|---|---|
| `etiqueta` | Rótulo corto, `text-xs font-semibold text-body-subtle` |
| `valor` | Número o texto corto **ya formateado** |
| `icono` | Font Awesome sin `fas`; por defecto `fa-chart-simple` |
| `tono` | `brand` (por defecto), `success`, `warning`, `danger`: color de la caja del ícono, **según significado** (la variante tablero lo ignora) |
| `variante` | `tablero` para la versión grande (ver *Variantes*). Sin ella, o con cualquier otro valor, es la chica |

Opcionales, para los tableros cuyos números escribe un JS (`becas-dashboard.js`). **Sin
ninguno de ellos el render es exactamente el de arriba**, carácter por carácter, y hay un
test que lo fija contra todas las invocaciones del repo:

| Parámetro | Efecto |
|---|---|
| `kpi_id` | marca el valor con `data-kpi="<kpi_id>"` para que el JS lo refresque |
| `sufijo` | texto corto pegado al valor (« %», « / »), en `text-sm text-body-subtle font-semibold` |
| `sufijo_id` | segundo número dentro del sufijo, también con `data-kpi`: el «M» de un valor compuesto «N / M». Su texto inicial sale de `valor_sufijo` («—») |
| `nota` | pie de tarjeta: `text-xs text-body-subtle mt-1` |
| `nota_id` | `data-kpi` del pie, cuando lo escribe el JS (ahí `nota` va vacía) |

**Con `sufijo`/`sufijo_id`, `kpi_id` marca un `<span>` y no el `<p>`:** el JS asigna
`textContent`, que sobre el `<p>` entero borraría el sufijo.

Render: card `bg-white rounded-xl border border-base p-4` (sin sombra); fila superior
`flex items-center justify-between gap-2` con la etiqueta y el ícono en caja
`w-8 h-8 rounded-lg … bg-{tono}-soft text-fg-{tono}` (ícono `text-sm`, `aria-hidden`); valor
`text-2xl font-bold text-heading mt-2`.

## Variantes (CMP-23)

La pieza tiene **dos tamaños declarados**. No es decoración: cada uno tiene su lugar.

| | Chica (por defecto) | Grande · `variante="tablero"` |
|---|---|---|
| Cuándo | listados, detalles y franjas dentro de un contenido | tableros y pantalla de inicio de programa: la franja de métricas que **encabeza** la pantalla |
| Caja de ícono | `w-8 h-8 rounded-lg`, color por `tono` | 52 px, radio 12, ícono blanco sobre `var(--gradient-brand)` (el `tono` no aplica) |
| Valor | `text-2xl font-bold` (24 px) | 32 px / peso 800 |
| Sombra | ninguna | `shadow-sm` |
| Reglas | utilidades de Tailwind | `static/custom/css/nodo-stat-card.css` (`.nodo-stat-tablero*`) |

Regla de uso: **una sola franja grande por pantalla**, y la grande nunca convive con la chica en
la misma franja. Los opcionales (`kpi_id`, `sufijo`, `nota`…) valen en las dos. El ícono se sigue
pasando por nombre de Font Awesome.

**Inicio (`templates/inicio.html`) — deuda abierta.** Sus cuatro tarjetas **no usan esta pieza**:
están escritas a mano con un `.stat-card` local (líneas 84-130) y el gradiente puesto con
`style=` inline en el marcado (línea 464 y siguientes), que es exactamente lo que la sección
*Prohibido* no admite. Es el caso que dio origen a CMP-23.

No se migra en esta task **por alcance, no porque no haga falta**: el inicio es la portada general
del sistema, no un tablero de programa, y cambiarlo de aspecto es una decisión del PM. Ahora que la
variante existe, la migración es reemplazar ese bloque por cuatro `{% stat_card %}` con
`variante="tablero"` y borrar el CSS local. Queda como deuda con nombre.

**La grilla la arma el consumidor:** `grid grid-cols-2 gap-3`, `grid-cols-1 sm:grid-cols-3 gap-4`,
lo que corresponda.

## Reglas

- Solo para números o estados de **alto valor operativo**: no es decoración.
- El número se calcula en la vista o el selector, nunca en el template (ni `|length` sobre un
  queryset, ni `.count()` repetido).
- El tono cambia con el significado (sin cupo = `danger`), no por variedad visual.
- El rótulo dice qué cuenta en lenguaje del usuario (en la golden, «Casos», no «Beneficiarios»,
  cuando cuenta todos los casos).

## Prohibido

- Cajas de ícono de 52 px, `var(--gradient-brand)`, valores de 32 px o peso 800 **escritos a mano**
  o con CSS local de la pantalla (el `.stat-card` viejo de Inicio): eso es CMP-23. La versión
  grande existe **solo** como `variante="tablero"`; ver *Variantes*.
- `text-3xl` o `font-extrabold` en el valor: la grande no se arma con utilidades.
- KPIs escritos a mano con utilidades sueltas (la deuda del tablero de Becas).
- Métricas que nadie usa para decidir.
- **Ranura de cuerpo.** La pieza no acepta contenido libre. Una tarjeta que necesita
  minigráfico o barra de progreso se escribe en la pantalla **con el mismo esqueleto**
  (es lo que hacen dos de las seis de `becas/config/_dashboard_panel.html`), hasta que
  exista el **arquetipo Dashboard**. No se le inventa una ranura.
