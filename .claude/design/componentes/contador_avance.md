# Componente · Contador de avance «N de N» (`components/_contador_avance.html`)

**Clasificación:** Canónico reutilizable. Dice cuántas unidades están hechas sobre un total contable
(«3 de 7 confirmadas»), con una barra que lo refuerza.
**Evidencia:** `templates/components/_contador_avance.html`, `core/tests/test_nodo_ui_emergencia.py`
(`ContadorAvanceTest`). El relleno de la barra reusa `.nodo-ficha-medidor` de
`static/custom/css/nodo-ficha.css`, que el shell del backoffice ya carga.
**Consumidores:** los integrantes de un caso de Emergencia. En E6, la cabecera de la surface «Integrantes»
(`programas/templates/programas/emergencia/dispositivo/integrantes.html`) y la celda «Confirmadas» de los
ingresos en curso (`dispositivo/llegadas.html`, con `nombre` propio por fila); en la ficha de la mesa, la
cabecera de «Integrantes» de E3 (`programas/templates/programas/emergencia/casos/detail.html`).

## Por qué no es `_ficha_avance`

`_ficha_avance.html` (`ficha_timeline.md`) es el medidor **en porcentaje** de una sección de ficha y no se
incluye suelto: lo usa `_ficha_seccion.html`. Acá el dato es una **cuenta de unidades** —personas, ítems— y
el texto «3 de 7» es lo que se lee; el porcentaje no le dice nada a quien está confirmando a la cuarta
persona. Por eso `aria-valuemax` es el total y no 100.

## Invocación

```django
{% include "components/_contador_avance.html" with hechos=caso.confirmadas total=caso.total_declarado etiqueta="confirmadas" only %}
```

| Parámetro | Efecto |
|---|---|
| `hechos` | Entero **ya contado** por la vista o el selector. Sin él, 0 |
| `total` | Entero ya contado. Sin él, 0: barra vacía y «0 de 0», sin dividir |
| `etiqueta` | Qué se cuenta, en plural y concordado («confirmadas», «recibidos»). Va pegada al «N de N» |
| `nombre` | Opcional. Nombre accesible de la barra (`aria-label`); por defecto «Avance». Pasalo si la pantalla tiene más de un contador |

Render: `span.inline-flex` con la barra (`w-20 h-2 rounded-full`, `role="progressbar"`,
`aria-valuemin="0"`, `aria-valuemax="{total}"`, `aria-valuenow="{hechos}"`,
`aria-valuetext="3 de 7 confirmadas"`) y el texto `text-sm font-semibold text-heading`. El ancho del relleno
viaja como custom property (`style="--avance:43%"`), la única forma admitida de pasar un número del servidor.

Con todo hecho (`total` mayor que 0 y `hechos` igual o mayor) la barra pasa a `bg-success` y el texto suma
`fa-circle-check`: es refuerzo, el «7 de 7» ya lo dice. Con `total` 0 no hay «todo hecho».

## Reglas

- **Los dos números llegan contados.** Nada de `|length` sobre un queryset ni `.count()` en el template.
- El texto es el portador; la barra nunca va sola.
- La etiqueta concuerda con lo que se cuenta y la escribe el consumidor: la pieza no pluraliza.
- Es `inline-flex`: entra en la cabecera de una surface, al lado del título, o en una celda.

## Prohibido

- Usarlo para un porcentaje sin unidades (avance de carga, ocupación): eso es `_ficha_avance` dentro de su
  sección, o una stat card.
- Barras de progreso escritas a mano con `style="width:…"`.
- Pasarle un total estimado: si el total cambia (se agrega una persona), la vista manda el nuevo.
