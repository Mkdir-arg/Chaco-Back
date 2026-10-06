# Arquetipos pendientes · wizard, revisión compleja y dashboard

**No hay golden. La instrucción es frenar y devolver la tarea al llamador** con el motivo y lo
que haga falta decidir. No se elige «el que más se parece» ni se clona una pantalla hermana.

## Wizard de backoffice

Decisión del cliente abierta: **no se define**. Si una tarea pide un alta en pasos dentro del
backoffice, frená.

Lo único aprovechable mientras tanto es la **semántica del stepper** del portal,
`portal/templates/portal/inscripcion/_stepper.html`: el paso activo no se distingue solo por
color, lleva `aria-current="step"` (con `data-step` conservado solo para el CSS del círculo) y
un `<span class="sr-only">Paso actual: </span>` antes del nombre del paso. Eso es semántica, no
un molde de pantalla: el stepper vive en el shell de inscripción, que el backoffice no usa.

El wizard que hoy existe en Configuración (alta de programa) **no es referencia**: extiende el
shell legacy.

## Revisión de caso compleja

`programas/templates/programas/becas/revision/formulario_detalle.html` es la pantalla de
revisión del dominio Becas: más de mil líneas, con validación de identidad, historial, panel de
SIIS, modales propios y acciones condicionadas por capacidad. **No sirve como molde**: casi todo
lo que tiene es dominio.

Si una tarea pide «una pantalla de revisión» en otro módulo, frená y devolvé el plan: hay que
decidir primero qué parte es realmente común (el detalle con solapas suele alcanzar).

## Dashboard

`programas/templates/programas/becas/config/_dashboard_panel.html` y
`static/custom/js/becas-dashboard.js` son el tablero del programa Becas. **No es molde**: tiene
deuda propia (KPIs en línea, títulos con tamaño fijo y un modal que todavía no usa el helper de
modales) y su contrato está atado a los datos de Becas.

Para una pantalla con números el arquetipo correcto suele ser Detalle con su franja de métricas
(`templates/components/_stat_card.html`). Un tablero con gráficos es una **novedad**: frená.

## Qué devolver cuando frenás

```
Tipo: B · Arquetipo: PENDIENTE (<wizard|revisión compleja|dashboard>)
Motivo: no hay golden para este arquetipo; la ficha de pendientes pide frenar.
Lo más cercano que existe: <pantalla> — qué sirve y qué no.
Novedades que habría que aprobar: <lista>
```

No escribas el template.
