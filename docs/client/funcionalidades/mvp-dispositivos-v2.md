# Programa Dispositivos — MVP de la Versión 2

!!! abstract "En una línea"
    Un primer alcance de **700 horas** que pone en funcionamiento dos cosas: el **relevamiento de los dispositivos desde la aplicación móvil**, con criticidad y evidencia fotográfica, y el **circuito operativo completo de las personas** —quién entra, dónde está, cómo se mueve y cuándo sale—.

| | |
|---|---|
| **Programa** | Dispositivos |
| **Estado** | Alcance definido por el Ministerio · a confirmar fecha de inicio |
| **Esfuerzo** | 700 h · cuatro bloques · aproximadamente 14 semanas |
| **Relación con la Versión 2** | Primer tramo de la [propuesta funcional completa](propuesta-dispositivos-v2.md); no la reemplaza, la ordena en el tiempo |
| **Última actualización** | 2026-10-08 |

---

## 1. Qué es este MVP

La [propuesta funcional de la Versión 2](propuesta-dispositivos-v2.md) describe el programa completo y está estimada en 827 horas repartidas en cinco etapas. Este documento define el **primer recorte que el Ministerio eligió para arrancar**: cuatro bloques de trabajo, 700 horas, con foco en lo que cambia la operación diaria desde el primer día.

El criterio del recorte es poner en marcha **el circuito de las personas y el relevamiento de los edificios**, dejando para una segunda instancia la configuración avanzada, la mirada de red y el programa de Merenderos.

---

## 2. Los cuatro bloques

### Bloque 1 · Aplicación, sectores y criticidad — 140 h

Pone al agente territorial a relevar en campo desde el celular, y a esa información a verse en el backoffice.

- **Vinculación de la aplicación móvil con el módulo Dispositivos**, con sus servicios, su autenticación y las pruebas de integración entre ambos.
- Selección del **dispositivo y del sector relevado**.
- Carga de **criticidad**, observaciones y **evidencia fotográfica** cuando corresponda.
- **Responsable, fecha y estado** de cada relevamiento.
- **Visualización desde el backoffice**: qué se relevó, quién lo relevó y en qué estado quedó.
- **Permisos** y estados básicos del circuito.
- **Alertas y semáforos de criticidad** sobre lo relevado.

> El desarrollo de la pantalla dentro de la aplicación móvil está incluido en este bloque y lo ejecuta el equipo móvil, en paralelo con el trabajo del backoffice.

### Bloque 2 · Ingresos y egresos — 220 h

La primera etapa operativa: que cada dispositivo pueda registrar quién entra, quién sale, cuándo y por qué.

- **Alta o selección de la persona**, sobre el legajo ciudadano que ya existe.
- **Ingreso al dispositivo**, con sus validaciones mínimas.
- **Asignación inicial a sector o plaza**, en los dispositivos donde aplique.
- **Historial de ingresos** de cada persona en el dispositivo.
- **Egreso** con motivo, fecha y destino o derivación.
- **Liberación del cupo** al egresar, para que la disponibilidad quede al día sola.
- **Trazabilidad** de todo el circuito.

### Bloque 3 · Circuito interno — 240 h

La operación puertas adentro, una vez que la persona ya está alojada.

- **Movimientos internos entre sectores**.
- **Permanencia** y cambios de estado de la estadía.
- **Novedades y observaciones**, con registro por turno o por responsable.
- **Seguimiento interno** de cada persona durante su estadía.
- **Alertas por criticidad**.
- **Vista de situación del dispositivo**: cómo está hoy, quién está alojado y dónde.
- **Auditoría básica** de lo actuado.

### Bloque 4 · Reserva — 100 h

No es un módulo: es una **bolsa explícita** para absorber lo que siempre aparece y nunca está en la lista.

- Ajustes de reglas y cambios que pida el Ministerio durante el desarrollo.
- Diferencias de operación entre un dispositivo y otro.
- Integración con la aplicación móvil.
- Retrabajo de interfaz.
- Pruebas adicionales, carga de datos reales y despliegue.

Se consume contra trabajo concreto y lo que no se use no se factura.

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

**Sobre el orden.** Los bloques 2 y 3 son secuenciales: el circuito interno se apoya en los ingresos. El bloque 1 es **independiente** y puede ir en paralelo, porque toca otra parte del sistema y suma al equipo móvil. Si se arranca por el bloque 2, a las seis semanas el Ministerio ya tiene dispositivos registrando ingresos y egresos reales.

---

## 4. Qué no entra en este MVP

Nada de esto se descarta: está definido y estimado en la [propuesta de la Versión 2](propuesta-dispositivos-v2.md) y se retoma en una segunda instancia.

**Del legajo de la institución.** El encuadre jurídico con titularidad del inmueble y dependencia de la gestión, la documentación con vigencia y aviso de vencimiento, los estados de *inauguración pendiente* y *suspensión*, y el control de duplicados al dar de alta.

**De la infraestructura.** El relevamiento del MVP cubre criticidad, observaciones y fotos. Quedan para después el estado de tenencia, la ubicación en mapa, la cantidad de habitaciones y el plano, los servicios disponibles —luz, agua, internet, señal—, el vencimiento automático cada seis meses y el tratamiento de los predios compartidos por varias instituciones.

**Del circuito de las personas.** La autorización previa del programa central antes del ingreso, la verificación de la situación de la persona en toda la red, el traslado entre instituciones con estado *en tránsito*, el préstamo de plaza y los permisos de salida con regreso previsto.

**De la operación diaria.** El pase de guardia entre turnos con constancia de quién entrega y quién recibe, y el censo automático del turno.

**Los formularios configurables por tipo de institución**, que son los que permiten al Ministerio cambiar un formulario sin pedir desarrollo.

**La mirada de red.** La lista de espera con prioridad, las derivaciones entre instituciones y a organismos externos, el tablero de toda la red y los reportes exportables.

**Los permisos avanzados.** El alcance por subsecretaría y los niveles de sensibilidad de la información médica, psicosocial y judicial.

**Consumos y contratos**, y los **tableros configurables por rol**.

**El programa Merenderos** completo.

---

## 5. Qué hay que definir antes de arrancar

Tres definiciones cortas, que conviene cerrar en una sola reunión:

1. **La criticidad.** Es un concepto nuevo, no estaba en la propuesta. ¿Qué escala usa —por ejemplo baja, media, alta, crítica—? ¿Quién la asigna, el agente territorial o el coordinador al revisar? ¿Y dispara algo además de avisar, o el sistema solo informa y la decisión queda en el área?

2. **Si el relevamiento es por sector o por edificio.** Este MVP lo plantea **por sector**, que da más detalle y más trabajo de carga. La propuesta original lo planteaba **por edificio**, que es lo que permite relevar una sola vez un predio compartido por varias instituciones, como el caso de Resistencia. Hay que elegir uno.

3. **Quién releva.** La propuesta establece que el relevamiento lo carga un agente territorial **externo a la institución**, para que no se omitan irregularidades. Conviene confirmar que se mantiene, porque condiciona los permisos del bloque 1.
