# Composiciones sin molde

Lo que figura acá **no tiene golden**. La instrucción es frenar y devolver la tarea al llamador
con el motivo y lo que haga falta decidir. No se elige «el que más se parece» ni se clona una
pantalla hermana.

El wizard **ya tiene golden**: ficha `.claude/design/arquetipos/wizard.md`. El dashboard de
programa **ya tiene golden**: ficha `.claude/design/arquetipos/dashboard.md`.

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

## Dashboard de Becas

El arquetipo **ya tiene golden** (`arquetipos/dashboard.md`, el esqueleto del tablero de
Dispositivos). Lo que sigue sin ser molde es el tablero del programa Becas:
`programas/templates/programas/becas/config/_dashboard_panel.html` y
`static/custom/js/becas-dashboard.js`. Tiene deuda propia (`<style>` de impresión, `style=`,
títulos con tamaño fijo y un modal que todavía no usa el helper de modales), vive como solapa del
detalle del programa y su contrato está atado a los datos de Becas. Un tablero nuevo se declara
del arquetipo Dashboard y clona su golden; de Becas solo toma el patrón de caché del servicio
(`programas/services/dashboard_becas.py`).

Un gráfico que no tenga ficha (barras pareadas, barra con marcas de umbral, mapa) sigue siendo
**novedad**: frená.

## Qué devolver cuando frenás

```
Tipo: B · Arquetipo: PENDIENTE (<composición>)
Motivo: no hay golden para este arquetipo; la ficha de pendientes pide frenar.
Lo más cercano que existe: <pantalla> — qué sirve y qué no.
Novedades que habría que aprobar: <lista>
```

No escribas el template.
