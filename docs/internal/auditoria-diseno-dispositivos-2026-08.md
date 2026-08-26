# Auditoría de diseño funcional y front — Programa Dispositivos

**Fecha:** 26/08/2026
**Alcance:** las 22 plantillas de `programas/templates/programas/dispositivos/` (17) y
`programas/templates/programas/admisiones/` (5), leídas contra `dispositivos_urls.py`,
`views/dispositivos_legajo.py`, `views/admisiones.py`, `views/dispositivos_config.py`,
`programas/models/__init__.py`, los servicios del programa y el shell
`templates/includes/base.html`.
**Marco:** `.claude/agents/chaco-design-system.md` (inventario y canon visual backoffice),
`.claude/agents/chaco-design-reviewer.md` (método) y `AGENTS.md` § *Cambios de interfaz*.
**Modo:** solo lectura. No se modificó ni una línea de código productivo.

**Antecedente obligado.** El [Cambio 36](requerimientos.md) (19/08/2026) ya diagnosticó
este programa y ejecutó dos de seis hallazgos (badges de estado y solapas reales). Esta
auditoría **no rehace ese trabajo**: verifica que lo hecho sigue en pie, confirma que los
cuatro pendientes registrados siguen abiertos y amplía el diagnóstico a lo funcional, al
circuito operativo completo y a las pantallas de admisión, que en aquella pasada se
miraron pero no se tocaron.

---

## 1. Resumen ejecutivo

Dispositivos ya no se ve mal: el Cambio 36 le puso badges de color a los siete estados y
convirtió las anclas disfrazadas en solapas reales, y eso resolvió la queja original.
Lo que queda no es un problema de apariencia sino de **circuito**: la pantalla está
prolija y el flujo tiene agujeros. La configuración —`_field.html` y los parciales de
formulario compartidos entre la página completa y el modal— es la mejor pieza del módulo
y, paradójicamente, la que menos se reusa: ocho formularios reimplementan a mano el
bloque que ya existe al lado.

Las tres cosas que más duelen:

1. **El F-00 es de escritura únicamente.** Todo el módulo `config/` existe para definir
   secciones, campos obligatorios y adjuntos del formulario de ingreso; se completa en la
   admisión y en el traslado, y **ninguna pantalla lo muestra después**. El detalle
   incluso publica un indicador «Completitud F-00 · Amarillo» que señala un problema que
   el operador no puede ni mirar ni corregir.
2. **Hay tres formas de perder o duplicar información sin que la UI lo diga:** el
   traslado sin cama deja a la persona alojada en el origen y en espera en el destino sin
   marca en ninguna de las dos pantallas; el parte diario pisa el de otro turno con el
   mismo mensaje de éxito; y eliminar un campo de tipo o rompe con 500 o deja huérfanas
   las respuestas históricas.
3. **Ninguna lista del programa pagina**, contra Becas, que sí lo hace en
   `views/revision.py:159` y `views/relevamientos.py:457`. El padrón provincial entero se
   renderiza en una sola página.

Como referencia de nivel, Becas está claramente arriba en paginación, permisos resueltos
en la vista y reutilización de includes. Pero **no como molde visual**: en confirmaciones
Dispositivos está mejor parado que Becas —usa SweetAlert2, la pieza canónica condicionada,
mientras Becas sigue sobre `ModernModal`, clasificado *Legacy solo mantenimiento*—, así
que varias propuestas de acá apuntan a extraer un include propio, no a copiar el de Becas.

**Auditoría mecánica:** el enunciado indica 0 errores y 0 warnings de
`scripts/design_audit.py` sobre las dos carpetas, coherente con lo registrado en el
Cambio 36 antes de tocar nada. No se pudo reejecutar en esta sesión (el intérprete del
venv requiere aprobación interactiva); nada de lo hallado acá depende de esa corrida,
porque todo está fuera de lo que el script puede ver.

---

## 2. Mapa de la superficie

Las 22 plantillas. Para las **piezas parciales** la clasificación es la del inventario del
agente canónico (contrato reutilizable). Para las **páginas completas** se usa la misma
escala leída como *arquetipo*: `Canónico reutilizable` = sirve de molde para una pantalla
nueva; `Legacy solo mantenimiento` = funciona y se conserva, pero no se propaga;
`Duplicado o conflictivo` = compite con otro contrato del repo o del propio módulo.

| # | Ruta | Para qué sirve | Clasificación | Evidencia |
|---|---|---|---|---|
| 1 | `dispositivos/_estado_badge.html` | Badge de los 7 estados del legajo | **Canónico reutilizable** | Consumido por `legajo/list.html:36` y `legajo/detail.html:18`; contrato `dispositivo` en contexto; variantes de `nodo-badges.css`; calcado de `becas/relevamientos/_estado_badge.html` |
| 2 | `dispositivos/_cama_estado_badge.html` | Badge de los 4 estados de cama | **Canónico reutilizable** | Consumido por `legajo/detail.html:113`; mismo contrato con `cama` |
| 3 | `legajo/list.html` | Padrón de dispositivos con filtros y exportes | **Duplicado o conflictivo** | Consume bien el filtro canónico (`data-dynamic-list-filters`, `base.html:362`), pero su tabla (`:36`) no sigue la tabla densa canónica, `divide-border` no existe en `static/custom/css/tailwind.css`, y `views/dispositivos_legajo.py:70` no define `paginate_by` |
| 4 | `legajo/detail.html` | Centro operativo del dispositivo | **Legacy solo mantenimiento** | Solapas Alpine correctas del Cambio 36 (`:59-82`), pero `role="tab"` sin `tabpanel`, motor de confirmación embebido (`:139-172`) y métricas fuera del patrón (`:50-53`). Se conserva; no se copia |
| 5 | `legajo/form.html` | Alta y edición del legajo | **Duplicado o conflictivo** | Submit interceptado que puede bloquear sin feedback (`:60-81`) y bloque de campo propio (`:10`) que compite con `config/_field.html` |
| 6 | `legajo/cama_form.html` | Editar una cama | **Legacy solo mantenimiento** | Correcto y chico; repite el bloque de campo (`:8`) |
| 7 | `legajo/camas_form.html` | Alta masiva de camas | **Legacy solo mantenimiento** | Ídem (`:9`); único form del legajo que sí muestra `non_field_errors` (`:8`) |
| 8 | `legajo/parte_diario.html` | Parte diario F-01 | **Duplicado o conflictivo** | `<main>` anidado sobre el del shell (`:4` vs `base.html:104`), `{{ field.errors }}` sin estilo (`:13-15`) y métricas debajo del submit (`:18`) |
| 9 | `config/tipo_list.html` | Listado de tipos de dispositivo | **Legacy solo mantenimiento** | Repite los desvíos de tabla de `legajo/list.html` (`:34`) sobre un conjunto acotado de configuración |
| 10 | `config/tipo_detail.html` | Shell del detalle + motor AJAX/modal/confirm | **Duplicado o conflictivo** | Motor de modal propio (`:61-165`): `data-edit-url`/`data-edit-modal` no aparecen en ningún otro archivo del repo; segundo handler de confirmación del módulo (`:234-255`). Pendiente 1 del Cambio 36 |
| 11 | `config/tipo_form.html` | Alta/edición de tipo, página completa | **Canónico reutilizable** | Header + surface + `{% include _tipo_form_fields %}` (`:16`); mismos campos que el modal, un solo origen |
| 12 | `config/campo_form.html` | Alta/edición de campo, página completa | **Canónico reutilizable** | Ídem (`:16`). Reserva: su JS (`:27-37`) duplica `tipo_detail.html:47-59` |
| 13 | `config/_tipo_detail_content.html` | Contenido del detalle, re-renderizable por AJAX | **Canónico reutilizable** | Re-render server-side desde `dispositivos_config.py:25-36`; único lugar del módulo con `btn-tertiary btn-back-circle` (`:4-8`) y con estado vacío con acción primaria (`:76-80`). Reserva: el `<form class="hidden">` de `:36` existe solo para alimentar al JS |
| 14 | `config/_tipo_form_fields.html` | Campos del formulario de tipo | **Canónico reutilizable** | Compartido por `tipo_form.html:16` y `_edit_modal.html:34`; expone `data-error` por campo para la validación AJAX |
| 15 | `config/_campo_form_fields.html` | Campos del formulario de campo | **Canónico reutilizable** | Compartido por `campo_form.html:16` y `_edit_modal.html:36`; agrupa `opciones_texto` bajo `data-opciones` (`:9`) |
| 16 | `config/_edit_modal.html` | Shell del modal de edición | **Duplicado o conflictivo** | Cuarto contrato de modal del repo (compite con `ModernModal` y con los modales Alpine de Becas); `data-reset="false"` (`:29`) que su propio motor nunca lee |
| 17 | `config/_field.html` | Bloque label + control + ayuda + error | **Canónico reutilizable** | La mejor pieza del módulo: marca de obligatorio (`:3`), `help_text` (`:6`) y caja de error direccionable (`:7-8`). Solo la usan los 2 parciales de config |
| 18 | `admisiones/admitir.html` | Alta de admisión + F-00 + cama/espera | **Duplicado o conflictivo** | Select de cama armado a mano fuera de Django Forms (`:12`), contra `CLAUDE.md` § Convenciones; dos botones de envío que compiten con ese mismo select (`:13`); bloque F-00 duplicado con `traslado.html:6` |
| 19 | `admisiones/egreso.html` | Registrar egreso | **Legacy solo mantenimiento** | Funciona; minificada en una sola línea, sin eyebrow y con ancho distinto al resto (`max-w-2xl`) |
| 20 | `admisiones/traslado.html` | Traslado en dos pasos | **Duplicado o conflictivo** | Repite entero el bloque F-00 de `admitir.html:11` (`:6`) y no expone el estado pendiente que su propio flujo genera (`services/admisiones.py:204-212`) |
| 21 | `admisiones/espera.html` | Lista de espera del dispositivo | **Legacy solo mantenimiento** | Permiso evaluado dentro del `for` (`:1`), sin paginación (`views/admisiones.py:251`), vacío como `<p>` suelto |
| 22 | `admisiones/promover.html` | Promover de espera a cama | **Legacy solo mantenimiento** | La más limpia de las cinco; repite el bloque de campo (`:1`) |

**Reparto:** 8 canónicas reutilizables (todas del par badges + config), 7 legacy de
mantenimiento, 7 duplicadas o conflictivas.

---

## 3. Hallazgos

Ordenados por prioridad y, dentro de cada una, por cantidad de pantallas afectadas.

### 🔴 Bloqueante

---

#### B1. El F-00 se carga y no hay ninguna pantalla que lo muestre

**Evidencia:** `programas/models/__init__.py:746` (`respuestas_f00 = models.JSONField`),
`programas/models/__init__.py:873-883` (`ArchivoAdmision`), captura en
`admisiones/admitir.html:11` y `admisiones/traslado.html:6`, indicador en
`legajo/detail.html:53`, tabla de admisiones en `legajo/detail.html:125`.
Búsqueda sobre todas las plantillas del repo: `respuestas_f00`, `archivos_f00`,
`motivo_egreso`, `destino_egreso` y `origen_traslado` **no aparecen en ninguna**. El único
lector de `respuestas_f00` en todo el código es `services/indicadores.py:69`.

**Qué pasa hoy:** el operador completa el F-00 —secciones, campos obligatorios y adjuntos
definidos en `config/`— al admitir y al trasladar. Después no existe ningún detalle de
admisión: la tabla del detalle muestra persona, cama, ingreso y dos acciones, y el nombre
de la persona ni siquiera es un enlace. Los archivos subidos (`ArchivoAdmision`) no se
listan en ningún lado. Los motivos y destinos de egreso tampoco.

**Impacto en el operador:** el dato del ingreso es de escritura únicamente. Todo el
esfuerzo de configurar tipos y campos no tiene devolución. Y el indicador «Completitud
F-00 · 60% · Amarillo» del detalle señala un problema sin ofrecer ninguna vía para ver de
quién falta qué, ni para completarlo: `F00DinamicoForm` solo se instancia en
`AdmisionCreateView` y `TrasladoAdmisionView`.

**Propuesta:** una pantalla de detalle de admisión (`dispositivos:admision_detalle`) que
renderice el F-00 agrupado por sección —reusando `config/_field.html` en modo lectura— con
sus adjuntos, los datos de egreso/traslado y la traza de la estadía. Enlazarla desde el
nombre de la persona en `legajo/detail.html:125` y en `espera.html`, y desde el indicador
de completitud hacia el listado de admisiones incompletas. Si además se quiere completar
el F-00 después del ingreso, la misma pantalla lo habilita.

**Esfuerzo:** alto.

---

#### B2. El traslado sin cama deja a la persona contada dos veces y ninguna pantalla lo dice

**Evidencia:** `services/admisiones.py:204-212` (sin cama, `poner_en_espera` en el destino
y el origen queda intacto en `ALOJADO`), `views/admisiones.py:357-361` (aviso por toast y
redirect al origen), `models/__init__.py:757-764` (`origen_traslado`),
`services/admisiones.py:248-249` (al promover, recién ahí se cierra el origen).
`origen_traslado` no se renderiza en ninguna plantilla.

**Qué pasa hoy:** si el destino no tiene cama libre, la persona queda **simultáneamente**
alojada con cama en el origen y en la lista de espera del destino. El origen la sigue
mostrando como una estadía normal en `legajo/detail.html:125`, con las acciones «Egreso» y
«Traslado» disponibles otra vez; el destino la muestra en `espera.html` como una más de la
cola. El único aviso es el toast «Destino sin cama: la persona quedó en espera y el origen
sigue alojado», que dura 7 segundos y aparece sobre la pantalla del origen.

**Impacto en el operador:** la ocupación del origen y la cola del destino se leen mal en
las dos puntas. Pasados esos 7 segundos no queda rastro en la interfaz, y dos operadores
distintos pueden actuar sobre la misma persona sin saber lo que hizo el otro. Es el mayor
riesgo operativo del módulo.

**Propuesta:** badge «Traslado pendiente a {destino}» en la fila de la admisión de origen
y «Viene de {origen}» en la fila de la espera del destino, ambos con enlace cruzado al otro
dispositivo; y en el origen, deshabilitar «Traslado» —con motivo visible— sobre una
admisión que ya tiene un traslado pendiente.

**Esfuerzo:** medio.

---

#### B3. El parte diario pisa el de otro turno con el mismo mensaje de éxito

**Evidencia:** `views/admisiones.py:179-183` (`turno = request.GET.get("turno")`; sin turno
el filtro no encuentra nada y el formulario sale vacío),
`services/registro_diario.py:58-67` (`get_or_create` y, si ya existía, sobreescritura de
`observaciones`, `observaciones_generales` y `firmado_por`), `views/admisiones.py:201`
(mismo mensaje para alta y para pisada), `legajo/parte_diario.html` (no lista los partes
del día).

**Qué pasa hoy:** se entra desde el botón del detalle (`legajo/detail.html:23`), que no
lleva `?turno`, y aparece un formulario en blanco. Si el operador elige un turno que otra
persona ya cargó, se reemplazan las observaciones y la firma de ese turno, y el sistema
responde «Parte mañana guardado con valores calculados» — idéntico a cuando lo crea.
La pantalla nunca muestra qué turnos del día ya están cargados ni quién los firmó.

**Impacto en el operador:** pérdida silenciosa del registro de otro agente en el documento
operativo diario del dispositivo, que es justamente el que después alimenta el indicador
de actualización.

**Propuesta:** encabezar la pantalla con los tres turnos del día y su estado (cargado por
quién y a qué hora, o vacío), y entrar en modo edición explícito («Editar el parte de la
mañana») con aviso de que se reemplaza lo cargado; distinguir el mensaje de creado del de
actualizado.

**Esfuerzo:** medio.

---

#### B4. Eliminar un campo de tipo: 500 si tiene archivos, historial huérfano si no

**Evidencia:** `views/dispositivos_config.py:219` (`campo.delete()` sin captura),
`models/__init__.py:877` (`ArchivoAdmision.campo` es FK con `on_delete=PROTECT`),
`models/__init__.py:746` + `services/indicadores.py:34-37` (las respuestas se guardan
indexadas por `str(campo.pk)`), `config/_tipo_detail_content.html:62-67` (el confirm dice
«Esta acción no se puede deshacer»).

**Qué pasa hoy:** dos desenlaces, ninguno bueno. Si alguna admisión subió un archivo para
ese campo, `campo.delete()` levanta `ProtectedError` sin capturar y el operador cae en una
página de error 500 **después** de haber confirmado la acción destructiva. Si no hay
archivos, el borrado procede y las respuestas históricas quedan como claves huérfanas en
el JSON de cada admisión: el dato sigue en la base pero ya no hay definición que lo
nombre, así que es ilegible para siempre. La completitud se recalcula sobre los campos
vigentes, de modo que el histórico también cambia de sentido hacia atrás.

**Impacto en el operador:** contradice el principio del programa —«historial permanente,
sin borrar registros», recogido en el perfil de Dispositivos del agente canónico— y en el
peor caso lo deja frente a un 500 sin saber si la acción se aplicó.

**Propuesta:** convertir el borrado en baja lógica (`activo=False` en
`CampoTipoDispositivo`), que saque el campo de los formularios nuevos y lo conserve para
leer el histórico. Mientras tanto —y en cualquier caso—, capturar `ProtectedError` y
responder con un toast que diga cuántas admisiones lo usan, y cambiar el texto del confirm
para informar el impacto real antes de confirmar.

**Esfuerzo:** medio.

---

#### B5. El alta se bloquea sin decir nada cuando el código duplicado está fuera de alcance

**Evidencia:** `legajo/form.html:28` (`mostrarCoincidencias` esconde el aviso si
`!data.coincidencias.length`), `legajo/form.html:64` (`if (data.codigo_duplicado) return;`),
`views/dispositivos_legajo.py:133-136` (filtra `coincidencias` por `dispositivos_visibles`
pero deja `codigo_duplicado` como vino), `services/dispositivos.py:172-175`.

**Qué pasa hoy:** cuando el código ya existe en un dispositivo que el usuario **no** tiene
en su alcance territorial, la respuesta trae `codigo_duplicado: true` con `coincidencias:
[]`. El aviso se oculta, el submit se cancela y no pasa absolutamente nada: ni mensaje, ni
error de campo, ni botón deshabilitado. El operador puede hacer clic en «Guardar borrador»
indefinidamente. Le ocurre siempre, además, a quien tiene `dispositivo.crear` sin
`dispositivo.ver`, porque la línea 136 le devuelve `none()` en todos los casos.

**Impacto en el operador:** callejón sin salida completo en el alta, y del peor tipo: la
interfaz no da ninguna pista de que hay un problema ni de a quién pedirle ayuda.

**Propuesta:** que `mostrarCoincidencias` muestre el aviso cuando `codigo_duplicado` es
verdadero aunque no haya coincidencias visibles («El código ya está en uso por una
institución fuera de tu alcance; pedí el traspaso o usá otro código»), con `role="alert"`
en el contenedor de `legajo/form.html:9` —que hoy se llena por JS sin anunciarse a lectores
de pantalla—, y que el botón quede deshabilitado con motivo visible en lugar de un submit
que no hace nada.

**Esfuerzo:** bajo.

---

### 🟠 Importante

---

#### I1. Ocho formularios reimplementan el bloque de campo que ya existe como include en el propio módulo

**Evidencia:** `config/_field.html` (label, marca de obligatorio, `help_text` y caja de
error direccionable) contra las copias manuales de `legajo/form.html:10`,
`legajo/camas_form.html:9`, `legajo/cama_form.html:8`, `admisiones/admitir.html:7` y `:10`,
`admisiones/egreso.html:1`, `admisiones/traslado.html:5`, `admisiones/promover.html:1` y
`legajo/parte_diario.html:13-15`.

**Qué pasa hoy:** el include canónico solo lo consumen los dos parciales de configuración.
Las consecuencias son verificables, no estéticas: **ningún** formulario fuera de config
marca los campos obligatorios (el `*` solo aparece en los bucles del F-00, tomado de
`item.campo.obligatorio`), **ninguno** muestra `help_text`, y las clases de label divergen
(`text-sm font-semibold` fuera de config, `text-[13px] font-semibold` adentro).
`legajo/form.html` además no imprime `non_field_errors`, mientras `camas_form.html:8` sí.

**Impacto en el operador:** en el alta del legajo no hay forma de saber qué es obligatorio
hasta que el envío a validación falla (ver I6), y un error no asociado a un campo puede
quedar invisible.

**Propuesta:** extender `config/_field.html` con las dos variantes que faltan (checkbox y
campo con contenedor) y consumirlo desde los ocho formularios, agregando el bloque de
`non_field_errors` que ya usan los parciales de config.

**Esfuerzo:** medio.

---

#### I2. Cinco tratamientos distintos del estado vacío, ninguno canónico

**Evidencia:** `legajo/list.html:38` y `config/tipo_list.html:58-61` (h2 + p centrados, sin
ícono ni acción), `config/_tipo_detail_content.html:76-80` (el único con acción primaria),
`legajo/detail.html:115`, `:125` y `:131` (`<p>` suelto), `espera.html` (`<p>` suelto),
`admisiones/admitir.html:11` (`{% empty %}` inline).

**Qué pasa hoy:** el canon pide bloque centrado con ícono, título de 17px, descripción y
acción primaria cuando corresponde; solo una de las seis lo cumple. Además, el vacío del
listado dice «No hay dispositivos en tu alcance» **también cuando el motivo real es un
filtro aplicado**, porque el `{% if dispositivos %}` no distingue los dos casos.

**Impacto en el operador:** un mensaje que atribuye a permisos lo que es un filtro manda a
pedir un alcance que ya se tiene. Y en el detalle, «Todavía no hay camas configuradas» no
ofrece el botón para crearlas aunque el usuario tenga el permiso.

**Propuesta:** un parcial `dispositivos/_estado_vacio.html` con ícono, título, descripción
y acción opcional, consumido por las seis; y en el listado, texto distinto cuando
`request.GET` trae filtros, con enlace a limpiarlos.

**Esfuerzo:** medio.

---

#### I3. Las cinco pantallas de admisión no comparten estructura

**Evidencia:** anchos `max-w-4xl` en `admitir.html:4`, `traslado.html:4` y `espera.html:1`
contra `max-w-2xl` en `egreso.html:1` y `promover.html:1`; eyebrow de sección solo en
`admitir.html:6`; `tracking-tight` en el `h1` solo en `admitir.html:6`; el enlace de vuelta
dice «← Volver al dispositivo» (`admitir.html:5`), «← Volver» (`egreso.html:1`,
`traslado.html:4`, `espera.html:1`) y «← Volver a la espera» (`promover.html:1`); tres de
las cinco están minificadas en una sola línea y dos formateadas. Ninguna usa el
`btn-tertiary btn-back-circle` que el propio módulo ya aplica en
`config/_tipo_detail_content.html:4-8` y que el canon fija para headers de detalle.

**Qué pasa hoy:** cada pantalla del circuito de admisión inventó su propio encabezado. El
operador que recorre admitir → egresar → trasladar → promover cambia de ancho de columna y
de forma de volver en cada paso.

**Impacto en el operador:** fricción baja pero constante, en las pantallas que más se usan.
Y para quien mantiene, tres archivos minificados que no se pueden diffear con sentido.

**Propuesta:** un parcial `admisiones/_header.html` con back-circle, eyebrow, título y
bajada; mismo contenedor `max-w-4xl` para las cinco; desminificar los tres archivos de una
línea en el mismo cambio.

**Esfuerzo:** medio.

---

#### I4. Ninguna lista del programa pagina

**Evidencia:** `views/dispositivos_legajo.py:70-98` (`DispositivoListView` sin
`paginate_by`), `views/admisiones.py:249-254` (espera sin límite),
`views/dispositivos_config.py:72` (tipos sin límite), `legajo/detail.html:113` y `:125`
(camas y admisiones activas completas). Contraste: `views/revision.py:159` y `:191`, y
`views/relevamientos.py:457` en Becas sí definen `paginate_by`.

**Qué pasa hoy:** el padrón provincial entero se renderiza en una sola página, sin
contador de resultados ni control de tamaño. Lo mismo con la lista de espera y con la
tabla de camas de un dispositivo grande.

**Impacto en el operador:** una lista larga se vuelve inmanejable en pantalla y lenta de
cargar; sin contador, tampoco puede saber cuántos resultados devolvió su filtro.

**Propuesta:** `paginate_by` en el listado de dispositivos y en la lista de espera con el
patrón de Becas, incluyendo el contador de resultados; camas y admisiones del detalle
acotadas con un «ver todas» que lleve a su propia vista paginada.

**Esfuerzo:** medio.

---

#### I5. Tres tablas, tres estilos, y una clase que no existe

**Evidencia:** `legajo/list.html:36` y `config/tipo_list.html:24-34`
(`th px-5 py-3 font-semibold`, sin uppercase, sin 11px, sin `tracking`, filas sin
`hover:bg-secondary`) contra `legajo/detail.html:113` y `:125` (`px-3 py-2` / `px-3 py-3`,
una tercera densidad) y contra `espera.html:1` (`px-4 py-3`, una cuarta). La tabla densa
canónica está inventariada con evidencia en `becas/config/_segmentos_table.html`.
Además, `divide-border` —usada en `legajo/list.html:36` y `config/tipo_list.html:34`— **no
existe en el CSS compilado**: `divide-y` sí está generado en
`static/custom/css/tailwind.css`, `divide-border` no.

**Qué pasa hoy:** cuatro densidades de tabla en un módulo de seis pantallas con tabla, y un
color de separador que nunca se aplicó porque la clase no llegó a generarse.

**Impacto en el operador:** las tablas no se leen como el mismo sistema al saltar de
pantalla, y el escaneo de encabezados es más lento sin el contraste del uppercase de 11px.

**Propuesta:** un parcial de tabla densa del módulo (wrapper `overflow-x-auto`, header
`bg-secondary`, `th` uppercase 11px con `tracking-[.05em]`, `td` de 13px, filas con
`hover:bg-secondary`) aplicado a las cuatro, y reemplazar `divide-border` por
`border-t border-light` en las celdas, que es lo que usa el canon.

**Esfuerzo:** medio.

---

#### I6. «Enviar a validación» falla sin decir qué falta

**Evidencia:** `services/dispositivos.py:178-181` calcula la lista `faltantes` y **la
descarta**, levantando siempre «Completá los campos obligatorios antes de validar el
dispositivo»; `services/dispositivos.py:17-25` define los siete campos exigidos (`tipo`,
`codigo`, `nombre`, `localidad`, `domicilio`, `responsable_nombre`, `contacto_telefono`);
`legajo/form.html:10` no marca ninguno como obligatorio; `legajo/detail.html:87-93` los
muestra con `—` cuando están vacíos, sin señalar que bloquean la validación.

**Qué pasa hoy:** el operador crea el borrador sin saber qué hace falta, aprieta «Enviar a
validación», recibe un toast genérico de 7 segundos y vuelve al formulario a adivinar cuál
de los siete campos quedó vacío.

**Impacto en el operador:** ciclo de prueba y error en la transición de estado más
frecuente del legajo.

**Propuesta:** incluir los `verbose_name` de los campos faltantes en el `ValidationError`;
marcar esos siete con `*` en el alta (resuelto de una si se aplica I1); y en el detalle,
mostrar una alerta inline canónica «Faltan N datos para poder validar» con los nombres y un
enlace a editar, en lugar de dejar que el error aparezca recién al intentar la transición.

**Esfuerzo:** bajo.

---

#### I7. Los indicadores operativos no se leen: «Sin datos» en rojo y el vocabulario del enum

**Evidencia:** `legajo/detail.html:52-53` — la cadena
`{% if VERDE %}…{% elif AMARILLO %}…{% else %}text-fg-danger{% endif %}` captura también
`SIN_DATOS`, que existe en `services/indicadores.py:54` y `:71`. Y `legajo/detail.html:50-53`
y `:110` imprimen `{{ …semaforo|title }}`, o sea «Verde» / «Amarillo» / «Rojo», que son los
valores internos de `services/camas.py:31-33`.

**Qué pasa hoy:** dos de los cuatro indicadores del detalle muestran «Sin datos» **pintado
del mismo rojo que un valor crítico**. Y los cuatro dicen cosas como «45% · Verde», que
repite en palabras lo que el color ya dice y usa el vocabulario del enum, no el del
operador. Se agrega una contradicción: con cero camas operativas,
`services/camas.py:27-33` da `porcentaje = 0` y semáforo `VERDE`, así que la franja muestra
«Ocupación 0% · Verde» al lado de «Disponibilidad 0% · Rojo» —`services/indicadores.py:11`
devuelve `ROJO` para ese mismo caso—, dos lecturas opuestas del mismo hecho.

**Impacto en el operador:** el panel que debería dar la salud del dispositivo de un vistazo
enciende alarmas falsas y se contradice a sí mismo. Es la primera franja de la pantalla y
la que más se mira.

**Propuesta:** rama explícita para `SIN_DATOS` con `text-body-subtle`; reemplazar la
palabra del semáforo por una lectura operativa («normal», «exigida», «crítica»); y tratar
`operativas == 0` como «Sin camas» en vez de verde.

**Esfuerzo:** bajo.

---

#### I8. Dos motores de confirmación con contratos incompatibles dentro del mismo módulo

**Evidencia:** `legajo/detail.html:139-172` usa `data-confirm` sobre un `<form>` envolvente
y soporta `data-requires-motivo`; `config/tipo_detail.html:234-255` usa `data-confirm-url`,
arma el formulario desde cero, no soporta motivo y toma el token con
`document.querySelector('[name=csrfmiddlewaretoken]').cloneNode()` **sin guarda de nulo**,
apoyándose en el `<form class="hidden">` que existe solo para eso en
`config/_tipo_detail_content.html:36`.

**Qué pasa hoy:** el mismo módulo tiene dos formas distintas de pedir una confirmación, con
nombres de atributo diferentes, y no son intercambiables. Es el pendiente 3 del Cambio 36,
sigue abierto. La copia de config es además frágil: si algún día se saca ese formulario
oculto, «Desactivar» y «Eliminar» dejan de hacer nada sin ningún error visible.

**Nota de reconciliación:** el Cambio 36 propuso tomar como modelo
`becas/_confirm_js.html`. Al leerlo, ese include está montado sobre `ModernModal`, que el
agente canónico clasifica como *Legacy solo mantenimiento*, mientras SweetAlert2 —lo que
usa Dispositivos— figura como *Canónico reutilizable, condicionado*. La salida correcta no
es copiar Becas sino extraer el include propio.

**Impacto en el operador:** ninguno visible hoy; el costo es de mantenimiento y de riesgo
de divergencia futura sobre acciones destructivas.

**Propuesta:** un `dispositivos/_confirm_js.html` único sobre SweetAlert2 que soporte las
dos formas (botón dentro de form y botón con URL), con `data-requires-motivo` y guarda de
nulo en el token, consumido por las dos pantallas; eliminar el formulario oculto.

**Esfuerzo:** bajo/medio.

---

#### I9. `|length` sobre querysets y permisos evaluados fila por fila

**Evidencia:** `legajo/detail.html:75` (`admisiones_activas|length`) y `:123`
(`esperas_activas|length`); `views/dispositivos_legajo.py:169-171` construye
`esperas_activas` con `select_related("admision__ciudadano")` y el template la usa **solo**
para contar. En `espera.html:1`, `{% puede_operar_dispositivo %}` se invoca **dentro** del
`{% for %}`, una vez por fila.

**Qué pasa hoy:** para pintar el contador de la solapa se traen todas las filas de espera
con su ciudadano; y la lista de espera resuelve el mismo permiso tantas veces como
personas tenga la cola. El método de revisión del agente canónico pide explícitamente
datos, permisos y contadores resueltos en la vista, y ausencia de `|length` sobre
querysets.

**Impacto en el operador:** carga más lenta del detalle y de la espera a medida que crece
el dispositivo; sin efecto visible mientras los números sean chicos.

**Propuesta:** `.count()` en la vista para los dos contadores, y calcular el permiso una
sola vez en `EsperaAdmisionListView` pasándolo por contexto.

**Esfuerzo:** bajo.

---

#### I10. La solapa Camas se muestra en tipos que no manejan camas y termina en un vacío sin salida

**Evidencia:** `legajo/detail.html:65-70` y `:98-116` renderizan la solapa siempre;
`maneja_camas` se consulta **únicamente** en `views/dispositivos_legajo.py:173`, y solo
para decidir si se muestra el botón «Agregar camas». No aparece en ninguna plantilla.

**Qué pasa hoy:** en un dispositivo de tipo ambulatorio, el detalle muestra igual la solapa
«Camas 0», cuatro métricas en cero, el mensaje «Todavía no hay camas configuradas» y ningún
botón para resolverlo, porque `puede_gestionar_camas` es falso por tipo. Además la franja
de indicadores encabeza con «Ocupación 0% · Verde» (ver I7).

**Impacto en el operador:** un estado vacío permanente que parece un pendiente de carga y
no lo es, sin ninguna explicación de por qué no hay acción disponible.

**Propuesta:** ocultar la solapa Camas y la métrica de ocupación cuando
`tipo.maneja_camas` es falso, pasando el flag al contexto; para esos tipos, la franja de
indicadores queda con actualización y completitud.

**Esfuerzo:** bajo.

---

#### I11. Las solapas no tienen panel asociado ni conservan el estado

**Evidencia:** `legajo/detail.html:59-82` declara `role="tablist"`, `role="tab"` y
`:aria-selected`, pero los paneles de `:85`, `:98`, `:120` y `:129` no tienen
`role="tabpanel"`, ni `id`, ni `aria-controls`, y los botones no manejan `tabindex` ni
navegación con flechas. El estado vive solo en `x-data` (`:10`), así que todos los
redirects al detalle —`views/dispositivos_legajo.py:323` y `:368`, `views/admisiones.py:239`
y `:361`— devuelven al operador a la solapa «Datos».

**Qué pasa hoy:** un lector de pantalla anuncia pestañas cuyo contenido no está asociado a
ellas. Y quien agrega camas, edita una cama, registra un egreso o confirma un traslado
vuelve siempre al principio, teniendo que reabrir la solapa en la que estaba trabajando.

**Impacto en el operador:** un clic extra en cada operación del circuito, sobre la pantalla
que más se repite; y semántica incompleta para navegación asistida.

**Propuesta:** `id` + `aria-controls` + `role="tabpanel"` + `aria-labelledby` en los cuatro
paneles, roving `tabindex` con flechas; y leer la solapa inicial de `?tab=`, agregándolo a
los cuatro redirects.

**Esfuerzo:** medio.

---

#### I12. El parte diario está clavado en el día de hoy

**Evidencia:** `views/admisiones.py:166`, `:181` y `:193` usan `timezone.localdate()` en los
tres lugares, sin ningún parámetro de fecha; `models/__init__.py:818` guarda `fecha` como
campo real y `:834` ordena por `-fecha`.

**Qué pasa hoy:** no hay forma de cargar el parte de ayer ni de consultar los de días
anteriores, aunque el modelo lo soporta perfectamente. Un dispositivo que no cargó el fin
de semana no puede regularizar, y el indicador «Actualización» —que mide exactamente los
días sin parte, `services/indicadores.py:52-64`— se queda en rojo sin salida.

**Impacto en el operador:** un semáforo que acusa un incumplimiento que la interfaz no le
permite subsanar, y ninguna vía para revisar el historial operativo del dispositivo.

**Propuesta:** selector de fecha acotado (por ejemplo los últimos 7 días) en el parte, y un
listado de partes del dispositivo por fecha y turno, enlazado desde la solapa de
Admisiones.

**Esfuerzo:** medio.

---

#### I13. El Historial muestra códigos internos y nombres de campo de la base

**Evidencia:** `legajo/detail.html:131` imprime `{{ traza.accion }}` en crudo, y los valores
que se guardan son `CREADO`, `EDITADO` (`services/dispositivos.py:131` y `:145`),
`ENVIADO_VALIDACION`, `VALIDADO`, `OBSERVADO`, `RECHAZADO`, `INACTIVADO` y `CERRADO`
(`services/dispositivos.py:209`, `:222`, `:238`, `:254`, `:267`, `:279`). Y
`models/__init__.py:626-630` arma `detalle_legible` con la **clave del campo**, no con su
`verbose_name`.

**Qué pasa hoy:** la solapa Historial muestra líneas como «ENVIADO_VALIDACION» seguidas de
«contacto_telefono: 3624… → 3624…». En la misma tarjeta, dos líneas más abajo, los estados
sí están humanizados vía `estado_anterior_legible`.

**Impacto en el operador:** la auditoría del legajo —que es una de las razones de ser del
programa— se lee como un log de sistema y no como el historial institucional que pretende
ser.

**Propuesta:** un parcial de etiqueta de acción, con el mismo criterio que los badges de
estado del Cambio 36 (el mapa se lee en el template); y usar `verbose_name` en
`detalle_legible`, que ya tiene el modelo a mano.

**Esfuerzo:** bajo.

---

#### I14. Seis botones de exportación compiten con la acción primaria del listado

**Evidencia:** `legajo/list.html:15-21` — seis enlaces `btn-secondary btn-sm` (padrón,
ocupación y movimientos × CSV/Excel) seguidos del `btn-brand` de «Nuevo dispositivo».

**Qué pasa hoy:** la acción principal de la pantalla queda al final de una hilera de siete
botones de aspecto casi idéntico. En pantalla chica, con `flex-wrap`, el bloque ocupa buena
parte del alto visible antes de que aparezcan los filtros y la tabla.

**Impacto en el operador:** cuesta encontrar el botón de alta, que es lo que más se usa, y
en móvil la lista queda debajo del pliegue.

**Propuesta:** un único control «Exportar» con menú de las seis combinaciones, dejando
`btn-brand` solo, siguiendo el criterio del canon de mantener los exportes separados de la
vista.

**Esfuerzo:** bajo.

---

### 🟡 Cosmético

---

#### C1. El `h1` sigue partido dentro del módulo

`legajo/list.html:10`, `config/tipo_list.html:9` y `config/_tipo_detail_content.html:11`
usan `style="font-size:28px; letter-spacing:-0.5px"`, mientras `legajo/detail.html:17` y las
otras once páginas usan `text-3xl font-extrabold tracking-tight`. El Cambio 36 registró que
la convención está partida en el propio canon y que Dispositivos no inventó el problema,
pero dentro del módulo la mezcla es 3 contra 11 y se puede unificar hacia el lado
mayoritario sin tocar Becas. **Esfuerzo: bajo.**

#### C2. Las stat cards siguen achatadas

`legajo/detail.html:50-53` y `:107-110`, más `parte_diario.html:18`: doce tarjetas con
`rounded-lg border-light p-4`, sin sombra ni ícono, contra el
`rounded-xl border-base shadow-sm` con ícono de color del canon. Es el pendiente 2 del
Cambio 36, sigue abierto. **Esfuerzo: bajo.**

#### C3. La lógica de opciones del campo está duplicada

`config/tipo_detail.html:47-59` y `config/campo_form.html:27-37` implementan el mismo
mostrar/ocultar de `data-opciones` en dos copias. **Esfuerzo: bajo.**

#### C4. `<main>` anidado en el parte diario

`legajo/parte_diario.html:4` abre un `<main>` dentro del que ya provee el shell en
`templates/includes/base.html:104`: dos landmarks `main` en el mismo documento.
**Esfuerzo: bajo.**

#### C5. Errores de Django sin estilo en el parte diario

`legajo/parte_diario.html:12`, `:13`, `:14` y `:15` usan `{{ …errors }}` directo, que
renderiza `<ul class="errorlist">`; `errorlist` no está definido en ningún CSS de
`static/custom/css/`, así que sale con los bullets y márgenes por defecto del navegador. El
resto del módulo usa `text-fg-danger`. **Esfuerzo: bajo.**

#### C6. En la configuración conviven dos modelos de interacción

Editar tipo o campo va por AJAX, con toast y sin recarga
(`config/tipo_detail.html:194-232`); «Desactivar» y «Eliminar» hacen submit clásico con
recarga completa (`config/tipo_detail.html:246-253` y `views/dispositivos_config.py:138-144`,
`:215-221`). En la misma pantalla, dos acciones vecinas se comportan distinto.
**Esfuerzo: bajo.**

#### C7. «Cancelar» en la edición del legajo tira a la lista, no al detalle

`legajo/form.html:10` apunta siempre a `dispositivos:lista`, mientras el enlace de vuelta de
`:7` sí distingue y vuelve al detalle cuando se está editando. Cancelar una edición saca al
operador del dispositivo en el que estaba. **Esfuerzo: bajo.**

#### C8. `data-reset="false"` es un atributo muerto

`config/_edit_modal.html:29` lo declara, pero el motor de `config/tipo_detail.html:167-232`
nunca lo lee; sí lo hace `becas/_ajax_js.html`, de donde se copió. Residuo de la copia que
señaló el Cambio 36. **Esfuerzo: bajo.**

#### C9. Sin estado de carga en el envío del alta

`legajo/form.html:60-81` intercepta el submit y espera un `fetch` antes de enviar, sin
deshabilitar el botón ni mostrar progreso; la variable `enviando` evita el reenvío pero no
comunica nada. El propio módulo lo hace bien en `config/tipo_detail.html:94-95`, con
`aria-busy` y `pointer-events-none`. **Esfuerzo: bajo.**

---

## 4. Lo que está bien

No todo hay que tocarlo, y algunas cosas conviene llevárselas a otros programas.

- **El par `_field.html` + `_tipo_form_fields.html` / `_campo_form_fields.html` es el mejor
  patrón de formulario del repo.** Un solo origen de marcado sirve a la página completa
  (`tipo_form.html:16`, `campo_form.html:16`) y al modal AJAX (`_edit_modal.html:34-36`), y
  la caja `data-error` por campo es lo que permite que la validación AJAX pinte errores sin
  recargar (`tipo_detail.html:206-224`). Es exactamente la clase de include mínimo que el
  agente canónico pide extraer, y ya está hecho.

- **Los badges de estado como parcial por entidad** (`_estado_badge.html`,
  `_cama_estado_badge.html`): el mapa de color se lee en el template, junto al dato, en vez
  de esconderse en un templatetag de Python. Buena decisión del Cambio 36 y buen precedente
  para cualquier entidad con más de tres estados.

- **El modal de configuración, pese a ser un motor paralelo, es accesible.** Foco inicial
  priorizando el campo inválido (`tipo_detail.html:68-71`), trampa de Tab (`:135-165`),
  Escape, devolución del foco al disparador (`:83-87`) y degradación limpia a página
  completa si el JS falla, porque los controles de cierre son `<a href>` reales
  (`_edit_modal.html:19-22`, `:41-43`). Si algún día se unifica el motor de modales, este es
  el comportamiento a preservar.

- **Toda acción mutante es POST con CSRF y confirmación**, y las transiciones de estado
  están centralizadas en `services/dispositivos.py:184-198` con `select_for_update` y
  validación de origen. La UI no inventa transiciones: expone exactamente las que el
  servicio permite, condicionadas por estado y permiso (`legajo/detail.html:25-38`).

- **La auditoría es aditiva por diseño.** `TrazaDispositivo`
  (`models/__init__.py:564-655`) bloquea `update`, `delete` y `bulk_update` a nivel de
  queryset y de instancia, y el detalle la expone en su propia solapa. Es el modelo a
  seguir para cualquier programa que necesite historial institucional.

- **Los indicadores se calculan en servicios** (`services/indicadores.py`,
  `services/camas.py`) y llegan resueltos al template, sin conteos ni lógica en el HTML.
  El problema de I7 es de presentación, no de arquitectura.

- **El listado consume el filtro dinámico canónico** (`legajo/list.html:25`,
  `data-dynamic-list-filters`, cargado por el shell en `base.html:362` con
  `templates/components/list_filters.html`), que aporta agregar/quitar filtros y limpiar
  sin que el módulo mantenga nada propio.

- **Todas las tablas van dentro de `overflow-x-auto`**: ninguna rompe el ancho en móvil.
  Es lo mínimo, pero está en las seis.

- **La configuración ya usa el sistema de toasts canónico** (`window.toast` en
  `tipo_detail.html:41`, `:44`, `:202`, `:221`) en lugar de mensajes inline, y el resto del
  módulo usa `messages` de Django, que el shell convierte en toast (`base.html:106-113`).

---

## 5. Tasks candidatas

Agrupadas por lo que conviene resolver junto. **Solo la lista: los issues los crea el PM.**

| # | Task | Agrupa | Esfuerzo |
|---|---|---|---|
| T1 | **Cerrar el circuito del F-00**: detalle de admisión con respuestas por sección, adjuntos y datos de egreso; enlaces desde la tabla de admisiones, la lista de espera y el indicador de completitud | B1 | Alto |
| T2 | **Parte diario operable**: turnos del día visibles con su firma, edición explícita en vez de pisada silenciosa, selector de fecha y listado histórico; de paso el `<main>` anidado y los errores sin estilo | B3, I12, C4, C5 | Medio/alto |
| T3 | **Hacer visible el traslado pendiente**: badges cruzados origen/destino con enlace, y bloqueo del segundo traslado sobre una admisión ya en tránsito | B2 | Medio |
| T4 | **Sanear las acciones destructivas de la configuración**: baja lógica del campo, captura de `ProtectedError`, texto de confirmación con impacto real y unificación del modelo de interacción | B4, C6 | Medio |
| T5 | **Desatascar el alta del legajo**: aviso de duplicado fuera de alcance con `role="alert"`, campos obligatorios marcados, faltantes nombrados al validar, cancelar al detalle y estado de carga en el submit | B5, I6, C7, C9 | Bajo/medio |
| T6 | **Un solo bloque de campo para todo el módulo**: extender `config/_field.html` y consumirlo desde los ocho formularios, con `non_field_errors` incluido | I1 | Medio |
| T7 | **Escala de las listas**: paginación y contador en listado y espera, `.count()` en vez de `|length`, permiso fuera del bucle, camas y admisiones acotadas en el detalle | I4, I9 | Medio |
| T8 | **Indicadores legibles**: `SIN_DATOS` neutro, vocabulario operativo en lugar del enum, «Sin camas» en vez de verde, solapa Camas oculta si el tipo no las maneja, stat cards al canon | I7, I10, C2 | Bajo/medio |
| T9 | **Listado y tablas al canon**: parcial de tabla densa para las cuatro, `divide-border` fuera, exportes en un solo menú, estados vacíos canónicos y mensaje distinto cuando hay filtro | I2, I5, I14 | Medio |
| T10 | **Homogeneizar las cinco pantallas de admisión**: header compartido con back-circle, mismo ancho, mismos textos de vuelta, desminificar los tres archivos de una línea | I3 | Medio |
| T11 | **Solapas accesibles y con estado**: `tabpanel`/`aria-controls`/flechas y `?tab=` preservado en los cuatro redirects al detalle | I11 | Medio |
| T12 | **Un motor de confirmación único en Dispositivos**: `_confirm_js.html` propio sobre SweetAlert2 con las dos formas, sin el formulario oculto; de paso el JS de opciones duplicado y `data-reset` muerto | I8, C3, C8 | Bajo/medio |
| T13 | **Historial en idioma de operador**: etiquetas de acción y `verbose_name` en el detalle de cambios; unificar el `h1` del módulo | I13, C1 | Bajo |
| T14 | **Orden de los campos de tipo de dispositivo**: aplicar el autonumerado sin repetidos del Cambio 23, cuyo pendiente registrado es exactamente este módulo | — | Bajo |

**Dependencias sugeridas:** T6 antes que T5 y T10 (los tres tocan los mismos formularios);
T1 antes que T8 (el indicador de completitud recién tiene sentido cuando hay dónde ir a
mirar); T4 antes de cualquier cambio sobre el motor de modales de configuración.

---

## Anexo — Estado de los pendientes del Cambio 36

| Pendiente | Estado hoy | Dónde quedó |
|---|---|---|
| 1. Motor de modal AJAX propio en la configuración | **Abierto** | Mapa §2 (filas 10 y 16), I8 |
| 2. Stat cards achatadas | **Abierto** | C2 |
| 3. Dos handlers de confirmación duplicados | **Abierto y divergido** (`data-confirm` vs `data-confirm-url`) | I8 |
| 4. La solapa de Dispositivos no se embebe en el legajo | **Abierto** — fuera del alcance de esta auditoría: es decisión de producto sobre `services/solapas.py`, no de template | — |

Lo ejecutado en el Cambio 36 sigue en pie y verificado: los badges de los siete estados en
`legajo/list.html:36` y `legajo/detail.html:18`, los de cama en `:113`, las solapas Alpine
reales en `:59-82`, los indicadores como franja fija fuera de las solapas en `:44-55` y
«Parte diario» entre las acciones del encabezado en `:23`.
