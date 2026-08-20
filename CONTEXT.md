# Automatización diaria de trabajo en Chaco

Lenguaje compartido para decidir y ejecutar grupos acotados de tareas asignadas mediante la automatización de Codex.

## Language

**Tarea programada de Codex**:
Ejecución recurrente configurada en Codex para analizar y proponer el trabajo diario de Chaco.
_Avoid_: Cron, tarea cron

**Ciclo programado**:
Ejecución que prioriza continuar el único Plan de grupo no terminal. Solo cuando no existe una reserva, autorización pendiente, Unidad activa, Espera de integración, pausa, Bloqueo externo ni cierre financiero puede reservar como máximo un grupo nuevo. Si su tiempo operativo termina, conserva el estado durable y reanuda antes de seleccionar trabajo nuevo.
_Avoid_: Planificación masiva, nuevo plan durante trabajo pendiente

**Excepción automática acotada**:
Autorización de gobernanza que permite únicamente a esta automatización reservar, liberar, bloquear, reanudar y entregar sus propias tareas mediante las transiciones acordadas, además de mantener alineado su Requerimiento vinculado. Los demás movimientos continúan bajo control del PM humano.
_Avoid_: Permiso general para agentes, administración automática del Project

**Sincronización del Requerimiento**:
Regla que refleja en el `[REQUERIMIENTO]` el inicio real de cualquiera de sus tareas y solo revierte esa marca cuando ninguna tarea del alcance avanzó más allá de `Ready` ni conserva trabajo activo. No autoriza a la automatización a llevar el Requerimiento a `In QA` o `Done`.
_Avoid_: Cierre automático del Requerimiento, movimiento de la épica, sincronización parcial

**Plan de grupo**:
Propuesta de trabajo que reúne un conjunto pequeño de tareas relacionadas y establece su orden, objetivo y límites. Requiere aprobación expresa antes de modificar código.
_Avoid_: Lote automático, plan aprobado

**Identificador de plan**:
Referencia legible y única con forma `PG-<tarea-ancla>-<AAAAMMDD>-<secuencia>:v<versión>` que enlaza todas las representaciones de un Plan de grupo. La versión cambia cuando cambia materialmente el plan.
_Avoid_: Nombre libre, fecha sin secuencia, identificador sin versión

**Brief operativo**:
Vista consolidada del contexto funcional y técnico de un Plan de grupo, suficiente para decidir su autorización sin reconstruir manualmente todos los Issues y archivos relacionados.
_Avoid_: Checklist mínima, copia exhaustiva de los Issues

**Matriz de dependencias**:
Tabla del Brief que, por cada Task, registra prerrequisito o contrato afectado, fuente verificable, estado (`integrado`, `misma unidad`, `PR padre calificado` o `no resuelto`), riesgo y resolución. Una relación no resuelta excluye la Task o el grupo antes de reservar.
_Avoid_: Dependencia asumida, lista genérica de riesgos, agrupación por módulo

**Resumen funcional del grupo**:
Explicación breve y en lenguaje llano, ubicada al inicio del Brief operativo, de qué pide el grupo y cuál será su resultado observable. Debe poder entenderse sin abrir los Issues ni leer detalles técnicos.
_Avoid_: Copia de títulos, resumen técnico, contexto extenso

**Grupo reservado**:
Conjunto de tareas incluido en un Plan de grupo y marcado como `In progress` mientras espera aprobación. La reserva impide generar otro plan para esas tareas, pero todavía no implica cambios de código.
_Avoid_: Grupo activo, trabajo implementado

**Reserva fallida**:
Intento incompleto de reservar un grupo que no llega a constituir un Plan de grupo pendiente válido. Las tareas ya movidas se devuelven a `Ready` y cualquier residuo debe reconciliarse antes de seleccionar más trabajo.
_Avoid_: Reserva vigente, grupo parcialmente válido

**Reserva vigente**:
Reserva de un Plan de grupo pendiente que no vence automáticamente y se revalida en cada ejecución programada. Bloquea la selección de otro grupo hasta resolverse. Solo un cambio material en sus tareas, alcance, criterios de aceptación o contratos relevantes la invalida; los cambios no relacionados no la afectan.
_Avoid_: Reserva vencida automáticamente, autorización implícita

**Cola de planes pendientes**:
Estado histórico de Planes reservados que esperan autorización manual. La automatización no crea una nueva reserva mientras exista alguno; primero debe esperar, rechazar, invalidar o recuperar el plan vigente.
_Avoid_: Planificación paralela, autorización implícita

**Tarea principal del grupo**:
Tarea que funciona como ancla del Grupo reservado y conserva el comentario con el Plan de grupo completo.
_Avoid_: Épica del grupo, issue de seguimiento

**Tarea ancla**:
Primera tarea elegible que encabeza la selección después de considerar iteración, prerequisitos, prioridad, capacidad de desbloqueo y antigüedad. La Unidad de entrega se construye alrededor de su resultado funcional.
_Avoid_: Tarea más corta, primera del listado, prioridad aislada

**Tarea elegible**:
Issue de Tipo `Task` en `Ready`, asignado exclusivamente al usuario, perteneciente a la iteración vigente y con todos los gates requeridos. Los demás estados solo intervienen para continuidad o revisión de bloqueos, no para seleccionar trabajo nuevo.
_Avoid_: Issue abierto, tarea asignada, item de Backlog

**Referencia de grupo**:
Comentario breve en cada tarea restante del Grupo reservado que enlaza el Plan de grupo alojado en la Tarea principal.
_Avoid_: Copia del plan, plan duplicado

**Cápsula operativa**:
Comentario editable único en la Tarea principal que muestra ID y versión del plan, Tasks, fase, snapshot GitHub-first, PR/rama/HEAD si existen, bloqueo, respuesta pendiente y próximo paso. Es una vista de seguimiento; no autoriza ni reemplaza Project, Eventos, PR o checks.
_Avoid_: Comentario canónico editable, dashboard paralelo, estado local

**Reconciliación GitHub-first**:
Comparación previa a reanudar, compensar o seleccionar entre Project, comentarios, Eventos, PR, ramas, checks, cierre financiero y memoria. GitHub prevalece; cualquier diferencia se documenta mediante un Evento de recuperación y bloquea mutaciones hasta resolverse.
_Avoid_: Memoria como verdad, liberación por timeout, recuperación silenciosa

**Autorización del plan**:
Confirmación explícita del usuario, emitida en la tarea de Codex que propuso el Plan de grupo e identificándolo de forma inequívoca. Solo queda disponible para ejecuciones futuras cuando Codex consigue persistir en GitHub un Sello de decisión y un Evento de decisión concordantes.
_Avoid_: OK, reacción manual aislada, aprobación implícita

**Observación de plan**:
Pregunta, comentario o pedido de ajuste expresado en la tarea de Codex sin autorizar ni rechazar el plan. No genera Sello de decisión y mantiene reservado el grupo mientras se responde o versiona nuevamente.
_Avoid_: Rechazo implícito, autorización parcial

**Sello de decisión**:
Reacción única que Codex agrega al comentario canónico del Plan de grupo para representar la decisión vigente expresada en su tarea: 👍 autoriza la versión exacta y 👎 la rechaza. Es un gate operativo, no una prueba de actuación humana directa en GitHub. Una nueva decisión reemplaza el sello anterior; nunca deben quedar ambos vigentes.
_Avoid_: Reacción del usuario en GitHub, reacción sin versión de plan

**Evento de decisión**:
Comentario inmutable y secuenciado que acompaña al Sello de decisión y conserva la trazabilidad de una autorización, rechazo o reemplazo: plan y versión, decisión, frase recibida, momento e identidad técnica relacionada. Solo el evento válido con mayor secuencia representa la decisión actual; la reacción muestra su estado vigente y los eventos anteriores conservan la historia.
_Avoid_: Reacción aislada, edición del comentario canónico, decisión sin trazabilidad

**Decisión no persistida**:
Decisión expresada en Codex cuyo Sello de decisión no pudo guardarse en GitHub. No cambia el estado del plan ni habilita acciones hasta que la persistencia se reintente con éxito.
_Avoid_: Autorización verbal suficiente, fallo ignorado

**Identidad autorizadora**:
Identidad GitHub estable del usuario con la que Codex persiste un Sello de decisión válido. Solo sus reacciones sobre el comentario y la versión exactos del plan tienen efecto; las demás se ignoran.
_Avoid_: Cualquier colaborador, nombre visible mutable

**Plan autorizado**:
Versión aprobada de un Plan de grupo que permite a ejecuciones programadas posteriores continuar la misma Unidad de entrega. El permiso deja de valer si cambian sus tareas, alcance o criterios de aceptación.
_Avoid_: Permiso indefinido, autorización para ampliar alcance

**Plan rechazado**:
Plan de grupo sin implementación funcional que el usuario declina explícitamente y se conserva como historial. Su reserva termina, sus tareas regresan a `Ready` y cualquier PR draft vacío ya creado se cierra sin eliminar la rama.
_Avoid_: Plan borrado, cancelación de una unidad activa

**Plan invalidado**:
Versión de un Plan de grupo que perdió vigencia porque cambió materialmente el contexto autorizado. Se conserva como historial y se reemplaza por una versión nueva que requiere otra autorización.
_Avoid_: Ajuste silencioso, rechazo del usuario

**Versión de plan**:
Comentario canónico e inmutable que fija las tareas, alcance y criterios exactos de un Plan de grupo. Un cambio material crea otro comentario y otra versión; ningún Sello de decisión se transfiere entre versiones.
_Avoid_: Plan editable, autorización heredada

**Cola de unidades autorizadas**:
Conjunto de Planes autorizados cuya implementación todavía no comenzó. Se activa una sola unidad a la vez, empezando por el plan más antiguo salvo prioridad explícita, y al terminar o detenerse una se continúa inmediatamente con la siguiente sin límite diario de política. Si un run no alcanza, la cola continúa en el siguiente.
_Avoid_: Implementación paralela, prioridad implícita por autorización

**Activación de unidad**:
Momento en que un Plan autorizado sale de la cola y comienza su implementación. Puede ocurrir en la misma tarea de Codex que persistió el 👍, cualquier día de la semana, cuando no existe otra Unidad activa.
_Avoid_: Autorización sin capacidad, inicio paralelo

**Unidad activa**:
Unidad de entrega autorizada cuya implementación está en curso. Es la única unidad que puede recibir cambios de código y bloquea la selección de otro grupo hasta terminar, pausar, recuperarse o resolverse formalmente.
_Avoid_: Grupo reservado, plan pendiente

**Unidad pausada**:
Unidad activa que el usuario detuvo expresamente sin decidir todavía su cierre o descarte. Conserva sus tareas en `In progress`, su rama y su PR draft, y no recibe nuevos cambios hasta una instrucción explícita.
_Avoid_: Plan rechazado, Bloqueo externo, trabajo descartado

**Control de ritmo**:
Regla por la que Codex propone Unidades de entrega conceptualmente acotadas y solo implementa las aprobadas expresamente. Toda unidad aprobada debe ejecutarse, sin límite numérico diario de política; el ritmo lo determinan las autorizaciones del usuario y el trabajo se reanuda si termina el tiempo operativo de un run.
_Avoid_: Límite diario, implementación automática de todo el backlog

**Unidad de entrega**:
Conjunto dinámico de una o más tareas que produce un único resultado funcional revisable y puede entregarse coherentemente en un mismo PR. Compartir épica, análisis, módulo o prioridad no alcanza para formar una unidad.
_Avoid_: Grupo por cantidad, épica completa, tareas parecidas

**Validación de la unidad**:
Comprobación coordinada de todas las tareas de una Unidad de entrega, aprovechando una misma preparación y una sola pasada cuando sus comportamientos relacionados lo permiten.
_Avoid_: Validación fragmentada obligatoria, prueba aislada por issue

**Validación proporcional**:
Profundidad de comprobación ajustada al riesgo y alcance de una Unidad de entrega: siempre valida lo afectado y suma controles transversales cuando toca modelos, permisos, seguridad, infraestructura o contratos compartidos.
_Avoid_: Suite completa obligatoria, pruebas mínimas fijas

**Entorno local de aceptación**:
Entorno local preparado al finalizar la implementación de una Unidad de entrega, con los datos necesarios para probar de punta a punta el resultado funcional.
_Avoid_: Entorno de producción, entorno vacío

**Ficha de aceptación reproducible**:
Guía enlazada desde el PR y la Cápsula que declara comandos existentes de inicio, fixture o seed sintético, roles, URL y health, pasos y resultados esperados por criterio, SHA/puertos y apagado exacto sin borrar volúmenes. Registra evidencia observada antes de ofrecer el entorno.
_Avoid_: Instrucciones vagas, datos productivos, `down -v`

**Decisión de entorno**:
Elección explícita del usuario, solicitada al finalizar la última unidad de la Cola de unidades autorizadas, entre conservar su Entorno local de aceptación funcionando o apagarlo. Mientras no haya respuesta, el entorno permanece activo y una futura unidad aprobada puede detenerlo mediante la Rotación de entorno.
_Avoid_: Consulta entre unidades aprobadas, limpieza de datos

**Rotación de entorno**:
Transición entre unidades aprobadas en la que Codex detiene el entorno anterior sin borrar sus volúmenes para liberar recursos y continuar con la siguiente. No requiere una decisión intermedia del usuario.
_Avoid_: Entornos simultáneos, eliminación de volúmenes, pausa de la cola

**Datos de aceptación**:
Datos sintéticos y reproducibles, preparados mediante fixtures o seeds versionados para probar una Unidad de entrega. Si faltan escenarios, la unidad incorpora un seed focalizado e idempotente; los datos productivos requieren una autorización separada.
_Avoid_: Copia de producción, carga manual irrepetible

**Cierre financiero estructurado**:
Consulta posterior a la guía de aceptación que exige una respuesta explícita por cada Task. Muestra los campos vigentes de `docs/client/financiero/detalle-tareas.md` y una recomendación de consumo; solo una distribución inequívoca por Task permite agregar filas nuevas, sin reescribir las históricas.
_Avoid_: Total global, imputación inferida, normalización de tablas históricas

**PR de trabajo**:
Pull request en draft que hace visible la rama y concentra el contexto de una Unidad de entrega inmediatamente después de autorizar su plan, antes de la implementación funcional. No representa una solicitud de revisión y sus tareas permanecen en `In progress`.
_Avoid_: PR listo para revisión, entrega terminada

**Commit de inicio**:
Commit vacío que permite publicar la rama y abrir el PR de trabajo sin duplicar el Plan de grupo dentro del repositorio. Si GitHub lo rechaza, puede reemplazarse por una referencia temporal al comentario canónico, que se elimina con el primer cambio funcional.
_Avoid_: Implementación inicial, plan versionado permanente

**Revisión independiente**:
Gate previo a solicitar revisión humana en el que contextos frescos evalúan por separado el cumplimiento de los estándares del repositorio y el cumplimiento del Plan autorizado. No equivale a aprobar el propio PR en GitHub.
_Avoid_: Autorrevisión, autoaprobación, revisión posterior

**Revisión limpia**:
Resultado de la Revisión independiente sin ningún hallazgo pendiente dentro del diff y de los contratos directamente afectados. La deuda preexistente no relacionada se informa, pero no amplía ni bloquea la Unidad de entrega.
_Avoid_: Cero deuda del repositorio, revisión solo crítica

**Gate de revisión humana**:
Condición para convertir el PR draft en listo y mover su unidad a `In review`: Validación proporcional aprobada, Revisión limpia y checks aplicables del último commit terminados sin fallos causados por el cambio. Un check aplicable ausente, pendiente, cancelado o fallido mantiene el PR draft y la unidad en `In progress`.
_Avoid_: CI de un commit anterior, PR listo con evidencia pendiente

**Bloqueo externo**:
Impedimento verificable que no puede resolverse dentro de la Unidad de entrega, como una decisión funcional, acceso o dependencia de un tercero. Se distingue de los fallos corregibles de implementación, pruebas o revisión.
_Avoid_: Test fallido, bug propio, dificultad técnica

**Fallo externo persistente**:
Fallo de validación atribuible a infraestructura o a un servicio externo que reaparece después de un reintento automático. Convierte la unidad en Bloqueo externo con evidencia y conserva el grupo hasta que el servicio se recupere o exista una instrucción explícita.
_Avoid_: Primer fallo, test roto por el cambio, reintento ilimitado

**Espera de integración**:
Estado de una unidad autorizada cuyo prerrequisito ya está implementado pero todavía no fue integrado en `development`. No apila ramas ni mueve tareas a `Blocked`; permanece en `In progress` y bloquea la selección de otro grupo hasta poder reanudarse.
_Avoid_: Bloqueo externo, rama apilada, duplicación del prerrequisito, trabajo paralelo

**Reanudación prioritaria**:
Regla por la que una Unidad de entrega destrabada vuelve a `In progress` y se reanuda antes de seleccionar trabajo nuevo. Mientras el Bloqueo externo persiste, la automatización informa la espera y no toma otro grupo.
_Avoid_: Abandono del grupo, selección sobre estado pendiente

**Resumen de espera**:
Aviso emitido cuando no quedan Tareas elegibles para formar otro grupo, que enumera por separado los Planes pendientes de autorización, las unidades autorizadas en cola, las Esperas de integración, las unidades pausadas y las unidades con Bloqueo externo.
_Avoid_: Sin trabajo, recordatorio genérico
