# Componente · Stat card / franja de métricas (`components/_stat_card.html`)

**Clasificación:** Canónico reutilizable. Pieza única.
**Evidencia:** `templates/components/_stat_card.html`, `core/tests/test_nodo_ui_piezas.py`.
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
| `tono` | `brand` (por defecto), `success`, `warning`, `danger`: color de la caja del ícono, **según significado** |

Render: card `bg-white rounded-xl border border-base p-4` (sin sombra); fila superior
`flex items-center justify-between gap-2` con la etiqueta y el ícono en caja
`w-8 h-8 rounded-lg … bg-{tono}-soft text-fg-{tono}` (ícono `text-sm`, `aria-hidden`); valor
`text-2xl font-bold text-heading mt-2`.

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

- Cajas de ícono de 52 px, `var(--gradient-brand)`, valores `text-3xl` o `font-extrabold`:
  quedaron fuera del canon.
- KPIs escritos a mano con utilidades sueltas (la deuda del tablero de Becas).
- Métricas que nadie usa para decidir.
