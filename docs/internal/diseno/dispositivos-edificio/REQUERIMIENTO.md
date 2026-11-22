# Requerimiento: el edificio como unidad operativa (Dispositivos)

> Para: la sesión coordinadora (modo juez) y los implementadores que despache.
> Prioridad del PM: **es lo primero que se implementa**.
> Regla del PM: **tiene que quedar tal cual el diseño.**

## 0. Dónde está el diseño

- Canvas aprobado (versión 15): https://claude.ai/artifact/6dki6Z9kJYJXb27Wr9B24m
  - Se lee con la herramienta `Artifact`, `action: "read"`.
- Copia local de cada pantalla: `C:\Users\mkdir\.claude\tareas\dispositivos-edificio\diseno\*.dc.html`
  - El orden y los títulos están en `canvas.json`.
- **Cómo leer un `.dc.html`:**
  - El cuerpo es el markup final, con **las clases reales del repo**. Se armó con el CSS compilado de producción, copiando `_page_header`, `_stat_card`, `_tarjeta_edificio`, `_mapa_plazas`, `nodo-tables`, `_menu_fila`, `_modal_header`/`_modal_footer`, `_field` y `nodo-toast`.
  - `<sc-for list="{{ x }}" as="y">` equivale a un `{% for %}`; `<sc-if value="{{ c }}">` equivale a un `{% if %}`.
  - Los textos y datos de ejemplo están en el arreglo de `renderVals()` del `<script>` final. **Los rótulos, los textos de ayuda y los textos de botones son los definitivos.** Los nombres entre corchetes (`[Operador 1]`) son datos de ejemplo.
  - El shell (sidebar y navbar) está dibujado para dar contexto: **no se toca**, se usa `includes/base.html`.

| Archivo | Pantalla |
|---|---|
| `Main.dc.html` | 1 · Ficha de la institución con sus edificios a la vista |
| `Edificio.dc.html` | 2 · Página del edificio, solapa Sectores y plazas |
| `Edificio-Acciones.dc.html` | 2b · «Más acciones» abierto (con Emergencia) |
| `Edificio-Estadias.dc.html` | 3 · Solapa Estadías |
| `Edificio-Kits.dc.html` / `Edificio-Kits-Detalle.dc.html` | 4 / 4b · Kits: tabla de entregas → detalle con recepción |
| `Edificio-Equipo.dc.html` | 5 · Solapa Equipo |
| `Equipo-Sumar-1..4.dc.html` | 5a–5d · Proceso «Sumar persona»: modal, búsqueda, Crear persona, resultado con toast |
| `Edificio-Edilicio.dc.html` / `Edificio-Edilicio-Detalle.dc.html` | 6 / 6b · Estado edilicio: tabla de relevamientos → detalle |
| `Edificio-Historial.dc.html` | 7 · Solapa Historial |

## 1. Problema y decisión

Hoy la ficha de la institución opera todo: plazas, estadías, kits y equipo, con un filtro por edificio. En la realidad **cada edificio maneja sus plazas, sus estadías, sus kits y su Emergencia**. El PM eligió la **opción A**:

- La institución muestra sus edificios.
- Cada edificio tiene su **página propia** con su operación.

### Decisiones tomadas por el PM (22-nov-2026) — no se discuten

1. **Institución → página propia del edificio.** La operación del día (Ingresar persona, Bitácora, Emergencia) vive en el edificio.
2. **El operador ve solo su institución.** En un predio compartido, lo de la otra institución **no aparece**: ni plazas, ni estadías, ni kits, ni equipo.
3. **La ficha de la institución no lleva «Bitácora del turno» ni «Ingresar persona».**
4. **Emergencia (Llegadas, Kits) va en «Más acciones» del edificio.**
5. **El encabezado del edificio no se comprime.** Lleva una franja de datos en 4 columnas, en una sección aparte.
6. **Patrón lista → detalle.** Kits y Estado edilicio muestran primero una tabla, y cada fila tiene un botón que abre el detalle.
7. **«Sumar persona» desde el edificio** usa el modal existente «Agregar persona al edificio» (Cambio 556, variante `edificio_fijo`), con «Crear persona» si la persona no existe.

### Consecuencia técnica de la decisión 2

La página del edificio **siempre está en el contexto de una institución**. Eso elimina la ambigüedad del predio compartido: todo se filtra por `dispositivo = pk` **y** `edificio = edificio_pk`.

- **Ruta nueva anidada:** `dispositivos/<int:pk>/edificios/<int:edificio_pk>/?tab=<solapa>`. Nombre sugerido: `dispositivos:edificio_operativo`.
- **404** si el edificio no está vinculado a esa institución o no está en el alcance del usuario. Se reusan `puede_operar_edificio` y `alcance_de_edificios` de `programas/services/dispositivos.py`.
- **Las acciones mantienen sus rutas actuales por institución** (`<pk>/...`) y reciben `?edificio=<id>` para preseleccionar o fijar el edificio. No se duplican vistas de operación.
- **La ficha global existente `edificios/<id>/` (`EdificioDetailView`, Cambio 555) queda como está**, para el módulo Edificios. No es esta pantalla.
- **Sin migraciones.** Las columnas ya existen: `Sector.edificio`, `EntregaKit.edificio`, `EntradaBitacora.edificio`, `InspeccionEdificio.edificio`, `MiembroEquipoDispositivo.alcance/edificios`. `Estadia` se deriva por `plaza__sector__edificio_id`.

## 2. Lote = las piezas primero (CLAUDE.md)

Antes de la primera solapa, el juez releva y construye estas piezas, cada una con su ficha en `.claude/design/` y su fila en `.claude/agents/chaco-design-system.md`:

1. **Página de detalle «Edificio operativo».** Es una pantalla nueva, así que se **clona la golden del arquetipo detalle** y se declara el *Plan de pantalla*. Lleva migas, título y código, acciones, franja de datos, alerta, indicadores y solapas, igual que `Edificio.dc.html`.
2. **`_tarjeta_edificio` extendida.** Suma estado edilicio, barra de ocupación (`_barra_umbral`), una lista de datos con Disponibles / Kits / Equipo y un pie «Abrir edificio» (`Main.dc.html`).
3. **Franja de datos del edificio**, en 4 columnas: `dl p-6 grid gap-6 sm:grid-cols-2 lg:grid-cols-4`.
4. **Parcial de los modales del Equipo** (Sumar, Crear persona, Cambiar alcance). Hoy dependen del contexto de `DispositivoDetailView` y hay que extraerlos para montarlos en las dos pantallas.

Una pieza que traiga una clase, una variante o un valor que no está en el inventario **no se escribe**: vuelve al juez y del juez al PM.

## 3. PRs: un implementador por solapa

El **PR 0 va primero y solo**. Del 1 al 7 se paralelizan, con **máximo 3 a la vez**. El historial va último, porque tiene una decisión abierta.

### PR 0 — Página del edificio: estructura, encabezado, indicadores y acciones
- **Diseño:** `Edificio.dc.html` (encabezado y solapas) y `Edificio-Acciones.dc.html`.
- **Contenido:**
  - Ruta y vista nuevas, con el contexto institución + edificio.
  - Migas: Dispositivos › Instituciones › institución › edificio.
  - Título y código (`EDI-055`).
  - Acciones: **Ingresar persona** (brand), **Bitácora**, **Más acciones**.
  - Franja de datos: Institución, Domicilio, Estado edilicio, Equipo en turno.
  - Alerta informativa «Predio compartido», solo si el edificio tiene otra institución. **No** muestra datos de la otra institución.
  - Los 4 indicadores con sus rótulos exactos: **Ocupación**, **Plazas operativas**, **Reservadas o prestadas**, **Disponibles**. Salen de `indicadores_de_plazas` y `ocupacion.conteo_del_edificio`, filtrados por edificio e institución.
  - Las 6 solapas con su contador: Sectores y plazas, Estadías, Kits, Equipo, Estado edilicio (con su badge de estado) e Historial. Cada solapa se carga por `?tab=`.
- **«Más acciones»** tiene 6 ítems, en el orden y con los textos de `Edificio-Acciones.dc.html`, incluidos **Emergencia → Llegadas** y **Emergencia → Kits** (rutas `emergencia_llegadas` y `dispositivo_kits` con `?edificio=`).
- **Ingresar persona** abre el asistente actual (`ingreso`) con el edificio fijado. Bitácora (`BitacoraTurnoView`) recibe `?edificio=`.
- **Permisos:** ver el edificio con `dispositivo.ver` + alcance; cada acción con su capacidad (`dispositivo.admitir`, `dispositivo.bitacora`, `emergencia.recibir_kit`…). Una acción sin capacidad no se muestra.
- **Aceptación:**
  - Un operador con alcance a un solo edificio entra solo a ese, y los demás dan 404.
  - En un predio compartido no se ve nada de la otra institución.
  - Se respeta el presupuesto de queries, con test en `scripts/perf_budgets.json`.

### PR 1 — Solapa Sectores y plazas
- **Diseño:** `Edificio.dc.html`, el cuerpo de la solapa.
- **Contenido:**
  - Se reusa `sectores/_cuerpo.html` y `sectores_con_plazas` (Cambio 558), con el edificio fijo y **sin** el filtro «Edificio».
  - Lleva la leyenda (`_leyenda_plazas`) y el mapa por sector.
  - Los modales (reubicar, reservar, fuera de servicio) se mantienen y apuntan a las rutas `<pk>/plazas/...` de la institución.
- **Aceptación:** muestra solo los sectores del edificio y de esa institución. Las acciones vuelven a esta solapa.

### PR 2 — Solapa Estadías
- **Diseño:** `Edificio-Estadias.dc.html`. Tabla con persona, ingreso y plaza (o «Sin plaza»), y menú de fila.
- **Contenido:** `estadias_del_dispositivo` + `Q(plaza__sector__edificio_id=edificio)`. El menú de fila y sus acciones (egreso, cambio de plaza, detalle) son las actuales.
- **Abierto:** cómo se muestran las estadías **sin plaza** (ver §4.1).

### PR 3 — Solapa Kits: tabla → detalle
- **Diseño:** `Edificio-Kits.dc.html` y `Edificio-Kits-Detalle.dc.html`.
- **Lista:** una sola tabla «Entregas a este edificio» con columnas Entrega (número + ítems), Estado (badge), Enviada, Recibida (fecha + quién), Diferencia y acción.
  - La entrega **en camino** lleva el botón brand **«Recibir»**.
  - El resto lleva el botón secundario **«Ver detalle»**.
  - Orden: de la más nueva a la más vieja.
- **Detalle:** el formulario actual de recepción (`RecibirKitView`, servicio `recibir_entrega`, sin cambios de regla) dentro de la solapa, con el enlace «Volver a las entregas».
  - Para una entrega ya recibida, el detalle muestra lo recibido y el remito, sin el formulario.
- **Datos:** `entregas_de(dispositivo, usuario)` más un parámetro `edificio=` exacto.
- **Abierto:** las entregas viejas con `edificio=NULL` (ver §4.2).

### PR 4 — Solapa Equipo + proceso «Sumar persona»
- **Diseño:** `Edificio-Equipo.dc.html` y `Equipo-Sumar-1..4.dc.html`.
- **Tabla:** Persona, Rol, Contratación, Alcance, Responsable y menú de fila (Cambiar alcance, Marcar como responsable, Dar de baja).
  - Lista a quienes tienen alcance a **toda la institución** o tienen este edificio en `edificios`.
  - Los tipos de contratación usan los rótulos del modelo.
- **«Sumar persona»** abre el modal **«Agregar persona al edificio»** (variante `edificio_fijo` del Cambio 556):
  - Persona y rol: buscador con sugerencias `nombre apellido — rol`.
  - Botón **Crear persona**.
  - Tipo de contratación.
  - «Edificio: …» fijo.
  - Interruptor «Es responsable del dispositivo».
  - Pie: Cancelar / **Sumar al Equipo**.
- **Crear persona** abre su modal: DNI, Nombre, Apellido, Correo, Rol, Tipo de contratación, edificio fijo y responsable. El pie dice **Crear y sumar al Equipo**.
- **Resultado:** la fila nueva aparece en la tabla y sale un toast de éxito con `window.toast()`. El texto está en `Equipo-Sumar-4.dc.html`.
- **Depende de** la pieza 4 del §2 (el parcial de los modales).

### PR 5 — Solapa Estado edilicio: tabla → detalle
- **Diseño:** `Edificio-Edilicio.dc.html` y `Edificio-Edilicio-Detalle.dc.html`.
- **Lista:** encabezado «Relevamientos del edificio» con el badge de estado y **Crear relevamiento** (la ruta `relevamiento_asignar` existente).
  - Tabla con Relevamiento (número + «Último»), Fecha, Relevó, Criticidad (badge), Observaciones, Fotos y **Ver detalle**.
- **Detalle:** enlace «Volver a los relevamientos», título «Relevamiento REL-xxxx», badge de criticidad y **Descargar informe** (`relevamiento_informe`).
  - Debajo: datos del relevamiento, observaciones y registro fotográfico **de ese relevamiento**.
- **Datos:** `registro_de_relevamientos`. Lo que se muestra respeta `inspecciones_visibles`.

### PR 6 — Ficha de la institución
- **Diseño:** `Main.dc.html`.
- **Contenido:**
  - Sección **«Edificios · N»** en el cuerpo de la ficha, no dentro de una solapa, con la `_tarjeta_edificio` extendida (pieza 2) y **Abrir edificio** → ruta del PR 0.
  - Alerta de advertencia cuando un edificio no tiene plazas disponibles. Texto: «Anexo Sur no tiene plazas disponibles».
  - Los indicadores operativos de la institución.
  - Solapas **Datos / Personas alojadas / Equipo / Historial**.
  - Se quitan de la ficha «Ingresar persona» y «Bitácora».
- **Cuidado:**
  - Es la pantalla con más snapshots y presupuestos de queries: `normalizar_solapa` y los links viejos `?tab=sectores|estadias|infraestructura` tienen que redirigir a la solapa equivalente o al edificio.
  - Si se toca una pieza canónica o una golden, el mismo diff actualiza su ficha.

### PR 7 — Solapa Historial (último)
- **Diseño:** `Edificio-Historial.dc.html`. Línea de tiempo `_linea_tiempo` con el punto coloreado por tipo y el texto «cuándo · turno · quién / título · detalle».
- **Abierto:** qué eventos entran (ver §4.3). No se implementa hasta que el PM conteste.

## 4. Decisiones del §4: CERRADAS por el PM el 22-nov-2026 — las tres recomendaciones quedan aprobadas tal cual

Ya no hay nada que preguntar: el PR 7 (Historial) queda desbloqueado.

1. **Estadías sin plaza** (PR 2). Una estadía sin plaza no tiene edificio.
   - *Recomendación:* mostrarlas **en la ficha de la institución** («Personas alojadas»), y en la solapa del edificio no. El diseño muestra una fila «Sin plaza», pero sin un dato que la ate al edificio, aparecería en todos.
2. **Entregas de kit con `edificio=NULL`** (PR 3).
   - *Recomendación:* no aparecen en ningún edificio. Quedan visibles desde Emergencia → Kits de la institución, para quien tiene alcance a toda la institución (regla del Cambio 523).
3. **Eventos del historial del edificio** (PR 7).
   - *Recomendación:* todo lo que se deriva al edificio. Estadías (ingreso, egreso, cambio y reserva de plaza, por plaza→sector→edificio), plazas y sectores del edificio (fuera de servicio, alta y baja), kits del edificio, relevamientos, bitácora del edificio y cambios de Equipo con ese edificio.
   - Las trazas de la institución sin edificio quedan en el historial de la institución.
   - Sin migración, salvo que se quiera guardar el edificio en la traza.

## 5. Cierre de cada PR (las condiciones de siempre)

- **Antes:** `scripts/requerimientos.py --tag dispositivos` y `--ver 523 555 556 558`, para no contradecir lo ya decidido.
- **UI:** se construye con el agente `chaco-frontend` y se revisa con `chaco-design-reviewer`.
- **Gates:**
  - `design_audit.py --ratchet` con 0 nuevos.
  - `--arquetipo detalle` sobre la pantalla nueva.
  - `compile_templates.py --bloques`.
  - `check_design_agent.py --base origin/development`.
- **Verificación:** `manage.py check`, tests (incluidos los de alcance por edificio verificados **por mutación**), presupuestos de queries y `npm run build:tailwind` si aparece una clase nueva.
- **Registro:** cada PR registra su Cambio en `docs/internal/requerimientos/<N>.md`. Las ramas paralelas toman número **de a una**.
- **Merge:** `/auditoria pr <N>` antes de cada merge.
- **Cotejo visual:** el juez compara cada solapa contra su `.dc.html` lado a lado. Ofrecer al PM verificarlo con Playwright en local antes de abrir el PR.
- **Al final del lote:** copiar `diseno/` y este archivo a `docs/internal/diseno/dispositivos-edificio/` en el primer PR, para que el diseño viva en el repo.
