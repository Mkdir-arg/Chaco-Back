# Análisis funcional 008 — Dispositivos, Versión 2: segunda etapa (lo que quedó afuera del MVP)

**Estado:** En análisis — no genera issues hasta cerrar las preguntas de la §11
**Fecha de análisis:** 2026-11-17
**Analista:** functional-analyst (sesión asistida)
**Sprint asociado:** Sin asignar
**Módulo/App:** `programas` (Dispositivos) · `legajos` (solapa Dispositivos) · `core/rbac.py` · `core/services/vencimientos.py`

**Fuentes contrastadas**

| Fuente | Qué aporta |
|---|---|
| [`propuesta-dispositivos-v2.md`](../../client/funcionalidades/propuesta-dispositivos-v2.md) | El alcance completo de la Versión 2 (827 h, cinco etapas, 14 cambios pedidos por las instituciones) |
| [`estimacion-programa-dispositivos.md`](../../client/funcionalidades/estimacion-programa-dispositivos.md) §11 | Los módulos M1–M17 con sus horas |
| [`mvp-dispositivos-v2.md`](../../client/funcionalidades/mvp-dispositivos-v2.md) | El recorte de 700 h: §2 qué se entrega, §3 qué no |
| [`dispositivos-v2/plan-mvp.md`](../dispositivos-v2/plan-mvp.md) y [`auditoria-mvp.md`](../dispositivos-v2/auditoria-mvp.md) | Cómo se construyó y la matriz final de promesas, apartamientos y exclusiones |
| `requerimientos.md`, Cambios 134, 183, 191 y 239–471 del programa Dispositivos | Lo que se agregó **después** de la auditoría del MVP (17/10) y que ya cierra parte de la §3 |
| Código de `programas/models/__init__.py`, `services/`, `selectors/` | La fuente de verdad: qué existe hoy |

> **Por qué este documento no es una copia de la §3 del MVP.** Entre el 17/10 y el 16/11 entraron unos 60 Cambios sobre Dispositivos. Varios cierran cosas que el MVP declaraba fuera (formularios por tipo, encuadre jurídico, reservas y préstamos, reactivación, el Equipo como alcance) y uno **borra Merenderos entero** (Cambio 452). El punteo de la §3 está hecho contra el código del 17/11/2026, no contra el documento del MVP.

---

## 1. Contexto y motivación

La Versión 2 del Programa Dispositivos se propuso al Ministerio como un alcance de 827 horas en cinco etapas, armado a partir de las visitas al Albergue Madre Teresa de Calcuta, el CIS N.º 3, Abordaje Psicosocial (Mírame/Vedia) y el Parador Nocturno. El Ministerio eligió arrancar por un recorte de 700 horas (el MVP), que puso en marcha el relevamiento edilicio en campo y el circuito básico de las personas —ingreso, plaza, movimientos, bitácora con censo y egreso— con entrega prevista el 13/11/2026.

Ese recorte dejó afuera, deliberadamente, la mitad de los cambios que pidieron las instituciones: la autorización previa del CIS N.º 3, el traslado con seguimiento, la estadía ambulatoria de Mírame/Vedia, el pase de guardia, la información sensible con acceso diferenciado, la mirada de red (espera, derivaciones, tablero) y todo lo del edificio que no es el relevamiento (tenencia, servicios, vigencia, consumos y contratos). El documento del MVP lo dice explícitamente: «nada de esto se descarta: está definido y estimado y se retoma después».

Este análisis es ese «después»: hace el inventario exacto de lo que falta, lo ordena en una segunda etapa entregable por bloques, fija las reglas que el MVP ya estableció y que lo nuevo no puede romper, y deja a la vista las decisiones del Ministerio y del PM que hay que cerrar antes de abrir issues.

---

## 2. Actores involucrados

Se parte de los roles que el MVP dejó funcionando (checklist de la §6 de la auditoría, con el alcance por **Equipo** del Cambio 446) y se agregan los que la segunda etapa necesita.

| Actor | Rol en el sistema | Qué hace en la segunda etapa | ¿Existe hoy? |
|---|---|---|---|
| Administrador del programa | `programa.configurar` + capacidades `dispositivo.*` | Configura reglas por tipo, catálogos, avisos; ve toda la red | Sí |
| Programa central (autorizador) | Rol de programa con capacidad nueva de autorizar ingresos | Autoriza, rechaza o devuelve solicitudes de ingreso; autoriza ingresos excepcionales | **No** — capacidad nueva |
| Operador institucional | Miembro del Equipo con `dispositivo.admitir/egresar/bitacora` | Solicita ingresos, registra permisos de salida, traslados, pase de guardia | Sí (capacidades nuevas para traslado y permiso) |
| Responsable de turno | Operador institucional | Cierra el turno con pase de guardia; el siguiente lo recibe | Rol existente, acción nueva |
| Validador | `dispositivo.validar` | Valida legajos y, con separación de funciones, movimientos que la exijan | Sí (la separación no existe) |
| Equipo técnico (salud, psicosocial, judicial) | Rol con nivel de sensibilidad | Completa y lee las secciones sensibles de la ficha | **No** — niveles nuevos |
| Coordinador de relevamientos | `inspeccion.asignar` | Crea relevamientos, fuerza «Relevar ya», revisa | Sí |
| Agente territorial | `inspeccion.relevar` | Releva desde la app, ahora también tenencia y servicios | Sí |
| Conducción (subsecretario / director) | Rol con alcance **por subsecretaría** | Ve el tablero de la red y su vista personalizada, acotados a su subsecretaría | **No** — alcance nuevo |
| Responsable administrativo | Capacidad nueva de consumos | Carga pagos y comprobantes de alquiler y servicios | **No** |
| Autoridad superior | Destinatario de escalados | Recibe el aviso cuando un contrato o servicio vence sin pago | **No** |

---

## 3. Punteo de lo que quedó afuera del MVP

Leyenda: **✅ Hecho después del MVP** (con su Cambio) · **🟡 Parcial** · **🔴 Pendiente** · **⚪ Descartado**.

### 3.1 Legajo de la institución (M1)

| Ítem de la §3 del MVP | Estado hoy | Evidencia / qué falta |
|---|---|---|
| Encuadre jurídico: titularidad del inmueble y dependencia de la gestión por separado | ✅ | Cambio 368: `Dispositivo.categoria`, `titularidad_inmueble`, `dependencia_gestion` |
| Subsecretaría de la que depende | ✅ (dato) | Cambio 368: `Dispositivo.area_ministerio` → `core.Subsecretaria`. **No** se usa todavía para el alcance (ver 3.9) |
| Documentación con vigencia y aviso de vencimiento | 🔴 | No hay entidad de documentos del dispositivo ni solapa «Documentación» en P4 (las solapas son datos, sectores, estadías, infraestructura, equipo, historial). Los adjuntos del formulario «Crear dispositivo» no tienen vigencia |
| Estados «inauguración pendiente» y «suspendida» con reactivación | 🟡 | `Dispositivo.Estado` no tiene ninguno de los dos. Sí existe reactivar un INACTIVO (Cambio 409 D1), que no es lo mismo: «suspendida» conserva a los alojados y no admite ingresos nuevos |
| Cierre con gente alojada resuelto en bloque (asistente) | 🔴 | No existe |
| Control de duplicados al alta | ✅ | Cambios 308/323: panel de duplicados en P3, bloqueo sin nombrar la ajena (C-8) |
| Fusión de instituciones repetidas | 🔴 | No existe |
| Procedencia y nivel de confianza del dato | 🟡 | Solo a nivel padrón (`fuente_padron`, `fecha_padron`, `responsable_padron`); no por dato ni con nivel de confianza |
| Servicios que brinda la institución | 🔴 | No modelado |

### 3.2 Infraestructura del edificio (M14)

| Ítem | Estado hoy | Evidencia / qué falta |
|---|---|---|
| Edificio como entidad, compartido entre instituciones | ✅ | `Edificio.dispositivos` (N:M); sector ubicado en un edificio (Cambio 429); tarjetas por edificio y ficha propia (Cambio 439) |
| Ubicación en mapa | ✅ con apartamiento | Coordenadas + enlace externo «ver en el mapa» (decisión C-14: la CSP bloquea los CDN de mapas) |
| Registro fotográfico histórico | ✅ | Fotos del relevamiento en línea de tiempo (Cambios 423, 439) |
| Estado de tenencia (propio, alquilado, comodato, donado, mixto) | 🔴 | `services/edificios.py` lo excluye explícitamente. Ojo: la `titularidad_inmueble` del **dispositivo** no es la tenencia del **edificio** |
| Cantidad de habitaciones y plano | 🔴 | No modelado; C-14 decidió «el plano como adjunto» |
| Servicios disponibles (luz, agua de red o alternativa, internet, señal móvil) | 🔴 | No modelado |
| Estado físico estructurado (condición, daños, faltantes, mantenimiento) | 🟡 | Hoy es criticidad + observaciones del relevamiento + el formulario «Relevamiento» por tipo (Cambio 388), que puede pedir estos datos pero no los normaliza |
| Vencimiento automático a los 6 meses (1 mes en obra) con aviso por correo | 🔴 | Decisión del MVP (Cambio 308): el vencido es el **de la asignación**, no una vigencia periódica. No hay estado «en obra» |
| Botón «Relevar ya» | 🔴 | No existe (sí «Crear relevamiento» desde la solapa, Cambio 384) |
| Agente externo a la institución | ✅ | Cambio 289/446: el personal del edificio (miembros del Equipo de cualquiera de sus dispositivos) no es asignable |

### 3.3 Relevamientos edilicios (M15)

| Ítem | Estado hoy | Qué falta |
|---|---|---|
| Crear, asignar, reasignar, cancelar, revisar | ✅ | — |
| Informe oficial vinculado al legajo | 🟡 | Hay informe en pantalla (Cambio 289). Falta el **documento oficial** (PDF numerado, firmable/imprimible) archivado en el legajo |
| Periodicidad, prioridad, exportar el listado | 🔴 | Excluidos en P21 por la auditoría |
| App móvil: almacenamiento local, modo avión, HEIC, cola | 🟡 | El servidor está verificado; **la app no** (auditoría §7). Es deuda de verificación del MVP, no alcance nuevo |

### 3.4 Circuito de las personas (M3)

| Ítem | Estado hoy | Evidencia / qué falta |
|---|---|---|
| Solicitud de ingreso con autorización previa del programa central (CIS N.º 3, Parador) | 🔴 | Todo ingreso es directo. `TipoDispositivo` no tiene la regla «exige autorización» |
| Detección automática de reingreso | 🟡 | P7 marca «Reingreso» (estadías anteriores en `detalle_de_estadia`). El asistente de ingreso **no** lo avisa al operador |
| Ingreso excepcional por encima de la capacidad, con quién autorizó y por qué | 🔴 | El asistente avisa ocupación crítica (Cambio 323) pero no deja ingresar sin plaza libre en tipos que exigen plaza |
| Traslado entre dispositivos con estado *en tránsito* | 🔴 | Hoy es egreso + ingreso sin vínculo. `Estadia.Estado` es solo ACTIVA/EGRESADA. El momento de formulario «Traslado» existe pero nada lo consume |
| Estadía ambulatoria (Mírame/Vedia), compatible con una residencial | 🔴 | La `clave_alojamiento` es una por persona en toda la red, sin distinguir tipo de estadía |
| Préstamo de plaza 12/24 h | ✅ | `ReservaPlaza.Tipo.PRESTAMO`; alta desde P5 (Cambio 389), liberación y aviso de vencido |
| Reserva de plaza | ✅ | Cambios 389/406/409; reservas de derivación de Emergencia (Cambio 468) |
| Permiso de salida con regreso previsto y aviso si no vuelve | 🔴 | Solo existe en la golden de referencia (`revision_referencia.html`) y como tipo automático `PERMISO` de bitácora, sin modelo ni servicio |
| Egreso con derivación formal y seguimiento | 🔴 | Destino de texto obligatorio (Cambio 321) |
| Avisos de la estadía: límite de permanencia por tipo (48 h UPI/ECA), permiso vencido, formulario incompleto, tránsito vencido | 🔴 | Las cinco reglas actuales de `alertas_dispositivos.py` son del dispositivo y de las plazas, no de la estadía |
| Cambios de estado de la estadía más allá de ingreso/egreso | 🔴 | Decisión PM n.º 11 del MVP: solo ACTIVA/EGRESADA |

### 3.5 Capacidad (M2)

| Ítem | Estado hoy | Qué falta |
|---|---|---|
| Tipos de plaza diferenciados (cama, cupo, turno) | ✅ | `Plaza.Tipo`, `TipoDispositivo.tipos_plaza_admitidos` (Cambio 372) |
| Estados de la plaza y reubicación | ✅ | Fuera de servicio con motivo; no se saca de servicio una ocupada; reubicar desde la plaza ocupada (Cambios 377, 437) |
| Disponibilidad neta | 🟡 | El servicio único de ocupación calcula disponibles. Falta **definir** si una plaza prestada cuenta como disponible (pregunta 4 de la §8.2 de la propuesta) y mostrar la neta en la red |

### 3.6 Operación diaria (M5)

| Ítem | Estado hoy | Qué falta |
|---|---|---|
| Versionado de las novedades | ✅ | Entró en el MVP por #695; adjuntos y personas al corregir (Cambios 426, 436) |
| Pase de guardia (cierre formal del turno, quién entrega, quién recibe) | 🔴 | `EntradaBitacora.Tipo.PASE` existe como valor; no hay acto de cierre ni recepción |
| Regularización de días anteriores, con marca de fuera de término | 🔴 | `services/bitacora.py` rechaza explícitamente toda carga fuera del turno en curso |
| Tipos de novedad configurables por el Ministerio | 🔴 | `EntradaBitacora.Tipo` es un `TextChoices` fijo |
| Exportar la bitácora | 🔴 | — |

### 3.7 Formularios (M4)

| Ítem | Estado hoy | Evidencia / qué falta |
|---|---|---|
| Configurador de formularios por tipo, sin desarrollo | ✅ | Cambio 344: constructor de Becas con el tipo como dueño, un formulario por momento |
| Formularios conectados a su acción | 🟡 | **Conectados:** Crear dispositivo (345), Ingreso (454), Egreso (455), Relevamiento en la app (388). **Definidos pero sin consumidor:** Asignación de plaza, Novedades del turno, Traslado, Propio |
| Ficha que acompaña toda la estadía, con avance por sección | 🔴 | P7 muestra lo respondido al ingreso; no hay secciones que se completen a lo largo del tiempo ni porcentaje de avance |
| Campos protegidos (persona, fecha, plaza) | 🟡 | El sistema los pide fuera del formulario, así que no se pueden borrar; falta mostrarlos en el constructor como «del sistema» |
| Impresión y exportación de la ficha | 🔴 | — |

### 3.8 Mirada de red (M6, M8, M9, M10)

| Ítem | Estado hoy | Qué falta |
|---|---|---|
| Lista de espera con prioridad y reserva de plaza | 🔴 | `EsperaAdmision` se borró en el MVP. `ListaEspera` del modelo es de Becas |
| Derivaciones entre instituciones y a organismos externos | 🔴 | Hay **dos** modelos de derivación que no cubren el caso: `DerivacionPrograma` (entre programas) y `Derivacion` de Emergencia (de la mesa al dispositivo, con aceptar/rechazar/vencer y reserva de plazas). Ver §5, RN-15 |
| Vista de plazas disponibles en la red | 🔴 | — |
| Tablero de la red (P1) | 🔴 | Sin pantalla; P1 además necesita la golden de dashboard (C-7) |
| Avisos configurables por regla y **proactivos** (correo, cron) | 🔴 | Decisión PM n.º 13: los avisos se calculan al consultar. Los comandos de cron no procesan los avisos de Dispositivos |
| Reportes exportables | 🟡 | Solo el padrón de instituciones (P2, CSV/Excel). Faltan ocupación, movimientos, censo, bitácora, espera y derivaciones |
| Importador del padrón | 🟡 | `import_padron_dispositivos` carga instituciones. No carga edificios, sectores, plazas ni personas alojadas |
| Auditoría única del programa, legible y exportable | 🟡 | Historial por dispositivo (`FeedAuditoria`) y por estadía. Falta la vista transversal y la exportación |

### 3.9 Permisos (M7)

| Ítem | Estado hoy | Qué falta |
|---|---|---|
| Alcance por institución | ✅ | Por **Equipo de personas** (Cambios 410, 411, 446) + `dispositivo.ver_todos` |
| Alcance por subsecretaría | 🔴 | El dato existe (`area_ministerio`), la regla no |
| Niveles de sensibilidad (general, social, salud, psicosocial, judicial) con aviso de lectura registrado, marca de agua y bloqueo de exportación | 🔴 | Decisión C-13 tomada (cuatro medidas reales); nada implementado |
| Separación de funciones (quien registra no valida) | 🔴 | `validar_dispositivo` y `marcar_revisado` no miran quién cargó |
| Reglas por tipo administradas desde el sistema (P14) | 🟡 | Hoy el tipo configura plazas, plaza obligatoria y umbrales del semáforo. Faltan: exige autorización previa, permite préstamo, límite de permanencia, secciones mínimas, catálogo de motivos de egreso desde la UI (hoy en Django Admin), umbrales de aviso |

### 3.10 Lo demás

| Ítem | Estado hoy | Nota |
|---|---|---|
| Consumos y contratos (M16) | 🔴 | Nada construido |
| Tableros configurables por rol y recordatorios (M17) | 🔴 | Nada construido |
| Programa Merenderos (M11, M12) | ⚪ | **Borrado del sistema** el 10/11/2026 (Cambio 452, decisión del PM: sin datos en ningún ambiente). No entra en esta etapa salvo decisión explícita en contrario (pregunta 1) |

### 3.11 Deuda de cierre del MVP (no es alcance nuevo, pero hay que cerrarla)

- Verificación real de la **app móvil** del relevamiento: APK, modo avión, conversión HEIC, cola de sincronización (auditoría §7).
- Suite completa contra **MySQL 8** (solo hubo MariaDB 10.11 focal).
- `DeleteModel` de `AsignacionDispositivo`, dos releases después del Cambio 446, con su `# CONTRACT:`.
- Varias entradas del registro de Dispositivos siguen 🟡 «En curso» (Cambios 409–451): conviene cerrarlas antes de abrir la etapa para no mezclar trabajo.

---

## 4. Descripción funcional de la segunda etapa

La segunda etapa se organiza en **cuatro bloques**, cada uno utilizable por sí mismo, en el orden en que más cambian la operación. Respeta el criterio de la propuesta original («las personas primero, el edificio después») y el de las etapas 1–5, reacomodado a lo que ya existe.

### Bloque A — El circuito completo de la persona

Cierra los tres pedidos más repetidos en las visitas que el MVP no cubrió: autorización previa, traslado con seguimiento y seguimiento sin alojamiento.

**Flujo principal: solicitud con autorización previa**

1. El tipo de institución declara «exige autorización previa» (regla nueva en P14).
2. En una institución de ese tipo, el operador inicia el ingreso: busca a la persona como hoy (paso 1 del asistente, verificación en la red incluida) y en vez de confirmar el ingreso **genera una solicitud** con motivo y, si quiere, la plaza a reservar.
3. La solicitud queda *pendiente* y aparece en la bandeja del programa central.
4. El programa central la **autoriza** (con vigencia en días y reserva opcional de la plaza), la **rechaza** con motivo, o la **devuelve** pidiendo datos.
5. Con la solicitud autorizada y vigente, el operador completa el ingreso; la solicitud queda *consumida* y vinculada a la estadía.
6. Si vence sin usarse, se libera la reserva y queda *vencida*.

**Flujo: ingreso excepcional**

- Condición: no hay plaza libre y el tipo exige plaza.
- Comportamiento: el asistente ofrece «Ingreso excepcional»; exige motivo y quién lo autorizó (un usuario con la capacidad de autorizar excepcionales, distinto de quien carga si la separación de funciones lo exige). La estadía queda marcada *excepcional*, sin plaza o en una plaza virtual de sobrecapacidad; el censo la cuenta y la ocupación puede superar el 100 %.

**Flujo: estadía ambulatoria**

- Condición: el tipo admite seguimiento ambulatorio (Mírame/Vedia) o el operador elige esa modalidad.
- Comportamiento: se abre una estadía de modalidad *ambulatoria*, sin plaza, que **no** ocupa la clave de alojamiento residencial. Puede convivir con una estadía residencial en otro dispositivo. Tiene su propia línea de tiempo (intervenciones) y su egreso.

**Flujo: permiso de salida**

1. Desde P7 el operador registra un permiso de salida con regreso previsto (fecha y hora) y motivo.
2. La plaza sigue asignada a la persona; el censo la cuenta como «con permiso de salida».
3. Al volver, se registra el regreso. Si pasa la hora prevista sin regreso, hay aviso en P4/P7 y en la bitácora.
4. Desde el aviso, el operador puede registrar el regreso tardío o el egreso por abandono.

**Flujo: traslado en tránsito**

1. Desde P7 el operador origen inicia el traslado: elige la institución destino, motivo y (si el tipo lo exige) completa el formulario «Traslado».
2. La estadía de origen pasa a *en tránsito*; su plaza queda reservada hasta la resolución; la persona **no** figura alojada en dos lugares.
3. El destino la ve en una bandeja «Traslados entrantes» (P8) y la **recibe** (abre la estadía en destino, cierra la de origen con motivo «Traslado» y libera la plaza) o la **rechaza** con motivo (la estadía de origen vuelve a *activa* con su plaza).
4. Si vence el plazo sin resolución, hay aviso en las dos puntas.

**Flujo: egreso con derivación**

- El egreso permite, además del destino en texto, registrar una **derivación** a otra institución de la red u organismo externo (Bloque C). Si se elige institución de la red, el egreso puede convertirse en traslado.

**Avisos de la estadía (nuevas reglas en `core/services/vencimientos.py`)**: límite de permanencia por tipo, permiso de salida vencido, tránsito vencido, solicitud autorizada por vencer, formulario incompleto pasados N días.

### Bloque B — La ficha, la sensibilidad y el turno

**Ficha de la estadía.** Los formularios por momento que ya existen dejan de ser «se completa una vez»: P7 gana una solapa *Ficha* con las secciones de los formularios del tipo (ingreso, novedades, egreso, propios), su avance por sección y quién la completa. Se conectan los momentos sin consumidor: *Asignación de plaza* (al asignar/cambiar plaza), *Novedades del turno* (al cargar una novedad o cerrar el turno), *Traslado* (Bloque A) y *Propio* (desde la solapa Ficha).

**Sensibilidad.** Cada sección del constructor declara un nivel: general, social, salud, psicosocial o judicial. Cada nivel es una capacidad tildable en el rol. El comportamiento (ya acordado en la propuesta, §4.7, y en la decisión C-13):

- Sin el nivel: la sección **se ve como existente**, con su avance y el equipo que la completa, sin el contenido.
- Con el nivel: al abrirla se pide confirmación; **cada apertura queda registrada** (usuario, sección, persona, fecha y hora).
- Dentro de una sección sensible: marca de agua con usuario y hora, bloqueo de exportación sin el nivel, y los reportes la excluyen para quien no lo tiene.

**Separación de funciones.** Quien cargó o envió un legajo no lo valida; quien registró un movimiento que requiere validación no la confirma; quien autoriza un ingreso excepcional no es quien lo carga (si la regla lo pide). Lo rechaza el servidor, no solo la pantalla.

**Pase de guardia.** Al terminar el turno, el responsable cierra el turno: el sistema le muestra el censo calculado y los pendientes (personas con permiso de salida, traslados en tránsito, avisos abiertos), agrega lo que queda para seguimiento y confirma. El turno siguiente ve el pase como primera cosa en P10 y confirma la recepción. Queda constancia de quién entregó y quién recibió. Un turno sin cerrar genera aviso.

**Regularización.** Se pueden cargar novedades de turnos anteriores dentro de una ventana configurable por tipo (días); la entrada queda marcada *fuera de término* con el momento real de carga y no altera el censo calculado desde los movimientos.

**Tipos de novedad configurables.** El catálogo de tipos manuales de la bitácora pasa a administrarse desde Configuración; los automáticos (ingreso, egreso, movimiento, permiso, pase) siguen siendo del sistema y no se pueden editar.

### Bloque C — La red y la conducción

**Lista de espera.** Por institución: persona, posición, prioridad por criterios configurables (medida judicial, edad, riesgo), origen, y reserva de plaza opcional (reusa `ReservaPlaza`). Cuando se libera una plaza el sistema **sugiere** a quién le toca; no promueve solo. Pasar de la espera al ingreso abre el asistente con la persona y la plaza cargadas.

**Derivaciones.** Entre instituciones de la red y a organismos externos (hospital, juzgado): destino, motivo, urgencia; el destino de la red acepta (abre solicitud o ingreso según el tipo), rechaza con motivo o deja vencer. Las externas se registran con seguimiento manual. Todo queda en la trayectoria de la persona (P16).

**Vista de red.** Dónde hay plazas disponibles por tipo, sector y localidad, acotada al alcance, para decidir la derivación.

**Tablero de la red (P1).** Capacidad por tipo y localidad, ocupación, disponibilidad, ingresos y egresos del período, permanencia promedio, alojados por sector, avisos abiertos; filtros por subsecretaría, tipo, localidad y período; exportable.

**Avisos proactivos.** El motor de avisos (`core/services/vencimientos.py`) pasa a: (a) reglas con umbrales configurables, (b) un comando programado que los evalúa y (c) envío por correo a los destinatarios definidos por regla, con escalado. Revierte la decisión PM n.º 13 del MVP para los avisos que el Ministerio elija.

**Alcance por subsecretaría.** Un rol con este alcance ve y opera (según sus capacidades) todas las instituciones cuya `area_ministerio` es su subsecretaría, sin estar en su Equipo.

**Reportes.** Ocupación por dispositivo y sector, movimientos del período, censo diario, bitácora, lista de espera y derivaciones, auditoría; CSV y Excel, acotados al alcance y a la sensibilidad, con registro de quién exportó.

**Carga inicial ampliada.** El importador suma edificios, sectores, plazas y, opcionalmente, personas alojadas hoy, con nivel de confianza «importado / sin verificar» que pasa a «verificado» cuando el equipo territorial lo confirma.

### Bloque D — La institución y el edificio

**Legajo.** Documentación del dispositivo con tipo, archivo y fecha de vigencia, y aviso de vencimiento; estados *inauguración pendiente* (no admite ingresos) y *suspendida* (no admite ingresos nuevos, conserva a los alojados, vuelve a activa); cierre con gente alojada mediante un asistente que egresa o traslada en bloque; fusión de dos legajos duplicados (conserva uno, mueve estadías, edificios, Equipo y trazas, deja traza de la fusión); servicios que brinda la institución.

**Edificio.** Tenencia (propio, alquilado, comodato, donado, mixto), cantidad de habitaciones, plano como adjunto, servicios disponibles (luz, agua de red o fuente alternativa, internet, conectividad móvil), estado «en obra». Los datos los carga el agente territorial en el relevamiento (formulario estructurado de la app) y quedan como los vigentes del edificio.

**Vigencia del relevamiento.** Un edificio vence a los 6 meses del último relevamiento realizado (1 mes si está en obra). El vencimiento genera aviso visual y por correo, y aparece en P21 como «Por relevar». «Relevar ya» fuerza el vencimiento y abre la asignación.

**Informe oficial.** Al revisar un relevamiento, el sistema genera un documento oficial (PDF con número, fecha, edificio, instituciones, criticidad, observaciones, fotos y revisor) que queda archivado en la documentación de cada institución del edificio.

**Consumos y contratos (P20).** Solapa en P4 con ítems (alquiler, luz, agua, internet y otros del catálogo), último pago, vencimiento y comprobante adjunto. Aviso 7 días antes; si vence sin pago registrado, escala a la autoridad superior.

**Tableros por rol y recordatorios (M17).** Sobre los datos del tablero de la red: cada administrador y director arma su vista con los indicadores del catálogo, acotada a su alcance. Recordatorios propios por institución. El agente territorial no accede.

---

## 5. Requerimientos

### Requerimientos funcionales

| ID | Requerimiento | Bloque | Prioridad | Notas |
|---|---|---|---|---|
| RF-008-01 | El tipo de institución configura si exige autorización previa del programa central y la vigencia por defecto de la autorización | A | Alta | P14 |
| RF-008-02 | Se registra una solicitud de ingreso con persona verificada en la red, motivo y plaza a reservar opcional | A | Alta | |
| RF-008-03 | El programa central autoriza (con vigencia), rechaza (con motivo) o devuelve una solicitud | A | Alta | Capacidad nueva |
| RF-008-04 | Solo una solicitud autorizada y vigente habilita el ingreso en un tipo que la exige; al ingresar queda consumida y vinculada a la estadía | A | Alta | |
| RF-008-05 | Ingreso excepcional sin plaza libre con motivo y autorizante registrados; el censo lo cuenta | A | Alta | |
| RF-008-06 | Estadía de modalidad ambulatoria, sin plaza, que convive con una residencial en otro dispositivo | A | Alta | |
| RF-008-07 | Permiso de salida con regreso previsto, registro de regreso y aviso si no regresa | A | Alta | |
| RF-008-08 | Traslado con estadía en tránsito visible en origen y destino, recepción o rechazo del destino y vencimiento | A | Alta | P8 |
| RF-008-09 | El asistente de ingreso avisa reingreso (estadías anteriores de la persona en la red) | A | Media | Hoy solo P7 |
| RF-008-10 | Avisos de estadía: límite de permanencia por tipo, permiso vencido, tránsito vencido, solicitud por vencer, formulario incompleto | A | Alta | |
| RF-008-11 | Solapa Ficha en P7 con secciones de los formularios del tipo, avance por sección y quién la completa | B | Alta | |
| RF-008-12 | Los momentos Asignación de plaza, Novedades del turno, Traslado y Propio se piden en su acción | B | Media | |
| RF-008-13 | Cada sección declara nivel de sensibilidad; el nivel es una capacidad del rol | B | Alta | |
| RF-008-14 | Sin nivel: la sección se ve como existente con avance y equipo, sin contenido | B | Alta | |
| RF-008-15 | Con nivel: confirmación al abrir y registro de cada apertura | B | Alta | |
| RF-008-16 | Marca de agua con usuario y hora y bloqueo de exportación en secciones sensibles | B | Media | C-13 |
| RF-008-17 | Separación de funciones en validación de legajo, revisión de relevamiento y autorización de excepcional | B | Alta | |
| RF-008-18 | Cierre de turno con pase de guardia (censo + pendientes) y recepción del turno siguiente | B | Alta | |
| RF-008-19 | Regularización de turnos anteriores dentro de una ventana por tipo, con marca de fuera de término | B | Media | |
| RF-008-20 | Catálogo de tipos de novedad manuales administrable | B | Baja | |
| RF-008-21 | Catálogo de motivos de egreso administrable desde Configuración (no Django Admin) | B | Baja | |
| RF-008-22 | Lista de espera por institución con prioridad, reserva y sugerencia (sin promoción automática) | C | Alta | |
| RF-008-23 | Derivaciones entre instituciones y a organismos externos con aceptación, rechazo y vencimiento | C | Alta | |
| RF-008-24 | Vista de plazas disponibles en la red por tipo, sector y localidad | C | Media | |
| RF-008-25 | Tablero de la red (P1) con filtros y exportación | C | Alta | Golden de dashboard |
| RF-008-26 | Avisos configurables por regla con evaluación programada y envío por correo | C | Media | Revierte decisión PM 13 |
| RF-008-27 | Alcance por subsecretaría | C | Alta | |
| RF-008-28 | Reportes de ocupación, movimientos, censo, bitácora, espera, derivaciones y auditoría | C | Media | |
| RF-008-29 | Importador de edificios, sectores, plazas y personas alojadas con nivel de confianza | C | Media | |
| RF-008-30 | Documentación del dispositivo con vigencia y aviso | D | Media | |
| RF-008-31 | Estados inauguración pendiente y suspendida, con vuelta a activa | D | Media | |
| RF-008-32 | Asistente de cierre con alojados (egreso o traslado en bloque) | D | Media | |
| RF-008-33 | Fusión de legajos duplicados | D | Baja | |
| RF-008-34 | Tenencia, habitaciones, plano, servicios y estado «en obra» del edificio | D | Media | |
| RF-008-35 | Vigencia del relevamiento 6 meses / 1 mes en obra, con aviso y «Relevar ya» | D | Media | |
| RF-008-36 | Informe oficial del relevamiento archivado en el legajo | D | Media | |
| RF-008-37 | Consumos y contratos con aviso a 7 días y escalado | D | Media | |
| RF-008-38 | Tableros por rol y recordatorios | D | Baja | |

### Requerimientos no funcionales

| ID | Requerimiento | Categoría |
|---|---|---|
| RNF-008-01 | Toda exclusión «una sola X activa» se resuelve con columna anulable + `UNIQUE` común o con `select_for_update()`, **nunca** con `UniqueConstraint(condition=...)` (no existe en MySQL/MariaDB) | Datos |
| RNF-008-02 | Ningún cálculo por fecha usa `Trunc*` sobre un `DateTimeField` (la base de ECOM no tiene tablas de zona horaria) | Datos |
| RNF-008-03 | Columnas nuevas nacen `null=True` o con `DEFAULT` real; todo `UUIDField` nuevo con su migración a `char(36)` | Migraciones |
| RNF-008-04 | Las cifras de ocupación, censo e indicadores salen del servicio único de ocupación; el tablero de la red no crea un segundo cálculo | Consistencia |
| RNF-008-05 | Toda pantalla nueva clona la golden de su arquetipo; P1 (dashboard) y P8 (caso complejo/bandeja) se declaran con su Plan de pantalla antes de escribir | UI |
| RNF-008-06 | La lectura de una sección sensible se registra en una traza solo-aditiva, como `TrazaDispositivo` | Seguridad |
| RNF-008-07 | Reportes y API respetan alcance y sensibilidad; las vistas tienen presupuesto de consultas en `perf_budgets.json` | Seguridad / Performance |
| RNF-008-08 | Lo que consume la app móvil (relevamiento ampliado) actualiza el test de contrato de la API en el mismo diff | API |

---

## 6. Reglas de negocio

Las reglas RN-008-01 a RN-008-08 vienen del MVP y **no se pueden romper**; las siguientes son nuevas.

| ID | Regla | Consecuencia si no se cumple |
|---|---|---|
| RN-008-01 | Una persona tiene a lo sumo **una estadía residencial** activa en toda la red (`clave_alojamiento`) | El motor rechaza el segundo alojamiento |
| RN-008-02 | La exclusión por plaza se toma bloqueando la fila de la plaza, con el orden de candados plaza → reserva → persona (Cambios 406/409) | Doble ocupación bajo concurrencia |
| RN-008-03 | Ocupación y censo se derivan de los movimientos; nadie tipea un número | Cifras que se contradicen |
| RN-008-04 | El sistema avisa y no bloquea por ocupación; bloquea por integridad (plaza ocupada, persona ya alojada) | — |
| RN-008-05 | Una plaza fuera de servicio no puede tener estadía, reserva ni préstamo vigente | El servicio rechaza |
| RN-008-06 | Los movimientos y la bitácora son solo-aditivos; corregir agrega versión | Se reescribe la historia |
| RN-008-07 | Al ingresar, se liberan las reservas abiertas de la persona, **salvo** las de derivación de Emergencia (Cambio 468) | Se liberan camas de una familia en llegada |
| RN-008-08 | El agente de relevamiento no es miembro vigente del Equipo de ningún dispositivo del edificio | Se omiten irregularidades |
| RN-008-09 | Una estadía ambulatoria **no** ocupa la clave de alojamiento residencial; dos ambulatorias simultáneas de la misma persona en el mismo dispositivo no se permiten | A definir si se permiten en dispositivos distintos (pregunta 4) |
| RN-008-10 | En un tipo con autorización previa no hay ingreso directo; la solicitud autorizada tiene vigencia y se consume una sola vez | — |
| RN-008-11 | Una estadía en tránsito no es alojamiento en destino hasta que el destino la recibe; durante el tránsito la plaza de origen queda reservada | La persona figura en dos lugares |
| RN-008-12 | El rechazo de un traslado devuelve la estadía de origen a activa con su plaza | — |
| RN-008-13 | Un ingreso excepcional exige motivo y autorizante con la capacidad correspondiente | — |
| RN-008-14 | Quien registra no valida: legajo, revisión de relevamiento y excepcional (y lo que el Ministerio agregue) | El servidor rechaza |
| RN-008-15 | Las derivaciones de Dispositivos no reemplazan a las de Emergencia: o se generaliza `Derivacion` con dos orígenes (caso de emergencia o estadía) o se crea una entidad hermana; no se duplican reglas de reserva | Dos circuitos que reservan plazas por caminos distintos |
| RN-008-16 | La lista de espera sugiere; la promoción es siempre una acción humana | — |
| RN-008-17 | La lectura de una sección sensible queda registrada en **cada** apertura | — |
| RN-008-18 | Un dispositivo suspendido o en inauguración pendiente no admite ingresos nuevos; suspendido conserva a los alojados | — |
| RN-008-19 | No se cierra un dispositivo con estadías activas o en tránsito sin pasar por el asistente | Personas huérfanas |
| RN-008-20 | La vigencia del relevamiento se calcula desde el último relevamiento **realizado**; Crítico sigue prevaleciendo sobre Vencido (decisión PM 6) | — |
| RN-008-21 | La regularización no altera el censo (que sale de movimientos) y marca la entrada como fuera de término | — |

---

## 7. Criterios de aceptación

- [ ] Dado un tipo con autorización previa, cuando el operador intenta ingresar sin solicitud autorizada, entonces el asistente solo ofrece «Generar solicitud».
- [ ] Dada una solicitud autorizada con reserva, cuando vence sin usarse, entonces la reserva se libera y la solicitud queda vencida, con traza.
- [ ] Dado un dispositivo sin plaza libre, cuando se registra un ingreso excepcional con motivo y autorizante, entonces la estadía queda marcada excepcional y el censo la suma.
- [ ] Dada una persona alojada en un dispositivo residencial, cuando se abre una estadía ambulatoria en Mírame/Vedia, entonces se permite y ambas aparecen en P16.
- [ ] Dado un permiso de salida con regreso previsto a las 22:00, cuando a las 22:01 no hay regreso, entonces P4 y P7 muestran el aviso.
- [ ] Dado un traslado iniciado, cuando el destino lo rechaza, entonces la estadía de origen vuelve a activa en su misma plaza y la persona nunca figuró alojada en el destino.
- [ ] Dado un traslado iniciado, cuando el destino lo recibe, entonces la estadía de origen se cierra con motivo «Traslado», la plaza se libera y se abre la estadía en destino, en una sola transacción.
- [ ] Dado un usuario sin nivel «salud», cuando abre la ficha, entonces ve la sección Salud con su avance y su equipo, sin contenido.
- [ ] Dado un usuario con nivel «salud», cuando abre la sección, entonces se pide confirmación y queda registrada la apertura con usuario, sección, persona y hora.
- [ ] Dado quien envió un legajo a validación, cuando intenta validarlo, entonces el servidor lo rechaza.
- [ ] Dado el fin de un turno, cuando el responsable cierra con pase de guardia, entonces el turno siguiente lo ve primero y su confirmación deja constancia de quién recibió.
- [ ] Dada una plaza liberada, cuando hay personas en lista de espera, entonces se sugiere a la primera por prioridad y nadie ingresa sin acción humana.
- [ ] Dado un rol con alcance por subsecretaría, cuando abre el listado de instituciones, entonces ve todas las de su subsecretaría y ninguna de otra.
- [ ] Dado un edificio relevado hace 6 meses y un día, cuando corre la evaluación de avisos, entonces el edificio figura vencido y se envía el correo configurado.
- [ ] Dado un contrato sin pago a su vencimiento, cuando vence, entonces escala a la autoridad superior.

---

## 8. Casos límite y excepciones

| Caso | Comportamiento esperado |
|---|---|
| Traslado iniciado a un dispositivo que se suspende antes de recibir | El destino no puede recibir; aviso en origen; se puede cancelar el traslado |
| La persona en tránsito intenta ingresar por otro dispositivo | La verificación de red la muestra «en tránsito» y bloquea como alojada |
| Permiso de salida abierto al egresar | El egreso cierra el permiso con la misma fecha |
| Pase de guardia sin turno siguiente configurado | El pase queda abierto y lo recibe el próximo turno que se abra |
| Dos responsables cierran el mismo turno a la vez | El segundo recibe «el turno ya fue cerrado por X», sin `IntegrityError` |
| Sección sensible dentro de un reporte | Se excluye para quien no tiene el nivel; el reporte lo dice |
| Estadías y reservas de derivación de Emergencia en una institución que se fusiona | La fusión mueve todo, incluidas las reservas con `derivacion`, o se bloquea si hay derivaciones vigentes (a decidir) |
| Persona importada como alojada que ya figura alojada en otro dispositivo | El importador la rechaza en la fila y lo informa; no se crea el segundo alojamiento |
| Cambio de la vigencia por tipo con solicitudes ya autorizadas | Las autorizadas conservan su vigencia original |

---

## 9. Dependencias

- **Golden de dashboard** para P1 (decisión C-7, pendiente desde el MVP).
- **Motor de formularios** (`DisenoFormulario`, constructor de Becas): la sensibilidad por sección se agrega sobre los grupos del diseño (`ItemDiseno`), que es el motor **compartido con Becas**; requiere análisis de impacto (`/impacto-de-cambio`).
- **`core/services/vencimientos.py`** y los comandos programados en ECOM para los avisos proactivos; correo SMTP de ECOM (ya configurado, Cambio 13).
- **App móvil (repo Chaco-mobile)** para el relevamiento ampliado (tenencia, servicios) y la verificación pendiente del MVP.
- **Emergencia**: comparte `ReservaPlaza`, `Estadia` y la señal `estadia_egresada`; el traslado, la espera y las derivaciones no pueden romper los puntos de extensión del Cambio 468.
- **Organigrama oficial** del Ministerio (pendiente desde el 16/09) para alcance por subsecretaría y tableros por rol.

---

## 10. Fuera de alcance

- Programa **Merenderos** (borrado, Cambio 452), salvo decisión en contrario.
- Lo que la propuesta ya dejaba fuera de toda la Versión 2 (§7 de la propuesta): inventario y stock, medicación, historial clínico, RRHH, control de acceso físico, layout interactivo y apps de cocina/lavadero/mantenimiento, Tablero de Comando central, planes de contingencia (hoy parcialmente cubiertos por el módulo Emergencia), Línea 102 como circuito propio, portal ciudadano de merenderos.
- Rediseño del ABM de Roles (decisión C-12: proyecto aparte).
- Mapa embebido (decisión C-14).
- Impedir capturas de pantalla (técnicamente imposible; ver nota de la propuesta §4.7).

---

## 11. Preguntas abiertas

Las 1 a 6 son nuevas; las 7 a 15 vienen de la §8.2 de la propuesta y siguen sin respuesta registrada.

| # | Pregunta | Responsable | Estado |
|---|---|---|---|
| 1 | ¿Merenderos vuelve en la Versión 2 o queda definitivamente fuera tras el Cambio 452? | PM / Ministerio | Abierta |
| 2 | ¿Qué presupuesto y qué bloques (A–D) aprueba el Ministerio para esta segunda etapa, y en qué orden? | PM / Ministerio | Abierta |
| 3 | Derivaciones: ¿se generaliza la `Derivacion` de Emergencia o se crea una entidad propia de Dispositivos? | PM + desarrollo | Abierta |
| 4 | Ambulatoria: ¿una persona puede tener dos seguimientos ambulatorios en dispositivos distintos a la vez? | Ministerio (Abordaje Psicosocial) | Abierta |
| 5 | ¿Los avisos proactivos por correo reemplazan la decisión PM 13 para todas las reglas o solo para algunas? ¿Quiénes reciben cada uno? | PM / Ministerio | Abierta |
| 6 | ¿El informe oficial del relevamiento necesita firma (digital u ológrafa) o basta el PDF numerado? | Ministerio | Abierta |
| 7 | Quién autoriza un ingreso por encima de la capacidad, y hasta qué límite | Ministerio | Abierta |
| 8 | Qué tipos exigen autorización previa, quién la otorga y por cuánto tiempo vale | Ministerio | Abierta |
| 9 | Préstamo: ¿la plaza prestada cuenta como disponible? (la regla de 12/24 h ya está implementada) | Ministerio | Abierta |
| 10 | Qué roles ven cada nivel de información sensible y qué secciones de cada formulario corresponden a cada nivel | Ministerio (Salud, CIS N.º 3) | Abierta |
| 11 | Fortalecimiento Familiar: ¿cupos, turnos o sin plazas? | Ministerio | Abierta |
| 12 | Albergues y contención nocturna: ¿tipo propio o variante de Abordaje Psicosocial? | Ministerio | Abierta |
| 13 | Bitácora: qué tipos de novedad son obligatorios en el pase de guardia y cuántos días se aceptan para regularizar | Ministerio | Abierta |
| 14 | Derivaciones a organismos externos: ¿destino de egreso o derivación con seguimiento? | Ministerio | Abierta |
| 15 | Escala de criticidad, estados del relevamiento y catálogo de motivos de egreso (hoy son defaults a confirmar) | Ministerio | Abierta |

---

## 12. Orden de magnitud (referencia, no cotización)

Derivado de las horas de **desarrollo** por módulo de la estimación original (§11.3, 626 h de desarrollo sobre 827 totales), descontando lo que el código ya tiene. Sirve para dimensionar los bloques; la cotización formal se hace al cerrar las preguntas.

| Bloque | Módulos de origen | Desarrollo original del módulo | Pendiente estimado |
|---|---|---:|---:|
| A · Circuito completo de la persona | M3 (resto), parte de M7 (reglas por tipo) | 110 + ~15 | ~70 h |
| B · Ficha, sensibilidad y turno | M4 (resto), M5 (resto), parte de M7 (sensibilidad, separación) | 88 + 32 + ~15 | ~80 h |
| C · Red y conducción | M6, M8, M9, M10 (resto), parte de M7 (subsecretaría) | 28 + 22 + 12 + 20 + ~10 | ~80 h |
| D · Institución y edificio | M1 (resto), M14 (resto), M15 (resto), M16, M17 | 44 + 48 + 44 + 28 + 32 | ~120 h |
| | | | **~350 h de desarrollo** |

A eso se suman, con la proporción de la estimación original, QA (~12 %), diseño (~5 %, incluida la golden de dashboard), análisis, despliegue y capacitación: del orden de **450–500 h totales**. Merenderos (M11–M12, 50 h de desarrollo) no está incluido.

---

## 13. Próximos pasos

1. Cerrar con el PM las preguntas 1–3 y 5 (son internas o de alcance) y llevar las demás a una reunión con el Ministerio.
2. Publicar la versión cliente de este punteo en `docs/client/funcionalidades/` (`/analisis:publicar`) cuando el PM lo apruebe.
3. Con las preguntas del bloque elegido cerradas, crear en GitHub la épica «Dispositivos v2 — segunda etapa», un análisis por bloque y sus sub-issues (método de `AGENTS.md`, en Backlog).

---

## 14. Historial de cambios del análisis

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-17 | Versión inicial | Pedido de punteo de lo que quedó afuera del MVP y análisis de la segunda etapa |
