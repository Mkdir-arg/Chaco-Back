# :material-package-variant: Versión 002

<div class="grid cards" markdown>

-   :material-circle:{ style="color: #f59e0b" } **Estado**

    En curso

-   :material-calendar-range: **Período**

    1 sep 2026 → en curso

-   :material-counter: **Avance**

    En ejecución

-   :material-clock-outline: **Horas del período**

    Ver [módulo financiero](../financiero/index.md)

</div>

!!! abstract "Objetivo"
    Que el equipo del Ministerio pueda **armar y administrar sus propios formularios** desde el sistema, sin depender de desarrollo, y llevar esa capacidad también a la **app de campo**. En paralelo, completar la remediación de interfaz del **Programa Dispositivos** y acompañar la puesta en operación de la inscripción por link público.

!!! info "Continuidad de la Versión 001"
    Esta versión toma los frentes que quedaron abiertos al [cierre de la Versión 001](version-001.md#informe-de-cierre-de-la-version). El alcance se completa a medida que se acuerdan las definiciones con el Ministerio: acá se publica solo lo confirmado.

---

## :material-clipboard-list-outline: Alcance de la versión

| # | Funcionalidad | Prioridad | Estado | Hs aprobadas |
|:-:|---|:-:|:-:|:-:|
| 1 | Constructor de formularios por convocatoria | Alta | En desarrollo | 270 h |
| 2 | Padrón de habilitados con herencia por relevamiento | Alta | En desarrollo | *(dentro del constructor)* |
| 3 | App de campo con el formulario por convocatoria | Alta | Pendiente — equipo móvil | A estimar |
| 4 | Remediación de interfaz del Programa Dispositivos | Media | En curso | A estimar |
| 5 | Primera convocatoria con inscripción por link público — acompañamiento | Media | En curso | — |
| 6 | Textos de los correos de credenciales — aprobación | Baja | Pendiente del Ministerio | — |

!!! note "Criterio de las horas"
    El constructor de formularios se aprobó con un alcance de **270 h**, de las cuales **94 h 30 min** se ejecutaron dentro de la Versión 001: quedan **175 h 30 min** por ejecutar en esta versión. Los frentes marcados *A estimar* se cuantifican cuando se cierre su definición. El consumo real se registra, como siempre, en el [detalle por entregable](../financiero/detalle-tareas.md).

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

---

## :material-server-network: Despliegue

La [guía de despliegue publicada en la Versión 001](version-001.md#despliegue-de-la-version) **sigue vigente** para esta versión: mismos requisitos de servidor, mismas variables de entorno y mismo procedimiento de actualización. Si esta versión introduce alguna variable nueva, se documenta acá y en `.env.qa.example`.

---

[:material-arrow-left: Ver el cierre de la Versión 001](version-001.md){ .md-button }
[:material-arrow-right: Todas las versiones](index.md){ .md-button }
