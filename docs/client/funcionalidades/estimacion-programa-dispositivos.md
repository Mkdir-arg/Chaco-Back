# Estimación de esfuerzo — Programa Dispositivos y Programa Merenderos
## Sistema de Gestión Operativa Integral — Legajos, admisiones, camas y asistencia alimentaria

**Fecha de la estimación base:** 2026-07-02
**Versión:** 1.1
**Alcance estimado:** definición funcional del Programa Dispositivos y Programa Merenderos, complementada con el relevamiento de campo realizado en el Albergue Madre Teresa de Calcuta, CIS N.º 3, Dirección de Abordaje Psicosocial (Programa Mírame/Vedia) y Parador Nocturno.
**Estado:** estimación base aprobada; relevamiento ampliado en validación con el Ministerio.

> **Base de la estimación:** la definición funcional publicada en [Programa Dispositivos](programa-dispositivos.md), con la conformidad del Ministerio sobre el alcance base, y el documento funcional del Sistema de Gestión Operativa Integral. El relevamiento confirma la necesidad de un legajo digital único, trazabilidad por turnos, ocupación calculada y permisos diferenciados. Esta etapa continúa siendo **100% backoffice** y reutiliza el motor de roles, la validación RENAPER, los formularios configurables y las solapas del legajo ciudadano ya construidos.

> **Criterio de lectura:** los hallazgos de campo se incorporan como contexto funcional, reglas y temas de alcance. Los módulos de inventario, asistencia de personal, libros institucionales, medicación, historial clínico, contingencias, equipamiento, conectividad e integración con ECOM no se suman automáticamente a las 436 horas: quedan identificados para confirmación y, cuando corresponda, una estimación específica.

---

## 1. Resumen ejecutivo

| Concepto | Horas |
|---|---:|
| Desarrollo Backend | 154 |
| Desarrollo Frontend | 103 |
| Diseño UX/UI | 60 |
| Pruebas funcionales y QA | 80 |
| Despliegue a ambiente QA | 25 |
| Capacitación | 14 |
| **Total** | **436** |

> Las horas corresponden a esfuerzo técnico neto. No incluyen reuniones de seguimiento ni gestión de proyecto. Los formularios de los tipos aún en relevamiento (UPI, ECA, Residencias Universitarias, Fortalecimiento Familiar) **no requieren desarrollo adicional**: se cargan como configuración cuando el Ministerio los entregue (ver §7).

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

---

## 2. Desarrollo

### 2.1 Detalle por módulo

| Ref | Módulo | Descripción | Horas | Perfil |
|---|---|---|---:|---|
| D-01 | Modelo de datos | Modelos del dominio: Dispositivo institucional, Tipo de dispositivo, Cama, Admisión/Estadía, campos configurables del formulario de admisión, Registro diario, Merendero, Entrega de mercaderías y Prestación mensual. Vínculo con el legajo ciudadano y membresía al programa (habilita la solapa). Migraciones y admin básico. | 24 | Backend |
| D-02 | Configuración del programa | ABM del catálogo de **tipos de dispositivo** y de los **campos del formulario de admisión por tipo** (secciones + tipos de campo: texto / número / selector / selector múltiple / fecha / archivo). Carga de la configuración inicial de **Adulto Mayor** (31 campos) y **Abordaje Psicosocial** (45 campos) según los formularios relevados. Catálogo de servicios del merendero. | 34 | Backend + Frontend |
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

## 3. Diseño UX/UI

| Concepto | Horas |
|---|---:|
| Flujos y wireframes de las 8 pantallas del programa (dispositivos, detalle, admisión/egreso, camas, merenderos, configuración, indicadores, reportes) | 24 |
| Diseño del formulario de admisión dinámico (secciones largas, estados de error, pre-completado) | 14 |
| Diseño de camas, semáforos e indicadores (estados visuales) | 10 |
| Ajustes sobre componentes del design system y revisión con el equipo | 12 |
| **Subtotal diseño** | **60** |

> El design system del proyecto ya está construido y aplicado (tokens, componentes, patrones de pantalla); el diseño de esta etapa compone sobre esa base en lugar de crear lenguaje visual nuevo.

---

## 4. Pruebas funcionales y QA

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
- Separación de funciones: el usuario que carga un movimiento no puede validarlo en el mismo circuito.
- Unicidad transversal: una persona no puede tener dos camas activas, aun en dispositivos distintos.
- Préstamo de cama: asignación excepcional configurable por 12 o 24 horas sin perder el vínculo del residente titular.
- Fechas y horarios: egreso nunca anterior al ingreso; horarios expresados en horas, sin minutos.
- CIS N.º 3: dosis solo con prescripción previa y una única marca por horario y día.
- CIS N.º 3 y Parador Nocturno: autorización previa del Programa Central/Media antes del alta, cuando aplique.
- UPI/ECA: alerta del límite de permanencia de 48 horas cuando el ingreso proviene de una medida de protección judicial.

---

## 5. Despliegue a ambiente QA

| Concepto | Horas |
|---|---:|
| Configuración del ambiente (Docker, variables de entorno, base de datos) | 8 |
| Despliegue del código y ejecución de migraciones | 5 |
| Carga de datos iniciales (tipos de dispositivo, configuración de los formularios de Adulto Mayor y Abordaje Psicosocial, roles y usuarios de prueba, merenderos de ejemplo) | 8 |
| Verificación post-despliegue y smoke tests | 4 |
| **Subtotal despliegue** | **25** |

---

## 6. Capacitación

| Sesión | Destinatarios | Horas |
|---|---|---:|
| Elaboración de materiales (guía de usuario por rol) | — | 4 |
| Administradores: configuración de tipos y formularios, validación de altas, indicadores y reportes | Equipo ministerio | 5 |
| Operadores de dispositivos: admisiones, egresos, camas y registro diario | Operadores / responsables | 3 |
| Área de merenderos: legajo, entregas de mercaderías y prestación mensual | Equipo del área | 2 |
| **Subtotal capacitación** | | **14** |

---

## 7. Fuera del alcance de esta estimación

Las siguientes funcionalidades forman parte del relevamiento y quedan documentadas como necesidades del Sistema de Gestión Operativa Integral, pero no están incluidas en la estimación base de 436 horas. Su alcance funcional debe validarse con el Ministerio antes de calcular el esfuerzo correspondiente.

### 7.1 Funcionalidades relevadas pendientes de estimación

| Funcionalidad | Alcance funcional relevado | Estimación |
|---|---|---|
| Inventario y stock integral | Registrar altas por compra o donación, bajas por consumo y existencias de alimentos, artículos de limpieza, fármacos, agua, colchones y kits. Permitir comparar consumo real, stock disponible y demanda para planificar abastecimiento. | **Pendiente** |
| Administración de medicación | Registrar prescripciones, dosis, horarios y entregas. No permitir registrar una dosis sin prescripción previa ni marcar más de una vez la misma dosis por horario y día. | **Pendiente** |
| Asistencia y gestión de RRHH | Digitalizar asistencia, situación de revista, horarios, guardias, cambios de turno y distribución de personal por institución o área. | **Pendiente** |
| Historial clínico y legajo de salud | Centralizar el legajo médico, diagnósticos, turnos e intervenciones de Salud/Enfermería, con permisos restringidos y trazabilidad de acceso. | **Pendiente** |
| Libros institucionales y bitácora de guardia | Reemplazar libros de actas, cuadernos del sereno y registros de operadores por una bitácora digital con traspaso de novedades entre turnos. | **Pendiente** |
| Funcionamiento offline y sincronización | Permitir carga operativa ante cortes momentáneos de conectividad y sincronizar luego con la base central, resolviendo conflictos y conservando la trazabilidad. | **Pendiente** |
| Control de acceso físico | Integrar huella digital o clave individual para registrar accesos, vincularlos con la estadía y eliminar o desactivar el permiso al finalizarla. | **Pendiente** |
| Layout de habitaciones y dispositivos móviles | Visualizar habitaciones, camas, tipo de paciente y régimen de comida; ofrecer interfaces móviles simples para Mantenimiento, Cocina y Lavadero. | **Pendiente** |
| Tablero de Comando central completo | Incorporar paneles de capacidad de la red, demanda y abastecimiento, población/vulnerabilidad/salud, alertas operativas y reportes para la conducción ministerial. | **Pendiente** |
| Planes de contingencia | Activar circuitos para inundaciones, temporales, incendios, frío extremo, calor extremo y emergencias sanitarias, incluyendo censo, triage, suministros y reportes periódicos. | **Pendiente** |
| Integración con ECOM | Integrar por API el stock y los movimientos logísticos con ECOM, según el alcance y momento que defina el equipo del Ministerio. | **Pendiente** |

Estas funcionalidades no modifican el subtotal de desarrollo ni el total general hasta que el Ministerio confirme su alcance y se realice una nueva estimación.

| Ítem | Motivo |
|---|---|
| Formularios de UPI, ECA, Residencias Universitarias y Fortalecimiento Familiar | En relevamiento por el Ministerio; **se cargan como configuración sin desarrollo adicional** cuando estén definidos (el mecanismo configurable está incluido en D-02) |
| Línea 102, denuncias y derivaciones de casos sensibles | Etapa posterior acordada con el Ministerio |
| Gestión de personal y dotación por dispositivo | Etapa posterior |
| Rendiciones de fondos y recursos (más allá del registro de kits) | Etapa posterior |
| Relevamiento de infraestructura y preparación tecnológica | Etapa posterior |
| Cierre mensual formal y tablero de comando completo | Etapa posterior (los indicadores básicos sí están incluidos en D-11) |
| Padrón nominal de niños y tutores y asistencia alimentaria diaria de merenderos | Alcance a confirmar con el Ministerio; se estimará por separado si se incorpora |
| App móvil | Esta etapa es de backoffice; no se requiere aplicación de campo |
| Inventario y stock integral de alimentos, limpieza, fármacos, agua, colchones y kits | Funcionalidad documentada en §7.1; estimación pendiente |
| Asistencia y situación de revista del personal | Funcionalidad documentada en §7.1; corresponde a Recursos Humanos y su estimación está pendiente |
| Libros institucionales digitales y bitácora de guardia completa | Funcionalidad documentada en §7.1; el registro diario incluido no equivale a un módulo integral |
| Administración de fármacos e historial clínico digital | Funcionalidades documentadas en §7.1; requieren definición clínica y estimación pendiente |
| Control de acceso por huella digital o clave individual | Propuesta del Albergue Calcuta; requiere equipamiento, definición de proveedor e integración |
| Layout interactivo de habitaciones y dispositivos móviles para Cocina, Lavadero y Mantenimiento | Necesidades de operación e infraestructura; no forman parte del backoffice estimado |
| Funcionamiento offline con sincronización automática | Funcionalidad documentada en §7.1; requiere definir conflictos y sincronización antes de estimar |
| Tablero de Comando central completo y planes de contingencia activables | Funcionalidades documentadas en §7.1; esta etapa incluye solo indicadores básicos |
| Integración de stock con ECOM vía API | Funcionalidad documentada en §7.1; alcance y momento pendientes de definición interna |

---

## 8. Supuestos y condiciones

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

## 9. Cronograma

**Inicio:** a definir con el Ministerio (sujeto a aprobación de esta estimación)
**Equipo:** 1 Backend, 1 Frontend, 1 Diseñador, 1 QA
**Supuesto:** 8 horas/día por persona

**Duración estimada:** ~6 semanas (30 días hábiles)

### Notas del cronograma

- El diseño arranca en paralelo con el modelo de datos y entrega primero las pantallas del legajo del dispositivo.
- El backend avanza por dependencias: modelo → configuración → dispositivos/camas → admisiones → merenderos.
- El frontend arranca cuando D-02/D-03 tienen endpoints listos.
- QA escribe casos desde el inicio y ejecuta a medida que cada módulo se completa.
- La carga inicial (D-13) requiere la planilla del Ministerio; puede correr en paralelo al final del desarrollo.
- La capacitación se realiza sobre el ambiente de QA desplegado.

---

## 10. Resumen por fase

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
