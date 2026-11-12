# Componente · Semáforo de SLA (`components/_semaforo_sla.html`)

**Clasificación:** Canónico reutilizable. Una pieza con dos variantes: el badge corto de una fila y el reloj
del tramo en la cabecera de una ficha. Dice en qué situación está un caso respecto del objetivo de su tramo.
**Evidencia:** `templates/components/_semaforo_sla.html`, `core/tests/test_nodo_ui_emergencia.py`
(`SemaforoSlaTest`).
**Consumidores previstos:** la bandeja de casos de Emergencia (columna «Tiempo en estado») y la cabecera de
la ficha del caso. Solo usa `badge` + variante de `static/custom/css/nodo-badges.css` (ficha
`botones_badges.md`): no trae CSS propio.

## Por qué una pieza y no dos

El badge de la fila y el reloj de la ficha traducen **el mismo estado**. Con dos piezas habría dos tablas
estado → tono → ícono → texto y, tarde o temprano, dos respuestas distintas para el mismo caso. La variante
cambia solo el largo del texto y el `role`.

## Invocación

```django
{% include "components/_semaforo_sla.html" with estado=sla.estado minutos=sla.minutos tramo=sla.tramo only %}
{% include "components/_semaforo_sla.html" with estado=sla.estado minutos=sla.minutos tramo=sla.tramo variante="reloj" only %}
```

| Parámetro | Efecto |
|---|---|
| `estado` | `EN_TERMINO`, `POR_VENCER` o `FUERA`, **ya resuelto** por el selector. Cualquier otro valor, o ninguno, dibuja el badge neutro «Sin SLA» |
| `minutos` | Entero ya calculado: en `EN_TERMINO` y `POR_VENCER`, los que faltan para que venza el tramo; en `FUERA`, los que lleva excedido. Sin él (None o vacío) el texto no lleva minutos; un 0 se muestra |
| `texto_tiempo` | Opcional: los mismos minutos ya escritos para leerse cuando son muchos («5 h», «3 d»), tal como los arma el selector (`EstadoSLA.texto_tiempo`). Reemplaza a «N min» solo si además llegan los `minutos`; sin él, el HTML es el de siempre |
| `tramo` | Opcional: el tramo en curso («tomar», «derivar», «aceptar», «alojar»). Solo lo usa el reloj; se presenta con mayúscula inicial venga como venga |
| `variante` | `reloj` para el texto largo con `role="status"`. Sin ella, o con otro valor, es el badge corto |

## Qué dibuja

| Estado | Variante de badge | Ícono | Badge corto | Reloj |
|---|---|---|---|---|
| `EN_TERMINO` | `badge-success` | `fa-circle-check` | «En término · 12 min» | «Derivar vence en 8 min» |
| `POR_VENCER` | `badge-warning` | `fa-clock` | «Por vencer · 3 min» | «Por vencer · Derivar vence en 3 min» |
| `FUERA` | `badge-danger` | `fa-triangle-exclamation` | «Fuera de SLA · 42 min» | «Derivar · Fuera de SLA · 42 min» |
| otro | `badge-gray` | `fa-circle` | «Sin SLA» | «Sin SLA» |

Render: `<span class="badge badge-dot badge-{variante}" data-semaforo-sla="{estado}">` con el ícono
(`aria-hidden`) y el texto. El atributo `data-semaforo-sla` lleva el estado conocido (vacío en el neutro): es
el gancho para quien necesite ubicar el semáforo en la página. El reloj sin `tramo` dice «Vence en 8 min» y
«Fuera de SLA · 42 min»; sin `minutos`, «Derivar en término», «Por vencer · Derivar» y «Derivar · Fuera de SLA».

Con `texto_tiempo` el lapso se lee «Fuera de SLA · 48 h» o «Aceptar vence en 5 h» en vez de «2880 min»: la
pieza no convierte nada, escribe el texto que recibe. Lo pasan la bandeja y la ficha del caso de Emergencia
(`programas/templates/programas/emergencia/casos/list.html` y `detail.html`).

## Reglas

- **La pieza no calcula nada.** No conoce objetivos, umbrales (el 80 % de «por vencer»), marcas de tiempo ni
  la hora actual: recibe la terna del selector y la traduce. Una regla de SLA en el template es un defecto.
- **Texto, ícono y color, siempre los tres.** «Por vencer» se dice en palabras también en el reloj: el texto
  de un caso por vencer no puede ser el mismo que el de uno en término.
- El reloj lleva `role="status"`: es la región que anuncia el cambio cuando la pantalla lo refresca. El badge
  de fila no lleva `role`: una tabla con veinte regiones vivas no se puede escuchar.
- Va **uno por caso**: en la fila, dentro de su `<td class="nodo-td">`; en la ficha, junto al encabezado.
- Autoescape siempre: ningún `|safe`.

## Prohibido

- Decidir el estado en la pantalla (`{% if minutos > objetivo %}`) o pasar el objetivo para que la pieza compare.
- Un semáforo que sea solo un punto de color, o reescribir el badge a mano con otro texto para el mismo estado.
- Usarlo para estados que no son de SLA (prioridad, estado del caso): eso es el mapa de estados del módulo.
- Más de un reloj (`variante="reloj"`) por pantalla.
