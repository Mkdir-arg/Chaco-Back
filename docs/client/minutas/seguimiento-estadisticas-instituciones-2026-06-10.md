# :material-note-text-outline: Minuta de Reunión — Tercera Sesión de Seguimiento

!!! abstract "Repaso del sistema y nuevo módulo de estadísticas de instituciones"
    Sesión orientada a repasar el funcionamiento macro del sistema y el flujo de diseño actual, y a evaluar e incorporar nuevos requerimientos urgentes sobre estadísticas de instituciones para el Ministerio de Desarrollo Humano.

---

## :material-information-outline: Metadatos

| Campo | Valor |
|---|---|
| :material-folder-outline: **Proyecto** | Chaco — Digitalización de procesos provinciales |
| :material-calendar-outline: **Fecha** | 2026-06-10 |
| :material-clock-outline: **Horario** | 15:00 a 16:30 hs |
| :material-video-outline: **Modalidad** | Virtual |
| :material-account-edit-outline: **Redactada por** | Equipo ICORE |

---

## :material-account-group-outline: Participantes

| Nombre | Rol | Organización |
|---|---|---|
| Agostina Coppola | Analista Funcional y QA | ICORE |
| Matías Fariña | Project Manager (PM) | ICORE |
| Guido Cortiglia | Coordinador operativo | Ministerio de Desarrollo de Chaco |
| Claudia Miserachs | Consultora externa | Ministerio de Desarrollo de Chaco |
| Andrea Alarcón | Coordinadora | Ministerio de Desarrollo de Chaco |

---

## :material-bullseye-arrow: Objetivo de la reunión

!!! quote ""
    Repasar el funcionamiento macro del sistema y el flujo de diseño actual, y evaluar e incorporar nuevos requerimientos urgentes sobre estadísticas de instituciones para el Ministerio de Desarrollo Humano.

---

## :material-forum-outline: Temas tratados

### :material-numeric-1-circle-outline: Repaso del sistema en diseño

- Se revisó cómo la creación de requisitos impacta en la app de campo, la rotación de los territoriales y el alcance del coordinador.
- Se discutió la definición de cupos (si aplican a segmentos o subsegmentos) y el carácter de los archivos adjuntos (fotos de DNI) en territorio.

### :material-numeric-2-circle-outline: Nuevo módulo de estadísticas de instituciones

Se introdujo una necesidad urgente e integral: el sistema abarcará progresivamente todo el Ministerio de Desarrollo Humano. El Ministro tiene una presentación y requiere un módulo/tablero de estadísticas reales de las instituciones internas.

**Tipos de institución:**

- **De internación:** hospitales, hogares de niños, geriátricos. Para estas, los indicadores clave exigidos por el Ministro son los de **corta estadía, media estadía y larga estadía**.
- **Ambulatorias:** comedores, merenderos.

**Estructura de formularios actuales (en papel):**

- **Formulario 00 (o de ingreso):** datos personales y portal ciudadano (universal o adaptado por área, como discapacidad, niñez o adultos mayores).
- **Formulario de Ocupación de Camas:** registro diario compilado (camas totales, ingresos, egresos, disponibles).
- **Formulario de Raciones:** control diario de raciones entregadas (desayuno, almuerzo, merienda, cena).

**Esquemas de trabajo planteados** para llegar a la presentación del Ministro con datos reales del último semestre:

- **Corto plazo:** el equipo de Chaco provee un Excel unificado con columnas parametrizadas para procesar los datos estadísticos históricos del semestre y visualizarlos directamente en el tablero.
- **Largo plazo:** digitalizar el ingreso de datos para que los usuarios de cada institución carguen la información de forma directa en el sistema, actualizando los KPI en tiempo real.

---

## :material-handshake-outline: Acuerdos y decisiones tomadas

| # | Acuerdo | Responsable | Fecha límite |
|:-:|---|---|:-:|
| 1 | El nuevo sistema no reemplazará al CIS en la gestión de pagos; solo consumirá su información por API en una fase futura para reportes consolidados. | Ambas partes | A definir |
| 2 | El sistema debe permitir configurar y controlar cupos tanto a nivel de segmento como de subsegmento. | Ambas partes | A definir |
| 3 | Las fotos de los DNI capturadas en territorio son requisitos obligatorios para avanzar con el trámite, no informativos. | Ambas partes | A definir |
| 4 | El tablero estadístico debe cruzar datos para "blanquear" la entrega de raciones y evitar que un mismo ciudadano reciba el beneficio en múltiples instituciones en paralelo. | Ambas partes | A definir |
| 5 | Se avanzará hacia la digitalización del ingreso de datos en origen (formulario de camas y raciones diario), con un flujo simplificado desde la computadora para alimentar los KPI en tiempo real. | ICORE | A definir |

---

## :material-arrow-right-bold: Próximos pasos

- [ ] Terminar de revisar el documento funcional de becas enviado para dar confirmación final esta semana. — :material-account-outline: Responsable: **Equipo Chaco** — :material-calendar-outline: Esta semana
- [ ] Enviar los formularios vacíos y simulados con datos ficticios (Formularios de Camas y Raciones). — :material-account-outline: Responsable: **Equipo Chaco** — :material-calendar-outline: A definir
- [ ] Enviar los formularios con los datos e información requerida para dar de alta una institución (domicilio, referentes, documentación exigida). — :material-account-outline: Responsable: **Equipo Chaco** — :material-calendar-outline: A definir
- [ ] Analizar el nuevo módulo de estadísticas de instituciones y armar las dos propuestas técnicas/fechas una vez recibido el formulario. — :material-account-outline: Responsable: **ICORE** — :material-calendar-outline: A definir
- [ ] Una vez recibida la confirmación, iniciar el documento de arquitectura y análisis técnico definitivo para cerrar el cronograma de entregas. — :material-account-outline: Responsable: **ICORE** — :material-calendar-outline: A definir
- [ ] Preparar una nueva versión (v2) del documento funcional con la estructura del formulario de relevamiento de la app. — :material-account-outline: Responsable: **ICORE** — :material-calendar-outline: A definir

---

## :material-calendar-plus-outline: Próxima reunión

| Campo | Valor |
|---|---|
| :material-calendar-outline: **Fecha propuesta** | A coordinar |
| :material-bullseye-arrow: **Objetivo** | A definir |

---

!!! note "Minuta cerrada"
    Documento consolidado con los acuerdos confirmados en reunión. Los elementos que no quedaron definidos se mantienen como pendientes de confirmación.
