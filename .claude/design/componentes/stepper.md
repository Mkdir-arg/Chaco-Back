# Componente · Indicador de pasos (stepper) del backoffice

**Clasificación:** Canónico reutilizable.
**Pieza:** `templates/components/_stepper.html` + `static/custom/css/nodo-stepper.css` (cargado por
`templates/includes/base.html`). **Evidencia:** la golden del arquetipo Wizard,
`configuracion/templates/configuracion/programa_wizard_paso4.html`.
**Test:** `core/tests/test_nodo_ui_piezas.py` (`StepperTest`).

No es el stepper del portal: `portal/templates/portal/inscripcion/_stepper.html` (`di-stepper`) vive
en el shell de inscripción pública y no se usa en el backoffice. De ese se tomó solo la semántica
accesible.

## Contrato

```django
{% include "components/_stepper.html" with pasos=pasos paso_actual=paso_actual %}
```

- `pasos`: lista armada **en la vista** de dicts con `etiqueta` y, opcional, `url`. La vista de
  Configuración lo hace con `_contexto_pasos(paso, programa=None)` (`configuracion/views/programas.py`).
- `paso_actual`: entero base 1. Los anteriores son *hechos*, los posteriores *pendientes*.
- `url` solo se dibuja como link en los pasos **hechos**: se vuelve atrás, nunca se salta adelante
  (el servidor valida cada paso). Los links entran en el orden de tabulación y tienen foco visible.

## Qué rinde

`<nav aria-label="Pasos del asistente">` con un `<ol class="nodo-stepper">`. Cada paso es un `<li>`
con círculo de 28 px y, entre pasos, un conector de 56 px (pseudo-elemento, sin markup).

| Estado | Círculo | Texto sr-only | Otros |
|---|---|---|---|
| Hecho | de marca con tilde | «Paso completado: » | link si trae `url`; el conector que lo sigue va de marca |
| Actual | borde y número de marca | «Paso actual: » | `aria-current="step"`, etiqueta en negrita |
| Pendiente | borde gris con número | «Paso pendiente: » | — |

El estado nunca es solo color: lo dicen el texto para lectores de pantalla, la tilde del hecho, el
número y el negrita del actual.

## Prohibido

- Armar el indicador a mano o con `bg-tertiary rounded-full h-2` (barra de progreso).
- Poner `url` en pasos pendientes para saltar adelante.
- Calcular el estado de los pasos en el template más allá de comparar con `paso_actual`.
- Usarlo en el shell del portal o de la inscripción pública.
