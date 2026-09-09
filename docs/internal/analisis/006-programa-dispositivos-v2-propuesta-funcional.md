# Propuesta funcional — Programa Dispositivos y Merenderos, versión 2 (rearmado completo)

**Tipo:** Propuesta funcional de programa (documento de trabajo interno)
**Estado:** Borrador para decisión del PM · no genera issues hasta cerrar las preguntas de la §12
**Fecha:** 2026-09-08
**Responsable (ICORE):** functional-analyst
**Reemplaza a:** `005-programa-dispositivos-relevamiento-propuesta.md` como modelo funcional. Conserva las decisiones del Ministerio (01/07/2026) y toma como insumo el relevamiento de campo de la estimación v1.1 (08/09/2026), las minutas del 19/06 y 26/06, la especificación NODO (P01–P13) y lo aprendido de la primera construcción (auditoría 26/08/2026).

> **Por qué se rearma.** La primera versión modeló el programa como una copia de Becas: una "admisión" con estados de aprobación que la operación nunca usa, un formulario que se completa una vez y no se vuelve a ver, camas como única forma de capacidad, un parte diario que pisa el de otro turno y un programa hermano (Merenderos) sin entrada en el menú. El relevamiento de campo muestra otra cosa: instituciones que operan **24 horas por turnos**, con **alta rotación** (Parador), **habitaciones con cupos por servicio** y préstamo de camas (Calcuta), **autorización previa** de un programa central (CIS N.º 3), **seguimiento ambulatorio** sin cama (Mírame/Vedia) y **información sensible** con acceso restringido. Esta propuesta parte de esa operación real, no del código existente.

---

## 1. Objetivo

Dar al Ministerio una **gestión operativa única de sus instituciones**: cada dispositivo y cada merendero con un legajo institucional, las personas que atiende con una estadía trazable desde el ingreso hasta el egreso, la capacidad (plazas) calculada siempre desde los movimientos, la operación diaria registrada por turno sin transcripciones, y una visión central de la red (ocupación, alertas, prestaciones) para decidir capacidad, abastecimiento y emergencias. Todo sobre el Legajo Ciudadano como dato único de la persona y con permisos que respetan la sensibilidad de la información.

---

## 2. Principios de diseño

| # | Principio | Qué implica en el producto |
|---|---|---|
| P1 | **La estadía es el eje, no el formulario.** | Todo lo que le pasa a una persona en una institución (ingreso, plaza, movimientos, novedades, egreso) cuelga de una estadía. La ficha se completa a lo largo de la estadía, no una sola vez. |
| P2 | **Capacidad = plazas, no solo camas.** | Un dispositivo tiene plazas agrupadas en sectores. Una plaza puede ser una cama, un cupo ambulatorio o un turno. La cama es un caso particular. |
| P3 | **El sistema calcula y alerta, la persona decide.** | Ocupación, disponibilidad y censo se derivan de los movimientos. Ningún nivel de ocupación bloquea automáticamente un ingreso: alerta y exige autorización registrada. |
| P4 | **Turnos y pase de guardia son ciudadanos de primera.** | Toda novedad lleva turno, responsable y hora. La bitácora reemplaza cuadernos: recepción, sereno, área social, alimentos. Lo de un turno no se pisa; se agrega. |
| P5 | **Historial permanente y separación de funciones.** | Nada se borra: se anula o se cierra con motivo. Quien carga un movimiento no lo valida. Cada acción queda auditada con antes/después. |
| P6 | **Un solo motor de formularios para todo el sistema.** | Las fichas por tipo de dispositivo usan el constructor de formularios ya existente (catálogo, grupos, condiciones, versiones), no un motor paralelo. |
| P7 | **Sensibilidad por sección, no por pantalla.** | Salud, psicosocial y situación judicial son secciones con nivel de sensibilidad y permiso propio; se ocultan a quien no corresponde, incluso dentro de la misma ficha. |
| P8 | **Configuración antes que código.** | Tipos de dispositivo, plazas, servicios de merendero, umbrales, motivos de egreso, tipos de novedad y reglas por tipo (autorización previa, límite de permanencia) se administran desde el backoffice. |
| P9 | **Lo que se carga se puede ver, buscar y exportar.** | Toda entidad tiene detalle, historial y exportación. No existe dato de escritura únicamente. |

---

## 3. Mapa del programa (módulos funcionales)

```
Programa Dispositivos
 ├─ M1 Legajo institucional             (común con Merenderos)
 ├─ M2 Capacidad: sectores y plazas
 ├─ M3 Estadías: solicitud · ingreso · movimientos · traslado · egreso
 ├─ M4 Ficha de la persona en la institución (formularios por tipo, con sensibilidad)
 ├─ M5 Operación diaria: bitácora por turno y censo
 ├─ M6 Lista de espera y derivaciones entre instituciones
 ├─ M7 Roles, alcance y separación de funciones   (transversal)
 ├─ M8 Tablero de la red e indicadores            (transversal)
 ├─ M9 Reportes y exportaciones                   (transversal)
 └─ M10 Padrón inicial, migración y auditoría     (transversal)

Programa Merenderos
 ├─ M1 Legajo institucional (misma base) + documentación respaldatoria con vigencia
 ├─ M11 Entregas de mercadería (catálogo de insumos y kits)
 ├─ M12 Prestación alimentaria (mensual, con servicios configurados por merendero)
 └─ M13 Padrón nominal y asistencia (fase posterior, a confirmar)
```

Merenderos sigue siendo **programa propio** (decisión del Ministerio, 01/07/2026), pero comparte el módulo M1 y los transversales M7–M10. Lo que cambia respecto de la primera versión es que ambos programas se ven, se navegan y se auditan igual.

---

## 4. M1 — Legajo institucional

Vale para dispositivos y merenderos. Es el "registro maestro por institución" que pide NODO P01.

### 4.1 Datos

| Bloque | Contenido |
|---|---|
| Identidad | Código institucional único (normalizado), nombre, nombre de fantasía, tipo (catálogo), programa/área del Ministerio que lo supervisa (Gerontología, Abordaje Psicosocial, Niñez, Merenderos…). |
| Encuadre jurídico | **Categoría**: Público/Estatal, Privado, ONG, Religioso (minuta 26/06). **Titularidad del inmueble** y **dependencia de la gestión** por separado (el edificio puede ser de la Iglesia y el personal del Ministerio). Instrumento de creación o convenio (número, fecha, adjunto). |
| Ubicación | Domicilio normalizado con la geografía del sistema, geolocalización, zona y barrio, referencias de acceso. |
| Responsables y contacto | Responsable institucional (persona del Legajo Ciudadano o dato libre), referente del área, teléfonos, correo, días y horarios de funcionamiento. |
| Servicios que brinda | Lista configurable: alojamiento, alimentación (desayuno, almuerzo, merienda, cena), atención social, salud/enfermería, actividades, etc. Determina qué módulos se habilitan y qué columnas tiene la prestación. |
| Documentación | Adjuntos tipificados con fecha de vigencia (habilitación, convenio, documentación respaldatoria del merendero). Vencimiento genera alerta. |
| Procedencia del dato | Fuente, fecha, responsable y **nivel de confianza** (verificado / declarado / migrado sin verificar). Un dato migrado sin verificar no se publica como oficial en los reportes. |

### 4.2 Estados

```
Borrador → Pendiente de validación → Activo
                                   → Observado  → (corregido) Pendiente de validación
                                   → Rechazado
Activo → Inauguración pendiente ⇄ Activo        (listo pero todavía no abrió; minuta 26/06)
Activo → Suspendido → Activo                    (no admite ingresos; conserva estadías)
Activo / Suspendido → Cerrado                   (terminal; conserva todo)
```

Reglas: el borrador admite datos incompletos; validar exige los obligatorios **y los nombra**; observar y rechazar exigen motivo; validar lo hace un rol distinto del que cargó (P5). Cerrar un dispositivo con estadías abiertas exige egresarlas o trasladarlas primero, con un asistente que lo resuelve en bloque.

### 4.3 Anti-duplicado

Búsqueda previa por código, nombre, domicilio y geolocalización (radio). Código repetido bloquea siempre y **dice por qué**, aunque la institución esté fuera del alcance del usuario (sin revelar sus datos). Coincidencia de nombre o domicilio advierte y pide confirmación. Fusión de duplicados como acción del administrador central, con traza.

---

## 5. M2 — Capacidad: sectores y plazas

### 5.1 Modelo

- **Sector**: agrupación física u operativa dentro del dispositivo (habitación, pabellón, ala, "servicio" en Calcuta, "turno noche" en el Parador). Tiene nombre, tipo, capacidad y condiciones (por ejemplo, solo mujeres, solo NNA).
- **Plaza**: unidad de capacidad dentro de un sector. Tipo de plaza: **cama** (internación), **cupo** (ambulatorio, fortalecimiento familiar, residencias sin cama fija), **turno** (paradores que asignan por noche). Código, estado, observaciones.
- El **tipo de dispositivo** define qué tipos de plaza admite y si la asignación es obligatoria al ingresar (internación) u opcional (ambulatorio).

### 5.2 Estados de plaza

```
Disponible → Reservada → Ocupada → Disponible
Disponible / Ocupada → Prestada (a otra estadía, por 12 o 24 h, sin perder el titular)
Cualquiera → Fuera de servicio (exige motivo; si está ocupada, exige reubicar primero con un asistente)
```

### 5.3 Cálculos (siempre derivados)

- Operativas = totales − fuera de servicio.
- Ocupadas = estadías activas con plaza asignada. Reservadas = reservas vigentes (espera con plaza reservada, traslado en tránsito, permiso de salida con reserva).
- Disponibles = operativas − ocupadas − reservadas. **Disponibilidad neta** (si el Ministerio lo confirma): disponibles + prestadas recuperables.
- Censo diario automático: existencia inicial + ingresos − egresos = existencia final, por dispositivo y por sector.
- Ocupación por sector y por dispositivo; semáforos con umbrales por tipo (P3: nunca bloquean).

---

## 6. M3 — Estadías

### 6.1 Ciclo de vida

```
[Solicitud de ingreso]  (solo si el tipo lo exige: autorización previa del programa central)
        ↓ autorizada / rechazada / vencida
Ingreso  →  Alojada | En seguimiento (ambulatoria)  →  Egresada
                    ↳ movimientos: cambio de plaza · préstamo · permiso de salida · en tránsito (traslado)
```

- **Solicitud de ingreso** (configurable por tipo, relevado en CIS N.º 3 y Parador): quien deriva o el propio dispositivo registra la solicitud; el programa central o el área la autoriza, la rechaza o pide más datos; una solicitud autorizada tiene vigencia y puede reservar plaza. Para tipos sin autorización previa, el ingreso es directo.
- **Ingreso**: búsqueda por DNI en el Legajo Ciudadano (si no existe, alta mínima con RENAPER); si la persona ya tiene una estadía **residencial** activa en otra institución de la red, el sistema lo muestra y exige resolverla (egreso o traslado) antes de alojar. Una estadía **ambulatoria** puede convivir con una residencial (seguimiento de Abordaje Psicosocial mientras la persona está alojada). Asignación de plaza (obligatoria u opcional según tipo); sin plaza disponible: lista de espera o **ingreso excepcional con autorización registrada** (quién autoriza y por qué). Reingreso detectado automáticamente en toda la red, no solo en el mismo dispositivo.
- **Movimientos de estadía** (cada uno con turno, hora, responsable, motivo y traza): cambio de plaza o sector; préstamo de plaza (12 o 24 h); permiso de salida y regreso (con reserva de la plaza y alerta si no regresa); observación de conducta o incidente (enlaza con la bitácora); actualización de la ficha.
- **Traslado**: se inicia en el origen y queda **En tránsito** hasta que el destino lo recibe. En tránsito se ve en ambos dispositivos, la plaza de origen queda reservada un tiempo configurable, no se puede iniciar otro traslado y hay alerta si supera el plazo. El destino puede recibir (abre estadía nueva, cierra la anterior como Trasladada) o rechazar (la persona vuelve a Alojada en origen). Traslado a un destino sin plaza va a su lista de espera **sin** dejar la estadía en dos lugares.
- **Egreso**: fecha y hora (nunca anteriores al ingreso), motivo (catálogo configurable: alta, derivación, abandono, fallecimiento, traslado…), destino, derivación a otra institución u organismo (crea una derivación en M6), observaciones, adjuntos. Libera la plaza. Egresos masivos por cierre del dispositivo con asistente.
- **Alertas de estadía**: límite de permanencia por tipo (UPI/ECA 48 h por medida judicial), permiso de salida vencido, ficha incompleta pasados N días, tránsito vencido.

### 6.2 Vistas

Detalle de la estadía (identidad, plaza, línea de tiempo de movimientos, ficha por secciones, adjuntos, egreso), listado de estadías del dispositivo con filtros y paginación, historial de estadías de la persona en su Legajo Ciudadano (incluidas las cerradas, con solapa embebida) y padrón de alojados del día.

---

## 7. M4 — Ficha de la persona en la institución

Reemplaza al "F-00 de una sola vez".

- **Un formulario por tipo de dispositivo** construido con el **constructor de formularios** del sistema: grupos (las secciones A–J de Adultos Mayores, 1–14 de Abordaje), preguntas del catálogo, preguntas propias del tipo, condiciones entre respuestas, versiones. Adultos Mayores y Abordaje Psicosocial se cargan como configuración inicial; UPI, ECA, Residencias y Fortalecimiento Familiar cuando el Ministerio los releve.
- **Datos de identidad desde el Legajo Ciudadano** (nombre, documento, nacimiento, género, obra social, domicilio, contacto): se muestran, no se preguntan; si se corrigen, se corrigen en el legajo.
- **Se completa en el tiempo**: al ingresar se exige el mínimo (configurable por tipo); el resto se completa después con **completitud visible** por sección y recordatorios. Cada guardado queda versionado (quién, cuándo, qué cambió).
- **Sensibilidad por sección**: cada grupo tiene nivel (general, social, salud, psicosocial, judicial). Ver o editar una sección exige la capacidad de ese nivel. Las secciones judiciales de NNA (menores bajo guarda, Línea 102) quedan bloqueadas por rol, sin copia ni exportación, y el sistema **consume** la referencia de GENACH cuando exista integración (minuta 26/06), sin duplicar la carga.
- **Cálculos dentro de la ficha**: totales de ingresos y egresos, saldo, edad, tiempo de permanencia, marcados como preguntas calculadas del constructor.
- **Lectura y exportación**: la ficha se ve completa en el detalle de la estadía, se imprime en el formato del papel original y se exporta con los permisos de sensibilidad aplicados.

---

## 8. M5 — Operación diaria: bitácora por turno y censo

Reemplaza y amplía al F-01.

- **Turnos configurables por dispositivo** (mañana, tarde, noche; o los que use la institución) con horario.
- **Bitácora**: cada entrada tiene turno, hora, responsable, tipo (novedad general, ingreso, egreso, permiso de salida, incidente, visita, mantenimiento, alimentos, limpieza, salud si el rol lo permite), texto, personas involucradas (enlace a estadías) y adjuntos. Las entradas **se agregan**, nunca se pisan; corregir crea una nueva versión visible.
- **Pase de guardia**: al cerrar un turno el responsable confirma el resumen (censo del turno, novedades pendientes de seguimiento) y el siguiente turno lo recibe como primer elemento de su vista. Queda registrado quién entregó y quién recibió.
- **Censo automático** por turno y por día: camas totales, ingresos, egresos, ocupación nocturna, disponibles, préstamos vigentes, personas con permiso de salida. Nada de esto se tipea.
- **Regularización**: se pueden cargar turnos de días anteriores dentro de una ventana configurable (propuesta: 7 días), con marca de "cargado fuera de término". Listado histórico por fecha y turno, filtrable y exportable.
- **Alertas**: turno sin cierre, día sin bitácora, incidente sin seguimiento.

Lo que **no** entra en esta etapa y se deja preparado como entrada de bitácora tipificada: administración de medicación, inventario y stock, asistencia del personal (módulos posteriores de la estimación v1.1 §7.1).

---

## 9. M6 — Lista de espera y derivaciones

- **Lista de espera por dispositivo** con posición, prioridad (criterios configurables: medida judicial, edad, riesgo), fecha, origen (ingreso directo, traslado, derivación) y plaza reservada opcional. Promoción manual con asistente cuando se libera una plaza; el sistema sugiere pero no promueve solo.
- **Derivaciones entre instituciones y a organismos externos** (retoma el análisis 002 con vocabulario del programa): quien deriva registra destino, motivo y urgencia; el destino acepta, rechaza con motivo o deja vencer; aceptar abre solicitud de ingreso o estadía según el tipo. Todo queda en el historial de la persona.
- **Vista de red**: dónde hay plazas disponibles por tipo, sector y localidad, para decidir la derivación.

---

## 10. Programa Merenderos (M1 + M11 + M12 + M13)

- **Legajo del merendero** sobre M1: solicitud iniciada por vecino/a (en esta etapa la carga el área en el backoffice; el portal ciudadano es fase posterior), con **documentación respaldatoria tipificada y con vigencia**; validación con separación de funciones; aprobación bloqueada sin documentación vigente; estados Activo, Suspendido, Cerrado con motivo y reactivación desde Suspendido; edición del legajo después de aprobado, con traza.
- **Catálogo de insumos y kits** (configuración del programa): qué contiene un kit, unidad, equivalencias declaradas (por ejemplo, raciones estimadas por kit) para poder medir cobertura.
- **Entregas de mercadería**: fecha, kits o insumos, cantidad, servicio al que se destinan, responsable que entrega y quien recibe (persona del legajo), remito o adjunto, anulación con motivo. Historial por merendero y por período.
- **Prestación alimentaria mensual**: grilla por día y servicio, con los **servicios configurados en el legajo del merendero** (no siempre los cuatro), carga de raciones (o marca por servicio si el Ministerio así lo define, configurable), total diario y mensual calculados, observaciones, firma por fila, cierre del mes con separación de funciones (carga el merendero o el área, confirma otro rol).
- **Cobertura alimentaria** (indicador): raciones servidas del mes contra raciones equivalentes entregadas y contra la capacidad declarada del merendero. Alerta cuando la demanda supera la entrega.
- **Padrón nominal y asistencia diaria** (M13, fase posterior a confirmar): personas y tutores vinculados al merendero por el Legajo Ciudadano, asistencia por servicio, y su relación con las raciones.
- **Navegación propia** en el menú, alcance por merendero o por zona, auditoría igual que dispositivos.

---

## 11. Módulos transversales

### 11.1 M7 — Roles, alcance y separación de funciones

- Capacidades por acción (ver, crear, editar, validar, ingresar, mover, egresar, cargar bitácora, cerrar turno, autorizar ingreso excepcional, ver sección sensible por nivel, configurar, exportar), sobre el motor RBAC del sistema.
- **Alcance en tres niveles**: institución (dispositivo o merendero), área o programa del Ministerio (todas las instituciones de Abordaje Psicosocial, por ejemplo) y central. Un rol se acota a uno o varios de estos alcances; el alcance se administra desde el ABM de Roles.
- **Separación de funciones** como regla del motor: la acción de validar, autorizar o confirmar cierre rechaza al mismo usuario que registró el movimiento.
- Perfiles de referencia: operador de turno, responsable institucional, equipo técnico (social, salud, psicología, con niveles de sensibilidad distintos), supervisor de área, programa central (autoriza ingresos), administrador central, área de merenderos, consulta y auditoría.

### 11.2 M8 — Tablero de la red e indicadores

- **Tablero del programa**: capacidad de la red por tipo y localidad, ocupación y disponibilidad, ingresos y egresos del período, permanencia promedio, alojados por sector, alertas activas (tránsitos vencidos, permanencias excedidas, turnos sin cerrar, documentación vencida, fichas incompletas), merenderos con cobertura en rojo. Filtros por área, tipo, localidad y período; todo exportable.
- **Tablero del dispositivo**: los mismos indicadores acotados, en la primera franja del detalle, con vocabulario operativo (normal, exigida, crítica, sin datos) y umbrales por tipo.
- Umbrales configurables por programa y por tipo. El tablero de comando completo, la matriz de alertas y los planes de contingencia (inundaciones, frío o calor extremo, emergencias sanitarias) quedan definidos como fase posterior; este módulo deja los datos y la estructura para incorporarlos.

### 11.3 M9 — Reportes y exportaciones

Padrón de instituciones (con encuadre jurídico y procedencia del dato), ocupación por dispositivo, sector y tipo, movimientos por período (ingresos, egresos, traslados, permisos), censo diario, bitácora por período, lista de espera y derivaciones, padrón de merenderos con entregas, prestaciones mensuales, cobertura alimentaria. CSV y Excel, con los filtros aplicados, acotados al alcance y a la sensibilidad del usuario, con auditoría de quién exportó qué.

### 11.4 M10 — Padrón inicial, migración y auditoría

- Importador de instituciones desde planilla normalizada con fuente, fecha, responsable y nivel de confianza; importa también sectores y plazas, y opcionalmente alojados actuales (estadía abierta con fecha de ingreso declarada) para arrancar con censo real.
- Reconciliación de duplicados antes del alta masiva y verificación territorial posterior (equipo territorial confirma o corrige; el dato pasa a verificado).
- **Auditoría única** para todo el programa: traza aditiva por institución, estadía, movimiento, bitácora, entrega y prestación, con antes y después, legible en idioma de operador y exportable.

---

## 12. Preguntas a cerrar antes de bajar a issues

Numeradas para responder en prosa.

1. **Unicidad de plaza en la red.** ¿Una persona puede estar alojada en dos dispositivos a la vez? La propuesta dice no para estadías residenciales y sí para una ambulatoria más una residencial. ¿Confirman?
2. **Ingreso sin plaza.** ¿Quién puede autorizar un ingreso excepcional sobre la capacidad (responsable institucional, supervisor de área, programa central) y hasta qué límite?
3. **Autorización previa.** ¿Qué tipos de dispositivo exigen autorización del programa central antes del ingreso, quién la otorga y con qué vigencia?
4. **Préstamo de plaza y disponibilidad neta.** ¿Se confirma la regla de 12 o 24 horas y que las plazas prestadas cuentan como disponibles?
5. **Sensibilidad.** ¿Qué roles ven las secciones de salud, psicosocial y judicial, y la información judicial de NNA se carga en el sistema o solo se referencia a GENACH?
6. **Fortalecimiento Familiar.** ¿Trabaja con cupos, con turnos o sin plazas?
7. **Albergues y contención nocturna.** ¿Son un tipo propio de dispositivo (Parador, Albergue) o variantes de Abordaje Psicosocial?
8. **Bitácora.** ¿Qué tipos de novedad son obligatorios en el pase de guardia y qué ventana de regularización se acepta?
9. **Merenderos.** ¿Los servicios se configuran por merendero? ¿La prestación se carga en raciones o como marca por servicio? ¿Entra el padrón nominal en esta versión?
10. **Kits.** ¿Existe un catálogo de kits del Ministerio con contenido y equivalencia en raciones, o lo definimos con el área?
11. **Derivaciones.** ¿Las derivaciones a organismos externos (hospital, juzgado) se registran como destino de egreso o como derivación con seguimiento?
12. **Alcance.** ¿El nivel intermedio de alcance es el área del Ministerio, la localidad o el territorio (minuta 19/06 habla de territorio, localidad y SIS)?

---

## 13. Fuera de alcance de esta versión (fase posterior)

Inventario y stock integral, administración de medicación, asistencia y situación de revista del personal, historial clínico, funcionamiento offline con sincronización, control de acceso físico (huella o clave), layout interactivo de habitaciones y dispositivos móviles para cocina, lavadero y mantenimiento, tablero de comando completo y planes de contingencia, integración de stock con ECOM, portal ciudadano para solicitudes de merendero, Línea 102 como circuito propio. El diseño de esta versión deja los puntos de enganche: entradas de bitácora tipificadas, servicios en el legajo institucional, sectores y plazas, niveles de sensibilidad y alertas configurables.

---

## 14. Relación con lo construido

Esta propuesta redefine el modelo funcional; la decisión de reutilizar o rehacer código es técnica y posterior. A título orientativo: el patrón de traza aditiva, las transiciones de estado en servicios con bloqueo, el alcance fino desde el ABM de Roles y los exportadores son reutilizables; el modelo de admisión con estados de aprobación, el motor propio de campos por tipo, el parte diario y la navegación de Merenderos se reemplazan por M3, M4, M5 y la base común de M1.

---

## 15. Próximos pasos

1. Decisión del PM sobre las §12 (o sesión con el Ministerio para las que son del cliente: 1 a 7, 9, 10 y 12).
2. Ajustar esta propuesta con las respuestas y publicar la versión para el cliente en `docs/client/funcionalidades/`.
3. Estimar por módulo (M1 a M13) sobre la base de las 436 h ya aprobadas y los módulos de la v1.1 §7.1.
4. Generar en GitHub: épica nueva o reencuadre de #127, un análisis por módulo y las tasks con casos de QA desde el nacimiento. Las 27 tasks actuales (hoy en Backlog) se cierran como superadas o se reescriben, según decida el PM.
