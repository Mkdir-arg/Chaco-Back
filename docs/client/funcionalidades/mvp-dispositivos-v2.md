# Programa Dispositivos — MVP de la Versión 2

!!! abstract "En una línea"
    Un primer alcance de **700 horas** que pone en funcionamiento dos cosas: el **relevamiento de los dispositivos desde la aplicación móvil**, con criticidad y evidencia fotográfica, y el **circuito operativo de las personas** dentro de cada dispositivo —quién entra, dónde está, cómo se mueve y cuándo sale—.

| | |
|---|---|
| **Programa** | Dispositivos |
| **Estado** | Alcance definido por el Ministerio · a confirmar fecha de inicio |
| **Esfuerzo** | 700 h · cuatro bloques · aproximadamente 14 semanas |
| **Relación con la Versión 2** | Primer tramo de la [propuesta funcional completa](propuesta-dispositivos-v2.md); no la reemplaza, la ordena en el tiempo |
| **Última actualización** | 2026-10-08 |

!!! warning "Para qué sirve este documento"
    El alcance que definió el Ministerio está escrito en cuatro párrafos breves. Acá se abre en detalle **qué queda funcionando y qué no** en cada bloque, para que no haya sorpresas al entregar. Si algo de lo que figura acá no coincide con lo que el Ministerio tenía en mente, **es el momento de corregirlo**: una vez acordado, esto es lo que se construye.

---

## 1. Qué es este MVP

La [propuesta funcional de la Versión 2](propuesta-dispositivos-v2.md) describe el programa completo y está estimada en 827 horas repartidas en cinco etapas. Este documento define el **primer recorte que el Ministerio eligió para arrancar**: cuatro bloques de trabajo, 700 horas.

El criterio del recorte es poner en marcha **el circuito de las personas puertas adentro de cada dispositivo** y **el relevamiento de los edificios en campo**, dejando para después la mirada de red, la configuración avanzada y el programa de Merenderos.

---

## 2. Los cuatro bloques

### Bloque 1 · Aplicación, sectores y criticidad — 140 h

Pone al agente territorial a relevar en campo desde el celular, y a esa información a verse en el backoffice.

**Queda funcionando**

- La **aplicación móvil conectada al módulo Dispositivos**: el agente entra con su usuario y ve los dispositivos sobre los que puede trabajar. Incluye los servicios del lado del sistema, la autenticación y las pruebas de integración entre ambas partes.
- **Selección del dispositivo y del sector** que se está relevando.
- Carga de **criticidad** —la calificación de severidad de lo que se encontró—, **observaciones** en texto y **fotos** como evidencia.
- **Responsable y fecha** se toman solos del usuario que carga y del momento de la carga: no se tipean.
- **Estado del relevamiento**, para saber si está cargado, revisado o pendiente.
- En el backoffice, **el listado de relevamientos** de cada dispositivo y el **detalle de cada uno** con sus fotos y observaciones.
- **Semáforo de criticidad** sobre el dispositivo, para ver de un vistazo cuáles están en rojo.
- **Permisos**: quién puede relevar, quién puede ver lo relevado y quién puede revisarlo.

**No incluye**

- El **resto de los datos de infraestructura** que pide la propuesta: estado de tenencia (propio, alquilado, comodato), ubicación en mapa, cantidad de habitaciones, plano del edificio y servicios disponibles —luz, agua, internet, señal—.
- El **vencimiento automático** del relevamiento a los seis meses, o al mes si el dispositivo está en obra, con su aviso por correo.
- El botón **«Relevar ya»** para forzar una revisión ante un reclamo puntual.
- La pantalla donde el **coordinador crea el relevamiento y se lo asigna** a un agente concreto. En este MVP el agente elige desde la app qué dispositivo y qué sector releva; no hay una tarea asignada previamente.
- La regla de que el agente sea **externo a la institución** que releva.
- El **informe oficial** generado y vinculado al legajo del dispositivo.
- El tratamiento de **predios compartidos** por varias instituciones: acá cada dispositivo se releva por separado, aunque compartan edificio.
- **Funcionamiento sin conexión.** El agente necesita señal en el momento de cargar; si el dispositivo está en una zona sin cobertura, no puede completar el relevamiento ahí.

### Bloque 2 · Ingresos y egresos — 220 h

La primera etapa operativa: que cada dispositivo registre quién entra, quién sale, cuándo y por qué.

**Queda funcionando**

- **Búsqueda de la persona por documento** en el legajo ciudadano que ya existe, con su identidad ya validada. Si no está, se da de alta ahí mismo.
- **Registro del ingreso** con fecha y hora.
- **Asignación a un sector o plaza** en los dispositivos que las manejen.
- **Validaciones mínimas**: que la persona no tenga ya un ingreso abierto en ese mismo dispositivo, que la plaza esté libre y que la fecha de egreso nunca sea anterior a la de ingreso.
- **Historial de ingresos** de cada persona en ese dispositivo, incluidos los cerrados.
- **Egreso** con fecha, motivo tomado de un catálogo y destino o derivación.
- **Liberación del cupo** al egresar: la disponibilidad del dispositivo se recalcula sola, nadie la tipea.
- **Trazabilidad** de todo el circuito: qué pasó, quién lo hizo y cuándo.

**No incluye**

- La **solicitud de ingreso con autorización previa** del programa central, que hoy usan el CIS N.º 3 y el Parador Nocturno. Acá todo ingreso es directo.
- La **verificación de la persona en toda la red.** Las validaciones miran solo el dispositivo donde se está cargando: **una persona puede quedar registrada como alojada en dos dispositivos a la vez** y el sistema no lo detecta.
- La **detección de reingreso** en la red.
- El **ingreso excepcional por encima de la capacidad** con registro de quién lo autorizó y por qué.
- El **traslado entre dispositivos** con estado *en tránsito* visible en las dos puntas. Un traslado se registra como un egreso acá y un ingreso allá, sin vínculo entre los dos.
- La **estadía ambulatoria**, el seguimiento de personas que no ocupan una plaza, que es como trabaja Abordaje Psicosocial.
- La **solapa Dispositivos en el legajo ciudadano**: el historial se ve desde el dispositivo, no desde la ficha de la persona.

### Bloque 3 · Circuito interno — 240 h

La operación puertas adentro, una vez que la persona ya está alojada.

**Queda funcionando**

- **Movimientos entre sectores** dentro del mismo dispositivo, con su registro.
- **Permanencia**: cuánto tiempo lleva alojada cada persona.
- **Cambios de estado** de la estadía.
- **Novedades y observaciones**, con registro de **turno y responsable**.
- **Seguimiento interno** de cada persona durante su estadía.
- **Alertas por criticidad**.
- **Vista de situación del dispositivo**: quiénes están alojados, en qué sector y cuántas plazas quedan.
- **Auditoría básica** de lo actuado.

**No incluye**

- El **pase de guardia**: el cierre formal del turno donde el responsable entrega un resumen y el turno siguiente lo recibe, con constancia de quién entregó y quién recibió.
- El **censo automático por turno** —existencia inicial, ingresos, egresos, existencia final—.
- El **versionado de las novedades**. Acá una corrección modifica el registro; no queda la versión anterior visible al lado de la nueva.
- La **regularización de días anteriores** con marca de carga fuera de término.
- El **préstamo de plaza** entre residentes por doce o veinticuatro horas.
- El **permiso de salida con regreso previsto** y el aviso cuando la persona no vuelve.
- Los **tipos de novedad configurables** por el Ministerio.
- Los **formularios de la persona por tipo de institución**: no hay ficha socioeconómica ni de salud, solo observaciones en texto.

### Bloque 4 · Reserva — 100 h

No es un módulo: es una **bolsa explícita** para absorber lo que siempre aparece y nunca está en la lista.

Se usa para ajustes de reglas y cambios que pida el Ministerio durante el desarrollo, diferencias de operación entre un dispositivo y otro, integración con la aplicación móvil, retrabajo de interfaz, pruebas adicionales, carga de datos reales y despliegue.

**Cómo se consume:** contra trabajo concreto, acordado en el momento y registrado con su detalle. **Lo que no se usa no se factura.**

---

## 3. Resumen y plazo

| | Bloque | Horas |
|---|---|---:|
| **1** | Aplicación, sectores y criticidad | 140 |
| **2** | Ingresos y egresos | 220 |
| **3** | Circuito interno | 240 |
| **4** | Reserva | 100 |
| | **Total** | **700** |

**Aproximadamente 14 semanas** con un desarrollador backend y uno frontend a tiempo completo, más el equipo móvil en el bloque 1.

**Sobre el orden.** Los bloques 2 y 3 son secuenciales: el circuito interno se apoya en los ingresos. El bloque 1 es **independiente** y puede ir en paralelo, porque toca otra parte del sistema y suma al equipo móvil. Arrancando por el bloque 2, **a las seis semanas** el Ministerio ya tiene dispositivos registrando ingresos y egresos reales.

---

## 4. Qué queda para después, tema por tema

Nada de esto se descarta: está definido y estimado en la [propuesta de la Versión 2](propuesta-dispositivos-v2.md).

| Tema | Qué entra en el MVP | Qué queda para después |
|---|---|---|
| **Legajo de la institución** | El dispositivo tal como está hoy | Encuadre jurídico con titularidad del inmueble y dependencia de la gestión; subsecretaría de la que depende; documentación con vigencia y aviso de vencimiento; estados de *inauguración pendiente* y *suspensión*; control de duplicados al dar de alta; fusión de instituciones repetidas |
| **Infraestructura** | Criticidad, observaciones y fotos del sector | Tenencia, mapa, habitaciones y plano, servicios disponibles, vencimiento automático, botón «Relevar ya» y predios compartidos |
| **Relevamientos** | El agente carga desde la app lo que elige relevar | Que el coordinador cree y asigne la tarea a un agente externo a la institución, con vencimiento e informe oficial |
| **Capacidad** | Sectores y plazas con asignación y liberación | Tipos de plaza (cama, cupo o turno), estados de la plaza, préstamo, reubicación asistida y disponibilidad neta |
| **Ingreso** | Alta o selección de la persona, ingreso directo | Autorización previa del programa central, verificación en toda la red, detección de reingreso e ingreso excepcional sobre la capacidad |
| **Traslado** | Egreso en origen e ingreso en destino, sin vínculo | Estado *en tránsito* visible en las dos instituciones, recepción o rechazo del destino, plazo y aviso |
| **Operación diaria** | Novedades con turno y responsable | Pase de guardia con constancia, censo automático, versionado de las novedades y regularización de días anteriores |
| **Formularios** | Observaciones en texto | Formularios configurables por tipo de institución, que el Ministerio arma y cambia sin pedir desarrollo |
| **Mirada de red** | Vista de cada dispositivo por separado | Lista de espera con prioridad, derivaciones entre instituciones y a organismos externos, tablero de toda la red y reportes exportables |
| **Permisos** | Permisos básicos de quién releva y quién ve | Alcance por subsecretaría, niveles de sensibilidad de la información médica, psicosocial y judicial, y separación de funciones |
| **Contratos y servicios** | — | Alquiler, luz, agua e internet con último pago, vencimiento, comprobante, aviso y escalado |
| **Conducción** | — | Tableros que cada responsable arma con los indicadores que necesita, y recordatorios propios |
| **Merenderos** | — | El programa completo: catálogo de kits, entregas con receptor y remito, prestación mensual y cobertura alimentaria |

---

## 5. Qué no se va a poder hacer el día uno

Dicho de la forma más directa, para que quede claro antes de empezar:

- **No se va a saber si una persona ya está alojada en otro dispositivo.** Cada dispositivo valida solo lo suyo.
- **No se va a poder trasladar a alguien con seguimiento.** El traslado se registra como dos movimientos sueltos, sin que las dos instituciones vean el mismo caso.
- **No se va a poder pedir autorización antes de un ingreso**, como hoy exigen el CIS N.º 3 y el Parador.
- **No se va a poder cambiar un formulario sin desarrollo**, porque todavía no hay formularios configurables.
- **No hay información sensible diferenciada.** Quien entra al dispositivo ve todo lo cargado; no existen todavía los niveles para salud, situación psicosocial y situación judicial.
- **No hay visión de la red.** Cada dispositivo se mira por separado: no hay tablero del conjunto ni reportes exportables.
- **El agente necesita señal para relevar.** Sin conexión no puede cargar en el momento.
- **Merenderos no entra.** Sigue funcionando como está hoy.

---

## 6. Definiciones a cerrar antes de arrancar

Cinco definiciones cortas, que conviene resolver en una sola reunión:

1. **La criticidad.** Es un concepto nuevo, no estaba en la propuesta. ¿Qué escala usa —por ejemplo baja, media, alta, crítica—? ¿Quién la asigna, el agente territorial o el coordinador al revisar? ¿Y dispara algo además de avisar, o el sistema solo informa y la decisión queda en el área?

2. **Si el relevamiento es por sector o por edificio.** Este MVP lo plantea **por sector**, que da más detalle y más trabajo de carga. La propuesta lo planteaba **por edificio**, que es lo que permite relevar una sola vez un predio compartido por varias instituciones, como el caso de Resistencia. Hay que elegir uno.

3. **Quién releva y cómo recibe la tarea.** En este MVP el agente elige libremente desde la app qué relevar. La propuesta establecía que el coordinador le asigna la tarea y que el agente es **externo a la institución**, para que no se omitan irregularidades. Si eso importa, hay que incorporarlo.

4. **Los estados del relevamiento.** Cuáles son y quién los mueve: alcanza con *cargado* y *revisado*, o hace falta un circuito de validación con observaciones y corrección.

5. **El catálogo de motivos de egreso.** Qué opciones tiene y si el Ministerio quiere poder modificarlo después sin pedir desarrollo.
