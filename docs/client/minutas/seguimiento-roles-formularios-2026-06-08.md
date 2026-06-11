# :material-note-text-outline: Minuta de Reunión — Segunda Sesión de Seguimiento

!!! abstract "Definición de Módulos y Reglas de Negocio"
    Sesión orientada a validar el alcance operativo de los roles de usuario en territorio, definir la estructura base y condicional de los formularios de relevamiento y responder el cuestionario técnico-funcional para asegurar la flexibilidad de la aplicación de becas y su interoperabilidad con el ecosistema provincial.

---

## :material-information-outline: Metadatos

| Campo | Valor |
|---|---|
| :material-folder-outline: **Proyecto** | Chaco — Digitalización de procesos provinciales |
| :material-calendar-outline: **Fecha** | 2026-06-08 |
| :material-clock-outline: **Horario** | 11:00 a 12:30 hs |
| :material-video-outline: **Modalidad** | Virtual |
| :material-account-edit-outline: **Redactada por** | Equipo ICORE |

---

## :material-account-group-outline: Participantes

| Nombre | Rol | Organización |
|---|---|---|
| Agostina Coppola | Analista Funcional y QA | ICORE |
| Matías Fariña | Project Manager (PM) | ICORE |
| Guido Cortiglia | Coordinador operativo | Ministerio de Desarrollo de Chaco |
| Diego Adrián Becla | Coordinador operativo | Ministerio de Desarrollo de Chaco |
| Claudia Miserachs | Consultora externa | Ministerio de Desarrollo de Chaco |

---

## :material-bullseye-arrow: Objetivo de la reunión

!!! quote ""
    Validar el alcance operativo de los roles de usuario en territorio, definir la estructura base y condicional de los formularios de relevamiento, y responder el cuestionario técnico-funcional para asegurar la flexibilidad de la aplicación de becas y su interoperabilidad con el ecosistema provincial.

---

## :material-forum-outline: Temas tratados

### :material-numeric-1-circle-outline: Contexto operativo e interoperabilidad

Se ratificó que el sistema funcionará de manera interoperable con otros ministerios. Se establecerá una integración obligatoria con el sistema existente (SIS) para la validación de los requisitos cargados.

Queda pendiente que el Ministerio confirme si se requiere una futura integración con el Ministerio de Salud y el Ministerio de Educación.

### :material-numeric-2-circle-outline: Asignación de usuarios y coordinación por segmento

Dentro del universo de becas existen diferentes segmentos. Cada usuario del sistema estará identificado y vinculado estrictamente al segmento que le corresponde.

Se estableció que habrá un coordinador por segmento (por ejemplo, 7 segmentos implican 7 coordinadores). Cada coordinador definirá de manera autónoma cuándo y dónde se realiza su respectiva campaña (localidad, fechas, etc.).

### :material-numeric-3-circle-outline: Estructura jerárquica y dinámica de usuarios

El sistema se dividirá en tres niveles de acceso con responsabilidades definidas:

- **Administrador General:** gestiona todas las funcionalidades, establece los requerimientos y los parámetros globales. Es el encargado de generar la convocatoria general y asignar un responsable.
- **Coordinador:** genera los relevamientos y asigna a los territoriales. Otorga los permisos a la persona que estará en campo en el momento, dado que no hay usuarios fijos en el territorio (esquema dinámico).
- **Territorial:** personal en campo encargado de la carga de datos. Tiene acceso restringido y solo ve sus propias tareas asignadas.

### :material-numeric-4-circle-outline: Flexibilidad operativa en territorio

El sistema no debe ser rígido con los horarios de cierre de los relevamientos, para evitar bloqueos u obstaculizar la operación si una jornada en campo se extiende más allá de la hora pactada (por ejemplo, convocatorias que terminan realizándose a las 20:00 o 21:00 hs).

### :material-numeric-5-circle-outline: Control de estados y cancelaciones

- Si termina el día y un relevamiento asignado no fue inicializado, el sistema cambiará automáticamente su estado a **"Vencido"**.
- El territorial no puede reabrirlo; solo el Coordinador tiene la potestad de reprogramarlo o modificar dicho estado.
- En caso de que un territorial solicite cambiar o cancelar una fecha (por ejemplo, por razones climáticas), el sistema le exigirá de forma obligatoria registrar el motivo.

### :material-numeric-6-circle-outline: Definición de formularios

Los formularios se dividirán en un **Formulario Base** (preguntas comunes transversales) y **Formularios por Segmento** (específicos y condicionales según los requisitos de cada línea).

- La cantidad total de preguntas queda a definir por el área competente (el Ministerio), otorgando flexibilidad para adaptar el diseño.
- El Formulario Base restringirá estrictamente el domicilio (solo personas de Chaco pueden acceder a la beca) y contemplará campos para teléfono, correo, grupo familiar, adultos mayores y preguntas de discapacidad con sus respectivas subpreguntas.

### :material-numeric-7-circle-outline: Evolución del producto y gestión de datos

- La postulación a la beca pasará a formar parte del legajo del beneficiario.
- El sistema deberá funcionar también como herramienta de consulta histórica (para revisar si un ciudadano fue aprobado o no y el motivo).
- Los tableros de control (dashboards) de la web contemplarán el seguimiento de las Becas y del Programa Ñachec (programa social propio del Ministerio).
- A futuro, se prevé que los ciudadanos puedan ingresar desde la web para autogestionar y cargar sus datos de manera directa.

---

## :material-handshake-outline: Acuerdos y decisiones tomadas

| # | Acuerdo | Responsable | Fecha límite |
|:-:|---|---|:-:|
| 1 | La matriz de usuarios permitirá roles combinados: un mismo usuario puede ser Administrador/Coordinador de un programa y Territorial de otro de manera simultánea según las necesidades operativas. | Ambas partes | A definir |
| 2 | El Coordinador/Administrador tiene permisos para editar y rectificar los datos del formulario desde el back office antes de la aprobación final. | Ambas partes | A definir |
| 3 | Cada coordinador podrá supervisar de manera macro todo el avance de los relevamientos y la carga de su segmento; los territoriales mantendrán una visualización atomizada exclusivamente de sus tareas asignadas. | Ambas partes | A definir |

---

## :material-arrow-right-bold: Próximos pasos

- [ ] Enviar la definición formal de los segmentos del público objetivo (ladrilleros, etc.) junto con los requisitos específicos para configurar los formularios. — :material-account-outline: Responsable: **Ministerio** — :material-calendar-outline: Entre hoy y mañana
- [ ] Indicar formalmente a qué otros sistemas externos (además de la integración con el SIS) se requiere integrarse. — :material-account-outline: Responsable: **Ministerio** — :material-calendar-outline: A definir
- [ ] Configurar la arquitectura para soportar el dinamismo de los formularios base/segmentados y avanzar en el diseño de los tableros de control web para el seguimiento de Becas y del Programa Ñachec. — :material-account-outline: Responsable: **ICORE** — :material-calendar-outline: A definir

---

## :material-calendar-plus-outline: Próxima reunión

| Campo | Valor |
|---|---|
| :material-calendar-outline: **Fecha propuesta** | A coordinar |
| :material-bullseye-arrow: **Objetivo** | A definir |

---

!!! note "Minuta cerrada"
    Documento consolidado con los acuerdos confirmados en reunión. Los elementos que no quedaron definidos se mantienen como pendientes de confirmación.
