# :material-map-marker-radius-outline: Plataforma Provincial de Gestión Social ante Emergencias

## Tres alternativas de desarrollo de aplicaciones

[Descargar propuesta ejecutiva en PDF](assets/propuesta-ejecutiva-icore-emergencias.pdf?v=equipo): resumen del objetivo, las alternativas y los perfiles de equipo, con marca ICORE y sin fechas.

| Campo | Detalle |
|---|---|
| Organismo destinatario | Ministerio de Desarrollo Humano de la Provincia del Chaco |
| Proponente | ICORE |
| Fecha de actualización | 16 de octubre de 2026 |
| Versión | 0.9 |
| Estado | Borrador de propuesta para revisión |
| Objeto | Desarrollo de una aplicación web para la gestión de emergencias sociales |
| Alternativas | Esencial, Operativa e Integral |
| Servicio opcional | Mesa de ayuda funcional dedicada 24/7, contratable con cualquiera de las alternativas |
| Estimación de la alternativa Integral | 6.000 a 6.500 horas totales de trabajo |
| Contenido | Funcionalidades, entregables, equipo y estimación en horas, sin importes |

!!! abstract "La propuesta"
    ICORE propone tres alternativas para desarrollar la Mesa de Situación. Cada una permite monitorear el territorio y registrar la respuesta social, con distinta profundidad en la gestión de asistencia, albergues, dispositivos y seguimiento. El Ministerio podrá elegir el alcance que mejor responda a sus prioridades.

!!! info "Cómo comparar las alternativas"
    Se contrata una alternativa. Operativa incluye las funciones de Esencial e Integral incluye las de Operativa. Las horas de cada opción corresponden a su alcance completo: no se suman entre sí.

El proyecto es independiente de Datañach. Su experiencia en relevamientos, legajos y gestión institucional se toma como referencia para el desarrollo.

!!! tip "Planificación por alternativa"
    Consultá el [anexo con los tres Gantt, hitos, equipos y horas por mes](planificacion-mesa-situacion-el-nino.md). Presenta escenarios de dedicación concentrada al inicio, calculados sobre las mismas horas de esta propuesta.

## 1. Objetivo

Contar con una aplicación que permita conocer la criticidad territorial y organizar la respuesta social y asistencial del Ministerio: población afectada, albergues, necesidades, recursos y acciones realizadas.

El mapa será la pantalla principal. Desde allí, los equipos podrán consultar la situación de cada zona y acceder a los registros que les correspondan por su función y territorio. Las competencias de Defensa Civil, Salud, Seguridad e Infraestructura permanecen en sus organismos; la aplicación permitirá registrar las derivaciones y su seguimiento.

## 2. Comparación de las tres propuestas

| Aspecto | Propuesta 1: Esencial | Propuesta 2: Operativa | Propuesta 3: Integral |
|---|---|---|---|
| Propósito | Conocer la situación y registrar la atención | Gestionar las cuatro mesas y el circuito de asistencia | Coordinar la respuesta completa y controlar movimientos y excepciones |
| Horas totales estimadas | **3.000 a 3.500 h** | **4.500 a 5.000 h** | **6.000 a 6.500 h** |
| Escenario central | 3.250 h | 4.750 h | 6.250 h |
| Aplicación | Web adaptable a computadoras y celulares | Web adaptable a computadoras y celulares | Web adaptable a computadoras y celulares |
| Usuarios concurrentes | Base de validación: 200 usuarios activos | Base de validación: 200 usuarios activos | Base de validación: 200 usuarios activos |
| Actualización en vivo | Mapa, incidentes y ocupación | Lo anterior, más solicitudes y stock | Lo anterior, más movimientos y tableros de seguimiento |
| Objetivo de propagación | Hasta 2 segundos en el 95% de las actualizaciones medidas | Mismo objetivo | Mismo objetivo |

Los rangos son estimaciones preliminares de horas-persona. Incluyen análisis, desarrollo, diseño, QA, gestión y capacitación. Expresan el esfuerzo total de trabajo para cada alternativa.

### Comparación funcional

| Funcionalidad | Esencial | Operativa | Integral |
|---|---|---|---|
| Mapa provincial | Zonas, puntos, filtros y criticidad registrada | Agrega filtros por mesa, responsable y estado de atención | Agrega comparación entre períodos y consulta del historial territorial |
| Alertas pluviales y fluviales | Registro manual con fuente y fecha | Igual que Esencial | Igual que Esencial |
| Población y familias | Identificación, ubicación, condición y necesidades | Agrega seguimiento de asistencia y validación de relevamientos | Agrega revisión de posibles duplicados e historial consolidado de intervenciones |
| Incidentes, Mesa 1 | Carga, prioridad, responsable, estado y derivación registrada | Agrega seguimiento de derivaciones, plazos y vínculo con solicitudes | Agrega escalamiento interno por reglas y seguimiento entre equipos |
| Asistencia y logística, Mesa 2 | Registro de necesidad y asistencia realizada; sin circuito FUSE ni inventario | FUSE con una autorización, un despacho y una recepción por solicitud; stock básico por ubicación | Agrega reservas, entregas parciales, devoluciones, anulaciones controladas y transferencias entre ubicaciones |
| Albergues, Mesa 3 | Ficha, capacidad, personas alojadas e ingresos/egresos | Agrega composición familiar, raciones, servicios y necesidades | Agrega traslados vinculados, seguimiento de capacidad y coordinación de abastecimiento |
| Dispositivos propios, Mesa 4 | Sin módulo específico | Ficha, estado, necesidades e incidencias | Agrega planes de acción, responsables, vencimientos y seguimiento de continuidad |
| Bitácora | Novedades y pendientes | Agrega pase de guardia y vinculación con casos | Agrega entrega y recepción de pendientes con trazabilidad |
| Reportes | Resumen por territorio, fecha y albergue; exportación básica | Agrega asistencia, stock, solicitudes y actividad por mesa | Agrega evolución, comparaciones, demanda sin resolver y tableros por rol |
| Avisos dentro de la aplicación | Indicadores de estado y pendientes | Agrega faltantes y vencimientos definidos | Agrega reglas configurables y escalamiento interno |
| Importación de padrones | Una plantilla acordada y reporte de errores | Agrega revisión previa de lotes y trazabilidad de importaciones | Agrega conciliación de posibles duplicados y correcciones supervisadas |
| Roles e historial | Permisos por función y territorio; autor y fecha de cambios | Agrega separación entre carga, validación y autorización | Agrega permisos más detallados para datos sensibles y consulta de auditoría |

## 3. Propuesta 1: aplicación Esencial

### Qué resuelve

Permite iniciar el registro coordinado de la emergencia. Los equipos ven las zonas afectadas, identifican personas y familias, cargan incidentes y consultan la ocupación de los albergues.

### Funcionalidades incluidas

- Mapa provincial con filtros por departamento y localidad, zonas críticas y semáforos registrados por los equipos.
- Indicadores de población afectada, incidentes abiertos y personas alojadas.
- Registro de personas y familias, ubicación, condición de afectación, necesidades y vulnerabilidades.
- Historial básico de relevamientos y asistencia realizada.
- Incidentes con prioridad, responsable, estado, acciones y derivación a otro organismo.
- Ficha de albergue, capacidad, ingreso y egreso de personas y ocupación calculada a partir de movimientos.
- Bitácora de novedades y pendientes.
- Reportes básicos y exportación de información autorizada.
- Usuarios, permisos, historial de cambios y carga inicial desde una plantilla de padrón.
- Actualización en vivo de las pantallas incluidas.

### Límite del alcance

Las necesidades y la asistencia realizada se registran como información del caso. El proceso de solicitud, autorización y despacho FUSE, el inventario y la gestión específica de dispositivos se incorporan a partir de la propuesta Operativa.

### Entregables

Aplicación web con los módulos incluidos, documentación funcional, casos de prueba, manual de uso y capacitación de los perfiles que participan en la operación.

**Estimación:** 3.000 a 3.500 horas totales.

## 4. Propuesta 2: aplicación Operativa

### Qué resuelve

Incluye la propuesta Esencial y permite trabajar con las cuatro mesas. Incorpora el circuito de asistencia, el stock por ubicación y la gestión de dispositivos, con trazabilidad entre las áreas que solicitan, autorizan y entregan.

### Funcionalidades que agrega

- Seguimiento de necesidades de personas y familias, con validación de relevamientos y asistencia vinculada.
- Derivaciones con responsable, plazos y seguimiento de respuesta.
- Circuito FUSE: solicitud, validación, autorización, despacho con remito y recepción.
- Un despacho y una recepción por solicitud, con historial de cada etapa.
- Stock por depósito o albergue, ingresos, egresos y avisos de faltantes.
- Albergues con composición familiar, raciones, necesidades, servicios y estado operativo.
- Ficha de dispositivos propios, recursos necesarios, incidencias y acciones registradas.
- Pase de guardia con pendientes vinculados a incidentes, solicitudes y albergues.
- Reportes de asistencia, solicitudes, stock y actividad por mesa.
- Revisión de padrones antes de confirmar su importación, con resultados por lote.
- Separación de permisos entre quienes cargan, validan y autorizan.

### Límite del alcance

El circuito de asistencia contempla una entrega completa por solicitud. Las entregas parciales, reservas, devoluciones y transferencias de stock se incorporan en Integral. Las correcciones del circuito simple conservarán el historial y se definirán durante el análisis.

### Entregables

Aplicación web con las cuatro mesas, circuitos vinculados, reportes operativos, documentación, pruebas de los flujos completos y capacitación por rol.

**Estimación:** 4.500 a 5.000 horas totales.

## 5. Propuesta 3: aplicación Integral

### Qué resuelve

Incluye la propuesta Operativa y amplía el control de la respuesta social: entregas parciales, movimientos entre ubicaciones, traslados de personas, pendientes entre equipos y análisis de la evolución territorial.

### Funcionalidades que agrega

- Consulta de la evolución territorial y comparación entre períodos, a partir de los datos registrados.
- Historial consolidado de relevamientos e intervenciones sobre personas y familias.
- Revisión supervisada de posibles duplicados en registros e importaciones.
- Reservas de insumos para solicitudes autorizadas.
- Despachos y recepciones parciales, con cantidades pendientes y cierre del circuito.
- Devoluciones, anulaciones y correcciones con motivo, permisos e historial.
- Transferencias de insumos entre depósitos y albergues, con origen, destino y confirmación de recepción.
- Traslados de personas entre albergues, conservando el vínculo entre egreso e ingreso.
- Seguimiento de necesidades de abastecimiento y capacidad de alojamiento.
- Planes de acción para dispositivos, con responsables, vencimientos y seguimiento.
- Entrega y recepción de pendientes entre guardias y equipos.
- Avisos y escalamiento dentro de la aplicación mediante reglas acordadas.
- Tableros por rol, comparación de períodos, evolución de entregas y situaciones sin resolver.
- Permisos detallados para información sensible y consulta de auditoría.

### Límite del alcance

Los avisos se generan con reglas acordadas sobre datos de la aplicación. La conexión automática con fuentes climáticas, las notificaciones por canales externos y las funciones predictivas se tratan como ampliaciones independientes.

### Entregables

Aplicación web con el alcance Integral, documentación de reglas y permisos, pruebas de concurrencia y de los circuitos con excepciones, manuales por rol y capacitación.

**Estimación:** 6.000 a 6.500 horas totales. **Escenario central:** 6.250 horas.

## 6. Horas de trabajo por alternativa

### Distribución por disciplina

La tabla muestra el escenario central de cada propuesta. Las horas se asignan al trabajo previsto; la dedicación de cada perfil varía según la etapa.

| Disciplina | Esencial | Operativa | Integral |
|---|---:|---:|---:|
| Análisis funcional | 600 | 900 | 1.200 |
| Desarrollo de la aplicación | 1.900 | 2.850 | 3.840 |
| QA y pruebas de aceptación | 360 | 500 | 640 |
| Diseño UX/UI | 120 | 160 | 200 |
| Gestión del proyecto | 150 | 220 | 240 |
| Manuales y capacitación | 120 | 120 | 130 |
| **Total de horas-persona** | **3.250** | **4.750** | **6.250** |
| **Rango de estimación** | **3.000–3.500** | **4.500–5.000** | **6.000–6.500** |

El desarrollo incluye diseño técnico, programación, revisión y corrección de defectos. QA contempla validación funcional, permisos, regresión, concurrencia y pruebas de aceptación. Los rangos expresan incertidumbre de la estimación, no una bolsa adicional sumada al total.

### Distribución de las horas de desarrollo por módulo

Estas horas están incluidas en la fila Desarrollo de la aplicación de la tabla anterior.

| Componente | Esencial | Operativa | Integral |
|---|---:|---:|---:|
| Base funcional, usuarios, permisos e historial | 240 | 260 | 320 |
| Tablero y mapa de criticidad | 300 | 340 | 440 |
| Población y relevamientos | 340 | 420 | 480 |
| Incidentes y articulación | 240 | 300 | 360 |
| Circuito FUSE y stock | 0 | 400 | 650 |
| Albergues | 260 | 360 | 460 |
| Dispositivos propios | 0 | 180 | 240 |
| Bitácora, avisos y reportes | 180 | 220 | 300 |
| Actualización en vivo y controles de concurrencia | 180 | 200 | 280 |
| Importación de padrones | 80 | 90 | 150 |
| Integración entre módulos y ajustes de rendimiento | 80 | 80 | 160 |
| **Total de desarrollo** | **1.900** | **2.850** | **3.840** |

En Esencial, el registro simple de asistencia está comprendido en Población e Incidentes. El valor cero de FUSE y stock indica que esa alternativa no incluye el circuito logístico.

## 7. Equipo de desarrollo

| Perfil | Esencial | Operativa | Integral |
|---|---|---|---|
| Analistas funcionales | Hasta 3; 600 h de análisis | Hasta 4; 900 h de análisis | Hasta 5; 1.200 h de análisis |
| Desarrolladores | Hasta 6, con uno a cargo de la conducción técnica | Hasta 9, con uno a cargo de la conducción técnica | Hasta 12, con uno a cargo de la conducción técnica |
| QA | 1 con dedicación por etapa | Hasta 2 con dedicación por etapa | Hasta 2 con dedicación por etapa |
| UX/UI | Participación en diseño y validación | Participación en diseño y validación | Participación en diseño y validación |
| Gestión | Dedicación parcial | Dedicación parcial | Dedicación parcial |

Las horas de la sección 6 se distribuyen entre los perfiles según el trabajo de cada disciplina. Los analistas también se reparten las horas de manuales y capacitación. El equipo se amplía para desarrollar circuitos en paralelo y concentra su dedicación al comienzo. El [anexo de planificación](planificacion-mesa-situacion-el-nino.md) detalla la asignación y los hitos de cada alternativa. Estas dotaciones son propuestas sujetas a disponibilidad y validación del plan de trabajo.

## 8. Entregas y aceptación

Cada entrega incluirá una demostración y criterios de aceptación correspondientes al alcance elegido.

La aceptación de la aplicación requerirá completar los casos funcionales acordados, verificar permisos y trazabilidad, y ejecutar las pruebas de carga de las pantallas y circuitos incluidos.

## 9. Criterios comunes de la aplicación

### Uso y permisos

La aplicación será web, adaptable a computadoras y dispositivos móviles con conexión a internet. Los permisos definirán qué puede consultar o modificar cada equipo según su función y territorio. El estado y los avisos se comunicarán con texto además de color.

### Actualización en vivo

Se conserva una base de validación de 200 usuarios activos simultáneamente y un objetivo de propagación de cambios de hasta dos segundos en al menos el 95% de las actualizaciones medidas.

La medición comienza cuando se confirma el registro y termina cuando otra sesión conectada visualiza el cambio. Antes de la prueba se acordarán conectividad, dispositivos, volumen de datos y mezcla de consultas y cargas. Este objetivo no equivale al tiempo de elaboración de reportes o importaciones extensas.

Cada pantalla informará la pérdida de conexión o la antigüedad de los datos y recuperará el estado vigente al reconectarse. La actualidad de un relevamiento depende de su carga por el operador; las alertas climáticas tendrán carga manual en las tres alternativas.

### Consistencia de los movimientos

Los circuitos incluidos deberán controlar operaciones simultáneas y reintentos. La ocupación se calculará a partir de ingresos y egresos; las alternativas con stock deberán conservar la relación entre solicitudes, entregas y movimientos.

### Organización de la aplicación

Se propone una interfaz web con módulos vinculados mediante una API y un modelo de datos común. React y TypeScript se plantean para la interfaz; Python y Django para las reglas de negocio; PostgreSQL con soporte geográfico para los registros territoriales y WebSockets para la actualización en vivo. Esta selección se confirmará durante el diseño técnico.

### Importaciones y experiencia previa

Cada alternativa incluye el tratamiento de padrones definido en su alcance. Las plantillas, los volúmenes, los campos obligatorios y los criterios de coincidencia se acordarán antes de importar. El Ministerio validará la información de origen y los resultados.

La experiencia de Datañach se utilizará como referencia para personas, familias, permisos y gestión institucional. La reutilización de componentes dependerá de su compatibilidad y autorización; la estimación no presupone un ahorro de código aún no verificado.

## 10. Ampliaciones independientes

| Ampliación | Alcance a definir |
|---|---|
| Aplicación de relevamiento offline | Formularios sin conexión, GPS, adjuntos y sincronización con resolución de conflictos |
| Integraciones con registros y sistemas existentes | Consulta o intercambio de datos mediante servicios acordados con cada organismo |
| Fuentes climáticas automáticas | Incorporación de mediciones y alertas, con identificación de fuente y fecha |
| Notificaciones por canales externos | Mensajes a destinatarios mediante canales acordados |
| Funciones predictivas con IA | Evaluación de datos y objetivos, seguida de una propuesta específica de desarrollo |

Estas ampliaciones no forman parte de las horas de ninguna de las tres alternativas. La propuesta Integral cubre la gestión funcional completa descrita en la sección 5.

Si se contrata una alternativa y luego se decide avanzar a otra, se estimará el trabajo restante a partir de lo entregado y de los cambios solicitados. La diferencia entre los totales actuales no constituye una cotización automática de la ampliación.

## 11. Servicio opcional: mesa de ayuda funcional 24/7

ICORE propone una mesa de ayuda funcional dedicada, disponible todos los días, incluidos fines de semana y feriados. Puede contratarse junto con Esencial, Operativa o Integral y acompañará el uso de las funciones incluidas en la alternativa elegida.

| Prestación | Alcance del servicio |
|---|---|
| Asistencia a usuarios | Orientación sobre pantallas, carga de información, consultas y circuitos de trabajo |
| Recepción de consultas e incidencias | Registro de tickets con prioridad, contexto, responsable y estado de atención |
| Diagnóstico funcional | Revisión del procedimiento seguido por el usuario y reproducción del caso cuando corresponda |
| Acompañamiento de casos | Seguimiento del ticket, comunicación de avances y confirmación del cierre con el usuario |
| Escalamiento | Derivación de defectos o consultas especializadas al responsable definido en el circuito de atención |
| Continuidad entre turnos | Entrega de pendientes e historial de acciones para que el siguiente operador continúe la atención |
| Base de conocimiento | Guías de uso, respuestas frecuentes y actualización de procedimientos funcionales |
| Reportes de atención | Informe periódico de consultas, incidencias, tiempos de respuesta y necesidades de capacitación |

### Cobertura y dotación de referencia

Se propone una posición funcional activa por turno, con una dotación inicial de 5 a 6 personas para cubrir relevos, descansos y ausencias. La cantidad final se acordará según el volumen de consultas, los canales y la atención simultánea requerida.

### Modalidad de contratación

La mesa de ayuda se contrata por separado. Sus horas y su equipo no están incluidos en los rangos de desarrollo de 3.000–3.500, 4.500–5.000 o 6.000–6.500 horas.

Antes de iniciar el servicio se acordarán los canales, prioridades, tiempos de primera respuesta, fecha de inicio y preparación de los operadores. La cobertura 24/7 se refiere a la atención funcional. Las correcciones de software y la intervención de especialistas se canalizarán según el acuerdo de mantenimiento y escalamiento que se establezca.

## 12. Condiciones para cerrar el alcance

| Condición | Definición a acordar |
|---|---|
| Alternativa elegida | Esencial, Operativa o Integral |
| Reglas de negocio | Condiciones de afectación, estados, permisos y criterios de aceptación de los módulos incluidos |
| Circuito FUSE | En las alternativas que lo incluyen, responsables de cada etapa y tratamiento de excepciones |
| Datos iniciales | Padrones, formatos, volúmenes, cantidad de lotes y responsables de validación |
| Rendimiento | Escenarios de uso y condiciones de medición de concurrencia y actualización en vivo |
| Referentes | Responsables de definir reglas de negocio y validar las entregas |
| Entrega y conformidad | Casos de aceptación, manuales y capacitación incluidos en la alternativa |
| Mesa de ayuda opcional | Contratación, canales, volumen de atención, turnos, tiempos de respuesta y circuito de escalamiento |

El documento presenta tres opciones para decidir alcance. La versión contractual incorporará la alternativa elegida y las definiciones acordadas.

## 13. Qué versión elegir

Las tres versiones permiten ver las zonas afectadas, registrar familias, atender situaciones y consultar albergues. Cada una suma herramientas para acompañar el trabajo de los equipos: Operativa incluye todo lo de Esencial e Integral incluye todo lo de Operativa.

### Las diferencias en el trabajo diario

| Necesidad del equipo | 1. Esencial | 2. Operativa | 3. Integral |
|---|---|---|---|
| Conocer la situación | Ver zonas afectadas, familias y necesidades | Sumar el estado de atención de cada mesa | Comparar cómo cambia la situación y dónde sigue faltando respuesta |
| Organizar la ayuda | Registrar qué se necesita y qué asistencia se realizó | Seguir cada pedido desde la solicitud hasta su entrega completa y consultar insumos disponibles | Entregar en varias etapas, ver qué queda pendiente, reservar insumos y moverlos entre depósitos y albergues |
| Acompañar a las familias | Registrar sus datos, necesidades y alojamiento | Seguir la asistencia recibida y revisar los relevamientos | Reunir el historial de atención y revisar posibles registros repetidos |
| Gestionar albergues | Saber cuántas personas hay y cuántos lugares quedan | Sumar raciones, servicios y necesidades | Seguir traslados entre albergues y coordinar su abastecimiento |
| Coordinar a los equipos | Asignar responsables y registrar novedades | Trabajar con las cuatro mesas y compartir pendientes entre turnos | Confirmar quién recibe los pendientes y seguir planes de acción con responsables y fechas |
| Tomar decisiones | Consultar resúmenes de la situación | Ver pedidos, entregas e insumos por mesa | Comparar períodos, seguir la evolución de la ayuda e identificar necesidades sin resolver |

### 1. Esencial: conocer y registrar

Una opción para comenzar con una visión compartida de la emergencia. Reúne la información de familias, incidentes y albergues, y permite dejar constancia de la atención realizada. La organización de pedidos y el control de insumos se incorporan en la siguiente versión.

### 2. Operativa: organizar la atención

Suma las herramientas para que las cuatro mesas trabajen sobre los mismos pedidos. Permite solicitar, autorizar y entregar ayuda, consultar existencias y acompañar las necesidades de albergues y dispositivos propios. Cada pedido se resuelve con una entrega completa.

### 3. Integral: acompañar la respuesta de principio a fin

Suma el seguimiento que hace falta cuando la atención continúa durante varios días: entregas en distintas etapas, insumos que se redistribuyen, familias que cambian de albergue y tareas que pasan de un equipo a otro. Permite consultar qué se hizo, qué falta y quién debe continuar, junto con la evolución de cada zona.

Por ejemplo, si un albergue solicita 100 bolsones y hoy recibe 60, Integral permite mantener los 40 restantes pendientes dentro del mismo pedido y completar la entrega después. También permite registrar el traslado de insumos desde otro depósito para cubrir esa necesidad.

!!! tip "Integral: la opción recomendada por ICORE"
    Para una Mesa de Situación que debe coordinar la respuesta durante toda la emergencia, recomendamos Integral. Reúne las herramientas de las otras dos versiones y permite acompañar los cambios de la atención diaria. Su valor está en contar con la información reunida para decidir a quién asistir, qué falta entregar y dónde reforzar los recursos.
