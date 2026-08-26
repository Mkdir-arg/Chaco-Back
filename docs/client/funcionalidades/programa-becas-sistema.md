---
hide:
  - navigation
---

# :material-school-outline: Programa Becas — el sistema construido

!!! abstract "Qué es este documento"
    La descripción detallada de **cómo funciona hoy el Programa Becas en DATAÑACH**: su estructura, quién hace qué, cómo entra una inscripción, cómo se resuelve y qué reglas aplica el sistema en cada paso.

    Es la **evolución de la [propuesta funcional de junio](programa-becas.md)**, que se conserva como registro de lo que se planteó al inicio de la Versión 001. Aquel documento describía lo que se iba a construir; éste describe lo que se construyó.

**Versión:** 001 · **Actualizado:** 26/08/2026 · **Módulo:** Programas

---

## :material-swap-horizontal: Qué cambió respecto de la propuesta original

La propuesta de junio se escribió antes de construir. En el desarrollo, varias definiciones cambiaron por decisiones acordadas con el programa. Las principales:

| Tema | Propuesta de junio | Sistema construido |
|---|---|---|
| Estructura | Programa → Convocatoria → Segmento | **Programa (SIIS) → Segmento → Subsegmento**, con la Convocatoria colgando del Segmento |
| Nivel superior | «Becas» como marco genérico | Un **programa real del catálogo de SIIS**, elegido de la lista que publica ECOM |
| Roles | Tres (Administrador, Coordinador, Territorial) | **Cinco**, con alcance por segmento y por subsegmento |
| Requisitos | Tres niveles | **Cuatro niveles**: generales, de programa, de segmento y de subsegmento |
| Relevamiento | De un solo día | **Período de fechas**, con día y hora de inicio y de fin |
| Cupo | Solo por segmento | Dos cupos distintos: **becas por segmento** y **personas cargables por relevamiento** |
| Canales de inscripción | Solo la app de campo | **Dos**: app de campo y **formulario público por link** |
| Zona del relevamiento | Texto libre | **Catálogo de municipios y localidades** |

Además se incorporaron funcionalidades que la propuesta no contemplaba: **pausas operativas** en toda la cadena, **cierre automático por vencimiento**, **control de vigencia del programa contra SIIS**, **padrón de habilitados** y **resolución de cargas duplicadas**.

---

## :material-file-tree: Cómo se organiza el programa

La información se ordena en cinco niveles. Cada uno cuelga del anterior.

```
Programa (del catálogo de SIIS)
└── Segmento
    └── Subsegmento (opcional)
        └── Convocatoria
            └── Relevamiento
```

### Programa

Es el nivel superior y **el único que se vincula con SIIS**. No se crea a mano: se elige de la lista de programas que publica ECOM. Al vincularlo, el sistema toma su nombre y guarda una copia de su detalle —descripción, jurisdicción, controles de elegibilidad y edad mínima— que queda congelada como referencia.

Un mismo programa de SIIS puede vincularse **una sola vez**.

Si SIIS informa que el programa dejó de estar vigente, o el programa desaparece de su catálogo, **toda su rama queda bloqueada**: sus segmentos, subsegmentos, convocatorias y relevamientos dejan de operar. El bloqueo es automático y se levanta solo cuando SIIS vuelve a informarlo activo.

### Segmento

Es la unidad de gestión del programa. Su nombre lo define el operador y debe ser único dentro del programa. Ahí se define:

- El **cupo de becas** disponible
- Si el formulario **pide ubicación GPS**
- El **coordinador** a cargo
- Los **territoriales** asignados

### Subsegmento

Es opcional y sirve para dividir un segmento. Tiene:

- **Cupo propio**, que debe caber dentro del cupo del segmento. Si un segmento tiene 100 becas y ya distribuyó 80 entre sus subsegmentos, un subsegmento nuevo no puede pedir más de 20.
- **Un referente** —un Coordinador Regional— que define su alcance de trabajo. Es uno solo: asignar otro reemplaza al anterior. Una misma persona puede tener varios subsegmentos a cargo, incluso de segmentos distintos.

Un subsegmento que ya está en uso por una convocatoria no se puede eliminar.

### Convocatoria

Es el llamado concreto. Pertenece a un segmento y opcionalmente a un subsegmento de ese mismo segmento. Define el **período** —fecha de inicio y de fin— dentro del cual tienen que caer todos sus relevamientos.

Cuando quien la crea es un **Coordinador Regional**, el subsegmento es obligatorio: una convocatoria a nivel segmento quedaría fuera de su alcance y no la vería en su propio listado.

**La fecha manda.** Una convocatoria cuya fecha de fin ya pasó no puede quedar activa. Para reactivarla hay que extender la fecha; no alcanza con volver a marcarla como activa.

### Relevamiento

Es la unidad operativa de captura. Cuelga de una convocatoria, de la que hereda el segmento y el subsegmento.

- Su **nombre y número se generan solos** —«Relevamiento 001 · Nombre de la convocatoria»— y la numeración es independiente en cada convocatoria.
- Tiene un **período propio** —día y hora desde, día y hora hasta— que debe caer dentro del período de la convocatoria.
- Tiene un **cupo de personas cargables**, por defecto 100.

Un relevamiento no se edita ni se elimina como tal. Lo que sí se puede hacer es:

- **Reasignar** el territorial a cargo
- **Reprogramar** las fechas, siempre dentro del período de la convocatoria
- **Modificar el cupo**, nunca por debajo de las personas ya cargadas
- **Reemplazar el padrón**, en los públicos

Reasignar, reprogramar, finalizar y reabrir quedan bloqueados mientras el relevamiento esté pausado.

**El territorial asignado debe pertenecer al segmento de la convocatoria.** Si ya tiene otro relevamiento asignado en fechas que se superponen, el sistema **avisa pero no bloquea**: el operador puede confirmar el solapamiento y conservarlo, porque hay casos donde es legítimo.

---

## :material-account-group-outline: Quién hace qué

Hay cinco perfiles. Lo que cada uno puede hacer se define por **capacidades**, y sobre eso se aplica un **alcance** que limita a qué segmentos o subsegmentos llega.

### Administrador del programa

Alcance completo sobre Becas. Es el único que puede:

- **Pausar y reanudar** cualquier nivel de la cadena
- **Revalidar la identidad** de una persona y corregir su género
- Configurar los **requisitos del programa**
- Exportar la información de las convocatorias

### Coordinador del segmento

Gestiona los segmentos que tiene asignados: crea convocatorias y relevamientos, **revisa formularios y resuelve casos**, y administra los territoriales de sus segmentos.

No configura el segmento ni sus requisitos, y no puede pausar.

### Coordinador Regional

Opera **únicamente los subsegmentos que tiene a cargo**. Crea convocatorias y relevamientos dentro de ellos y consulta el cupo.

No accede a la revisión de formularios: crea los relevamientos, pero no resuelve los casos que salen de ellos. Tampoco puede abrir el subsegmento de otro coordinador del mismo segmento.

### Referente

Asiste a un Coordinador y **hereda su alcance**. Administra los territoriales de esos segmentos y consulta convocatorias, relevamientos, revisión y cupo, todo en **solo lectura**. No crea ni resuelve.

### Territorial

Es el perfil de campo. Trabaja **exclusivamente desde la app** y **no puede ingresar al backoffice**: el sistema rechaza su acceso al sitio web.

Solo ve los relevamientos que tiene asignados.

**El alcance se asigna, no se hereda del rol.** Un Coordinador recibe sus segmentos por asignación explícita; un Coordinador Regional, por ser referente de un subsegmento; un Referente, del Coordinador al que asiste; un Territorial, del segmento que se le carga en su usuario. Esas asignaciones se administran desde la configuración del segmento y desde el alta de usuarios.

!!! info "Sobre el alcance"
    Un Coordinador sin segmentos asignados no accede a nada. El alcance no es una preferencia de pantalla: se aplica en la consulta, así que lo que está fuera de alcance no aparece en los listados y tampoco se puede abrir escribiendo la dirección a mano.

---

## :material-clipboard-list-outline: Qué se le pregunta a la persona

El formulario que completa el ciudadano se arma con **cuatro niveles de campos**, que se combinan en una sola lista:

| Nivel | Alcance |
|---|---|
| **Generales** | Transversales a todo el sistema. Son los «requisitos generales» y el cuestionario social. |
| **Del programa** | Los heredan todos los segmentos de ese programa. |
| **Del segmento** | Aplican a todas las convocatorias del segmento. |
| **Del subsegmento** | Solo a las convocatorias de ese subsegmento. |

Cada campo tiene un **tipo** —texto, número, selector, selección múltiple, fecha o archivo—, puede ser obligatorio u opcional, y tiene un **orden** dentro de su lista. El orden se autonumera si se deja vacío y no puede repetirse dentro de la misma lista.

Los **adjuntos** —foto del DNI, certificado de domicilio, constancia de estudios y demás— se modelan como campos de tipo archivo. No son una lista fija del sistema: cada programa configura los que necesita.

Una pregunta general marcada como inactiva desaparece del formulario sin borrarse.

---

## :material-account-plus-outline: Cómo se inscribe una persona

Hay **dos canales**. Los dos terminan en el mismo tipo de registro, y una vez cargados el backoffice no los distingue.

### Canal 1 — App de campo

El territorial trabaja desde la aplicación, con su usuario y contraseña.

1. **Ve solo sus relevamientos vigentes.** Los públicos no le aparecen.
2. **Inicia el relevamiento**, siempre que esté dentro del período y no haya ninguna pausa activa.
3. **Carga a cada persona.** Puede escanear el DNI o consultar la base de personas para precargar los datos, o cargarlos a mano.
4. **Adjunta los archivos** que pidan los requisitos.
5. **Finaliza el relevamiento** cuando terminó de sincronizar.

Funciona **sin conexión**: el dispositivo guarda las cargas y las sincroniza después. Si una sincronización se reintenta, el sistema reconoce la carga y **no la duplica**.

Para tolerar dispositivos con la hora corrida, se aceptan cargas fechadas **hasta cinco minutos en el futuro** respecto del servidor.

Cuando el mismo documento se carga **dos veces en el mismo relevamiento**, la app no bloquea: crea el registro y lo marca como carga duplicada para que una persona lo resuelva en la revisión.

Al llegar al cupo de personas del relevamiento, la carga se rechaza.

### Canal 2 — Formulario público por link

Pensado para que un público objetivo se inscriba solo. Se genera un link con una dirección **no adivinable** que se distribuye por el canal que el programa elija.

**Paso 1 — Identificación.** La persona ingresa su documento y sexo, y resuelve una verificación anti-robots. El sistema controla, en orden:

- Que no haya demasiados intentos desde la misma conexión ni sobre el mismo documento
- Que el documento esté en el **padrón de habilitados**, si el relevamiento tiene uno cargado
- Que esa persona **no se haya inscripto ya** en esa convocatoria
- Los datos de identidad contra la base de personas provincial

**Paso 2 — Formulario.** Si la identidad se validó, los datos personales aparecen precargados y en solo lectura; si no, se completan a mano. Debajo van los datos de contacto, las preguntas y requisitos de la convocatoria, los adjuntos y —si corresponde— el apoderado. La ubicación se toma del navegador si la persona la autoriza.

**Paso 3 — Comprobante.** Se muestra el número de formulario y, si el relevamiento tiene activado el aviso por correo, se informa que el comprobante fue enviado.

!!! info "Reglas propias del formulario público"
    - **Sin padrón cargado, el link queda abierto**: cualquiera que lo reciba puede inscribirse y ocupar cupo.
    - **Si la identidad no se puede validar, se deja pasar igual**, con la carga marcada como no validada. La revisión humana es la que decide después.
    - **Una sola pantalla** cubre los casos de relevamiento vencido, pausado, con cupo lleno o cerrado, sin decir cuál de los cuatro es.
    - **La identificación caduca a los 45 minutos**, para que en una computadora compartida no quede disponible el documento de la persona anterior.
    - **Los mensajes de rechazo son idénticos** entre sí, para que nadie pueda reconstruir el padrón ni averiguar quién ya está inscripto probando documentos.

### Reglas comunes a los dos canales

- **El apoderado es obligatorio para menores de edad.** Si la persona es menor, se piden nombre, apellido, documento, género y fecha de nacimiento del apoderado.
- **Teléfono y correo electrónico son obligatorios** en ambos canales.
- Toda inscripción **crea o vincula el legajo ciudadano** en el mismo acto.
- Toda inscripción nace en estado **Enviado**.
- Los **archivos adjuntos** que se suben desde el formulario público admiten **JPG, PNG y PDF, hasta 5 MB** cada uno.

---

## :material-clipboard-check-outline: Cómo se revisa y se resuelve un caso

La bandeja de revisión es donde el Administrador o el Coordinador procesan, uno por uno, los formularios que llegaron.

### Lo que se puede hacer sobre un caso

| Acción | Quién |
|---|---|
| Ver el caso completo | Administrador, Coordinador, Referente |
| Corregir datos de contacto y apoderado | Administrador, Coordinador |
| Consultar SIIS | Administrador, Coordinador |
| Aprobar o rechazar | Administrador, Coordinador |
| Resolver una carga duplicada | Administrador, Coordinador |
| Revalidar identidad y corregir género | **Solo Administrador** |

**Todo queda auditado.** Cada corrección y cada decisión genera un registro permanente con el campo afectado, qué decía antes, qué dice ahora, quién lo hizo y cuándo. Ese historial no se puede modificar ni borrar.

Además de la bandeja por relevamiento, el Administrador tiene una **bandeja de identidades pendientes** que reúne los casos cuya identidad todavía no fue validada, para revalidarlos en conjunto sin recorrer relevamiento por relevamiento.

Durante la revisión se corrigen los **datos de contacto y del apoderado**. Las respuestas a las preguntas y requisitos se ven, pero no se editan.

### La consulta a SIIS

Antes de resolver, el sistema consulta a SIIS si la persona es compatible con el programa. La consulta se dispara al aprobar, al rechazar y con un botón de reintento manual, y **siempre queda registrada** —incluidos los errores técnicos y los tiempos de espera agotados—.

- **Para aprobar**, la última consulta tiene que haber dado compatible **para ese mismo documento y ese mismo programa**. No alcanza con que alguna vez lo haya sido.
- **Para rechazar**, la consulta se registra pero no bloquea: un error técnico queda visible para reintentar, pero no impide dejar asentada la decisión.

### Aprobar

Aprobar tiene **dos desenlaces**, según haya cupo:

- **Con cupo disponible**, el caso queda **Aprobado** y consume una beca del segmento.
- **Sin cupo**, la persona entra en **lista de espera**. El caso no queda aprobado.

En los dos casos, **si el relevamiento tiene los avisos encendidos, la persona recibe un correo** que dice exactamente qué pasó: aprobada, o en lista de espera. Son mensajes distintos justamente porque son desenlaces distintos.

Además de la compatibilidad con SIIS, aprobar exige que la identidad esté validada, que el legajo tenga documento y que el segmento tenga su programa configurado.

### Rechazar

Rechazar **exige un motivo escrito**. El caso pasa a **Rechazado** y el motivo queda registrado. Si los avisos están encendidos, **la persona recibe un correo con ese motivo, tal como lo escribió el técnico**.

Un caso ya resuelto no se puede volver a rechazar: la acción solo está disponible mientras esté pendiente.

### Cargas duplicadas

Cuando el mismo documento se cargó dos veces en el mismo relevamiento, el caso queda marcado y **no se puede aprobar ni rechazar hasta resolverlo**. La resolución es una decisión entre dos:

- **Conservar la carga previa** — se rechaza la nueva
- **Conservar la carga actual** — se rechaza la previa, siempre que ésta no haya sido resuelta ya

La decisión no tiene vuelta atrás.

### Cierre del relevamiento

Un relevamiento pasa a **En revisión** para trabajar su bandeja, y a **Terminado** cuando **no queda ningún formulario sin resolver**. Si quedan pendientes, el sistema informa cuántos y no deja cerrarlo.

---

## :material-counter: Cupos y lista de espera

Hay **dos cupos distintos** que no se relacionan entre sí:

| Cupo | Qué limita | Dónde se define |
|---|---|---|
| **Cupo de becas** | Cuántas personas pueden quedar aprobadas | En el segmento |
| **Cupo de personas** | Cuántas personas se pueden cargar | En cada relevamiento |

El cupo de personas del relevamiento se ocupa con **toda** carga, sin importar si después se aprueba o se rechaza. Puede aumentarse, pero nunca reducirse por debajo de las ya cargadas.

El cupo de becas del segmento se ocupa **solo con las aprobaciones**, y se calcula en el momento. Dos aprobaciones simultáneas no pueden superar el cupo: el sistema las ordena.

### Lista de espera

Cuando se aprueba sin cupo, la persona entra a la lista de espera del segmento con una posición.

- **La promoción es manual.** Dar de baja a un beneficiario libera el cupo, pero no promueve a nadie automáticamente: el sistema avisa que hay lugar y el operador elige a quién. **Al promover, la persona recibe el correo de aprobación.**
- El operador también puede **agregar a alguien a la lista a mano**, y en ese caso recibe el mismo aviso que si hubiera llegado por falta de cupo.
- **Al promover se vuelve a controlar todo**, incluida la compatibilidad con SIIS. Si en el ínterin SIIS pasó a informar incompatible, la promoción se bloquea.

### Baja de un beneficiario

Un beneficiario aprobado puede darse de baja, lo que libera su cupo. La baja no tiene reversa directa: para reincorporarlo hace falta una inscripción nueva.

---

## :material-pause-octagon-outline: Pausas y vencimientos

### Pausas operativas

Cinco niveles se pueden pausar a mano: **programa, segmento, subsegmento, convocatoria y relevamiento**. Cada pausa y cada reanudación **exige un motivo** y queda registrada de forma permanente con el elemento afectado, la acción, el motivo, quién la hizo y cuándo.

**La pausa se hereda hacia abajo.** Un relevamiento queda bloqueado si está pausado él mismo, o su convocatoria, o su segmento, o su subsegmento, o su programa.

Con el relevamiento pausado, **el trabajo de campo se corta completo**: no se puede iniciar, cargar personas, adjuntar archivos, finalizar ni reabrir. La app informa «Pausado» con el motivo y reintenta después. Nada se borra: los formularios ya cargados y el estado del relevamiento quedan como estaban.

El link público también se cierra mientras dure la pausa.

Solo el Administrador del programa pausa y reanuda.

### Cierre automático por vencimiento

Todos los días, el sistema revisa las fechas:

- Una **convocatoria activa cuya fecha de fin ya pasó se cierra sola**, y queda marcado que el cierre fue automático.
- Un **relevamiento abierto pasa a En revisión** si venció su convocatoria o si pasó su propia fecha de fin.

El corte es por día completo: una convocatoria que termina el 31 de julio **sigue vigente todo el 31** y vence el 1 de agosto.

Un relevamiento cerrado por vencimiento no se reabre: su trabajo continúa en la bandeja de revisión.

---

## :material-email-outline: Correos al ciudadano y a los operadores

### Al ciudadano

| Correo | Cuándo |
|---|---|
| **Comprobante de inscripción** | Al inscribirse por el formulario público |
| **Tu inscripción fue aprobada** | Cuando el técnico aprueba el caso y hay cupo |
| **Tu inscripción quedó en lista de espera** | Cuando se aprueba sin cupo disponible, o cuando el operador la agrega a la lista |
| **Novedades sobre tu inscripción** | Cuando el caso se rechaza. Incluye el motivo que escribió el técnico |
| **Tu inscripción fue aprobada** | Cuando se la promueve desde la lista de espera |

### A los operadores

| Correo | Cuándo |
|---|---|
| **Credenciales de acceso** | Al dar de alta un usuario del backoffice |
| **Recuperación de contraseña** | Cuando el usuario la solicita desde el ingreso |

### Cómo se controlan

Los avisos al ciudadano son **opcionales por relevamiento**: un mismo interruptor decide si ese relevamiento notifica o no, y vale tanto para los públicos como para los territoriales. Viene **apagado** por defecto, así que hay que encenderlo relevamiento por relevamiento.

**El correo nunca interrumpe nada.** Si no puede enviarse, la inscripción se completa igual y la persona ve su comprobante en pantalla; y del lado del técnico, la aprobación o el rechazo quedan firmes aunque el aviso falle.

**Hay un caso en que no se avisa, deliberadamente:** cuando se resuelve una carga duplicada. Las dos cargas son de la misma persona, así que descartar la repetida es limpieza de datos y no la resolución de su inscripción — la carga que queda avisa cuando se resuelva de verdad. Tampoco avisa la baja de un beneficiario, que está pendiente de definición.

La clave que se envía al dar de alta un usuario es **provisoria**: el primer ingreso obliga a cambiarla. El link de recuperación de contraseña vale **24 horas**.

!!! warning "Los correos todavía no salen"
    El servidor de correo institucional está configurado pero **su funcionamiento nunca pudo verificarse**: el puerto no responde desde fuera de la red de la provincia. Hasta que se confirme, **ningún correo llega a destino**: ni comprobantes, ni avisos de resolución, ni credenciales de acceso. Conviene dejar los avisos apagados hasta entonces. Ver *Dependencias de ECOM*.

---

## :material-connection: Integraciones

### SIIS — compatibilidad y catálogo de programas

Dos usos distintos:

- **El catálogo de programas** puebla el selector al vincular un programa nuevo.
- **La consulta de compatibilidad** verifica, antes de aprobar, que la persona sea apta para el programa.

Además, un proceso diario revisa si los programas ya vinculados siguen vigentes, y bloquea la rama de los que dejaron de estarlo.

### Base de Personas provincial

Es la fuente que **precarga los datos de identidad**: la usa el paso 1 del formulario público y la revalidación de identidad del backoffice.

De la respuesta se toman **solo nombre, apellido y fecha de nacimiento**. El domicilio nunca se consulta ni se guarda, aunque la fuente lo devuelva: el paso 1 es una pantalla pública y se acotó deliberadamente qué información puede revelar.

Si la base no responde o el documento no figura, **la inscripción continúa igual** con los datos cargados a mano y marcada como no validada.

---

## :material-alert-circle-outline: Dependencias de ECOM

Tres piezas están construidas y probadas de nuestro lado, pero **dependen de ECOM para funcionar**. Mientras falten, el sistema no se rompe: sigue operando y deja constancia de que no pudo validar o enviar.

| Dependencia | Situación | Qué queda sin funcionar |
|---|---|---|
| **Programas en el catálogo de SIIS** | El servicio responde correctamente pero **publica cero programas** para el cliente de prueba. Los cuatro programas solicitados por el Ministerio no fueron incorporados. | No se puede vincular ningún programa, y sin programa no se puede aprobar ninguna beca. |
| **Credenciales de la Base de Personas** | Sin cargar en los ambientes de prueba. | El paso 1 del formulario público nunca precarga datos: toda inscripción queda como carga manual. |
| **Servidor de correo** | Credenciales cargadas; el envío real **nunca pudo verificarse** porque el puerto no responde desde la red de desarrollo. | No sale ningún correo: ni comprobantes, ni credenciales de acceso, ni recuperación de contraseña. |

Ninguna de las tres requiere desarrollo adicional. Se resuelven con configuración del ambiente o con una definición de ECOM.

---

## :material-chart-box-outline: Reportes y exportaciones

El programa cuenta con cinco reportes. Todos respetan el alcance de quien los consulta: cada uno ve únicamente los segmentos y convocatorias que tiene a cargo.

| Reporte | Qué muestra |
|---|---|
| **Cupos** | Por segmento: cupo total, cuánto se distribuyó entre sus subsegmentos, cuánto está ocupado y cuánto queda disponible. |
| **Avance** | Por convocatoria: cuántos relevamientos hay en cada estado —asignados, en curso, finalizados, en revisión, terminados—. |
| **Producción** | Rendimiento del trabajo de campo: cuánto cargó cada territorial y cada relevamiento, con filtros por segmento, territorial y período. |
| **Embudo** | El recorrido de los casos: cuántos se cargaron, cuántos se aprobaron, cuántos se rechazaron y cuántos quedan pendientes, con el resultado de la última consulta a SIIS. |
| **Beneficiarios** | El padrón de aprobados, con filtros por segmento, convocatoria y período. |

Todos admiten filtrar por **rango de fechas** y se pueden **exportar**.

Desde cada convocatoria, el Administrador puede además exportar tres listados puntuales: **beneficiarios**, **lista de espera** y **relevamientos**.

---

## :material-card-account-details-outline: Qué ve el ciudadano en su legajo

Cada persona tiene un legajo único en el sistema, y ahí una **solapa de Becas** que reúne su historia en el programa: en qué convocatorias se inscribió, en qué estado quedó cada caso y su posición si está en lista de espera.

El legajo se crea o se vincula automáticamente en el momento de la inscripción, por cualquiera de los dos canales. Una misma persona que se inscribe en convocatorias distintas tiene **un solo legajo** con todos sus casos.

---

## :material-state-machine: Estados de referencia

### Estados del relevamiento

| Estado | Qué significa |
|---|---|
| **Asignado** | Creado y a la espera de que el territorial lo inicie |
| **En curso** | Operativo: se pueden cargar personas |
| **Finalizando** | El dispositivo está sincronizando lo que cargó |
| **Finalizado** | El territorial terminó su trabajo de campo |
| **En revisión** | Su bandeja de casos se está procesando |
| **Terminado** | Todos sus casos fueron resueltos |

Los relevamientos públicos **nacen En curso**, porque no hay operador que los inicie, y se cierran solos al vencer.

### Estados del caso

| Estado | Qué significa |
|---|---|
| **Enviado** | Cargado y pendiente de resolución |
| **Aprobado** | Beneficiario: ocupa una beca del segmento |
| **Rechazado** | Resuelto negativamente, con motivo registrado |
| **Baja** | Fue beneficiario y se lo dio de baja; su cupo quedó liberado |

Estar **en lista de espera** no es un estado del caso: el caso sigue Enviado y tiene además una posición en la lista de su segmento.

Lo que el ciudadano ve en su legajo se resuelve con esta prioridad: **Beneficiario → En lista de espera → Rechazado → Baja → Pendiente**.

---

## :material-file-document-outline: Documentos relacionados

- [Propuesta funcional original (junio 2026)](programa-becas.md) — lo que se planteó al inicio de la Versión 001
- [Estimación del Programa Becas](estimacion-programa-becas.md)
- [Correos de credenciales](correos-credenciales.md)
- [Versión 001](../versiones/version-001.md)
