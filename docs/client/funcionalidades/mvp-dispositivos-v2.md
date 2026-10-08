# Programa Dispositivos — MVP de la Versión 2

!!! abstract "En una línea"
    Un primer alcance de **700 horas** que pone en funcionamiento dos cosas: el **relevamiento de los dispositivos en campo**, desde la aplicación móvil y aunque no haya señal, y el **circuito operativo de las personas** —quién entra, dónde está, cómo se mueve y cuándo sale—, con verificación en toda la red.

| | |
|---|---|
| **Programa** | Dispositivos |
| **Estado** | Alcance definido por el Ministerio · a confirmar fecha de inicio |
| **Esfuerzo** | 700 h · aproximadamente 14 semanas |
| **Relación con la Versión 2** | Primer tramo de la [propuesta funcional completa](propuesta-dispositivos-v2.md); no la reemplaza, la ordena en el tiempo |
| **Última actualización** | 2026-10-08 |

!!! warning "Para qué sirve este documento"
    El alcance que definió el Ministerio está escrito en cuatro párrafos breves. Acá se abre en detalle **qué se entrega y qué no**, para que no haya sorpresas al momento de la entrega. Si algo de lo que figura acá no coincide con lo que el Ministerio tenía en mente, **es el momento de corregirlo**: una vez acordado, esto es lo que se construye.

---

## 1. Qué es este MVP

La [propuesta funcional de la Versión 2](propuesta-dispositivos-v2.md) describe el programa completo y está estimada en 827 horas repartidas en cinco etapas. Este documento define el **primer recorte que el Ministerio eligió para arrancar**: 700 horas.

El criterio del recorte es poner en marcha **el circuito de las personas** y **el relevamiento de los edificios en campo**, dejando para después la configuración avanzada, la mirada de red y el programa de Merenderos.

---

## 2. Qué se entrega

### El relevamiento en campo

- **La aplicación móvil conectada al módulo Dispositivos**: el agente entra con su usuario y ve los dispositivos sobre los que puede trabajar. Incluye los servicios del lado del sistema, la autenticación y las pruebas de integración entre ambas partes.
- **Creación y asignación del relevamiento**: el coordinador elige el dispositivo, asigna el agente que lo va a relevar y la tarea le llega a su aplicación. El agente no elige libremente qué relevar: recibe lo que se le asignó.
- **Selección del dispositivo y del sector** que se está relevando.
- Carga de **criticidad** —la calificación de severidad de lo que se encontró—, **observaciones** en texto y **fotos** como evidencia.
- **Responsable y fecha** se toman solos del usuario que carga y del momento de la carga: no se tipean.
- **Funcionamiento sin conexión.** El agente puede completar el relevamiento y sacar las fotos **sin señal**; cuando el celular recupera conexión, todo se sincroniza solo. Es la pieza de mayor peso técnico de este MVP.
- **Estado del relevamiento**, para saber si está asignado, cargado o revisado.
- En el backoffice, **el listado de relevamientos** de cada dispositivo y el **detalle de cada uno** con sus fotos y observaciones.
- **Semáforo de criticidad** sobre el dispositivo, para ver de un vistazo cuáles están en rojo.

### El ingreso y el egreso de las personas

- **Búsqueda de la persona por documento** en el legajo ciudadano que ya existe, con su identidad ya validada. Si no está, se da de alta ahí mismo.
- **Registro del ingreso** con fecha y hora.
- **Asignación a un sector o plaza** en los dispositivos que las manejen.
- **Verificación de la persona en toda la red.** Antes de alojarla, el sistema avisa si ya figura alojada en otro dispositivo, para que se resuelva primero. Nadie queda registrado en dos lugares a la vez.
- **Validaciones**: que la plaza esté libre y que la fecha de egreso nunca sea anterior a la de ingreso.
- **Egreso** con fecha, motivo tomado de un catálogo y destino o derivación.
- **Liberación del cupo** al egresar: la disponibilidad del dispositivo se recalcula sola, nadie la tipea.
- **La solapa Dispositivos en el legajo ciudadano**: desde la ficha de cualquier persona se ve su paso por los dispositivos, incluidas las estadías cerradas.
- **Trazabilidad** de todo el circuito: qué pasó, quién lo hizo y cuándo.

### La operación diaria del dispositivo

- **Movimientos entre sectores** dentro del mismo dispositivo, con su registro.
- **Permanencia**: cuánto tiempo lleva alojada cada persona.
- **Cambios de estado** de la estadía.
- **Novedades y observaciones**, con registro de **turno y responsable**.
- **Censo automático por turno**: existencia inicial, ingresos, egresos y existencia final se calculan solos a partir de los movimientos. Nadie tipea un número.
- **Seguimiento interno** de cada persona durante su estadía.
- **Alertas por criticidad**.
- **Vista de situación del dispositivo**: quiénes están alojados, en qué sector y cuántas plazas quedan.
- **Auditoría básica** de lo actuado.

---

## 3. Qué no se entrega

Nada de esto se descarta: está definido y estimado en la [propuesta de la Versión 2](propuesta-dispositivos-v2.md) y se retoma después.

### Del legajo de la institución

- Encuadre jurídico con **titularidad del inmueble** y **dependencia de la gestión** por separado.
- La **subsecretaría** de la que depende cada institución.
- **Documentación con vigencia** y aviso de vencimiento.
- Estados de **inauguración pendiente** y **suspensión** con reactivación.
- **Control de duplicados** al dar de alta y **fusión** de instituciones repetidas.

### De la infraestructura del edificio

- **Estado de tenencia**: propio, alquilado, comodato o donado.
- **Ubicación en mapa**, más allá de la dirección en texto.
- **Cantidad de habitaciones** y plano del edificio.
- **Servicios disponibles**: luz, agua, internet y señal.
- **Vencimiento automático** del relevamiento a los seis meses, o al mes si el dispositivo está en obra, con aviso por correo.
- El botón **«Relevar ya»** para forzar una revisión ante un reclamo puntual.
- **Predios compartidos**: acá cada dispositivo se releva por separado, aunque compartan edificio.
- El **informe oficial** generado y vinculado al legajo del dispositivo.
- La regla de que el agente sea **externo a la institución** que releva.

### Del circuito de las personas

- La **solicitud de ingreso con autorización previa** del programa central, que hoy usan el CIS N.º 3 y el Parador Nocturno. Acá todo ingreso es directo.
- La **detección automática de reingreso**.
- El **ingreso excepcional por encima de la capacidad**, con registro de quién lo autorizó y por qué.
- El **traslado entre dispositivos** con estado *en tránsito* visible en las dos puntas. Un traslado se registra como un egreso acá y un ingreso allá, sin vínculo entre los dos.
- La **estadía ambulatoria**: el seguimiento de personas que no ocupan una plaza, que es como trabaja Abordaje Psicosocial.
- El **préstamo de plaza** entre residentes por doce o veinticuatro horas.
- El **permiso de salida con regreso previsto** y el aviso cuando la persona no vuelve.

### De la capacidad

- **Tipos de plaza** diferenciados: cama, cupo o turno según el dispositivo.
- **Estados de la plaza** y reubicación asistida cuando se saca de servicio una que está ocupada.
- **Disponibilidad neta**.

### De la operación diaria

- El **pase de guardia**: el cierre formal del turno donde el responsable entrega un resumen y el turno siguiente lo recibe, con constancia de quién entregó y quién recibió. El censo sí se calcula solo; lo que no hay es el acto de entrega entre turnos.
- El **versionado de las novedades**. Una corrección modifica el registro; no queda la versión anterior visible al lado de la nueva.
- La **regularización de días anteriores** con marca de carga fuera de término.
- Los **tipos de novedad configurables** por el Ministerio.

### De los formularios

- Los **formularios de la persona por tipo de institución**: no hay ficha socioeconómica ni de salud, solo observaciones en texto.
- El **configurador** que permite al Ministerio armar y cambiar un formulario sin pedir desarrollo.

### De la mirada de red

- **Lista de espera** con prioridad y reserva de plaza.
- **Derivaciones** entre instituciones y a organismos externos, con aceptación, rechazo y vencimiento.
- **Tablero de toda la red** y **reportes exportables**.
- **Importador** del padrón inicial de instituciones, sectores y plazas.

### De los permisos

- **Alcance por subsecretaría**: hoy el permiso se asigna institución por institución.
- **Niveles de sensibilidad** de la información médica, psicosocial y judicial.
- **Separación de funciones**: que quien registra un movimiento no pueda validarlo.

### Lo demás

- **Consumos y contratos**: alquiler, luz, agua e internet con último pago, vencimiento, comprobante, aviso y escalado.
- **Tableros configurables por rol** y recordatorios propios.
- El **programa Merenderos** completo.

---

## 4. Esfuerzo y plazo

El Ministerio organizó el presupuesto en cuatro bloques:

| | Bloque | Horas |
|---|---|---:|
| **1** | Aplicación, sectores y criticidad | 140 |
| **2** | Ingresos y egresos | 220 |
| **3** | Circuito interno | 240 |
| **4** | Reserva | 100 |
| | **Total** | **700** |

**Aproximadamente 14 semanas** con un desarrollador backend y uno frontend a tiempo completo, más el equipo móvil.

**Sobre el orden.** El ingreso y el egreso son la base: el circuito interno se apoya en ellos. El relevamiento en campo es **independiente** y puede ir en paralelo, porque toca otra parte del sistema y suma al equipo móvil. Arrancando por el ingreso y el egreso, **a las seis semanas** el Ministerio ya tiene dispositivos registrando movimientos reales.

!!! note "Sobre la reserva"
    Las 100 horas de reserva absorben ajustes de reglas, diferencias de operación entre dispositivos, retrabajo de interfaz, pruebas adicionales, carga de datos reales y despliegue. Se consumen contra trabajo concreto, acordado en el momento, y **lo que no se usa no se factura**.

    Conviene saber que **una parte está comprometida desde el arranque**: el funcionamiento sin conexión, la verificación en toda la red, la solapa en el legajo ciudadano, la asignación del relevamiento y el censo automático se incorporaron al alcance después de la estimación inicial. El primero es, por lejos, el de mayor peso.

## 5. Definiciones a cerrar antes de arrancar

Cinco definiciones cortas, que conviene resolver en una sola reunión:

1. **La criticidad.** Es un concepto nuevo, no estaba en la propuesta. ¿Qué escala usa —por ejemplo baja, media, alta, crítica—? ¿Quién la asigna, el agente territorial o el coordinador al revisar? ¿Y dispara algo además de avisar, o el sistema solo informa y la decisión queda en el área?

2. **Si el relevamiento es por sector o por edificio.** Este MVP lo plantea **por sector**, que da más detalle y más trabajo de carga. La propuesta lo planteaba **por edificio**, que es lo que permite relevar una sola vez un predio compartido por varias instituciones, como el caso de Resistencia. Hay que elegir uno.

3. **Quién puede ser asignado a un relevamiento.** La propuesta pedía que el agente fuera **externo a la institución** que releva, para que no se omitan irregularidades. El MVP incorpora la asignación, pero no esa restricción: hay que decidir si se aplica.

4. **Los estados del relevamiento.** Cuáles son y quién los mueve: alcanza con *asignado*, *cargado* y *revisado*, o hace falta un circuito de validación con observaciones y corrección.

5. **El catálogo de motivos de egreso.** Qué opciones tiene y si el Ministerio quiere poder modificarlo después sin pedir desarrollo.
