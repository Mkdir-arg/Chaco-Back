# Programa Dispositivos — Segunda etapa de la Versión 2

!!! abstract "En una línea"
    Completar lo que el MVP dejó para después: el **circuito completo de la persona** —autorización previa, traslado con seguimiento, seguimiento sin alojamiento, permisos de salida—, la **información sensible** con acceso diferenciado, el **pase de guardia**, la **mirada de red** para la conducción y **todo lo del edificio** que no es el relevamiento en campo.

| | |
|---|---|
| **Programa** | Dispositivos |
| **Estado** | **Propuesta en definición** · alcance y orden de las etapas a confirmar con el Ministerio |
| **Relación con la Versión 2** | Continuación del [MVP](mvp-dispositivos-v2.md) dentro de la [propuesta funcional completa](propuesta-dispositivos-v2.md); no la reemplaza |
| **Esfuerzo** | A confirmar: se cotiza al cerrar el alcance de cada bloque |
| **Merenderos** | **Fuera de esta etapa** |
| **Última actualización** | 2026-11-17 |

!!! warning "Para qué sirve este documento"
    El MVP aclaró qué entraba y qué no. Este documento toma **todo lo que no entró**, descuenta lo que ya se fue incorporando desde entonces y ordena lo que queda en cuatro bloques que se pueden aprobar por separado. Si algo no coincide con lo que el Ministerio tiene en mente, **es el momento de corregirlo**.

---

## 1. De dónde partimos

El [MVP de la Versión 2](mvp-dispositivos-v2.md) puso en funcionamiento el relevamiento edilicio en campo y el circuito básico de las personas: ingreso con verificación en toda la red, asignación de sector y plaza, movimientos, bitácora por turno con censo automático, egreso con liberación del cupo y la trayectoria de cada persona en su legajo ciudadano.

### 1.1 Lo que se sumó después del MVP

Varias funciones que el MVP había dejado para después **ya están incorporadas**, y por eso no forman parte de esta etapa:

| Función | Qué hace hoy el sistema |
|---|---|
| :material-file-document-edit-outline: **Formularios por tipo de institución** | El Ministerio arma desde la configuración, sin pedir desarrollo, el formulario de cada momento. Ya se piden en el alta de la institución, el ingreso, el egreso y el relevamiento edilicio |
| :material-scale-balance: **Encuadre jurídico** | Categoría, área del Ministerio, titularidad del inmueble y dependencia de la gestión, por separado |
| :material-bed-outline: **Tipos de plaza** | Cada tipo de institución define si trabaja con camas, cupos o turnos |
| :material-bookmark-outline: **Reserva y préstamo de plaza** | Se reserva o se presta una plaza libre (12 o 24 horas), con aviso de vencimiento y liberación |
| :material-swap-horizontal: **Reubicación** | Desde una plaza ocupada se cambia a la persona de plaza antes de sacarla de servicio |
| :material-account-group-outline: **Equipo de cada institución** | Las personas que trabajan en cada dispositivo, con su rol, definen quién ve y opera qué |
| :material-restore: **Reactivación** | Una institución inactiva vuelve a estar activa |
| :material-office-building-outline: **Edificios con sus sectores** | Cada sector se ubica en un edificio, y la infraestructura se ve por edificio con su registro fotográfico |

---

## 2. Qué se propone: cuatro bloques

<div class="grid cards" markdown>

-   :material-account-arrow-right-outline: **A · El circuito completo de la persona**

    ---

    Autorización previa, ingreso excepcional, seguimiento ambulatorio, permiso de salida y traslado con seguimiento.

-   :material-shield-lock-outline: **B · La ficha, la información sensible y el turno**

    ---

    Ficha que acompaña toda la estadía, acceso diferenciado a salud, psicosocial y judicial, y pase de guardia.

-   :material-map-marker-radius-outline: **C · La red y la conducción**

    ---

    Lista de espera, derivaciones, tablero de la red, avisos por correo, alcance por subsecretaría y reportes.

-   :material-home-city-outline: **D · La institución y el edificio**

    ---

    Documentación con vigencia, estados de la institución, datos del edificio, vencimiento del relevamiento y consumos y contratos.

</div>

!!! tip "Cómo leer los bloques"
    Cada bloque se entrega y se usa por sí mismo. **El A es el que más cambia la operación diaria**: resuelve los pedidos que más se repitieron en las visitas —la autorización previa del CIS N.º 3 y el Parador, el traslado con seguimiento y el trabajo de Abordaje Psicosocial con personas que no están alojadas—.

---

## 3. Cómo funciona cada bloque

### 3.1 Bloque A — El circuito completo de la persona

**Solicitud de ingreso con autorización previa.** Para los tipos de institución que lo exijan —como el CIS N.º 3 y el Parador—, el ingreso deja de ser directo. El operador busca a la persona como hoy, con la verificación en toda la red, y genera una **solicitud**. El programa central la **autoriza** con una vigencia y, si corresponde, con la plaza reservada; la **rechaza** con motivo, o la **devuelve** pidiendo datos. Con la autorización vigente se completa el ingreso; si vence sin usarse, la plaza se libera sola.

**Ingreso excepcional.** Cuando no hay plaza libre, el sistema permite igual el ingreso, con el **motivo** y **quién lo autorizó** registrados. El censo lo cuenta. El sistema avisa, no bloquea.

**Seguimiento ambulatorio.** Una estadía sin plaza, para personas que no están alojadas —la forma de trabajo de Abordaje Psicosocial—. **Puede convivir** con una estadía residencial en otra institución, y tiene su propia línea de tiempo de intervenciones.

**Permiso de salida.** Se registra con regreso previsto. La persona conserva su plaza y figura en el censo como «con permiso». Si no vuelve a la hora prevista, el sistema avisa.

**Traslado con seguimiento.** El traslado deja de ser un egreso acá y un ingreso allá. La estadía queda **en tránsito**, visible en las dos instituciones, con la plaza de origen reservada. El destino la **recibe** o la **rechaza** con motivo; si la rechaza, la persona vuelve a su plaza de origen. Si se vence el plazo, hay aviso en las dos puntas. La persona nunca figura alojada en dos lugares.

**Reingreso a la vista.** Al ingresar a alguien, el asistente avisa si la persona ya pasó antes por la red.

**Avisos de la estadía.** Límite de permanencia por tipo de institución, permiso de salida vencido, traslado sin resolver, autorización por vencer y ficha incompleta.

### 3.2 Bloque B — La ficha, la información sensible y el turno

**La ficha de la estadía.** Los formularios del tipo de institución dejan de completarse una sola vez: el detalle de la estadía suma una **ficha** con sus secciones, el **avance** de cada una y qué equipo la completa. Se piden también los formularios de asignación de plaza, novedades del turno y traslado, y los propios que arme el Ministerio. La ficha se puede imprimir y exportar.

**Acceso diferenciado a la información sensible.** Cada sección declara su nivel: general, social, salud, psicosocial o judicial. El nivel se asigna al rol como cualquier otro permiso.

- **Sin el nivel**, la sección no desaparece: se ve que existe, cuánto está completa y qué equipo la completa, sin su contenido.
- **Con el nivel**, al abrirla el sistema avisa que la información es sensible y pide confirmación. **Cada apertura queda registrada** con usuario, sección, persona, fecha y hora.
- Dentro de una sección sensible, el contenido lleva **marca de agua** con el usuario y la hora, y no se exporta sin el nivel.

!!! note "Sobre las capturas de pantalla"
    Como se aclaró en la propuesta, una captura de pantalla no se puede impedir en ningún sistema web. Lo que protege de verdad es lo que se implementa acá: el permiso por nivel, el aviso de lectura registrado, la marca de agua y el bloqueo de exportación.

**Separación de funciones.** Quien registra no valida: quien carga un legajo no lo valida, quien registra un relevamiento no lo revisa y quien carga un ingreso excepcional no es quien lo autoriza. Lo rechaza el sistema.

**Pase de guardia.** Al cerrar el turno, el responsable ve el censo calculado y lo que queda pendiente —personas con permiso de salida, traslados en tránsito, avisos abiertos—, suma lo que deja para seguimiento y confirma. El turno siguiente lo ve como primera cosa y confirma la recepción. Queda constancia de quién entregó y quién recibió.

**Regularización de días anteriores.** Se pueden cargar novedades de turnos ya cerrados dentro de una ventana de días configurable. Quedan marcadas como **cargadas fuera de término**.

**Catálogos administrables.** Los tipos de novedad de la bitácora y los motivos de egreso se administran desde la configuración del programa.

### 3.3 Bloque C — La red y la conducción

**Lista de espera.** Por institución, con posición, **prioridad** por criterios configurables —medida judicial, edad, riesgo—, origen y plaza reservada opcional. Cuando se libera una plaza, el sistema **sugiere** a quién le toca, pero no promueve solo: la decisión es de una persona.

**Derivaciones.** Entre instituciones de la red y a organismos externos. Quien deriva registra destino, motivo y urgencia; el destino acepta, rechaza con motivo o deja vencer. Todo queda en la trayectoria de la persona.

**Plazas disponibles en la red.** Una vista de dónde hay lugar, por tipo, sector y localidad, para decidir la derivación.

**Tablero de la red.** Capacidad por tipo y localidad, ocupación, disponibilidad, ingresos y egresos del período, permanencia promedio y avisos abiertos, con filtros por subsecretaría, tipo, localidad y período. Exportable.

**Avisos por correo.** Además de verse en pantalla, los avisos que el Ministerio elija se envían por **correo** a quien corresponda, con escalado cuando no se atienden.

**Alcance por subsecretaría.** Un rol con este alcance ve todas las instituciones de su subsecretaría, sin que nadie tenga que sumarlo al equipo de cada una.

**Reportes exportables** en CSV y Excel: ocupación por institución y sector, movimientos del período, censo diario, bitácora, lista de espera, derivaciones y auditoría. Cada uno sale acotado al alcance y al nivel de sensibilidad de quien lo pide, y queda registrado quién exportó qué.

**Carga inicial completa.** El importador del padrón suma edificios, sectores, plazas y, si se quiere, las personas alojadas hoy, marcadas como «sin verificar» hasta que el equipo territorial las confirme.

### 3.4 Bloque D — La institución y el edificio

**Documentación con vigencia.** Cada institución guarda sus documentos con fecha de vigencia y aviso antes del vencimiento.

**Estados de la institución.** Se suman **inauguración pendiente** —lista pero todavía sin abrir— y **suspendida** —no admite ingresos nuevos y conserva a quienes ya están alojados—, con vuelta a activa. Cerrar una institución con personas alojadas se resuelve con un asistente que las egresa o traslada en bloque.

**Instituciones duplicadas.** Dos legajos repetidos se **fusionan** en uno, conservando todo su historial.

**Servicios que brinda** cada institución, como parte de su legajo.

**Los datos del edificio.** Tenencia —propio, alquilado, comodato, donado o mixto—, cantidad de habitaciones, plano como adjunto, servicios disponibles —luz, agua de red o fuente alternativa, internet y señal móvil— y si está **en obra**. Los carga el agente territorial en el relevamiento.

**Vencimiento del relevamiento.** Un edificio vence a los **6 meses** del último relevamiento, o al **mes** si está en obra, con aviso en pantalla y por correo. El botón **«Relevar ya»** fuerza una revisión inmediata ante un reclamo puntual.

**Informe oficial.** Al revisar un relevamiento, el sistema genera un informe oficial con su número, que queda archivado en la documentación de cada institución del edificio.

**Consumos y contratos.** Una solapa en el detalle de la institución con alquiler, luz, agua e internet: último pago, vencimiento y comprobante. Aviso **siete días antes** del vencimiento y escalado a la autoridad superior si vence sin pago registrado.

**Tableros por rol y recordatorios.** Cada administrador y director arma su vista con los indicadores que necesita, acotada a su alcance, y registra recordatorios propios por institución. El agente territorial no accede a esta sección.

---

## 4. Qué no incluye esta etapa

- El **programa Merenderos**.
- Lo que la [propuesta de la Versión 2](propuesta-dispositivos-v2.md#7-lo-que-queda-fuera-de-esta-version) ya dejaba fuera de toda la versión: inventario y stock, administración de medicación, historial clínico, asistencia del personal, control de acceso físico, vista interactiva de habitaciones, apps para cocina, lavadero y mantenimiento, y la Línea 102 como circuito propio.
- El **mapa embebido** en la pantalla: la ubicación se muestra con coordenadas y un enlace que abre el mapa aparte.
- Impedir capturas de pantalla, que técnicamente no es posible.

---

## 5. Definiciones a confirmar con el Ministerio

Para cerrar el alcance de cada bloque hacen falta estas definiciones. Mientras no estén, se trabaja con los criterios por defecto de la propuesta.

| | Definición | Bloque |
|---|---|---|
| 1 | Qué bloques se aprueban y en qué orden | Todos |
| 2 | Qué tipos de institución exigen autorización previa, quién la otorga y por cuánto tiempo vale | A |
| 3 | Quién autoriza un ingreso por encima de la capacidad, y hasta qué límite | A |
| 4 | Si una persona puede tener seguimientos ambulatorios en más de una institución a la vez | A |
| 5 | Si una plaza prestada cuenta como disponible | A |
| 6 | Qué roles ven cada nivel de información sensible y qué secciones de cada formulario corresponden a cada nivel | B |
| 7 | Qué novedades son obligatorias en el pase de guardia y cuántos días se aceptan para regularizar | B |
| 8 | Si las derivaciones a organismos externos —hospital, juzgado— llevan seguimiento o se registran como destino del egreso | C |
| 9 | Qué avisos se envían por correo y a quién | C |
| 10 | Si el informe oficial del relevamiento lleva firma | D |
| 11 | Fortalecimiento Familiar: si trabaja con cupos, con turnos o sin plazas | A |
| 12 | Albergues y contención nocturna: si son un tipo de institución propio o una variante de Abordaje Psicosocial | A |
| 13 | La escala de criticidad, los estados del relevamiento y el catálogo de motivos de egreso | B · D |
| 14 | El organigrama oficial del Ministerio, para el alcance por subsecretaría y los tableros por rol | C · D |

---

## 6. Documentos relacionados

- [Propuesta funcional de la Versión 2](propuesta-dispositivos-v2.md)
- [MVP de la Versión 2](mvp-dispositivos-v2.md)
- [Estimación de esfuerzo del programa](estimacion-programa-dispositivos.md)
