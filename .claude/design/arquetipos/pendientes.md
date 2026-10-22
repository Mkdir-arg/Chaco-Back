# Arquetipos pendientes dashboard

**No hay golden. La instrucción es frenar y devolver la tarea al llamador** con el motivo y lo
que haga falta decidir. No se elige «el que más se parece» ni se clona una pantalla hermana.

El wizard **ya tiene golden**: ficha `.claude/design/arquetipos/wizard.md`.

## Revisión de caso compleja

**Ya tiene golden** para el caso de una persona con ficha por secciones (`arquetipos/revision.md`).
Lo que sigue sin ser molde es esta pantalla de Becas:

`programas/templates/programas/becas/revision/formulario_detalle.html` es la pantalla de
revisión del dominio Becas: validación de identidad, historial, panel de SIIS, modales propios y
acciones condicionadas por capacidad. **No sirve como molde**: casi todo lo que tiene es dominio.

El archivo son 88 líneas que solo declaran el **orden** de las secciones; cada una vive en
`revision/_detalle/*.html` (`_identidad`, `_trazabilidad`, `_contacto`, `_respuestas`,
`_siis_resultado`, `_siis_envio`, `_aviso_ciudadano`, `_trazas`, `_acciones`, `_modales`…). Que
esté partida **no la convierte en molde**: los includes son secciones de este dominio, no piezas
reutilizables, y no se incluyen desde ninguna otra pantalla.
`_siis_resultado` y `_siis_envio` se incluyen solo con `siis_aplica` (programa que valida con SIIS).

## Dashboard

`programas/templates/programas/becas/config/_dashboard_panel.html` y
`static/custom/js/becas-dashboard.js` son el tablero del programa Becas. **No es molde**: tiene
deuda propia (KPIs en línea, títulos con tamaño fijo y un modal que todavía no usa el helper de
modales) y su contrato está atado a los datos de Becas.

Para una pantalla con números el arquetipo correcto suele ser Detalle con su franja de métricas
(`templates/components/_stat_card.html`). Un tablero con gráficos es una **novedad**: frená. Lo que sí existe para abrir un tablero de programa es
`{% hero_inicio %}` (ficha `componentes/hero_inicio.md`), solo ahí y en el Inicio.

## Qué devolver cuando frenás

```
Tipo: B · Arquetipo: PENDIENTE (< dashboard>)
Motivo: no hay golden para este arquetipo; la ficha de pendientes pide frenar.
Lo más cercano que existe: <pantalla> — qué sirve y qué no.
Novedades que habría que aprobar: <lista>
```

No escribas el template.
