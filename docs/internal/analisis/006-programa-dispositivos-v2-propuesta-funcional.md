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

### 6.3 La solapa Dispositivos del Legajo Ciudadano

**Definición del PM (09/09/2026): la solapa muestra toda la información de la persona en el programa.**
Las dos familias de institución son un solo programa de la tabla `programas`, así que hay **una sola
solapa** y ahí adentro está todo: estadías abiertas y cerradas en cualquier institución de la red,
movimientos, egresos con motivo, derivaciones, paso por lista de espera y estado de la ficha.

Esto **no es adaptar lo que hay, es invertirlo**. Hoy la solapa hace lo contrario, y por tres puertas
distintas:

| Dónde | Qué hace hoy | Efecto |
|---|---|---|
| `programas/services/solapas.py:53` | Si no hay una `Admision` en estado `ALOJADO`, no agrega la solapa | La solapa **desaparece** del legajo cuando la persona egresa |
| `legajos/views/dispositivos.py:35` | Sin admisión `ALOJADO`, la vista tira `PermissionDenied` | El historial es inalcanzable incluso entrando por la URL |
| `legajos/views/dispositivos.py:24` | La inscripción tiene que estar `ACTIVO` o `EN_SEGUIMIENTO` | Una inscripción cerrada también borra la solapa |

El listado de admisiones en sí ya trae abiertas y cerradas (`views/dispositivos.py:26-34`): el
historial existe, está escrito y está tapado por los tres candados. La v2 los saca.

**Qué la limita: la sensibilidad, no el alcance.** La solapa se abre con la capacidad del programa
(`dispositivo.ver` sobre Dispositivos, que la vista ya exige en `views/dispositivos.py:16`) y **no**
se filtra por las instituciones asignadas al rol. Cualquiera del programa que abra el legajo ve la
trayectoria completa de la persona en la red y puede entrar al detalle de cada registro; lo que ve
adentro lo determina el nivel de sensibilidad de cada sección (M4, RN2 y RN3), igual que en el resto
del sistema. En consecuencia se **quita** el filtro por `dispositivos_visibles` de la vista del
legajo: el alcance por institución y por subsecretaría (§11.1) gobierna la **operación dentro del
programa**, no la lectura del legajo de la persona.

**El detalle no es entrar al programa.** Desde la solapa se abre una vista **de lectura** de la
estadía dentro del legajo ciudadano: identidad, institución, plaza, fechas, movimientos, motivo de
egreso y las secciones de ficha que el nivel del usuario habilita. Sin acciones operativas —no se
mueve de plaza, no se egresa, no se carga bitácora desde ahí—; para eso hay que entrar al programa,
donde sí manda el alcance.

Consecuencia a asumir explícitamente: alguien asignado solo a la institución X puede leer que la
persona estuvo en la institución Y, con fechas y motivo de egreso. Es deliberado —el legajo es el
dato único de la persona— y queda auditado como cualquier lectura y exportación (M10). Qué secciones
son de nivel general y cuáles exigen nivel sigue abierto en la pregunta 5 de §12, que es del
Ministerio.

Consecuencias para el backlog: hay que reescribir la solapa contra el modelo de Estadía —si no, se
rompe sola, porque la v2 reemplaza `Admision`— y ninguna de las 45 tasks la tiene a cargo. Se agrega
una task en M3. Los tests existentes (`programas/tests/test_solapa_dispositivos.py`) afirman hoy el
comportamiento viejo y hay que reescribirlos con la regla nueva.

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
- **Alcance en tres niveles** (definido por el PM el 09/09/2026, cierra la pregunta 12 de §12):
    - **Por institución** — *ya existe.* El rol se asigna a una o varias instituciones concretas (`AsignacionDispositivo`). Cubre dos perfiles con el mismo mecanismo: el responsable institucional, que tiene una, y el **programa central**, que tiene las n instituciones que se le asignen, aunque pertenezcan a subsecretarías distintas.
    - **Por subsecretaría** — *nuevo.* El nivel intermedio es la **subsecretaría del Ministerio**, no la localidad ni el territorio. Cada institución declara de qué subsecretaría depende y cada rol declara la subsecretaría que supervisa; un rol con este alcance ve todas las instituciones de la suya y ninguna de otra, sin que nadie se las asigne de a una.
    - **Total** — *ya existe.* Lo confiere `programa.configurar` sobre Dispositivos y es el administrador central. No se modifica.
- **Encuadre institucional del alcance.** El Programa Dispositivos depende de la **Secretaría de Desarrollo**, que tiene dos subsecretarías; hoy cada una gestiona un tipo de institución. Tres consecuencias de diseño:
    - El vínculo con la subsecretaría va **en la institución**, no en el tipo, para admitir instituciones del mismo tipo repartidas entre subsecretarías. Campo nuevo en el legajo institucional (M1), requerido para validar, y columna nueva del importador de padrón (M10).
    - La subsecretaría se asigna **al rol**, no a la persona, por consistencia con el resto del alcance, que vive en el rol y no en el usuario. Implica un rol por subsecretaría y un campo nuevo en `RolMeta`, con la misma validación que hoy tiene `programa`.
    - `Programa.subsecretaria` **no se toca**: es una FK única y no puede expresar un programa repartido entre dos subsecretarías. Queda como dato informativo del programa; la fuente del alcance es la institución.
    - El catálogo de secretarías existe en el sistema pero **no tiene carga inicial**: se administra a mano desde Configuración. Crear la Secretaría de Desarrollo con sus dos subsecretarías y asignarle la suya a cada institución del padrón es tarea de datos iniciales, no de desarrollo.
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
12. ~~**Alcance.** ¿El nivel intermedio de alcance es el área del Ministerio, la localidad o el territorio?~~ **Cerrada el 09/09/2026 por el PM: la subsecretaría.** El detalle y sus consecuencias de diseño están en §11.1. Nota sobre la minuta del 19/06: los «tres niveles de control (territorio, localidad y SIS)» del acuerdo 3 son de **Becas** —la cadena de validación del padrón que elimina las planillas de carga masiva—, no de Dispositivos; esta definición no revierte ningún acuerdo.

---

## 11.5 El configurador de tipos de dispositivo (replanteo de `/dispositivos/config/`)

**Definición del PM (09/09/2026).** El módulo de configuración se mantiene como el lugar donde se
configura el tipo de institución, y crece: además de la lógica operativa que ya administra
(`maneja_camas`, umbrales del semáforo de ocupación, identidad del tipo), pasa a **construir los
formularios del tipo**. No un formulario, **varios**: cada uno se usa en un momento distinto del
procedimiento de la institución.

Esto **reemplaza** el planteo anterior de migrar la ficha al constructor de formularios de Becas
(Cambio 58) y desactiva esa dependencia de cronograma, que era dura: el constructor de Becas no está
construido (análisis #326, tasks #336–#356, 150 h, todas en Backlog) y su alcance acordado excluye
explícitamente el F-00 de Dispositivos.

**Por qué encaja con la realidad del cliente.** Las instituciones no tienen una ficha, tienen una
serie de formularios: F-00 de admisión por tipo, F-01 Registro Diario de Novedades por Turno, F-02
Prestación mensual, más las fichas de referencia (Línea 102, Calcuta, Relevamiento de PC). La v1
modeló solo el F-00, como una lista plana de campos colgada del tipo. La Versión 2, en su primera
redacción, disolvía los formularios del cliente en módulos de código fijo (M4 reemplazaba el F-00, M5
reemplazaba y ampliaba el F-01). Con esta definición vuelven a ser lo que son: formularios
configurables, atados a un momento del procedimiento.

**Qué resuelve:**

- **La ficha que se completa a lo largo de la estadía** deja de necesitar un mecanismo de completitud
  por sección con plazos y recordatorios sobre un único formulario gigante: cada formulario se
  completa cuando llega su momento.
- **El saldo estimado del F-00** (`CampoTipoDispositivo.rol_calculo`, campos numéricos marcados como
  ingreso o egreso que producen el bloque `_totales`) se conserva, porque el motor sigue siendo propio.
- **Los tipos nuevos siguen creándose por configuración, sin código**, que es lo que esta pantalla ya
  hace hoy y por lo que se cerró la Q-1 del relevamiento v1 el 02/07/2026.

**Qué exige, y no es menor.** El modelo actual cuelga `CampoTipoDispositivo` directo del tipo, con la
sección como texto libre y las respuestas en `Admision.respuestas_f00` indexadas por la pk del campo.
El modelo nuevo necesita tipo → formulario → sección → campo, y una tabla de respuestas por instancia
de formulario que no dependa de a qué entidad pertenece. La sensibilidad por sección hay que
construirla igual, con este motor o con el de Becas.

### 11.5.1 Formularios base: precreados y llamados por código

**Definición del PM (09/09/2026).** Los formularios que ya sabemos que existen y que usan las
funcionalidades concretas —ingreso, asignación, bitácora, egreso, prestación— **se precrean como
parametría base** del sistema y vienen por defecto. Cada acción sabe a qué formulario llamar: el botón
de ingreso invoca el F-00, el de bitácora invoca el F-01, y así. El vínculo es **por código en el
sistema, no configurable**; desde el configurador se editan los campos del formulario, no a qué acción
responde.

**No hace falta un motor de momentos.** Se pueden crear formularios adicionales desde el
configurador, pero **cuándo se usan queda deliberadamente abierto**: el formulario existe, se
administra, y no lo invoca ninguna acción hasta que se defina. Es una decisión de alcance: evita
construir un motor de disparadores que hoy nadie pidió, sin cerrar la puerta.

**Campos protegidos.** Cada formulario base tiene campos que son columnas reales del modelo y de los
que depende el código (la fecha y la plaza en el ingreso; la fecha, el turno y las cantidades
calculadas en la bitácora; la fecha, el motivo y el destino en el egreso). Esos campos se muestran en
el configurador pero **no se pueden borrar ni cambiar de tipo**; lo que el Ministerio agrega son
campos propios alrededor. Es el mismo criterio de los bloques fijos protegidos del constructor de
Becas (Cambio 58, decisión D5).

**Estado actual de cada formulario base.** Solo el F-00 es configurable hoy; el resto está escrito a
mano y es lo que este replanteo convierte en parametría:

| Formulario base | Lo invoca | Campos protegidos (columnas de hoy) | Configurable hoy |
|---|---|---|---|
| **F-00 Admisión** | Botón Admitir (`AdmisionCreateView`) | ciudadano, dispositivo, plaza, fecha de ingreso, reingreso | **Sí** (`CampoTipoDispositivo` → `Admision.respuestas_f00`) |
| **Asignación de plaza** | Asignar o cambiar plaza | plaza | No |
| **F-01 Registro diario por turno** | Parte diario (`ParteDiarioView`) | fecha, turno, cantidades calculadas, firmado por | **No** — los conceptos son una tupla fija en `RegistroDiarioForm.OBSERVACIONES_POR_CONCEPTO` |
| **Egreso** | Botón Egresar (`EgresoAdmisionView`) | fecha de egreso, motivo, destino, responsable | No |
| **Traslado** | Botón Trasladar | los del egreso más la institución destino | No |
| **F-02 Prestación mensual** | Merenderos | mes, raciones y observaciones por día | Parcial (observaciones por día) |
| **Entrega de mercadería** | Merenderos | fecha, kits, servicio, receptor | No |

### 11.5.2 Secciones sensibles: bloqueo con avance visible y consentimiento auditado

**Definición del PM (09/09/2026).** Reemplaza el compromiso de «inhabilitar capturas o copias» de la
minuta del 19/06, que **no es técnicamente posible** en una aplicación web: nada impide una foto de
la pantalla o la captura del sistema operativo. Se implementa todo lo que sí protege:

1. **Dónde se declara.** Al armar el formulario en el configurador, cada sección declara si es
   sensible, con qué nivel, y **qué equipo la completa**.
2. **Sin el nivel, la sección se ve que existe y se ve su avance.** No se oculta: en lugar del
   contenido aparece el bloqueo, con el equipo responsable y el porcentaje completado. El texto
   modelo es *«Tu rol no accede a esta sección. La completa el equipo de psicología»*, con el avance
   al lado (por ejemplo, 80 %). Quien atiende a la persona sabe que esa información existe, que está
   cargada y a quién pedírsela, sin verla.
3. **Con el nivel, no alcanza con tenerlo.** Al abrir la sección el sistema advierte que la
   información es sensible y **exige un OK explícito**. Ese OK queda registrado con usuario, sección,
   entidad leída y fecha y hora. Tener el permiso habilita; leer requiere un acto deliberado y deja
   rastro. **Se pide cada vez que se abre la sección** (decisión del PM: trazabilidad por sobre
   comodidad). Consecuencia asumida: la auditoría acumula una fila por apertura, así que el reporte de
   lecturas agrupa por usuario, persona y día para seguir siendo legible, sin perder el detalle.
4. **Medidas complementarias:** bloqueo de copiado y de exportación en las secciones sensibles, marca
   de agua con usuario y hora para que una filtración sea rastreable, y auditoría de cada lectura
   dentro de la auditoría única del programa (M10).

**Restricción de arquitectura, para que esto sea implementable.** El sistema autoriza **por capacidad,
nunca por nombre de rol** (`core/rbac.py`), y el catálogo de capacidades es la fuente única que
alimenta el seed, el árbol del ABM de Roles y el modelo ancla: no puede crecer por configuración. Por
lo tanto la sección **elige su nivel de una lista fija** —general, social, salud, psicosocial,
judicial—, cada nivel tiene su capacidad en el catálogo, y los roles la tildan en el ABM de Roles. El
configurador puede mostrar, a título informativo, qué roles tienen hoy cada nivel. Lo que no puede
hacer es que cada sección lleve su propia lista de roles: sería un permiso por sección creado por
configuración, fuera del catálogo.

---

**A quién pertenece el formulario (PM, 09/09/2026): al tipo de institución.** Así queda dentro del
configurador del tipo, donde se decidió que viva. Para que eso no signifique configurar a mano siete
formularios por cada uno de los ocho tipos, la **carga inicial los crea para todos los tipos a partir
de un contenido común**, y después cada tipo puede divergir donde de verdad se diferencia: el F-00
arranca distinto por tipo, porque ya lo es; la bitácora, el egreso y el traslado arrancan iguales en
todos y se tocan solo si una institución lo pide.

---

## 12.3 Reconciliación de horas y recotización (09/09/2026)

**Los números del documento del cliente cerraban; el que había quedado viejo era el backlog.** La
conciliación, con las cuentas explícitas:

| Concepto | Horas |
|---|---:|
| Suma de las 45 tasks del Project | 410 |
| menos los 3 ajustes sobre lo entregado, declarados sin cargo (T03 6 h, T05 8 h, T36 4 h) | −18 |
| = desarrollo cobrable según el backlog | 392 |
| más el descuento por reutilización mal aplicado a diez tasks sin base en el sistema | +24 |
| **= desarrollo cobrable, igual al §11.4 del documento publicado** | **416** |

El desfase por módulo entre el documento y el backlog era exactamente ese descuento: M3 +12, M4 +4,
M5 +2, M7 +2, M11 +2, M12 +2. La corrección se hizo en el documento el 08/09 y **no se bajó a las
tasks**; hay que sincronizarlas.

Clasificación de las 45 tasks: **27 nuevas** (252 h en el backlog, 276 h corregidas), **15
ampliaciones** de lo existente (140 h) y **3 ajustes** sobre lo entregado (18 h, sin cargo).

### Recotización aprobada por el PM: 628 h

Las definiciones de esta revisión mueven el alcance:

| Cambio | Antes | Después |
|---|---:|---:|
| M4 — se rehace: motor propio de formularios, configurador, seis formularios base a parametría, sensibilidad con lectura registrada, baja lógica de campos respondidos | 50 | 88 |
| M3 — solapa del Legajo Ciudadano, que no tenía task | 98 | 110 |
| M1 — fusión de duplicados, que no tenía task | 36 | 44 |
| M7 — alcance por subsecretaría | 40 | 40 |
| **Desarrollo cobrable** | **416** | **474** |

Y los rubros que se calculan como proporción del desarrollo se ajustan: **QA 64 → 73 h** y **diseño
24 → 27 h**. Análisis (24 h), despliegue (16 h) y capacitación (14 h) no cambian.

| Concepto | Horas |
|---|---:|
| Backend | 285 |
| Frontend | 189 |
| Análisis funcional y definiciones | 24 |
| Pruebas y QA | 73 |
| Diseño UX/UI | 27 |
| Despliegue a QA y datos iniciales | 16 |
| Capacitación | 14 |
| **Total Versión 2** | **628** |

**Total del programa: 1.064 h** (436 de base más 628 de adición). Cuatro etapas de 302, 148, 98 y
80 h, doce semanas, dos desarrolladores a tiempo completo. Publicado en
`docs/client/funcionalidades/estimacion-programa-dispositivos.md`.

---

## 12.2 Decisiones del PM del 09/09/2026 y ajustes al backlog

Resultado de la revisión punto por punto. Cada fila es una instrucción para la sincronización del
backlog; ninguna cambia el modelo funcional.

| # | Qué | Decisión / ajuste |
|:-:|---|---|
| 1 | **Alcance en tres niveles** | El nivel intermedio es la **subsecretaría** (§11.1). Renombrar la task de M7, hoy «Alcance en tres niveles (institución, área, central)», y hacer el campo de M1 una FK a `core.Subsecretaria` |
| 2 | **Solapa del Legajo Ciudadano** | Task nueva en M3 (~12 h): reescribir la solapa contra Estadía, sacar los tres candados, rehacer `test_solapa_dispositivos.py` (§6.3) |
| 3 | **Configurador de tipos** | Se replantea: N formularios por tipo, base precreados y llamados por código, campos protegidos (§11.5). M4 se reescribe |
| 4 | **Secciones sensibles** | Bloqueo con avance visible, OK auditado en cada apertura, marca de agua, bloqueo de copiado (§11.5.2). Reemplaza el compromiso de «inhabilitar capturas» |
| 5 | **Fusión de duplicados** | RF8 del análisis de M1 no tiene task. Crear: la ejecuta el administrador central, con traza, conservando el historial de las dos instituciones |
| 6 | **RN-DI-11 recuperada** | Una institución en estado **Observado no habilita ingresos nuevos**. El estado sobrevivió en las transiciones de la v2; la regla se había perdido. Agregar a la task de estados de M1 |
| 7 | **RN-DI-19 resuelta** | La colisión entre el «dispositivo institucional» y el alias `dispositivo` de `LegajoAtencion` (`legajos/models/base.py:296`) **queda resuelta** por el nombre del modelo común de la v2: `Institucion` |
| 8 | **RN-DI-20 recuperada** | Un dato **migrado sin verificar no se publica como oficial**. El nivel de confianza está en el modelo pero la task de reportes de M9 no lo menciona: agregar el requisito, que los reportes distingan verificado, declarado y migrado sin verificar |
| 9 | **Pertenencias al ingreso (Parador)** | Sin task: lo resuelve el configurador. El Parador agrega el campo a su formulario de ingreso, sin desarrollo |
| 10 | **Referencia de GENACH** | Igual: es un campo del formulario, lo agrega el Ministerio. La integración con GENACH sigue fuera de alcance |
| 11 | **Préstamo de plaza** | **No exige autorización de un segundo usuario.** Alcanza con que queden registrados quién lo hizo y por qué, más las 12 o 24 h y la traza. Lo relevado en Calcuta decía «con autorización»; el PM define que el registro es suficiente |
| 12 | **Cobertura alimentaria de merenderos** | **Se mantiene** (6 h, M12). Declarado: no lo pidió el Ministerio en ninguna minuta, era un criterio excluido del issue #183 en la v1 y se repuso por propuesta nuestra |
| 13 | **Terminología de disponibilidad y ocupación** | El vocabulario operativo (normal, exigida, crítica, sin datos) queda **pendiente de confirmación con el área de Salud**, que era lo relevado. No figura como cerrado |
| 14 | **Horas que no son desarrollo** | Las 142 h de análisis, QA, diseño, despliegue y capacitación **se cargan como tasks** al terminar la revisión, para que el Project cierre contra el documento del cliente |
| 16 | **Borrado de campos del formulario (#313)** | De las catorce tasks de remediación cerradas el 08/09 como «terminadas de la v1», trece están cubiertas por el backlog v2 y **una no**: #313, «Sanear el borrado de campos de tipo: baja lógica y ProtectedError». Su bug está vivo: `CampoTipoDispositivoDeleteView` (`programas/views/dispositivos_config.py:215-221`) hace `campo.delete()` sin guarda, así que las respuestas ya cargadas quedan huérfanas con una clave que no apunta a nada, y si el campo tiene un adjunto el `PROTECT` de `ArchivoAdmision` levanta un `ProtectedError` sin manejar (error 500). **El requisito se agrega al modelo de formularios de M4**: un campo con respuestas no se borra, se da de baja lógica y deja de pedirse; el borrado real solo procede si nunca se respondió |
| 15 | **Casos de prueba** | Se generan **después** de cerrar la revisión, no antes: M4 se reescribió y escribir casos sobre tasks que van a cambiar es trabajo perdido. Hoy ninguna de las 45 tasks los tiene, así que ninguna es Ready |

---

## 12.1 Dependencias abiertas del Ministerio

Cinco entregables acordados en las minutas del 19/06 y del 26/06/2026 siguen sin recibirse, con
responsable **Equipo Chaco** y sin fecha. Se dejan asentados como **dependencia explícita de la Versión 2**, para
reclamarlos en la próxima reunión (decisión del PM, 09/09/2026):

| Entregable pendiente desde el 26/06 | Qué bloquea de la v2 |
|---|---|
| Formato de registro del programa **CDI** | El tipo CDI no existe como tipo de dispositivo ni tiene ficha; no está estimado |
| Visita a un dispositivo **ECA** para relevar los datos de intervención | La ficha de ECA y las reglas de permanencia de 48 h por medida judicial |
| Formularios de **Residencia Universitaria** y **Fortalecimiento Familiar** | Sus fichas, y la pregunta 6 de §12 (si Fortalecimiento trabaja con cupos, turnos o sin plazas) |
| Reenvío de **accesos y datos de infraestructura** | El despliegue a QA (§11.5 etapa 4) |
| Planillas y documentación de los formularios de la **Línea 102** (minuta 19/06, Guido Cortiglia) | La sección judicial de NNA y qué referencia de GENACH se guarda |

**Fichas por tipo: qué está cubierto y qué no.** La carga inicial de la v2 cubre los **dos** tipos
aprobados campo a campo: Adultos Mayores (33 campos de operador) y Abordaje Psicosocial (45). Sin
documento fuente quedan UPI, ECA, Residencias Universitarias, Fortalecimiento Familiar, CDI y —dato
llamativo— **las tres instituciones que motivaron la propia Versión 2**: Albergue Madre Teresa de
Calcuta, CIS N.º 3 y Parador Nocturno. El relevamiento de campo de septiembre las relevó a nivel de
**proceso**, no de campos (§2.4 de la estimación describe cómo operan y qué necesitan, no qué
preguntas tiene su ficha). Los tipos nuevos se crean por configuración, sin código, así que no hay
desarrollo bloqueado; lo que falta es el documento y quién carga cada ficha.

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
