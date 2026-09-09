# Estimación de esfuerzo — Programa Dispositivos y Programa Merenderos
## Sistema de Gestión Operativa Integral — Legajos, admisiones, camas y asistencia alimentaria

**Fecha de la estimación base:** 2026-07-02 · **Fecha de la Versión 2:** 2026-09-09
**Versión:** 2.0
**Alcance estimado:** **Versión 1** — definición funcional del Programa Dispositivos y Programa Merenderos aprobada el 01/07/2026, ya desarrollada. **Versión 2** — las funcionalidades que identificó el relevamiento de campo realizado en el Albergue Madre Teresa de Calcuta, CIS N.º 3, Dirección de Abordaje Psicosocial (Programa Mírame/Vedia) y Parador Nocturno.
**Estado:** Versión 1 aprobada y desarrollada · Versión 2 en validación con el Ministerio.

> **Base de la estimación:** la definición funcional publicada en [Programa Dispositivos](programa-dispositivos.md), con la conformidad del Ministerio sobre el alcance base, y el documento funcional del Sistema de Gestión Operativa Integral. El relevamiento confirma la necesidad de un legajo digital único, trazabilidad por turnos, ocupación calculada y permisos diferenciados. Esta etapa continúa siendo **100% backoffice** y reutiliza el motor de roles, la validación RENAPER, los formularios configurables y las solapas del legajo ciudadano ya construidos.

> **Criterio de lectura:** los hallazgos de campo se incorporan como contexto funcional, reglas y temas de alcance. Los módulos de inventario, asistencia de personal, libros institucionales, medicación, historial clínico, contingencias, equipamiento, conectividad e integración con ECOM no se suman automáticamente a las 436 horas: quedan identificados para confirmación y, cuando corresponda, una estimación específica.

---

## 1. Resumen ejecutivo

El programa se estima en dos etapas. La **Versión 1** es el alcance aprobado en julio de 2026, ya
desarrollado. La **Versión 2** son las funcionalidades que el relevamiento de campo identificó como
necesarias para que las instituciones operen con el sistema y que la definición original no
contemplaba: turnos y pase de guardia, cupos por sector, autorización previa de ingreso, permisos de
salida, traslados con seguimiento, información sensible con acceso diferenciado y derivaciones.

| Etapa | Horas | Estado |
|---|---:|---|
| Versión 1 — alcance base | 436 | Aprobada y desarrollada |
| **Versión 2 — alcance que se agrega** | **628** | **En validación con el Ministerio** |
| **Total del programa** | **1.064** | |

El detalle de la Versión 2 —los cambios que pidió cada institución, en qué se diferencian de lo ya
entregado, los módulos, las etapas y los tiempos— está en la **sección 11**.

> Las horas corresponden a esfuerzo técnico neto. No incluyen reuniones de seguimiento ni gestión de proyecto. Los formularios de los tipos aún en relevamiento (UPI, ECA, Residencias Universitarias, Fortalecimiento Familiar, CDI y las tres instituciones visitadas en septiembre) **no requieren desarrollo adicional**: se cargan como configuración cuando el Ministerio los entregue (ver §7).

### 1.1 Necesidad de negocio relevada

Las cuatro instituciones visitadas actualmente trabajan con cuadernos, libros de guardia, fichas socioeconómicas y planillas desconectadas. Esto provoca pérdida de información entre turnos, dificultad para auditar insumos y raciones, demoras en derivaciones y falta de visibilidad ministerial sobre camas, personas atendidas y prestaciones.

El sistema debe reemplazar esa dispersión por una gestión operativa única que permita:

- reutilizar un legajo ciudadano y un legajo institucional en todos los módulos;
- registrar altas, cambios, validaciones, ingresos, raciones y egresos con usuario, fecha y hora;
- conservar el historial mediante cierres o inactivaciones, sin borrado;
- mostrar ocupación y disponibilidad reales a partir de movimientos registrados;
- reducir la carga del personal de territorio automatizando identidad, fechas y cálculos;
- brindar a la conducción una visión centralizada para decisiones de capacidad, abastecimiento y emergencias.

### 1.2 Trazabilidad del relevamiento

| Fuente | Aporte al alcance | Estado |
|---|---|---|
| Definición funcional del Programa Dispositivos | Legajo institucional, admisiones, camas, egresos y Programa Merenderos | Base aprobada para desarrollo |
| Informe técnico de reingeniería | Sistema integral, tablero central, instituciones y contingencias | Marco de referencia |
| Relevamiento de campo | Procesos reales, registros en papel, necesidades operativas y reglas específicas | En curso; primeras visitas realizadas |

!!! abstract "Cómo leer este documento"
    Las secciones **2 a 10** son la estimación de la **Versión 1**, ya desarrollada, e incluyen el
    relevamiento de campo que la Dirección realizó en cuatro instituciones (§2.3 a §2.6) y que motivó
    la Versión 2. La **estimación y la propuesta de la Versión 2** están completas en la
    **sección 11**.

## 2. Versión 1 — desarrollo

### 2.1 Detalle por módulo

| Ref | Módulo | Descripción | Horas | Perfil |
|---|---|---|---:|---|
| D-01 | Modelo de datos | Modelos del dominio: Dispositivo institucional, Tipo de dispositivo, Cama, Admisión/Estadía, campos configurables del formulario de admisión, Registro diario, Merendero, Entrega de mercaderías y Prestación mensual. Vínculo con el legajo ciudadano y membresía al programa (habilita la solapa). Migraciones y admin básico. | 24 | Backend |
| D-02 | Configuración del programa | ABM del catálogo de **tipos de dispositivo** y de los **campos del formulario de admisión por tipo** (secciones + tipos de campo: texto / número / selector / selector múltiple / fecha / archivo). Carga de la configuración inicial de **Adulto Mayor** (33 campos) y **Abordaje Psicosocial** (45 campos) según los formularios relevados. Catálogo de servicios del merendero. | 34 | Backend + Frontend |
| D-03 | Legajo del dispositivo | ABM con búsqueda anti-duplicado, alta en borrador, circuito de validación del área (validar / observar / rechazar), estados del dispositivo, domicilio con geolocalización, responsable y contacto. Pantalla de detalle con información base y configuración de camas. | 26 | Backend + Frontend |
| D-04 | Gestión de camas | Estado por cama (disponible / reservada / ocupada / fuera de servicio), regla "una cama, una persona", **ocupación y disponibilidad calculadas** a partir de las estadías (nunca carga manual), semáforo de ocupación configurable por tipo. | 16 | Backend + Frontend |
| D-05 | Admisiones, estadía y egreso | Búsqueda de la persona por DNI en el legajo ciudadano (con pre-completado de identidad vía RENAPER), asignación de cama, **formulario de admisión dinámico según el tipo** (secciones, campos configurables, totales calculados), **detección automática de reingreso**, estados de la admisión, lista de espera, egreso con liberación de cama y traslado con nueva estadía vinculada al mismo legajo. | 40 | Backend + Frontend |
| D-06 | Registro diario de novedades (F-01) | Parte diario por turno (mañana / tarde / noche): el operador elige turno y escribe observaciones; camas totales, ingresos, egresos, ocupación nocturna y disponibles se calculan solos. | 11 | Backend + Frontend |
| D-07 | Solapa Dispositivos en legajo | Pestaña dinámica en el legajo del ciudadano mientras tiene una admisión activa: estado de la estadía, dispositivo y acceso al detalle. | 10 | Backend + Frontend |
| D-08 | Roles y autorización | Roles Operador de dispositivo, Responsable institucional, Supervisor de área, Administrador central y Consulta/auditoría, integrados al motor de roles existente, con alcance por dispositivo/área. | 14 | Backend |
| D-09 | Legajo de merenderos | ABM institucional del **Programa Merenderos**: solicitud del vecino/a con **documentación respaldatoria** (adjuntos), circuito de validación del área, estados del merendero y registro de **entregas de mercaderías** (kits, fecha, servicio). | 24 | Backend + Frontend |
| D-10 | Prestación alimentaria mensual (F-02) | Planilla mensual del merendero: una fila por día y una columna por servicio, carga de raciones, total diario calculado, firma automática por fila. | 13 | Backend + Frontend |
| D-11 | Indicadores | Semáforos de ocupación, disponibilidad, actualización de datos y completitud; panel básico del programa. La definición de umbrales operativos queda sujeta a validación del Ministerio. | 16 | Backend + Frontend |
| D-12 | Reportes | Exportación CSV/Excel: padrón de dispositivos, ocupación, admisiones/egresos por período y padrón de merenderos con entregas. | 13 | Backend + Frontend |
| D-13 | Carga inicial de dispositivos | Importador del padrón existente desde planilla normalizada provista por el Ministerio, conservando fuente y fecha del dato, con validación anti-duplicados previa al alta masiva. | 16 | Backend |
| | **Subtotal desarrollo** | | **257** | |

### 2.2 Distribución por perfil

| Perfil | Módulos | Horas |
|---|---|---:|
| Desarrollador Backend | D-01, D-08, D-13 + parte de D-02 a D-12 | 154 |
| Desarrollador Frontend | Parte de D-02 a D-12 (pantallas sobre el design system existente) | 103 |
| **Total** | | **257** |

### 2.3 Mapeo de los registros actuales al sistema

El relevamiento muestra que los módulos estimados deben reemplazar o centralizar los siguientes registros físicos:

| Registro actual | Módulo equivalente dentro del alcance base o candidato |
|---|---|
| Protocolo de ingreso y legajo en papel | Legajo digital único, admisión y estadía |
| Cuaderno de censo diario de alojados | Registro diario y métricas de ocupación |
| Libro de actas de operadores y libro del sereno | Registro diario de novedades; una bitácora de guardia ampliada requiere confirmación |
| Registros de entregas y raciones de merenderos | Entregas de mercaderías y prestación mensual F-02 |
| Planillas y fichas con información específica | Formularios de admisión configurables por tipo |
| Planilla de medicación | Módulo de administración de fármacos, posterior a esta estimación |
| Carpeta de legajo de salud | Historial clínico digital, posterior y con permisos específicos |
| Libro unificado de entradas y salidas | Inventario y stock, posterior a esta estimación |
| Planilla de asistencia de personal | Módulo de asistencia de Recursos Humanos, posterior a esta estimación |

Los últimos cuatro módulos requieren definición funcional, permisos, reglas de auditoría e integración con los procesos ministeriales antes de estimar su desarrollo.

### 2.4 Hallazgos por institución

| Institución | Operación observada | Necesidades funcionales destacadas |
|---|---|---|
| Albergue Madre Teresa de Calcuta | Alojamiento transitorio, evaluación social, recepción, habitaciones con cupos por servicio y dos economatos. Se utilizan cuadernos separados para recepción, serenazgo, área social, alimentos y limpieza. | Legajo único, niveles de acceso, disponibilidad por servicio, préstamo de camas con autorización, y reducción de transcripciones entre turnos. La incorporación de equipo interdisciplinario, control de acceso, layout de habitaciones, dispositivos móviles y equipamiento queda fuera de esta estimación. |
| CIS N.º 3 | Internación/alojamiento con intervención de Equipo Técnico, operadores 24 horas, Salud/Enfermería, medicación en tres horarios y registros físicos diferenciados. | Integración de la autorización previa del Programa Central/Media, permisos para información médica y psicosocial, y trazabilidad de admisiones. Medicación, historial clínico, asistencia de personal e inventario integral requieren módulos posteriores. |
| Dirección de Abordaje Psicosocial — Programa Mírame/Vedia | Primera intervención, evaluación, plan de acción, trabajo territorial, seguimiento y coordinación de derivaciones. Parte del proceso continúa en papel. | Legajo compartido, historial de intervenciones, derivaciones y coordinación con dispositivos y organismos externos. La digitalización integral de casos sensibles y derivaciones debe definirse por separado. |
| Parador Nocturno | Alojamiento nocturno de alta rotación, con equipos técnicos, recepción, operadores, economato y administración. Registra manualmente ingresos, egresos, pertenencias, conducta, compras e inventario. | Admisión/egreso de alta rotación, articulación con el equipo técnico y trazabilidad de prestaciones. Seguridad, dotación, prioridad sanitaria, equipamiento e inventario formal quedan como necesidades posteriores. |

### 2.5 Actores y separación de responsabilidades

| Actor | Responsabilidad en el alcance base |
|---|---|
| Operador del dispositivo | Carga y actualiza personas, admisiones, egresos y datos operativos de su dispositivo. |
| Responsable institucional | Controla la carga y confirma cierres de su dispositivo. |
| Supervisor del área | Valida altas, cambios sensibles, observaciones y correcciones. |
| Administrador central | Administra catálogos, perfiles, permisos y duplicados. |
| Equipo territorial | Releva y propone correcciones de datos institucionales. |
| Consulta/auditoría | Accede a reportes y trazabilidad sin modificar información. |

La persona que carga un movimiento no puede validarlo dentro del mismo circuito. Los accesos a información médica, psicosocial y judicializada deben restringirse a los roles habilitados.

### 2.6 Tablero de Comando y emergencias

El relevamiento propone un Tablero de Comando Central con tres vistas futuras: capacidad global de la red, demanda y abastecimiento, y población/vulnerabilidad/salud. También identifica planes para inundaciones, temporales, incendios, frío extremo, calor extremo y emergencias sanitarias.

La presente estimación incluye únicamente indicadores básicos del programa. En todos los niveles de ocupación el sistema debe alertar, pero nunca bloquear automáticamente un ingreso; la decisión de admitir o derivar corresponde al área responsable. La matriz completa, los despachos logísticos, centros auxiliares, reportes automáticos y planes activables requieren alcance y estimación propios.

---

## 3. Versión 1 — diseño UX/UI

| Concepto | Horas |
|---|---:|
| Flujos y wireframes de las 8 pantallas del programa (dispositivos, detalle, admisión/egreso, camas, merenderos, configuración, indicadores, reportes) | 24 |
| Diseño del formulario de admisión dinámico (secciones largas, estados de error, pre-completado) | 14 |
| Diseño de camas, semáforos e indicadores (estados visuales) | 10 |
| Ajustes sobre componentes del design system y revisión con el equipo | 12 |
| **Subtotal diseño** | **60** |

> El design system del proyecto ya está construido y aplicado (tokens, componentes, patrones de pantalla); el diseño de esta etapa compone sobre esa base en lugar de crear lenguaje visual nuevo.

---

## 4. Versión 1 — pruebas funcionales y QA

| Concepto | Horas |
|---|---:|
| Escritura de casos de prueba documentados (módulos D-01 a D-13) | 20 |
| Ejecución de pruebas por módulo | 28 |
| Pruebas de flujo end-to-end (alta del dispositivo → validación → admisión → estadía → egreso → censo) y del circuito completo de merenderos (solicitud → validación → entrega → prestación) | 16 |
| Verificación de cálculos: ocupación, disponibilidad, reingresos, totales del formulario y del registro diario | 8 |
| Registro de defectos, re-test y cierre | 8 |
| **Subtotal QA** | **80** |

### Escenarios críticos cubiertos

- Flujo completo del dispositivo: alta anti-duplicado → validación del área → configuración de camas → admisión con formulario por tipo → egreso con liberación de cama.
- Reingreso: persona con estadía anterior cerrada → el sistema lo detecta solo y vincula la nueva estadía al mismo legajo.
- Regla de camas: intento de asignar una cama ocupada; cama fuera de servicio no cuenta como disponible.
- Sin cupo: admisión validada sin cama disponible → lista de espera → promoción manual.
- Traslado: cierre de estadía en el dispositivo A y apertura en el B conservando historial.
- Autorización: operador del dispositivo A intentando operar el dispositivo B; rol de consulta intentando modificar.
- Pre-completado: datos de identidad y obra social desde el legajo ciudadano / RENAPER, sin re-preguntar.
- Merenderos: solicitud sin documentación respaldatoria → observada; prestación mensual con totales diarios calculados.

> Los escenarios que surgieron del relevamiento de campo (separación de funciones, una sola plaza
> activa por persona en toda la red, préstamo de plaza, autorización previa de ingreso y límite de
> permanencia de 48 horas en UPI/ECA) **no forman parte de esta etapa**: se prueban con la Versión 2 (§11.6)
> y sus horas están en §11.3. La regla de dosis con prescripción previa corresponde al módulo de
> medicación, que sigue fuera de alcance (§7.1).

---

## 5. Versión 1 — despliegue a ambiente QA

| Concepto | Horas |
|---|---:|
| Configuración del ambiente (Docker, variables de entorno, base de datos) | 8 |
| Despliegue del código y ejecución de migraciones | 5 |
| Carga de datos iniciales (tipos de dispositivo, configuración de los formularios de Adulto Mayor y Abordaje Psicosocial, roles y usuarios de prueba, merenderos de ejemplo) | 8 |
| Verificación post-despliegue y smoke tests | 4 |
| **Subtotal despliegue** | **25** |

---

## 6. Versión 1 — capacitación

| Sesión | Destinatarios | Horas |
|---|---|---:|
| Elaboración de materiales (guía de usuario por rol) | — | 4 |
| Administradores: configuración de tipos y formularios, validación de altas, indicadores y reportes | Equipo ministerio | 5 |
| Operadores de dispositivos: admisiones, egresos, camas y registro diario | Operadores / responsables | 3 |
| Área de merenderos: legajo, entregas de mercaderías y prestación mensual | Equipo del área | 2 |
| **Subtotal capacitación** | | **14** |

---

## 7. Versión 1 — fuera del alcance

Las siguientes funcionalidades forman parte del relevamiento y quedan documentadas como necesidades del Sistema de Gestión Operativa Integral, pero no están incluidas en la estimación base de 436 horas. Su alcance funcional debe validarse con el Ministerio antes de calcular el esfuerzo correspondiente.

### 7.1 Funcionalidades relevadas que quedaron fuera de la Versión 1

| Funcionalidad | Alcance funcional relevado | Estimación |
|---|---|---|
| Inventario y stock integral | Registrar altas por compra o donación, bajas por consumo y existencias de alimentos, artículos de limpieza, fármacos, agua, colchones y kits. Permitir comparar consumo real, stock disponible y demanda para planificar abastecimiento. | **Pendiente** |
| Administración de medicación | Registrar prescripciones, dosis, horarios y entregas. No permitir registrar una dosis sin prescripción previa ni marcar más de una vez la misma dosis por horario y día. | **Pendiente** |
| Asistencia y gestión de RRHH | Digitalizar asistencia, situación de revista, horarios, guardias, cambios de turno y distribución de personal por institución o área. | **Pendiente** |
| Historial clínico y legajo de salud | Centralizar el legajo médico, diagnósticos, turnos e intervenciones de Salud/Enfermería, con permisos restringidos y trazabilidad de acceso. | **Pendiente** |
| Libros institucionales y bitácora de guardia | Reemplazar libros de actas, cuadernos del sereno y registros de operadores por una bitácora digital con traspaso de novedades entre turnos. | **Incluida en la Versión 2** (§11.4, módulo de bitácora y pase de guardia: 32 h) |
| Funcionamiento offline y sincronización | Permitir carga operativa ante cortes momentáneos de conectividad y sincronizar luego con la base central, resolviendo conflictos y conservando la trazabilidad. | **Pendiente** |
| Control de acceso físico | Integrar huella digital o clave individual para registrar accesos, vincularlos con la estadía y eliminar o desactivar el permiso al finalizarla. | **Pendiente** |
| Layout de habitaciones y dispositivos móviles | Visualizar habitaciones, camas, tipo de paciente y régimen de comida; ofrecer interfaces móviles simples para Mantenimiento, Cocina y Lavadero. | **Pendiente** |
| Tablero de Comando central completo | Incorporar paneles de capacidad de la red, demanda y abastecimiento, población/vulnerabilidad/salud, alertas operativas y reportes para la conducción ministerial. | **Pendiente** |
| Planes de contingencia | Activar circuitos para inundaciones, temporales, incendios, frío extremo, calor extremo y emergencias sanitarias, incluyendo censo, triage, suministros y reportes periódicos. | **Pendiente** |
| Integración con ECOM | Integrar por API el stock y los movimientos logísticos con ECOM, según el alcance y momento que defina el equipo del Ministerio. | **Pendiente** |

Estas funcionalidades no modifican el subtotal de desarrollo ni el total general hasta que el Ministerio confirme su alcance y se realice una nueva estimación.

| Ítem | Motivo |
|---|---|
| Formularios de UPI, ECA, Residencias Universitarias, Fortalecimiento Familiar y CDI, y de las tres instituciones relevadas en septiembre (Albergue Madre Teresa de Calcuta, CIS N.º 3 y Parador Nocturno) | En relevamiento por el Ministerio; **se cargan como configuración sin desarrollo adicional** cuando estén definidos (el mecanismo configurable está incluido en D-02 y se amplía en la Versión 2). El relevamiento de campo de septiembre describió cómo operan estas tres instituciones, no los campos de su ficha |
| Línea 102, denuncias y derivaciones de casos sensibles | Etapa posterior acordada con el Ministerio |
| Gestión de personal y dotación por dispositivo | Etapa posterior |
| Rendiciones de fondos y recursos (más allá del registro de kits) | Etapa posterior |
| Relevamiento de infraestructura y preparación tecnológica | Etapa posterior |
| Cierre mensual formal y tablero de comando completo | Etapa posterior (los indicadores básicos sí están incluidos en D-11) |
| Padrón nominal de niños y tutores y asistencia alimentaria diaria de merenderos | Alcance a confirmar con el Ministerio; se estimará por separado si se incorpora |
| App móvil | Esta etapa es de backoffice; no se requiere aplicación de campo |
| Inventario y stock integral de alimentos, limpieza, fármacos, agua, colchones y kits | Funcionalidad documentada en §7.1; estimación pendiente |
| Asistencia y situación de revista del personal | Funcionalidad documentada en §7.1; corresponde a Recursos Humanos y su estimación está pendiente |
| ~~Libros institucionales digitales y bitácora de guardia completa~~ | **Ya no aplica:** la bitácora de guardia con turnos y pase de novedades está incluida en la Versión 2 (§11.4). Siguen fuera los libros de economato, inventario y limpieza |
| Administración de fármacos e historial clínico digital | Funcionalidades documentadas en §7.1; requieren definición clínica y estimación pendiente |
| Control de acceso por huella digital o clave individual | Propuesta del Albergue Calcuta; requiere equipamiento, definición de proveedor e integración |
| Layout interactivo de habitaciones y dispositivos móviles para Cocina, Lavadero y Mantenimiento | Necesidades de operación e infraestructura; no forman parte del backoffice estimado |
| Funcionamiento offline con sincronización automática | Funcionalidad documentada en §7.1; requiere definir conflictos y sincronización antes de estimar |
| Tablero de Comando central completo y planes de contingencia activables | Funcionalidades documentadas en §7.1; esta etapa incluye solo indicadores básicos |
| Integración de stock con ECOM vía API | Funcionalidad documentada en §7.1; alcance y momento pendientes de definición interna |

---

## 8. Versión 1 — supuestos y condiciones

1. El motor de roles (RBAC) y el design system del proyecto están operativos; los módulos los reutilizan sin modificaciones estructurales.
2. La validación RENAPER reusa el servicio existente sin cambios en su contrato.
3. El padrón inicial de dispositivos y merenderos es provisto por el Ministerio en planilla normalizada (una fila por institución, columnas acordadas) antes de la carga inicial (D-13).
4. Los formularios de Adulto Mayor y Abordaje Psicosocial se cargan según los documentos relevados y aprobados el 01/07/2026; ampliaciones posteriores se incorporan por configuración.
5. La prestación de merenderos se carga como **cantidad de raciones** (numérica); si el Ministerio define el criterio "marca por servicio (S/N)", el ajuste es de configuración menor y no altera esta estimación.
6. El ambiente de QA cuenta con Docker Compose operativo y acceso a la base de datos.
7. La capacitación se realiza presencial o por videoconferencia con grupos de hasta 10 personas por sesión; sesiones adicionales se cotizan por separado.
8. El sistema prioriza interfaces de baja fricción y reproduce, cuando sea conveniente, la lógica de los instrumentos en papel para facilitar la adopción en territorio.
9. Las reglas de medicación, autorización previa, préstamo de cama y límite de 48 horas de UPI/ECA se consideran hallazgos funcionales a validar antes de convertirlos en criterios definitivos de desarrollo.
10. La disponibilidad neta se definirá como capacidad total menos camas en reparación más camas prestadas, si el Ministerio confirma este criterio.
11. En ningún nivel de ocupación el sistema bloqueará automáticamente un ingreso: el semáforo alerta y escala la atención, pero la decisión final queda en el área responsable.
12. La eventual provisión de computadoras, conectividad, dispositivos móviles y mecanismos de control de acceso corresponde al Ministerio y no está incluida en las horas de software.

### 8.1 Puntos aún no confirmados

- Formularios completos de UPI, ECA, Residencias Universitarias y Fortalecimiento Familiar.
- Si Fortalecimiento Familiar trabaja con camas o con cupos/plazas.
- Encuadre de albergues y operativos de contención nocturna como tipos propios o variantes de Abordaje Psicosocial.
- Alcance del padrón nominal de niños, niñas y adolescentes, tutores y asistencia alimentaria diaria de merenderos.
- Criterio de carga de la prestación de merenderos: cantidad de raciones o marca por servicio.
- Terminología del área de Salud para disponibilidad y ocupación de camas.
- Alcance y momento de la integración con ECOM.
- Definición de los paneles del Tablero de Comando, la matriz de alertas y los seis planes de contingencia.
- Factibilidad y alcance de conectividad híbrida, sincronización offline, control de acceso físico y equipamiento operativo.

---

## 9. Versión 1 — cronograma

**Inicio:** a definir con el Ministerio (sujeto a aprobación de esta estimación)
**Equipo:** 1 Backend, 1 Frontend, 1 Diseñador, 1 QA
**Supuesto:** 8 horas/día por persona

**Duración estimada:** ~6 semanas (30 días hábiles)

<iframe class="clickup-embed" src="https://sharing.clickup.com/90171120919/g/h/6-901715393894-7/f9adc251126f1e3" onwheel="" width="100%" height="700px" style="background: transparent; border: 1px solid #ccc;"></iframe>

### Notas del cronograma

- El diseño arranca en paralelo con el modelo de datos y entrega primero las pantallas del legajo del dispositivo.
- El backend avanza por dependencias: modelo → configuración → dispositivos/camas → admisiones → merenderos.
- El frontend arranca cuando D-02/D-03 tienen endpoints listos.
- QA escribe casos desde el inicio y ejecuta a medida que cada módulo se completa.
- La carga inicial (D-13) requiere la planilla del Ministerio; puede correr en paralelo al final del desarrollo.
- La capacitación se realiza sobre el ambiente de QA desplegado.

---

## 10. Versión 1 — resumen por fase

```
Desarrollo Backend ·········· 154 h  ████████████████████████████░░░░░░░░
Desarrollo Frontend ········· 103 h  ███████████████████░░░░░░░░░░░░░░░░░
Diseño UX/UI ················  60 h  ███████████░░░░░░░░░░░░░░░░░░░░░░░░░
Pruebas y QA ················  80 h  ███████████████░░░░░░░░░░░░░░░░░░░░░
Despliegue a QA ·············  25 h  █████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
Capacitación ················  14 h  ███░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░

Total                        436 h
```

| | Horas | % |
|---|---:|---:|
| Desarrollo Backend | 154 | 35 % |
| Desarrollo Frontend | 103 | 24 % |
| Diseño UX/UI | 60 | 14 % |
| Pruebas y QA | 80 | 18 % |
| Despliegue | 25 | 6 % |
| Capacitación | 14 | 3 % |
| **Total** | **436** | **100 %** |

---

## 11. Estimación y propuesta — Versión 2

Esta sección es la propuesta de la Versión 2 de punta a punta: qué pidió cada institución durante las
visitas, en qué se diferencia de lo que el sistema ya hace, cuánto cuesta, en qué etapas se entrega y
en cuánto tiempo.

### 11.1 Los cambios que pidieron las instituciones

Cada fila nace de una visita. La columna «hoy» es lo que hace el sistema entregado en la Versión 1.

| Cambio solicitado | Quién lo pidió | Hoy | Se agrega |
|---|---|---|---|
| **Disponibilidad por servicio y cupos por habitación** | Albergue Madre Teresa de Calcuta | Camas planas por institución, sin agrupar | Sectores con cupos por servicio, y plazas de tipo cama, cupo o turno según el dispositivo |
| **Préstamo de cama con autorización** | Albergue Madre Teresa de Calcuta | No existe | Préstamo de plaza por 12 o 24 horas sin perder el vínculo del residente titular |
| **Dejar de transcribir entre turnos** | Albergue Calcuta y Parador Nocturno | Un parte por turno que el turno siguiente sobrescribe | Bitácora por turno cuyas novedades se agregan y nunca se sobrescriben, con pase de guardia y censo automático |
| **Autorización previa antes del alta** | CIS N.º 3 y Parador Nocturno | No existe: el ingreso es directo | Solicitud de ingreso que el programa central autoriza, con vigencia y reserva de plaza |
| **Acceso diferenciado a la información médica y psicosocial** | CIS N.º 3 y Albergue Calcuta | La ficha se ve completa o no se ve | Secciones con nivel de sensibilidad y permiso propio para salud, situación psicosocial y situación judicial |
| **Trazabilidad de las admisiones** | CIS N.º 3 | Historial solo del legajo de la institución | Auditoría de estadías, movimientos, bitácora, entregas y prestaciones |
| **Derivaciones y coordinación con organismos externos** | Dirección de Abordaje Psicosocial (Mírame/Vedia) | No existe | Derivaciones entre instituciones y a organismos externos, con aceptación, rechazo y vencimiento |
| **Historial de intervenciones y legajo compartido** | Dirección de Abordaje Psicosocial | Formulario de ingreso que se completa una sola vez | Ficha que se completa a lo largo de la estadía, con avance por sección, y su lectura, impresión y exportación |
| **Seguimiento de personas que no están alojadas** | Dirección de Abordaje Psicosocial | Solo se registra a quien ocupa una cama | Estadía ambulatoria de seguimiento, compatible con una estadía residencial |
| **Ingreso y egreso de alta rotación** | Parador Nocturno | Alta de una persona por vez, sin movimientos intermedios | Estadía con cambio de plaza, permiso de salida con regreso previsto y traslado con seguimiento |
| **Registro de entregas con quién recibe** | Parador Nocturno y área de merenderos | Entrega con el servicio en texto libre | Catálogo de insumos y kits con equivalencia en raciones, y entregas con receptor y remito |
| **Visibilidad de camas y personas para la conducción** | Dirección del programa | Indicadores de cada institución por separado | Tablero de la red con capacidad, movimientos, permanencia y avisos configurables |
| **Encuadre real de las instituciones** | Albergue Calcuta (edificio de la Iglesia, gestión del Ministerio) | Un solo campo de identidad institucional | Categoría, titularidad del inmueble y dependencia de la gestión por separado, más documentación con vigencia |
| **Que el sistema avise y no bloquee** | Todas | La admisión exige cama disponible | Ingreso excepcional sobre la capacidad con autorización registrada: el sistema avisa y la decisión queda en el área |

### 11.2 De lo que se hizo a lo que hay que hacer

La Versión 1 se definió sobre los formularios en papel y el esquema del Ministerio. El relevamiento
mostró **cómo trabajan las instituciones de verdad**: turnos de veinticuatro horas con pase de
guardia, alta rotación en el parador, habitaciones con cupos por servicio en el albergue,
autorización previa del programa central antes de un ingreso, préstamos de cama entre residentes,
seguimiento de personas que no están alojadas, e información de salud y de situación judicial que
solo puede ver el equipo habilitado.

La diferencia, área por área:

| Área | La Versión 1 hace hoy | La Versión 2 tiene que hacer |
|---|---|---|
| **Capacidad** | Camas con estado y ocupación calculada | Sectores con cupos por servicio; plazas de tipo cama, cupo o turno; préstamo de plaza por 12 o 24 horas; disponibilidad neta |
| **Ingreso** | Admisión con búsqueda por documento y asignación de cama | Solicitud con autorización previa del programa central; verificación de la situación de la persona en toda la red antes de alojarla; ingreso excepcional sobre la capacidad con autorización registrada; estadía ambulatoria sin plaza |
| **Durante la estadía** | Registro de la admisión y del egreso | Cambio de plaza o de sector con historial; permiso de salida con regreso previsto y aviso si no regresa; y una pantalla de la estadía con su línea de tiempo completa |
| **Traslado** | Cierre de la estadía en el origen y apertura en el destino | Estado *en tránsito* visible en las dos instituciones, con recepción o rechazo del destino, plazo de vencimiento y aviso |
| **Ficha de la persona** | Formulario de ingreso por tipo, que se completa al admitir | Ficha que se completa a lo largo de la estadía, con avance por sección y plazo; secciones con nivel de sensibilidad; y lectura, impresión en el formato del papel y exportación |
| **Operación diaria** | Parte diario por turno con cantidades calculadas | Bitácora por turno con novedades tipificadas que se agregan y nunca se sobrescriben; pase de guardia con constancia de quién entrega y quién recibe; censo automático; y regularización de días anteriores |
| **Legajo de la institución** | Identidad, domicilio, responsable y circuito de validación | Encuadre jurídico con categoría, titularidad del inmueble y dependencia de la gestión por separado; documentación con vigencia y aviso de vencimiento; estados de *inauguración pendiente* y de *suspensión* con reactivación; y nivel de confianza del dato |
| **Derivaciones** | No contemplado | Derivaciones entre instituciones y a organismos externos, con aceptación, rechazo y vencimiento; lista de espera con prioridad; y vista de dónde hay plazas disponibles en la red |
| **Permisos** | Roles con alcance por institución | Alcance por área del Ministerio; niveles de sensibilidad de la información; y separación de funciones: quien registra un movimiento no puede validarlo |
| **Configuración** | Tipos de dispositivo y campos del formulario | Reglas por tipo administradas desde el sistema: qué plazas admite, si exige autorización previa, si permite préstamo, límite de permanencia, secciones mínimas de la ficha, catálogos de motivos y umbrales de aviso |
| **Conducción** | Indicadores de cada institución | Tablero de la red con capacidad, movimientos, permanencia y avisos configurables por regla |
| **Merenderos** | Solicitud, validación, entregas y prestación mensual | Catálogo de insumos y kits con equivalencia en raciones; entregas con quién recibe y remito; prestación con los servicios y los días de funcionamiento de cada merendero; cierre mensual; y cobertura alimentaria |
| **Trazabilidad** | Historial del legajo institucional | Auditoría única de todo el programa: estadías, movimientos, bitácora, entregas y prestaciones |
| **Carga inicial** | Importación del padrón de instituciones | Importación de sectores, plazas y personas alojadas, para arrancar con el censo real del día uno |

!!! tip "Qué no se vuelve a hacer"
    El motor de roles, la validación de identidad contra la Base de Personas, el legajo ciudadano, las
    solapas del legajo, el sistema de diseño y el constructor de formularios ya están construidos y se
    reutilizan. Por eso la Versión 2 estima **628 h** y no las **más de 900 h** que costaría el mismo
    alcance partiendo de cero. Los **ajustes sobre funcionalidad ya entregada** (18 h: paginación del
    padrón, aviso de código repetido y vocabulario de los indicadores) **no se suman a las 628 h**.

### 11.3 Cómo se compone la estimación

| Concepto | Horas |
|---|---:|
| Desarrollo Backend | 285 |
| Desarrollo Frontend | 189 |
| Análisis funcional y definiciones con el Ministerio | 24 |
| Pruebas funcionales y QA | 73 |
| Diseño UX/UI | 27 |
| Despliegue a ambiente QA y datos iniciales | 16 |
| Capacitación | 14 |
| **Total Versión 2** | **628** |

Para comparar con lo ya aprobado:

| Etapa | Horas | Estado |
|---|---:|---|
| Versión 1 — alcance base | 436 | Aprobada y desarrollada |
| Versión 2 — alcance que se agrega | 628 | En validación |
| **Total del programa** | **1.064** | |

### 11.4 Detalle por módulo

Los doce módulos cubren el alcance completo del programa con las funcionalidades relevadas. Las horas
son de desarrollo; el análisis, las pruebas, el diseño, el despliegue y la capacitación están en
§11.3 y se reparten por etapa en §11.5.

| Ref | Módulo | Qué incorpora | Horas |
|---|---|---|---:|
| M1 | Legajo institucional | Base común de dispositivos y merenderos: encuadre jurídico, subsecretaría de la que depende, servicios que brinda, documentación con vigencia, procedencia y confianza del dato, estados de inauguración y suspensión, listado, detalle y fusión de instituciones duplicadas | 44 |
| M2 | Sectores y plazas | Sectores con cupos por servicio, plazas de tipo cama, cupo o turno, préstamo, reubicación asistida y cálculo único de ocupación, disponibilidad y censo | 28 |
| M3 | Estadías | Solicitud con autorización previa, ingreso guiado con verificación en la red, movimientos (cambio de plaza, préstamo, permiso de salida), traslado en tránsito, egreso con derivación, pantalla de la estadía, avisos, y el historial completo de la persona en su Legajo Ciudadano | 110 |
| M4 | Formularios de la institución | Configurador donde el Ministerio arma **los formularios de cada tipo de institución** sin depender de desarrollo: ingreso, asignación, bitácora, egreso, traslado y prestación pasan a ser parametría con campos protegidos. Secciones sensibles con acceso por rol, aviso de lectura registrado, bloqueo de copiado y marca de agua. Lectura, impresión y exportación | 88 |
| M5 | Operación diaria | Bitácora por turno con novedades tipificadas y versiones, pase de guardia, censo automático y regularización | 32 |
| M6 | Espera y derivaciones | Lista de espera con prioridad y reserva, derivaciones entre instituciones y a organismos externos, y vista de plazas en la red | 28 |
| M7 | Permisos y configuración | Alcance por institución, por subsecretaría y total; niveles de sensibilidad; separación de funciones; y la configuración de reglas por tipo de dispositivo | 40 |
| M8 | Tablero y avisos | Tablero de la red con capacidad, movimientos, permanencia y cobertura, y motor de avisos configurable por regla | 22 |
| M9 | Reportes | Diez reportes exportables en CSV y Excel, acotados al alcance y a la sensibilidad de cada usuario, con registro de quién exportó | 12 |
| M10 | Carga inicial y auditoría | Importación de instituciones, sectores, plazas y personas alojadas con nivel de confianza y verificación en campo, y auditoría única del programa | 20 |
| M11 | Merenderos | Legajo con navegación propia y edición con historial, documentación con vigencia, catálogo de insumos y kits con equivalencia en raciones, y entregas con receptor y remito | 32 |
| M12 | Prestación y cobertura | Prestación mensual con los servicios y días de cada merendero, cierre del mes y cobertura alimentaria | 18 |
| | **Subtotal desarrollo** | | **474** |

> Los 18 h de ajustes sobre funcionalidad ya entregada no figuran en esta tabla ni en el total: se absorben.

### 11.5 Propuesta de etapas y tiempos

El alcance se entrega en **cuatro etapas**, cada una utilizable por sí misma. El Ministerio puede
aprobarlas por separado y detenerse al final de cualquiera de ellas.

| Etapa | Qué queda operativo al terminarla | Qué cambios solicitados resuelve | Horas | Duración |
|---|---|---|---:|---|
| **1** | La institución opera: legajo con encuadre y documentación, permisos por subsecretaría con separación de funciones, reglas por tipo, sectores y plazas, y el circuito completo de estadías con traslados | Cupos por servicio · préstamo de cama · autorización previa · alta rotación · traslado con seguimiento · seguimiento sin alojamiento · avisar sin bloquear · encuadre real | 302 | 5 semanas |
| **2** | Los formularios y el turno: configurador de formularios por tipo con secciones sensibles y lectura registrada, bitácora por turno con pase de guardia y censo | Dejar de transcribir entre turnos · acceso diferenciado a información médica y psicosocial · historial de intervenciones · formularios que el Ministerio cambia sin desarrollo | 148 | 3 semanas |
| **3** | La red y la conducción: derivaciones, lista de espera con prioridad, tablero de la red, reportes y carga inicial del padrón | Derivaciones y organismos externos · visibilidad para la conducción · trazabilidad de admisiones | 98 | 2 semanas |
| **4** | Merenderos: catálogo de kits, entregas con receptor, prestación mensual y cobertura, más el despliegue final y la capacitación | Registro de entregas con quién recibe | 80 | 2 semanas |
| | **Total** | | **628** | **12 semanas** |

**Equipo:** 1 desarrollador backend y 1 desarrollador frontend a tiempo completo, con análisis
funcional, diseño y QA en paralelo a tiempo parcial.
**Supuesto:** 8 horas por día y por persona.
**Inicio:** a definir con el Ministerio, sujeto a la aprobación de esta estimación.

!!! note "Si hubiera que elegir una sola etapa"
    La **etapa 1** es la que más cambia la operación: resuelve ocho de los catorce cambios solicitados,
    incluidos los tres más repetidos en las visitas (cupos por servicio, autorización previa de ingreso
    y traslado con seguimiento). Las etapas 3 y 4 suman 178 h y ninguna bloquea la operación diaria.

### 11.6 Escenarios críticos que se prueban en esta etapa

Además de los de la Versión 1, las 64 h de pruebas cubren los escenarios que surgieron del
relevamiento:

- **Separación de funciones:** quien carga un movimiento no puede validarlo en el mismo circuito.
- **Una sola plaza activa por persona en toda la red**, compatible con un seguimiento ambulatorio.
- **Préstamo de plaza** por 12 o 24 horas sin perder el vínculo del residente titular.
- **Autorización previa de ingreso** del programa central en los tipos que la exigen, con vigencia.
- **Ingreso excepcional sobre la capacidad:** el sistema avisa y nunca bloquea; queda registrado quién autoriza y por qué.
- **Límite de permanencia de 48 horas** en UPI y ECA cuando el ingreso viene de una medida de protección judicial.
- **Traslado en tránsito:** la persona nunca queda alojada en dos instituciones a la vez, y el tránsito vencido avisa.
- **Turno pisado:** una novedad cargada por un operador no puede ser sobrescrita por el del turno siguiente.
- **Acceso a información sensible:** sin el nivel correspondiente no se ve ni se exporta, tampoco por acceso directo.
- **Cierre del mes de prestación** por un rol distinto del que cargó, y reapertura con motivo registrado.

### 11.7 Horas por perfil y por etapa

Resumen de las 628 h en las dos vistas que se usan para planificar y aprobar.

| Perfil | Horas | Proporción |
|---|---:|---:|
| Desarrollador Backend | 285 | 45 % |
| Desarrollador Frontend | 189 | 30 % |
| Pruebas funcionales y QA | 73 | 12 % |
| Análisis funcional y definiciones | 24 | 4 % |
| Diseño UX/UI | 27 | 4 % |
| Despliegue a ambiente QA | 16 | 3 % |
| Capacitación | 14 | 2 % |
| **Total Versión 2** | **628** | **100 %** |

| Etapa | Horas | Proporción | Acumulado |
|---|---:|---:|---:|
| 1 — Institución, permisos, capacidad y estadías | 302 | 48 % | 302 |
| 2 — Formularios y operación por turno | 148 | 24 % | 450 |
| 3 — Red, conducción y carga inicial | 98 | 16 % | 548 |
| 4 — Merenderos, despliegue y capacitación | 80 | 12 % | 628 |
| **Total** | **628** | **100 %** | |

El Ministerio puede aprobar por tramos: la columna «acumulado» muestra cuántas horas suma detenerse al
final de cada etapa.

### 11.8 Qué no está incluido

Las horas son de esfuerzo técnico neto: no incluyen reuniones de seguimiento ni gestión de proyecto.
Los 18 h de ajustes sobre funcionalidad ya entregada se absorben y no se suman al total.

Los módulos de §7.1 —inventario y stock, administración de medicación, asistencia y recursos humanos,
historial clínico, bitácora de guardia ampliada, funcionamiento sin conexión, control de acceso
físico, plano de habitaciones, tablero de comando completo, planes de contingencia e integración con
ECOM— **no están incluidos** en las 628 h y se estiman por separado cuando el Ministerio confirme su
alcance. Tampoco entran el padrón nominal de niñas, niños y adolescentes de los merenderos ni la
aplicación móvil.
