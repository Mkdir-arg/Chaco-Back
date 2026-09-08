# :material-package-variant: Versión 002

<div class="grid cards" markdown>

-   :material-circle:{ style="color: #f59e0b" } **Estado**

    En curso

-   :material-calendar-range: **Período**

    1 sep 2026 → en curso

-   :material-counter: **Avance**

    Constructor al 53%

-   :material-clock-outline: **Horas del período**

    164 h (al 05/09)

</div>

!!! abstract "Objetivo"
    Que el equipo del Ministerio pueda **armar y administrar sus propios formularios** desde el sistema, sin depender de desarrollo, y llevar esa capacidad también a la **app de campo**. En paralelo, completar la remediación de interfaz del **Programa Dispositivos** y acompañar la puesta en operación de la inscripción por link público.

!!! info "Continuidad de la Versión 001"
    Esta versión toma los frentes que quedaron abiertos al [cierre de la Versión 001](version-001.md#informe-de-cierre-de-la-version). El alcance se completa a medida que se acuerdan las definiciones con el Ministerio: acá se publica solo lo confirmado.

---

## :material-clipboard-list-outline: Alcance de la versión

| # | Funcionalidad | Prioridad | Estado al 05/09 | Hs aprobadas | Ejecutado |
|:-:|---|:-:|:-:|:-:|:-:|
| 1 | Constructor de formularios por convocatoria | Alta | En desarrollo | 270 h | **143 h 30 min (53%)** |
| 2 | Padrón de habilitados con herencia por relevamiento | Alta | Desarrollado — pendiente de publicación | *(dentro del constructor)* | — |
| 3 | App de campo con el formulario por convocatoria | Alta | Pendiente — equipo móvil | A estimar | — |
| 4 | Remediación de interfaz del Programa Dispositivos | Media | En curso | A estimar | — |
| 5 | Primera convocatoria con inscripción por link público | Media | **Abierta en producción desde el 01/09** — en acompañamiento | — | 20 h |
| 6 | Textos de los correos de credenciales — aprobación | Baja | Pendiente del Ministerio | — | — |
| 7 | Dashboard del Programa Becas | Media | Analizado — a validar por el Ministerio | 86 h *(propuestas)* | 5 h 30 min |
| 8 | Programa Dispositivos — análisis de la versión 2 | Media | En análisis | A estimar | 9 h |
| 9 | Rendimiento del acceso al sistema | Media | Código listo — pendiente de publicación | — | 9 h 30 min |

!!! note "Criterio de las horas"
    El constructor de formularios se aprobó con un alcance de **270 h**, de las cuales **94 h 30 min** se ejecutaron dentro de la Versión 001: quedan **175 h 30 min** por ejecutar en esta versión. El dashboard se presentó al Ministerio el 05/09/2026 con **86 h**; si el bloque de respuestas de los formularios se posterga hasta terminar el constructor, la propuesta baja a **70 h**. Los frentes marcados *A estimar* se cuantifican cuando se cierre su definición. El consumo real se registra, como siempre, en el [detalle por entregable](../financiero/detalle-tareas.md).

---

## :material-chart-timeline-variant: Avance al 05/09/2026

**164 horas** de trabajo en la primera semana de la versión, con el equipo completo. Lo que se movió:

- **La inscripción por link público abrió el 1 de septiembre** en el entorno del organismo. Además del acompañamiento de la apertura y de la medición de uso, el programa pidió **cuatro ajustes de texto** sobre el link ya publicado —qué contacto se muestra en cada pantalla y qué dice el mensaje cuando un documento no puede inscribirse—, que se aplicaron y publicaron en el día.
- **Constructor de formularios: 143 h 30 min de 270 (53%)**. En la semana, el formulario que se sirve pasó a acompañar al catálogo vivo sin desincronizarse, y cada inscripción fija la versión del formulario que la persona respondió. La cobertura automatizada acompañó cada etapa. **Quedan 126 h 30 min**, que incluyen la fase de la app de campo.
- **Dashboard del Programa Becas**: propuesta, boceto navegable y análisis con sus nueve tareas ejecutables, presentado al Ministerio el 05/09.
- **Programa Dispositivos — versión 2**: relevamiento funcional en curso.
- **Rendimiento del acceso al sistema**: se identificó por qué el ingreso demora, con el cambio de método de resguardo de contraseñas y el modo de ejecución con varios procesos ya resueltos en código; queda publicarlo y acordar la configuración con la infraestructura del organismo.

---

## :material-file-tree: Los frentes en detalle

### :material-form-select: 1. Constructor de formularios por convocatoria

Hoy el formulario que completa cada persona —desde la app de campo o desde el link público— es fijo: cualquier cambio en las preguntas, en el orden o en el comportamiento requiere desarrollo. Con el constructor, **cada convocatoria arma su propio formulario desde el sistema**:

- **Catálogo de preguntas en grupos**, reordenables arrastrando, donde cada pregunta declara en qué canal se pide (app de campo, link público o ambos).
- **Constructor por convocatoria con vista previa en vivo**: se ordenan grupos y preguntas, se agregan títulos y textos de ayuda y se crean campos propios de esa convocatoria, viendo en el momento lo que verá la persona.
- **Preguntas y grupos condicionales**: un campo se muestra solo si se cumple una condición sobre respuestas anteriores (por ejemplo, los datos del apoderado solo para menores de 18). Las reglas se validan también en el servidor.
- **Cada inscripción conserva la versión exacta de su formulario**, de modo que un cambio de diseño posterior no reinterpreta los casos anteriores.

### :material-account-multiple-check: 2. Padrón de habilitados con herencia

El padrón que define quién puede inscribirse se carga una vez en la convocatoria y lo usan todos sus relevamientos. Si un relevamiento necesita su propia lista —una escuela, un barrio— se le carga un **padrón propio** y deja de heredar el general; al quitarlo, vuelve a heredarlo.

### :material-cellphone-arrow-down: 3. App de campo con el formulario por convocatoria

La aplicación móvil pasa a mostrar los formularios diseñados por convocatoria, con sus grupos, preguntas condicionales y campos propios. Lo toma el equipo móvil. **Mientras tanto la app actual sigue funcionando sin cambios**: el sistema traduce automáticamente entre el esquema anterior y el nuevo, de modo que ambas modalidades conviven durante la transición.

### :material-palette-outline: 4. Remediación de interfaz del Programa Dispositivos

Las catorce tareas derivadas de la auditoría funcional y de interfaz del programa, para que sus pantallas queden alineadas al sistema de diseño y al comportamiento esperado.

### :material-link-variant: 5. Primera convocatoria con inscripción por link público

Acompañamiento de la apertura: configuración de la convocatoria y su padrón, seguimiento de los casos que ingresan por el link y de su revisión en el backoffice.

### :material-email-check-outline: 6. Textos de los correos de credenciales

Los correos de alta de usuario y de recuperación de contraseña están operativos; sus [textos siguen publicados](../funcionalidades/correos-credenciales.md) para revisión del Ministerio. Si piden ajustes, se editan sin cambiar el circuito.

### :material-chart-box-outline: 7. Dashboard del Programa Becas

Una nueva solapa **Dashboard** dentro de la configuración del programa, junto a *Requisitos del programa*, que concentra en una sola pantalla los indicadores de seguimiento y permite descargar la información. Propuesta enviada al Ministerio el 05/09/2026 con un [mock up navegable](https://claude.ai/code/artifact/672365a4-39ae-4ef9-895d-3664a99e77fb); queda a su validación.

- **Filtros** por período, segmento, convocatoria, relevamiento y canal de carga (territorial o link público). Todos los indicadores, gráficos y descargas responden a los filtros aplicados.
- **Indicadores principales:** convocatorias activas, relevamientos en curso, formularios recibidos y su variación respecto del período anterior, aprobados y tasa de aprobación, cupo ocupado y lista de espera.
- **Gráficos:** formularios recibidos por semana, estado de los formularios, avance por convocatoria, relevamientos por estado, embudo de revisión, producción por territorial, respuestas de los formularios por pregunta y formularios por localidad.
- **Exportación:** cada gráfico se puede ver como tabla y descargar en CSV; descarga general en Excel con una hoja por bloque; impresión o PDF del tablero completo.
- **Permisos:** lo ven los mismos perfiles que hoy acceden a los reportes, cada uno dentro de su alcance.

**Estimación:** 86 h para el desarrollo completo (análisis, desarrollo, pruebas automáticas, control de calidad y puesta en producción). Como alternativa, el bloque *Respuestas de los formularios* puede postergarse hasta finalizar el constructor de formularios, que cambia la forma en que se guardan las respuestas: en ese caso la propuesta queda en 70 h.

---

## :material-server-network: Despliegue

La [guía de despliegue publicada en la Versión 001](version-001.md#despliegue-de-la-version) **sigue vigente** para esta versión: mismos requisitos de servidor, mismas variables de entorno y mismo procedimiento de actualización. Si esta versión introduce alguna variable nueva, se documenta acá y en `.env.qa.example`.

---

[:material-arrow-left: Ver el cierre de la Versión 001](version-001.md){ .md-button }
[:material-arrow-right: Todas las versiones](index.md){ .md-button }
