# Programa Dispositivos y Merenderos — Propuesta funcional de la Versión 2

!!! abstract "En una línea"
    Llevar el sistema desde el **registro de una institución y sus camas** hasta la **gestión operativa real de la red**: la estadía de cada persona trazada de punta a punta, la capacidad calculada sola, la operación diaria registrada por turno sin transcribir nada, los formularios de cada tipo de institución armados por el Ministerio sin depender de desarrollo, y la información sensible accesible solo para quien corresponde.

| | |
|---|---|
| **Programas** | Dispositivos y Merenderos |
| **Estado** | Versión 1 desarrollada y entregada · **Versión 2 en validación del Ministerio** |
| **Origen** | Relevamiento de campo en el Albergue Madre Teresa de Calcuta, el CIS N.º 3, la Dirección de Abordaje Psicosocial (Programa Mírame/Vedia) y el Parador Nocturno, más las reuniones del 19/06 y del 26/06 |
| **Esfuerzo estimado** | 628 h · cuatro etapas entregables por separado · 12 semanas ([detalle](estimacion-programa-dispositivos.md)) |
| **Última actualización** | 2026-09-14 |

!!! success "Mockup navegable"
    Todo lo que describe este documento está dibujado sobre el sistema real: **[siete flujos y dieciocho pantallas](../mockups/dispositivos-v2.html)**. Cada sección enlaza a la pantalla que le corresponde.

---

## 1. Por qué hay una Versión 2

La Versión 1 se definió sobre los formularios en papel y el esquema que el Ministerio tenía armado. Está desarrollada y entregada, y resolvió lo que se acordó: el registro de las instituciones, las camas, las admisiones, el parte diario, los merenderos y los reportes.

Después se visitaron cuatro instituciones. Y lo que se vio ahí es que **la operación real es otra cosa**.

### 1.1 Lo que mostró el relevamiento

| Institución | Cómo trabaja de verdad |
|---|---|
| **Albergue Madre Teresa de Calcuta** | Alojamiento transitorio con habitaciones que tienen **cupos por servicio**, no camas sueltas. Se prestan camas entre residentes. Se usan cuadernos separados para recepción, serenazgo, área social, alimentos y limpieza, y cada turno transcribe lo del anterior. El edificio es de la Iglesia y la gestión es del Ministerio. |
| **CIS N.º 3** | Internación con operadores las veinticuatro horas, equipo técnico y Salud/Enfermería. **Ningún ingreso entra directo**: lo autoriza antes el Programa Central. La información médica y psicosocial no la puede ver cualquiera. |
| **Dirección de Abordaje Psicosocial (Mírame/Vedia)** | Trabaja con personas que **no están alojadas**: primera intervención, evaluación, plan de acción, seguimiento territorial y derivaciones a otros organismos. El legajo se construye a lo largo del tiempo, no en un formulario de ingreso. |
| **Parador Nocturno** | **Alta rotación**: la misma persona entra y sale muchas veces. Se registran a mano ingresos, egresos, pertenencias, conducta y economato. |

Ninguna de las cuatro entra en el modelo de la Versión 1, que supone una institución con camas planas, una admisión que se aprueba una vez y un formulario que se completa al ingresar y no se vuelve a mirar.

### 1.2 Los catorce cambios que pidieron las instituciones

Cada fila nace de una visita. La columna «hoy» es lo que hace el sistema entregado.

| Cambio solicitado | Quién lo pidió | Hoy | Se agrega |
|---|---|---|---|
| **Disponibilidad por servicio y cupos por habitación** | Albergue Calcuta | Camas planas por institución, sin agrupar | Sectores con cupos por servicio, y plazas de tipo cama, cupo o turno según el dispositivo |
| **Préstamo de cama** | Albergue Calcuta | No existe | Préstamo de plaza por 12 o 24 horas sin perder el vínculo del residente titular |
| **Dejar de transcribir entre turnos** | Albergue Calcuta y Parador Nocturno | Un parte por turno que el turno siguiente sobrescribe | Bitácora por turno cuyas novedades se agregan y nunca se sobrescriben, con pase de guardia y censo automático |
| **Autorización previa antes del alta** | CIS N.º 3 y Parador Nocturno | No existe: el ingreso es directo | Solicitud de ingreso que el programa central autoriza, con vigencia y reserva de plaza |
| **Acceso diferenciado a la información médica y psicosocial** | CIS N.º 3 y Albergue Calcuta | La ficha se ve completa o no se ve | Secciones con nivel de sensibilidad y permiso propio para salud, situación psicosocial y situación judicial |
| **Trazabilidad de las admisiones** | CIS N.º 3 | Historial solo del legajo de la institución | Auditoría de estadías, movimientos, bitácora, entregas y prestaciones |
| **Derivaciones y coordinación con organismos externos** | Abordaje Psicosocial | No existe | Derivaciones entre instituciones y a organismos externos, con aceptación, rechazo y vencimiento |
| **Historial de intervenciones y legajo compartido** | Abordaje Psicosocial | Formulario de ingreso que se completa una sola vez | Formularios que acompañan toda la estadía, con avance por sección, lectura, impresión y exportación |
| **Seguimiento de personas que no están alojadas** | Abordaje Psicosocial | Solo se registra a quien ocupa una cama | Estadía ambulatoria de seguimiento, compatible con una estadía residencial |
| **Ingreso y egreso de alta rotación** | Parador Nocturno | Alta de una persona por vez, sin movimientos intermedios | Estadía con cambio de plaza, permiso de salida con regreso previsto y traslado con seguimiento |
| **Registro de entregas con quién recibe** | Parador Nocturno y área de merenderos | Entrega con el servicio en texto libre | Catálogo de insumos y kits con equivalencia en raciones, y entregas con receptor y remito |
| **Visibilidad de camas y personas para la conducción** | Dirección del programa | Indicadores de cada institución por separado | Tablero de la red con capacidad, movimientos, permanencia y avisos configurables |
| **Encuadre real de las instituciones** | Albergue Calcuta | Un solo campo de identidad institucional | Categoría, titularidad del inmueble y dependencia de la gestión por separado, más documentación con vigencia |
| **Que el sistema avise y no bloquee** | Todas | La admisión exige cama disponible | Ingreso excepcional sobre la capacidad con autorización registrada: el sistema avisa y la decisión queda en el área |

---

## 2. Qué queda de la Versión 1

Nada de lo entregado se tira. La Versión 2 **crece sobre** lo construido, y por eso cuesta 628 h y no las más de 900 que costaría el mismo alcance partiendo de cero.

**Se conserva y se reutiliza tal cual:**

- El **Legajo Ciudadano** como dato único de la persona, con la validación de identidad contra el Registro de Personas. Ninguna institución vuelve a cargar el nombre, el documento o el domicilio de nadie.
- El **motor de roles y permisos** del sistema, que ya autoriza por acción y ya acota un rol a las instituciones que le asignan.
- El **registro maestro de instituciones** con su circuito de carga, validación, observación y rechazo, y el control de duplicados.
- El **catálogo de tipos de institución** y la pantalla donde se configuran sus formularios sin tocar código, con Adultos Mayores y Abordaje Psicosocial ya cargados campo por campo.
- El **programa Merenderos** completo en su primera forma: solicitudes con documentación, entregas de mercadería y prestación mensual.
- Los **reportes y exportaciones**, el sistema de diseño y toda la plataforma sobre la que corre el backoffice.

**Se profundiza sin rehacerse:** las camas se vuelven plazas dentro de sectores, la admisión se vuelve estadía, el parte diario se vuelve bitácora por turno, y el formulario de ingreso se vuelve un conjunto de formularios que acompaña todo el paso de la persona por la institución. En los tres casos lo construido queda como base.

---

## 3. Qué cambia, área por área

| Área | La Versión 1 hace hoy | La Versión 2 tiene que hacer |
|---|---|---|
| **Capacidad** | Camas con estado y ocupación calculada | Sectores con cupos por servicio; plazas de tipo cama, cupo o turno; préstamo de plaza por 12 o 24 horas; disponibilidad neta |
| **Ingreso** | Admisión con búsqueda por documento y asignación de cama | Solicitud con autorización previa del programa central; verificación de la situación de la persona en toda la red antes de alojarla; ingreso excepcional sobre la capacidad con autorización registrada; estadía ambulatoria sin plaza |
| **Durante la estadía** | Registro de la admisión y del egreso | Cambio de plaza o de sector con historial; permiso de salida con regreso previsto y aviso si no regresa; y una pantalla de la estadía con su línea de tiempo completa |
| **Traslado** | Cierre de la estadía en el origen y apertura en el destino | Estado *en tránsito* visible en las dos instituciones, con recepción o rechazo del destino, plazo de vencimiento y aviso |
| **Formularios** | Un formulario de ingreso por tipo, que se completa al admitir | Varios formularios por tipo de institución, uno por cada momento de la operación, que el Ministerio arma y cambia por su cuenta; con secciones de nivel de sensibilidad |
| **Operación diaria** | Parte diario por turno con cantidades calculadas | Bitácora por turno con novedades tipificadas que se agregan y nunca se sobrescriben; pase de guardia con constancia de quién entrega y quién recibe; censo automático; y regularización de días anteriores |
| **Legajo de la institución** | Identidad, domicilio, responsable y circuito de validación | Encuadre jurídico con categoría, titularidad del inmueble y dependencia de la gestión por separado; la subsecretaría de la que depende; documentación con vigencia y aviso de vencimiento; estados de *inauguración pendiente* y de *suspensión* con reactivación; y nivel de confianza del dato |
| **Derivaciones** | No contemplado | Derivaciones entre instituciones y a organismos externos, con aceptación, rechazo y vencimiento; lista de espera con prioridad; y vista de dónde hay plazas disponibles en la red |
| **Permisos** | Roles con alcance por institución | Alcance también por subsecretaría; niveles de sensibilidad de la información con aviso de lectura registrado; y separación de funciones: quien registra un movimiento no puede validarlo |
| **Configuración** | Tipos de dispositivo y campos del formulario | Reglas por tipo administradas desde el sistema: qué plazas admite, si exige autorización previa, si permite préstamo, límite de permanencia, secciones mínimas, catálogos de motivos y umbrales de aviso |
| **Conducción** | Indicadores de cada institución | Tablero de la red con capacidad, movimientos, permanencia y avisos configurables por regla |
| **Merenderos** | Solicitud, validación, entregas y prestación mensual | Catálogo de insumos y kits con equivalencia en raciones; entregas con quién recibe y remito; prestación con los servicios y los días de funcionamiento de cada merendero; cierre mensual; y cobertura alimentaria |
| **Trazabilidad** | Historial del legajo institucional | Auditoría única de todo el programa: estadías, movimientos, bitácora, entregas y prestaciones |
| **Carga inicial** | Importación del padrón de instituciones | Importación de sectores, plazas y personas alojadas, para arrancar con el censo real del día uno |

---

## 4. Cómo funciona la Versión 2

### 4.1 El legajo de la institución

Es el registro maestro, y vale igual para un dispositivo y para un merendero. Guarda la identidad, el **encuadre jurídico** —categoría pública, privada, ONG o religiosa; titularidad del inmueble y dependencia de la gestión por separado, porque el edificio puede ser de una congregación y el personal del Ministerio—, la **subsecretaría** de la que depende, la ubicación con geolocalización, los responsables, los **servicios que brinda** y la documentación con su fecha de vigencia.

Cada dato guarda además **de dónde salió**: fuente, fecha, responsable y nivel de confianza. Un dato migrado que nadie verificó nunca se publica como oficial en un reporte.

El legajo se carga, pasa a validación y lo valida **una persona distinta de la que lo cargó**. Además de activo, observado y rechazado, ahora tiene dos estados que faltaban: **inauguración pendiente**, para la institución que está lista pero todavía no abrió, y **suspendida**, que no admite ingresos nuevos pero conserva a quienes ya están alojados, con vuelta a activa. Cerrar una institución con gente alojada obliga primero a egresarla o trasladarla, y el sistema lo resuelve en bloque con un asistente.

*Ver: [flujo de estados](../mockups/dispositivos-v2.html#f2) · [listado](../mockups/dispositivos-v2.html#p2) · [alta con control de duplicados](../mockups/dispositivos-v2.html#p3) · [detalle](../mockups/dispositivos-v2.html#p4)*

### 4.2 La capacidad: sectores y plazas

Hoy una institución tiene camas sueltas. En la Versión 2 tiene **sectores** —una habitación, un pabellón, un ala, un «servicio» del albergue, el turno noche del parador— y dentro de cada sector, **plazas**.

Una plaza puede ser de tres clases: una **cama** cuando hay internación, un **cupo** cuando la atención es ambulatoria, o un **turno** cuando el dispositivo asigna por noche. El tipo de institución define cuáles admite y si asignar una es obligatorio al ingresar.

Una plaza puede estar disponible, reservada, ocupada, **prestada** —cedida a otra persona por 12 o 24 horas sin que el titular pierda su vínculo— o fuera de servicio. Poner fuera de servicio una plaza ocupada obliga a reubicar primero.

Y todo lo demás **se calcula solo**: operativas, ocupadas, reservadas, disponibles, ocupación por sector y el censo del día. Nadie tipea un número.

*Ver: [flujo de plazas y cálculo](../mockups/dispositivos-v2.html#f5) · [sectores y plazas](../mockups/dispositivos-v2.html#p5)*

### 4.3 La estadía de la persona

Es el corazón del cambio. Todo lo que le pasa a una persona en una institución cuelga de su **estadía**: la plaza que ocupa, los movimientos, las novedades, la ficha, el egreso.

**Antes de entrar.** Si el tipo de institución lo exige —como el CIS N.º 3 y el Parador—, primero hay una **solicitud de ingreso** que el programa central autoriza, rechaza o devuelve pidiendo datos. Una solicitud autorizada tiene vigencia y puede reservar la plaza. Para los tipos que no lo exigen, el ingreso sigue siendo directo.

**El ingreso** es un asistente de cuatro pasos. Se busca la persona por documento en el Legajo Ciudadano y, si no existe, se da de alta con los datos del Registro de Personas. Acá pasa algo que hoy no pasa: **el sistema mira toda la red**. Si la persona ya está alojada en otra institución, lo muestra y obliga a resolverlo antes de alojarla de nuevo —una persona no puede tener dos camas al mismo tiempo—. Un seguimiento ambulatorio, en cambio, **sí** puede convivir con una estadía residencial, que es exactamente lo que necesita Mírame/Vedia. Después se asigna la plaza; si no hay, la persona va a lista de espera o entra igual como **ingreso excepcional**, y ahí queda registrado quién lo autorizó y por qué. El sistema avisa, nunca bloquea.

**Durante la estadía** se registran movimientos, cada uno con su turno, hora, responsable y motivo: cambio de plaza o de sector, préstamo de plaza, permiso de salida con regreso previsto —con aviso si no regresa—, observaciones de conducta o incidentes.

**El traslado** deja de ser cerrar acá y abrir allá. La estadía queda **en tránsito**, visible en las dos instituciones a la vez, con la plaza de origen reservada. El destino la recibe o la rechaza, y si se vence el plazo hay aviso. La persona nunca figura alojada en dos lugares.

**El egreso** pide fecha y hora —nunca anteriores al ingreso—, motivo de un catálogo configurable, destino y, si corresponde, la derivación con su seguimiento.

**Los avisos** de la estadía son automáticos: límite de permanencia por tipo —las 48 horas de UPI y ECA cuando el ingreso viene de una medida judicial—, permiso de salida vencido, formulario incompleto pasados los días configurados y tránsito vencido.

*Ver: [estadía de punta a punta](../mockups/dispositivos-v2.html#f3) · [traslado en tránsito](../mockups/dispositivos-v2.html#f4) · [ingreso](../mockups/dispositivos-v2.html#p6) · [detalle de la estadía](../mockups/dispositivos-v2.html#p7) · [recepción del traslado](../mockups/dispositivos-v2.html#p8) · [egreso](../mockups/dispositivos-v2.html#p9)*

### 4.4 Los formularios de cada tipo de institución

Este es el cambio con más consecuencias, y el que más autonomía le da al Ministerio.

Hoy cada tipo de institución tiene **un** formulario, el de ingreso, y se completa una sola vez. Pero las instituciones no trabajan con un formulario: trabajan con una serie —el F-00 de admisión, el F-01 de novedades del turno, el F-02 de prestación mensual—, cada uno en su momento.

En la Versión 2, **cada tipo de institución tiene varios formularios**, y se arman desde la pantalla de configuración sin pedirle nada a desarrollo. Los que el sistema ya necesita vienen creados de fábrica y cada acción sabe a cuál llamar: el botón de admitir llama al de ingreso, el de egresar al de egreso, la bitácora al de novedades del turno. Y se pueden crear formularios propios además de esos.

Sobre cada formulario, el Ministerio decide sus secciones, sus campos y el orden. Algunos campos están **protegidos** porque el sistema depende de ellos —la fecha de ingreso, la plaza, la persona—: se ven, pero no se borran. Y un campo que ya tiene respuestas cargadas nunca se elimina: se da de baja, deja de pedirse y lo ya respondido se conserva.

Los formularios de Adultos Mayores y de Abordaje Psicosocial quedan cargados campo por campo, como están hoy. Los tipos que todavía están en relevamiento —UPI, ECA, Residencias Universitarias, Fortalecimiento Familiar, CDI y las tres instituciones visitadas en septiembre— **no necesitan desarrollo**: se cargan desde esta pantalla cuando el Ministerio entregue sus formularios.

*Ver: [formularios del tipo](../mockups/dispositivos-v2.html#p17) · [reglas por tipo](../mockups/dispositivos-v2.html#p14)*

### 4.5 La operación diaria: bitácora por turno

Reemplaza los cuadernos y el parte diario que se pisa.

Los **turnos** los configura cada institución. Cada entrada de la bitácora lleva turno, hora, responsable, tipo —novedad, ingreso, egreso, permiso de salida, incidente, visita, mantenimiento, alimentos, limpieza—, las personas involucradas y sus adjuntos. Las entradas **se agregan**: corregir una crea una versión nueva y la anterior sigue visible. Nada de un turno se pierde porque el siguiente escribió encima.

Al cerrar el turno, el responsable confirma el **pase de guardia**: el censo del turno y lo que queda pendiente de seguimiento. El turno siguiente lo recibe como primera cosa que ve, y queda registrado quién entregó y quién recibió.

El **censo es automático**: plazas totales, ingresos, egresos, ocupación nocturna, disponibles, préstamos vigentes y personas con permiso de salida. Nadie lo tipea.

Se pueden **regularizar** días anteriores dentro de una ventana configurable, y queda marcado que se cargó fuera de término.

*Ver: [flujo del turno](../mockups/dispositivos-v2.html#f6) · [bitácora y pase de guardia](../mockups/dispositivos-v2.html#p10)*

### 4.6 Lista de espera y derivaciones

La **lista de espera** de cada institución tiene posición, prioridad por criterios configurables —medida judicial, edad, riesgo—, origen y plaza reservada opcional. Cuando se libera una plaza el sistema sugiere a quién le toca, pero **no promueve solo**: la decisión es de una persona.

Las **derivaciones** van entre instituciones y también a organismos externos. Quien deriva registra destino, motivo y urgencia; el destino acepta, rechaza con motivo o deja vencer. Aceptar abre una solicitud de ingreso o una estadía según el tipo. Todo queda en el historial de la persona.

Y hay una **vista de red** que muestra dónde hay plazas disponibles por tipo, sector y localidad, para poder decidir la derivación.

*Ver: [espera y derivaciones](../mockups/dispositivos-v2.html#p11)*

### 4.7 Quién ve qué: alcance y sensibilidad

**El alcance** define qué instituciones ve cada rol, y tiene tres niveles:

- **Por institución**, que ya existe: el rol se asigna a una o varias. Es el caso del responsable de una institución, y también el del programa central, que tiene asignadas todas las que autoriza aunque sean de subsecretarías distintas.
- **Por subsecretaría**, que es nuevo: un rol con este alcance ve **todas** las instituciones de su subsecretaría y ninguna de otra, sin que nadie se las asigne una por una.
- **Total**, que es el administrador central y ya existe.

**La sensibilidad** es otra cosa, y es independiente del alcance. Cada sección de un formulario declara su nivel —general, social, salud, psicosocial o judicial—, y el permiso se tilda en el rol como cualquier otro.

Lo importante es **cómo se comporta**. Si no tenés el nivel, la sección **no desaparece**: ves que existe, ves cuánto está completa y ves qué equipo la completa. Algo así como «tu rol no accede a esta sección; la completa el equipo de psicología, está completa al 80 %». Quien atiende a la persona sabe que esa información existe y a quién pedírsela, sin verla.

Y si **sí** tenés el nivel, tampoco alcanza con tenerlo. Al abrir la sección el sistema avisa que la información es sensible y hay que confirmarlo. **Esa confirmación queda registrada** con el usuario, la sección, la persona y la fecha y hora, cada vez que se abre. Además, dentro de las secciones sensibles el contenido no se puede copiar ni exportar sin el nivel, y lleva una marca de agua con el usuario y la hora para que una filtración sea rastreable.

!!! note "Sobre las capturas de pantalla"
    En la reunión del 19 de junio se planteó «inhabilitar capturas o copias» de la información de la Línea 102. Corresponde ser claros: **una captura de pantalla no se puede impedir** en ningún sistema web —siempre queda la foto con el celular—. Lo que sí protege de verdad es lo que se implementa: el permiso por nivel, el aviso de lectura registrado, el bloqueo de copiado y exportación, la marca de agua y la auditoría de quién leyó qué.

Por último, **separación de funciones**: quien registra un movimiento no puede validarlo ni confirmar su cierre. No es una recomendación, lo rechaza el sistema.

*Ver: [roles, alcance y sensibilidad](../mockups/dispositivos-v2.html#p15) · [sección sensible y aviso de lectura](../mockups/dispositivos-v2.html#p18)*

### 4.8 El tablero de la red y los avisos

Un **tablero del programa** con la capacidad de toda la red por tipo y localidad, la ocupación y la disponibilidad, los ingresos y egresos del período, la permanencia promedio, los alojados por sector y los merenderos con cobertura en rojo. Con filtros por subsecretaría, tipo, localidad y período, y todo exportable.

Los **avisos** se configuran por regla, no vienen fijos: tránsito vencido, permanencia excedida, turno sin cerrar, documentación vencida, formulario incompleto, espera prolongada, cobertura en rojo.

Cada institución tiene además su propia franja de indicadores, con vocabulario operativo: normal, exigida, crítica, sin datos.

*Ver: [tablero de la red](../mockups/dispositivos-v2.html#p1)*

### 4.9 Reportes, carga inicial y auditoría

**Diez reportes** exportables en CSV y Excel: padrón de instituciones, ocupación por dispositivo y sector, movimientos del período, censo diario, bitácora, lista de espera y derivaciones, padrón de merenderos con entregas, prestaciones y cobertura. Cada uno sale acotado al alcance y a la sensibilidad de quien lo pide, y queda registrado quién exportó qué.

Para **arrancar con datos reales**, un importador carga las instituciones, sus sectores, sus plazas y —opcionalmente— las personas alojadas hoy, con su nivel de confianza. Después el equipo territorial verifica en campo y el dato pasa a verificado.

Y una **auditoría única** para todo el programa: cada estadía, movimiento, entrada de bitácora, entrega y prestación queda con su antes y su después, legible en idioma de operador y exportable.

### 4.10 Merenderos

Merenderos sigue siendo un **programa propio**, como se definió el 1.º de julio, pero comparte el legajo institucional y toda la parte transversal, y pasa a verse, navegarse y auditarse igual que Dispositivos.

Lo que se agrega: un **catálogo de insumos y kits** con qué contiene cada kit y su equivalencia en raciones; **entregas** con el kit del catálogo, quién recibe, remito adjunto, bloqueo si falta documentación vigente y anulación con motivo; y una **prestación mensual** armada con los servicios y los días que cada merendero declara en su legajo —no siempre son los cuatro—, con totales calculados, cierre del mes por un rol distinto del que cargó y reapertura con motivo.

Se suma un indicador de **cobertura alimentaria**: raciones servidas contra raciones entregadas y contra la capacidad declarada, con aviso cuando la demanda supera la entrega.

*Ver: [flujo de merenderos](../mockups/dispositivos-v2.html#f7) · [detalle del merendero](../mockups/dispositivos-v2.html#p12) · [prestación mensual](../mockups/dispositivos-v2.html#p13)*

### 4.11 La persona en su legajo ciudadano

Desde el legajo de cualquier ciudadano, la solapa **Dispositivos** muestra **toda su trayectoria en el programa**: las estadías abiertas y las cerradas, en cualquier institución de la red, con fechas, motivo de egreso, derivaciones y paso por lista de espera. Hoy esa solapa desaparece del legajo en cuanto la persona egresa; en la Versión 2 el historial queda.

Esa solapa **no se filtra por alcance**: cualquiera del programa que abra el legajo ve la trayectoria completa, porque el legajo es el dato único de la persona. Lo que decide qué se ve adentro es la sensibilidad de cada sección. Y es una vista **de lectura**: para operar sobre una estadía hay que entrar al programa, donde sí manda el alcance.

*Ver: [solapa en el legajo ciudadano](../mockups/dispositivos-v2.html#p16)*

---

## 5. Los flujos

Los siete circuitos completos, dibujados de punta a punta:

| | Flujo | Qué muestra |
|---|---|---|
| **F1** | [Mapa de módulos y navegación](../mockups/dispositivos-v2.html#f1) | Cómo se ordena el programa y desde dónde se llega a cada cosa |
| **F2** | [Legajo institucional: estados](../mockups/dispositivos-v2.html#f2) | El camino del legajo desde el borrador hasta el cierre, con quién valida |
| **F3** | [Estadía de punta a punta](../mockups/dispositivos-v2.html#f3) | Solicitud, ingreso, movimientos y egreso |
| **F4** | [Traslado en tránsito](../mockups/dispositivos-v2.html#f4) | Qué ve el origen y qué ve el destino mientras la persona viaja |
| **F5** | [Plazas: estados y cálculo](../mockups/dispositivos-v2.html#f5) | Cómo se derivan ocupación y disponibilidad desde los movimientos |
| **F6** | [Turno, bitácora y pase de guardia](../mockups/dispositivos-v2.html#f6) | El día de una institución de veinticuatro horas |
| **F7** | [Merenderos: de la solicitud a la prestación](../mockups/dispositivos-v2.html#f7) | El circuito completo del programa hermano |

## 6. Las pantallas

Dieciocho pantallas dibujadas sobre el sistema real, con su menú, su tipografía y sus componentes:

| | Pantalla | | Pantalla |
|---|---|---|---|
| **P1** | [Tablero de la red](../mockups/dispositivos-v2.html#p1) | **P10** | [Bitácora del turno y pase de guardia](../mockups/dispositivos-v2.html#p10) |
| **P2** | [Instituciones: listado](../mockups/dispositivos-v2.html#p2) | **P11** | [Lista de espera y derivaciones](../mockups/dispositivos-v2.html#p11) |
| **P3** | [Alta con control de duplicados](../mockups/dispositivos-v2.html#p3) | **P12** | [Merendero: detalle](../mockups/dispositivos-v2.html#p12) |
| **P4** | [Detalle del dispositivo](../mockups/dispositivos-v2.html#p4) | **P13** | [Prestación alimentaria mensual](../mockups/dispositivos-v2.html#p13) |
| **P5** | [Sectores y plazas](../mockups/dispositivos-v2.html#p5) | **P14** | [Configuración: reglas por tipo](../mockups/dispositivos-v2.html#p14) |
| **P6** | [Ingreso de una persona](../mockups/dispositivos-v2.html#p6) | **P15** | [Roles, alcance y sensibilidad](../mockups/dispositivos-v2.html#p15) |
| **P7** | [Detalle de la estadía](../mockups/dispositivos-v2.html#p7) | **P16** | [Solapa en el Legajo Ciudadano](../mockups/dispositivos-v2.html#p16) |
| **P8** | [Traslado visto desde el destino](../mockups/dispositivos-v2.html#p8) | **P17** | [Formularios del tipo de institución](../mockups/dispositivos-v2.html#p17) |
| **P9** | [Egreso](../mockups/dispositivos-v2.html#p9) | **P18** | [Sección sensible y aviso de lectura](../mockups/dispositivos-v2.html#p18) |

---

## 7. Lo que queda fuera de esta versión

Se releva, se documenta y **no se estima acá**. Cada uno requiere definición funcional propia antes de poder cotizarse:

- Inventario y stock integral de alimentos, limpieza, fármacos, agua, colchones y kits, y su integración con ECOM.
- Administración de medicación: prescripciones, dosis, horarios y entregas.
- Historial clínico y legajo de salud.
- Asistencia, situación de revista y distribución del personal.
- Funcionamiento sin conexión con sincronización posterior.
- Control de acceso físico por huella o clave.
- Vista interactiva de habitaciones y aplicaciones móviles para cocina, lavadero y mantenimiento.
- Tablero de Comando central completo y planes de contingencia activables por emergencia.
- La Línea 102 como circuito propio. Lo que sí queda previsto es que la información judicial de NNA **se referencie y no se duplique**.
- Portal ciudadano para solicitudes de merendero y padrón nominal de niños y tutores.

La Versión 2 deja preparados los puntos de enganche para todo esto: entradas de bitácora tipificadas, servicios en el legajo, sectores y plazas, niveles de sensibilidad y avisos configurables.

---

## 8. Lo que necesitamos del Ministerio

### 8.1 Documentación pendiente

Cinco entregables quedaron acordados en las reuniones de junio y todavía no llegaron. Ninguno frena el desarrollo, pero cada uno bloquea una parte del alcance:

| Pendiente desde | Entregable | Qué destraba |
|---|---|---|
| 26/06 | Formato de registro del programa **CDI** | Que el tipo CDI exista con su formulario |
| 26/06 | Visita a un dispositivo **ECA** para relevar los datos de intervención | El formulario de ECA y las reglas de permanencia de 48 horas |
| 26/06 | Formularios de **Residencia Universitaria** y **Fortalecimiento Familiar** | Sus formularios, y si Fortalecimiento trabaja con cupos, con turnos o sin plazas |
| 26/06 | Reenvío de **accesos y datos de infraestructura** | El despliegue al ambiente de pruebas |
| 19/06 | Planillas y documentación de los formularios de la **Línea 102** | Qué referencia se guarda de la información judicial |

### 8.2 Definiciones para la reunión de arranque

Hay un conjunto de decisiones que tomamos por defecto para no frenar, y que conviene confirmar o corregir en una sola sesión al empezar. Las principales:

1. **Una sola plaza por persona en toda la red**, con la excepción de que un seguimiento ambulatorio conviva con una estadía residencial.
2. **Quién autoriza un ingreso por encima de la capacidad**, y hasta qué límite.
3. **Qué tipos de institución exigen autorización previa** del programa central, quién la otorga y por cuánto tiempo vale.
4. **El préstamo de plaza**: se confirma la regla de 12 o 24 horas, y si las plazas prestadas cuentan como disponibles.
5. **Qué roles ven cada nivel de información sensible** y qué secciones de cada formulario corresponden a cada nivel.
6. **Fortalecimiento Familiar**: si trabaja con cupos, con turnos o sin plazas.
7. **Albergues y contención nocturna**: si son un tipo de institución propio o una variante de Abordaje Psicosocial.
8. **La bitácora**: qué tipos de novedad son obligatorios en el pase de guardia y cuántos días se aceptan para regularizar.
9. **Merenderos**: si la prestación se carga en raciones o como marca por servicio, y si los servicios se configuran por merendero.
10. **Los kits**: si existe un catálogo del Ministerio con su contenido y equivalencia en raciones, o lo armamos juntos.
11. **Las derivaciones a organismos externos** —hospital, juzgado—: si se registran como destino de egreso o como derivación con seguimiento.
12. **El vocabulario de ocupación y disponibilidad**: los términos operativos propuestos requieren confirmación del área de Salud.

---

## 9. Esfuerzo, etapas y plazos

La Versión 2 se estima en **628 horas**, sobre una Versión 1 de 436 horas ya aprobada y desarrollada. El detalle módulo por módulo, la composición por perfil y el criterio de las horas están en la **[estimación del programa](estimacion-programa-dispositivos.md)**.

Se entrega en **cuatro etapas**, y cada una es utilizable por sí misma. El Ministerio puede aprobarlas por separado y detenerse al final de cualquiera:

| Etapa | Qué queda funcionando | Horas | Duración |
|---|---|---:|---|
| **1** | La institución opera: legajo con encuadre y documentación, permisos por subsecretaría con separación de funciones, reglas por tipo, sectores y plazas, y el circuito completo de estadías con traslados | 302 | 5 semanas |
| **2** | Los formularios y el turno: el configurador de formularios por tipo con secciones sensibles y lectura registrada, y la bitácora por turno con pase de guardia y censo | 148 | 3 semanas |
| **3** | La red y la conducción: derivaciones, lista de espera, tablero de la red, reportes y carga inicial del padrón | 98 | 2 semanas |
| **4** | Merenderos: catálogo de kits, entregas con receptor, prestación mensual y cobertura, más el despliegue final y la capacitación | 80 | 2 semanas |
| | **Total** | **628** | **12 semanas** |

!!! tip "Si hubiera que elegir una sola etapa"
    La **etapa 1** es la que más cambia la operación: resuelve ocho de los catorce cambios que pidieron las instituciones, incluidos los tres que más se repitieron en las visitas —cupos por servicio, autorización previa de ingreso y traslado con seguimiento—. Las etapas 3 y 4 suman 178 horas y ninguna bloquea la operación diaria.

**Equipo:** un desarrollador backend y uno frontend a tiempo completo, con análisis funcional, diseño y pruebas en paralelo a tiempo parcial. **Inicio:** a definir con el Ministerio, sujeto a la aprobación de esta propuesta.
