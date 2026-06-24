# :material-note-text-outline: Minuta de Reunión — Cuarta Sesión de Seguimiento

!!! abstract "Aprobación del inicio de Becas y modelado del Legajo de Dispositivos"
    Sesión orientada a presentar la estimación, el plan de trabajo y el esquema de arquitectura del **Módulo de Becas** al referente técnico del SIS, y a avanzar en el modelado del **Legajo de Dispositivos** (estadísticas de instituciones): formularios físicos, validaciones del legajo ciudadano y tratamiento de información sensible.

---

## :material-information-outline: Metadatos

| Campo | Valor |
|---|---|
| :material-folder-outline: **Proyecto** | Chaco — Digitalización de procesos provinciales |
| :material-calendar-outline: **Fecha** | 2026-06-19 |
| :material-clock-outline: **Horario** | 16:00 a 17:20 hs |
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
| Walter Giordano | Referente de Tecnología y Sistemas | Ministerio de Desarrollo de Chaco |
| Alberto Tablate Aquino | Nexo técnico en SIS | Ministerio de Desarrollo de Chaco |

---

## :material-bullseye-arrow: Objetivo de la reunión

!!! quote ""
    **Módulo de Becas:** presentar la estimación de horas, el plan de trabajo y el esquema de arquitectura técnica al referente técnico del SIS para obtener la aprobación del inicio de desarrollo.

    **Estadísticas de Instituciones (Dispositivos):** analizar el mapeo de los formularios físicos (00, 01 y 02), revisar el modelado en Miro y coordinar el relevamiento de la Línea 102 junto con el cruce de datos sensibles.

---

## :material-forum-outline: Temas tratados

### :material-numeric-1-circle-outline: Módulo de Becas — estimación, plan y arquitectura

- Se propuso una **arquitectura mínima** para los ambientes de QA y homologación (4 CPU, 8 GB RAM, disco SSD, Ubuntu). Se evaluó utilizar una subcuenta en **Amazon Web Services (AWS)** con instancias EC2, Aurora para MySQL y un bucket S3 para el almacenamiento de archivos multimedia, con el objetivo de aislar el entorno y acelerar los tiempos.
- Se aclaró que, en su fase inicial, la aplicación **no será de acceso público** en las tiendas (Play Store / App Store), sino una **herramienta interna para operadores**. Se estima una base inicial de **50 usuarios concurrentes** (coordinadores y territoriales).
- El programa de becas iniciará de forma **progresiva**: el primer mes con el sector ladrilleros (unas 6.000 personas, de manera paulatina) y luego se sumarán los segmentos de adolescentes y cultura.
- Se revisó el estado de avance del proyecto sobre el tablero de gestión, el diagrama de Gantt y el seguimiento de horas.

### :material-numeric-2-circle-outline: Legajo de Dispositivos — información base y categorías

Se revisó en Miro el esquema del Legajo de Dispositivos. Se definió que existirá una **información base común** (nombre, dirección, teléfono, responsable) compartida por todos los centros —Adultos Mayores, Abordaje Psicosocial, UPI, Residencias Universitarias y Fortalecimiento Familiar— y **campos específicos según la categoría** del instituto.

### :material-numeric-3-circle-outline: Legajo ciudadano y vínculos familiares

- Se demostró el funcionamiento del **legajo ciudadano**, que evita duplicaciones mediante la **validación del DNI**.
- Se validó la funcionalidad para registrar de forma **dinámica las redes de sostén y los vínculos familiares**, indicando si existe o no convivencia entre los miembros.

### :material-numeric-4-circle-outline: Formularios 00, 01 y 02

- Se ratificó que el **Formulario 00** es para el ingreso de datos del beneficiario.
- Los **Formularios 01** (control de camas totales y disponibles) y **02** (raciones / alimentación diaria) son **transversales** a todos los dispositivos de internación donde las personas pernoctan (Adultos Mayores, Psicosocial, Casas Cuna, etc.).
- Claudia aclaró que el **Formulario 01 será un resultado estadístico automatizado**, derivado del control de ingresos y egresos diarios cargados en el sistema.
- Los **merenderos** se tipificarán como **instituciones ambulatorias** (asociaciones externas) que solo registran asistencia y entrega de insumos (por ejemplo, leche).

### :material-numeric-5-circle-outline: Tratamiento de información sensible (menores y Línea 102)

Se trató la **alta sensibilidad** de la información legal y judicial de los menores bajo situación de guarda. Guido expuso que los juzgados demoran meses en otorgar los DNI de niños institucionalizados. Como propuesta de tratamiento, se planteó implementar **campos bloqueados según el rol del usuario** para garantizar el secreto de sumario y la confidencialidad, inhabilitando capturas o copias de los datos de la **Línea 102**.

---

## :material-handshake-outline: Acuerdos y decisiones tomadas

| # | Acuerdo | Responsable | Fecha límite |
|:-:|---|---|:-:|
| 1 | Precargar al ciudadano mediante su documento para arrastrar su historial unificado (becas, dispositivos, etc.) y evitar duplicaciones en el sistema. | Ambas partes | A definir |
| 2 | El Formulario 01 no requerirá carga manual diaria e independiente: el sistema calculará la disponibilidad automáticamente a partir de los ingresos y egresos registrados en el Formulario 00. | Ambas partes | A definir |
| 3 | El flujo contará con tres niveles de control (territorio, localidad y SIS), eliminando la necesidad de procesar planillas de carga masiva manuales. | Ambas partes | A definir |

---

## :material-arrow-right-bold: Próximos pasos

- [ ] Enviar el correo formal con el **"Ok" de inicio de desarrollo** del Módulo de Becas al finalizar la jornada. — :material-account-outline: Responsable: **Equipo Chaco (Guido Cortiglia)** — :material-calendar-outline: Inmediato
- [ ] Compartir las planillas y la documentación de los formularios correspondientes a la **Línea 102** para su posterior análisis e integración. — :material-account-outline: Responsable: **Equipo Chaco (Guido Cortiglia)** — :material-calendar-outline: A definir
- [ ] Procesar el Miro y las carpetas compartidas de formularios para armar y presentar un **documento de propuesta funcional general** del módulo de estadísticas institucionales. — :material-account-outline: Responsable: **ICORE** — :material-calendar-outline: A definir
- [ ] Coordinar una reunión entre el equipo administrativo de ambas partes para definir la viabilidad y aplicación de **horas extra en el contrato de junio**. — :material-account-outline: Responsable: **Ambas partes** — :material-calendar-outline: A coordinar
- [ ] Coordinar una reunión entre los equipos técnicos para definir las **subcuentas de AWS**, políticas de firewall, ciberseguridad e **integración por API con el SIS**. — :material-account-outline: Responsable: **Ambas partes (equipos técnicos)** — :material-calendar-outline: A coordinar

---

## :material-calendar-plus-outline: Próxima reunión

| Campo | Valor |
|---|---|
| :material-calendar-outline: **Fecha propuesta** | A coordinar |
| :material-bullseye-arrow: **Objetivo** | Definir la infraestructura en AWS, la integración por API con el SIS y avanzar con la propuesta funcional del módulo de estadísticas institucionales |

---

!!! note "Minuta cerrada"
    Documento consolidado con los acuerdos confirmados en reunión. Los elementos que no quedaron definidos se mantienen como pendientes de confirmación.
