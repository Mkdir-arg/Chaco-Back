# Tablero de Dispositivos — diseño, funcionalidades e implementación

Fecha: 2026-11-08. Estado: borrador para revisión del PM. Solo documentación: no hay código ni issues.

Insumos: el mockup aprobado `docs/superpowers/specs/2026-11-08-tablero-dispositivos/mockup-tablero.dc.html`
(datos de ejemplo; lienzo privado https://claude.ai/artifact/WrZGCzTFd7ey1pmRqqfWRJ), el sistema de
diseño (`.claude/agents/chaco-design-system.md`, `.claude/design/`) y el código de `programas/`.
La factibilidad del mapa con Leaflet está en
[`2026-11-04-emergencia-design.md` §7.1](2026-11-04-emergencia-design.md); acá se reusa, no se reescribe.

Convención: **«verificado»** = leído en el repo (ruta citada). **«A confirmar»** = no hay evidencia en el
código o depende de una decisión del PM.

## 0. Qué es y para quién

Una pantalla de gestión **solo del programa Dispositivos** (la red completa dentro del alcance de quien
mira), que responde en un vistazo: ¿cuánta gente hay alojada, dónde quedan plazas, qué dispositivo está
tensionado, qué relevamientos vencieron, qué hay que atender hoy? Se descartó una versión transversal a
todos los programas.

| Actor | Qué hace con el tablero |
|---|---|
| Coordinación de la red (usuario con `dispositivo.ver` sobre el programa) | Mira la red, filtra por tipo y localidad, decide dónde derivar y a quién llamar. Es el usuario principal. |
| Administración del programa (`CAPS_ADMIN_PROGRAMA`) | Igual, más acceso a configuración de tipos y umbrales (pantalla ya existente: `dispositivos:tipos`). |
| Operador de un dispositivo | Ve solo su dispositivo (el alcance lo recorta); el tablero le sirve poco, pero no se le oculta. |
| `is_superuser` | Bypass total, como en todo `core/rbac.py`. |

Dos solapas: **Resumen** (todo el trabajo diario) y **Mapa** (Leaflet + OSM cargado a pedido).

## 1. Qué ya existe (verificado)

| Pieza | Dónde | Estado |
|---|---|---|
| Censo de plazas, 3 consultas fijas sin `Trunc*` | `programas/services/ocupacion.py` · `ocupacion_de_plazas(dispositivos)` → `Censo` (`por_dispositivo`, `total`, `de()`), con `Conteo` (`totales`, `fuera_de_servicio`, `operativas`, `ocupadas`, `reservadas`, `prestadas`, `disponibles`) | Existe |
| Nivel de tensión con umbrales del tipo | mismo módulo · `tension_de_ocupacion(conteo, tipo=)` → `Tension` (`porcentaje`, `nivel`, `tono`, `etiqueta`) | Existe. Sin `tipo` usa 60/80 (`UMBRAL_EXIGIDA`, `UMBRAL_CRITICA`) |
| Umbrales por tipo | `TipoDispositivo.umbral_ocupacion_amarillo` (default 50) y `umbral_ocupacion_rojo` (default 80), `programas/models/__init__.py` l.438; `clean()` exige amarillo < rojo | Existe, configurables |
| Semáforo de relevamientos por dispositivo | `programas/services/inspecciones.py` · `semaforos_de_dispositivos(ids)` (3 consultas fijas: `al_dia`, `por_vencer`, `vencidos`) y `programas/selectors/vencimiento_inspecciones.py` | Existe |
| Alertas por dispositivo | `programas/services/alertas_dispositivos.py` (`reservas_vencidas`, `plazas_fuera_de_servicio`, `edificios_criticos`, `relevamientos_vencidos`, `sin_turnos`) | Existe, **una consulta por dispositivo**: no sirve tal cual para la red |
| Alcance | `programas/services/dispositivos.py` · `dispositivos_visibles(user)`, `dispositivos_en_alcance(user, cap)` | Existe |
| Listado de instituciones | `programas/views/dispositivos_legajo.py` · `DispositivoListView` (`capacidad_requerida = "dispositivo.ver"`, pagina de a 25, filtros `tipo`/`estado`/`localidad` por `filtrar_dispositivos` en `programas/services/reportes.py`) | Existe: es el «Ver listado completo» |
| Sugerir personas | `programas/selectors/personas_sugeridas.py` · `sugerir_personas(texto)` (mín. 3 caracteres, tope 10, `istartswith`); vista `PersonasSugeridasView` | Existe, ver §4 |
| Estadías y reservas | `Estadia` (`fecha_ingreso`/`fecha_egreso` son `DateTimeField`), `Estadia.objects.activas()`, `dias_de_permanencia()`; `ReservaPlaza` (`hasta` `DateTimeField` nulo, `estado` VIGENTE/CONSUMIDA/LIBERADA, `vigentes()`, `abiertas()`) | Existe |
| Fechas en día argentino | `core/utils_fechas.py` (`inicio_del_dia_local`) | Existe: usarlo para «hoy» y los 14 días |
| Tablero de Becas | `programas/services/dashboard_becas.py`: JSON, caché 5 min (`CACHE_TIMEOUT=300`), clave sha256 de filtros + huella de alcance, freno de recálculo y degradación sin Redis | Patrón de referencia para el caché |
| **NO existe** | Tablero de Dispositivos; agregación de red más allá de `Censo.total`; servicio de «estadías largas»; función de «reservas por vencer» (solo `reservas_vencidas`); capacidad propia del tablero; Leaflet en `static/`; `logo` en `Dispositivo`; `municipio` (la localidad es texto libre) | — |

Hechos del modelo que condicionan el diseño:

- `Dispositivo.estado` (l.589) tiene BORRADOR, PENDIENTE_VALIDACION, **ACTIVO**, OBSERVADO, RECHAZADO,
  INACTIVO y CERRADO. **No existe `activo`.** El tablero cuenta solo `ACTIVO` (a confirmar con el PM: ¿entra
  OBSERVADO?).
- `Dispositivo.localidad` es `CharField` libre con índice; `latitud`/`longitud` son `Decimal(9,6)` nulos.
  Un dispositivo sin coordenadas no se puede ubicar en el mapa ni medir a distancia.
- Ocupada, reservada y prestada **no se guardan en `Plaza`**: se derivan de `Estadia` activa y `ReservaPlaza`
  vigente. `Plaza.tipo` ∈ CAMA / CUPO / TURNO y `Plaza.estado` ∈ OPERATIVA / FUERA_SERVICIO.
- El «relevamiento» del dispositivo es `InspeccionEdificio` (l.1926), que **cuelga del edificio**
  (`Edificio.dispositivos`, M2M). `Relevamiento` (l.3218) es el de Becas: no confundir. «Vencido», «por vencer»
  y «al día» se derivan de `fecha_vencimiento` (`DateField`); no son estados.
- Los tipos (Hogar, Parador, …) **no están sembrados en código**: los carga el PM en `dispositivos:tipos`.
  Los cinco nombres del mockup son de ejemplo.

## 2. Pantalla, bloque por bloque

Ruta propuesta: `dispositivos:tablero` bajo `config/urls.py:43` (`dispositivos/` → `programas.dispositivos_urls`).
La vista vive en `programas/views/` (archivo nuevo, p. ej. `dispositivos_tablero.py`), sin lógica de dominio;
la agregación en un servicio nuevo `programas/services/tablero_dispositivos.py`. Todo lo calculado se calcula
una vez por request sobre `dispositivos_visibles(user)` filtrado.

### 2.1 Hero

- **Muestra**: eyebrow «Programa Dispositivos · Abordaje Psicosocial», título «Red de dispositivos», bajada
  con los números («538 de 554 plazas ocupadas en 18 dispositivos de 14 localidades. 3 están sobre el umbral
  crítico de su tipo.») y la acción «Ver instituciones» → `dispositivos:lista`.
- **Datos**: ocupadas/operativas de `Censo.total`; cantidad de dispositivos y localidades distintas del
  conjunto filtrado; críticos = ver 2.3. La bajada se arma **en la vista**, no en el template
  (`.claude/design/componentes/hero_inicio.md`).
- **Reglas**: «Ninguno sobre el umbral crítico.» si no hay; «Ningún dispositivo coincide con el filtro.» si
  el filtro vacía la red.
- **Pieza**: `{% hero_inicio %}`. Hoy `HERO_PANTALLAS` está vacía (`scripts/design_audit.py:769`) y ningún
  template de producto lo usa: la ficha dice que lo estrena este tablero. Incorporar la pantalla = agregar su
  ruta a `HERO_PANTALLAS` en el mismo PR.
- **Estados**: sin permiso → 403 por el decorador; sin dispositivos en alcance → bajada vacía y estado vacío (2.5).

### 2.2 Filtros

- **Muestra**: píldoras «Tipo», «Localidad» y «Situación» (Todas / Necesitan atención), botón **Filtrar**
  visible, «Limpiar», «Actualizado a las HH:MM» y «Exportar».
- **Datos**: tipos activos de `TipoDispositivo`; localidades = valores distintos de `Dispositivo.localidad`
  dentro del alcance (texto libre: pueden venir «Resistencia» y «resistencia»; a confirmar si hay que normalizar).
- **Reglas**: lo elegido queda pendiente hasta «Filtrar» (WCAG 3.2.2, `componentes/filtros.md`).
  «Necesitan atención» deja los dispositivos con nivel crítico (o «exigida», a decidir) **o** relevamiento vencido,
  igual que `criticos` del mockup. Los filtros son GET y afectan **todos** los bloques del Resumen y el Mapa.
- **Pieza**: `components/_filtro_pildora.html` (`pildoras` armadas en la vista). **Choque a resolver**: la ficha
  pide que, con solapas, cada panel lleve su propio include con el oculto `tab` de su panel; el mockup tiene un
  solo bloque arriba de las solapas. Propuesta: un solo bloque con `ocultos=(("tab", solapa_actual),)` y que el
  filtro **no** cambie de solapa (se aparta de la ficha: pieza «salto entre solapas», §3.2). Alternativa
  conforme a la ficha: repetir las píldoras dentro de cada panel (filtran lo mismo en ambos).
- **Exportar**: no existe un export de red (`dispositivos:exportar` exporta el listado de instituciones).
  A confirmar si «Exportar» del tablero es el mismo CSV con los filtros o queda fuera de v1 (§8).

### 2.3 Franja de métricas (stat cards `variante="tablero"`)

Cinco tarjetas, **una sola franja grande** (regla de `stat_card.md`):

| Tarjeta | Cálculo | Fuente | Tono |
|---|---|---|---|
| Ocupación de la red | `ocupadas / operativas` redondeado, nota «N de M plazas» | `Censo.total` | `tension_de_ocupacion(total)` sin tipo (60/80); mockup usa 70/85: **diferencia a resolver** |
| Plazas libres | suma de `disponibles` (resta fuera de servicio, ocupadas **y reservadas**); nota «en N dispositivos» con `disponibles > 0` | `Conteo.disponibles` | `success` |
| Dispositivos críticos | cantidad con `nivel == critica`: ocupación ≥ umbral rojo **de su tipo** | `tension_de_ocupacion(conteo, tipo=d.tipo)` | `danger` si > 0 |
| Relevamientos vencidos | dispositivos con al menos un relevamiento vencido | `semaforos_de_dispositivos(ids)` → `vencidos` | `danger` si > 0 |
| Movimientos de hoy | «+ingresos / −egresos» del día argentino | `Estadia.fecha_ingreso` / `fecha_egreso` (`DateTime`), agrupado en Python | sin tono (gradiente) |

Notas que no coinciden con el mockup y hay que decidir:

- El mockup calcula libres como `capacidad − ocupadas`. El código resta además `fuera_de_servicio` y
  `reservadas`: **el tablero usa `disponibles`**, o promete plazas que ya están reservadas.
- Sin plazas operativas el porcentaje es «—», nunca 0 (`Tension.porcentaje is None`, nivel `sin_plazas`,
  precedente de `stat_card.md` P4/P19).
- Un `Conteo` con `ocupadas=None` es «sin dato», no cero: no se suma como cero.
- El vocabulario del código es **Normal / Exigida / Crítica / Sin plazas** (`_TENSION`); el mockup dice
  «En alerta» y «Crítico». Se usa el del código (pregunta 7).

### 2.4 Solapas (Resumen / Mapa)

- **Pieza**: `tabs.md` (alpine, `role="tablist"`, deep link `?tab=`), con `nodo-tabs.js` para el teclado
  (cargado una vez en `templates/includes/base.html:417`). La barra vive dentro de una `surface`; los
  paneles, aparte. El mockup respeta esto.
- **Regla**: el panel Mapa **no calcula nada propio**: usa el mismo conjunto filtrado (ver §5 para no
  duplicar consultas).

### 2.5 Estado vacío general

Con filtros que dejan la red vacía: `estado_vacio` con «Limpiar filtros» hacia la URL sin parámetros
(`request.GET|hay_filtros`, `estado_vacio.md`). Sin dispositivos en alcance (no filtro): estado vacío sin acción.

### 2.6 Necesita atención

- **Muestra**: hasta 4 alertas (`_alerta`), ordenadas por tensión descendente: «X al N %» / «X está lleno»
  (danger) y «Atención: relevamiento vencido» (warning). Pie «Mostrando 4 de 7» y «Ver en la tabla».
- **Datos**: críticos por `tension_de_ocupacion` con el tipo; relevamiento vencido por
  `semaforos_de_dispositivos`. **No** se reusa `alertas_dispositivos.py` (consulta por dispositivo).
- **Reglas**: el mockup solo genera dos clases de alerta. Existen otras tres en el servicio (reservas vencidas,
  plazas fuera de servicio, edificios críticos): **a confirmar** si entran; cada una sumaría una consulta
  agregada nueva.
- **Interacción**: «Ver en la tabla» aplica el filtro «Necesitan atención» conservando tipo y localidad.
- **Estado vacío**: «Nada pendiente».
- **Pieza**: `components/_alerta.html` (con `accion_url`/`accion_texto`; en el mockup la acción es
  «Ver plazas» → `dispositivos:sectores`, «Ver relevamiento» → `dispositivos:relevamientos`).

### 2.7 Ocupación por tipo (con umbrales del tipo)

- **Muestra**: por cada tipo: nombre, cantidad de dispositivos, «ocupadas / plazas», badge «N % · Estado», barra
  con dos marcas (alerta y crítico) y «Alerta desde X % · crítico desde Y %».
- **Datos**: suma de `Conteo` por `dispositivo.tipo`; umbrales = `umbral_ocupacion_amarillo/rojo` del tipo.
  Estado = `tension_de_ocupacion(conteo_del_tipo, tipo=tipo)`.
- **Reglas**: **crítico = ocupación ≥ umbral rojo del tipo** (no un valor fijo). La barra pinta el color por
  nivel y las marcas se ubican en `left: umbral %`. Tipos sin dispositivos en el filtro no se listan.
- **Accesibilidad**: color + ícono + texto en el badge (nunca solo color); las marcas llevan `title` y la
  leyenda las repite como texto.
- **Pieza nueva**: «barra con marcas de umbral» (§3.2).

### 2.8 Dispositivos de la red (tabla)

- **Muestra**: nombre + tipo, localidad, barra de ocupación + %, «ocupadas / capacidad», libres, estado de
  ocupación y estado de relevamiento; acciones «Ver» (`dispositivos:detalle`) y «Ver plazas»
  (`dispositivos:sectores`). Orden por defecto: **tensión** = `porcentaje − umbral rojo` descendente.
- **Datos**: `Censo.por_dispositivo` + `tension_de_ocupacion(...)` + `semaforos_de_dispositivos(ids)`.
- **Reglas**: columnas ordenables con `aria-sort` y `th-orden`; el orden se resuelve **en Python** sobre el
  conjunto ya calculado (la red tiene decenas de dispositivos, no miles; a confirmar el tamaño real).
  Relevamiento «al día / por vencer / vencido» sale del semáforo; un dispositivo **sin edificio vinculado**
  no tiene relevamiento: mostrar «Sin relevamiento» (a confirmar con el PM, el mockup no lo prevé).
- **Estados**: tabla vacía por filtro → estado vacío con «Limpiar filtros».
- **Pieza**: `tabla.md` (`.tabla`, `nodo-thead-row`, `acciones`, `nodo-icon-btn`) y badges con ícono + texto
  (`botones_badges.md`). Si la red crece, la tabla pasa a paginar con `_paginacion.html`; hoy el listado
  completo ya es `DispositivoListView` (pagina de a 25).

### 2.9 Relevamientos

- **Muestra**: cuatro mini-tarjetas: Asignados, Al día, Por vencer, Vencidos.
- **Datos**: `semaforos_de_dispositivos(ids)` (cuenta por **dispositivo**, no por inspección). Es la misma
  cuenta que la P21 (`programas/templates/programas/dispositivos/relevamientos/list.html`, l.29-32), que usa
  stat cards `variante="tablero"` en su propia pantalla.
- **Reglas / choque**: la tarjeta chica y la grande **no pueden convivir en la misma franja**
  (`stat_card.md`); acá están en otra `surface` y es lo que hace el mockup, pero «cuatro mini-tarjetas» es una
  composición no declarada: se aprueba como parte de la pieza nueva «barra/mini-stat» o se resuelve con
  `_stat_card.html` chica (`grid-cols-2`, sin la variante grande). **Recomendación**: la chica canónica.
- **Consistencia a cuidar**: «Vencidos» del KPI (2.3) y de esta tarjeta tienen que dar el mismo número; salen
  de la misma llamada.

### 2.10 Plazas libres por localidad

- **Muestra**: las 7 localidades con más plazas libres, con barra proporcional al máximo y el número.
- **Datos**: suma de `disponibles` por `Dispositivo.localidad` (texto libre).
- **Reglas**: respeta el filtro; si el filtro es una sola localidad, la lista tiene una fila (a confirmar si
  se oculta el bloque).
- **Pieza**: barra simple; mismo componente de barra que 2.7 sin marcas.

### 2.11 Ingresos y egresos (14 días)

- **Muestra**: barras pareadas por día (ingresos / egresos), eje 0–máx, leyenda con los totales y
  `aria-label` del conjunto.
- **Datos**: `Estadia.fecha_ingreso` y `fecha_egreso` (`DateTimeField`). **No existe agregación diaria.**
- **Reglas de cálculo**: ventana = los últimos 14 días argentinos (helper `core/utils_fechas.py`); **agrupar en
  Python**, nunca `TruncDate` ni `TruncWeek` (ECOM no tiene tablas de timezone: `CONVERT_TZ` devuelve NULL).
  Una consulta por cada columna con filtro por rango `[inicio, fin)` sobre un índice (a confirmar el índice
  de `fecha_ingreso`; hoy no se verificó) y conteo en memoria, o dos `values_list` acotados.
  Egreso = `fecha_egreso` no nula dentro de la ventana.
- **Accesibilidad**: el `role="img"` con el total no alcanza para ver el detalle por día; agregar la tabla
  equivalente oculta (`sr-only`) o el `title` por par. A resolver en la ficha de la pieza.
- **Pieza nueva**: gráfico de barras (§3.2). `becas-dashboard.js` usa Chart.js; **a confirmar** si se
  reusa Chart.js (ya vendorizado según §7.1 del spec de emergencia) o se dibuja con CSS puro como el mockup.

### 2.12 Buscar persona

- **Muestra**: píldora con campo de texto «DNI o apellido», botones Buscar / Limpiar; resultados con nombre,
  DNI, edad, badge (Estadía activa / Con reserva de plaza / Estadía egresada), dónde (dispositivo · sector ·
  plaza), detalle (días de estadía o vencimiento) y acciones «Ver legajo» y «Ver estadía». Hasta 5 personas;
  estadías anteriores indentadas debajo.
- **Datos**: personas = `legajos.Ciudadano` (búsqueda por DNI desde 4 dígitos o apellido desde 3 letras);
  estadías = `Estadia` (`activa`/`egresada`) y `ReservaPlaza` vigente; lugar = `Estadia.plaza` →
  `Sector` → `Dispositivo`. `sugerir_personas` existe pero **busca por prefijo y devuelve 10** y no trae
  estadías: sirve de base, no alcanza (a confirmar con el PM la regla de mínimo de caracteres).
- **Reglas**: el resultado se recorta por `dispositivos_visibles(user)`: solo se ven estadías en dispositivos
  del alcance. La búsqueda es **por envío** (botón/Enter), no mientras se escribe, y se hace por POST/GET con
  `no-store`. Mensaje de ayuda con menos de 4 dígitos / 3 letras. Una persona sin ninguna estadía visible **no**
  aparece (no se confirma ni se niega su existencia fuera del alcance).
- **Estados**: ayuda inicial, resultados (`aria-live="polite"`), vacío «Ninguna persona coincide con…».
- **Datos personales**: ver §4. Es el bloque de mayor riesgo.
- **Pieza nueva**: fila de resultado de persona (§3.2) y píldora con campo de texto (§3.2).

### 2.13 Encontrar plaza libre

- **Muestra**: píldoras «Tipo de plaza» (Cama / Cupo / Turno), «Tipo de dispositivo» y «Cerca de»
  (localidad); hasta 5 dispositivos con nombre, badge de ocupación, meta, «N libres de M · a unos X km» y las
  acciones «Reservar» y «Ver en el mapa».
- **Datos**: `Plaza.tipo` (CAMA/CUPO/TURNO, **existe en el código**) y `Conteo.disponibles` por dispositivo y por
  tipo de plaza. En el mockup el tipo de plaza se **deduce** del tipo de dispositivo (Hogar/Parador/Residencia
  → Cama, Comunidad terapéutica → Cupo, Centro de día → Turno): en el código **no hace falta ese mapeo**, se
  filtra por `Plaza.tipo` real y por `TipoDispositivo.tipos_plaza_admitidos`. El mapeo del mockup es inventado
  (pregunta 1).
- **Reglas**: solo dispositivos con `disponibles > 0` del tipo pedido. Orden: distancia ascendente y, a igual
  distancia, más libres. **La distancia necesita coordenadas**: `Dispositivo.latitud/longitud` sí existen
  (nulas); las del origen «Cerca de» **no** (la localidad es texto, no encontré coordenadas por localidad en el
  código). Opciones: (a) origen = otro dispositivo de esa localidad, (b) tabla de localidades con coordenadas,
  (c) sin distancia y orden por localidad. A decidir (pregunta 3). Distancia haversine en línea recta, con el
  pie «Distancia aproximada».
- **«Reservar»**: crear una `ReservaPlaza` exige elegir plaza y persona y existe `estadias.reservar_plaza`
  (citado en el spec de emergencia §1). El mockup no define el flujo: **a confirmar** (pregunta 2). Mientras
  tanto el botón lleva al mapa de plazas del dispositivo (`dispositivos:sectores`).
- **Estados**: vacío «Ningún dispositivo tiene plazas de ese tipo» con «Limpiar filtros».
- **Los filtros de esta herramienta son propios** (no los del tablero): afectan solo esta tarjeta.
- **Pieza nueva**: fila de plaza libre (§3.2).

### 2.14 Estadías largas y reservas que vencen

- **Muestra**: tabla con persona + DNI, dispositivo + sector/plaza, situación (badge «Estadía larga» /
  «Reserva vence hoy»), plazo («87 días» / «hoy · 18:00 h») y una acción. Respeta los filtros del tablero.
- **Datos**: estadías largas = `Estadia` `ACTIVA` con `fecha_ingreso` anterior a hoy − 60 días; reservas que
  vencen hoy = `ReservaPlaza` `VIGENTE` con `hasta` dentro del día argentino de hoy. **No hay servicio para
  ninguna de las dos** (solo `reservas_vencidas`, con el vencimiento ya pasado). Se agregan al servicio nuevo.
- **Reglas**: el umbral de 60 días es del mockup; **no hay constante ni configuración** en el código (a
  confirmar si es fijo o por tipo; propuesta: constante en el servicio, configurable después). Orden: reservas
  primero (por hora), luego estadías por antigüedad descendente. Tope (propuesta 25) con aviso «mostrando N de M»;
  la tabla no pagina.
- **Estados**: vacío «Nada por vencer».
- **Pieza**: tabla nodo; badges con ícono + texto. Las acciones del mockup («Revisar la estadía»,
  «Confirmar o liberar la reserva») llevan a pantallas existentes del detalle de estadía; **a confirmar** que
  «liberar reserva» ya existe como acción en `dispositivos:sectores`.

### 2.15 Solapa Mapa

- **Muestra**: mapa de la red con un círculo por dispositivo (color por nivel, tamaño por cantidad de plazas),
  leyenda como badges, panel «Dispositivo seleccionado» (ficha con ocupación, libres, relevamiento, «Ver
  dispositivo» y «Ver plazas») y lista «Más tensionados» (los 8 más cerca del umbral crítico de su tipo).
- **Datos**: los mismos del conjunto filtrado (2.8) más `Dispositivo.latitud/longitud`. Los dispositivos sin
  coordenadas **no se dibujan**: el contador dice «N dispositivos para ubicar» y se agrega un aviso «M sin
  ubicación» (el mockup no lo prevé). Los puntos viajan a la página una sola vez como `json_script`.
- **Reglas**: cargar a pedido, patrón SEC-33 (`programas/templates/programas/becas/revision/_detalle/_scripts.html`
  l.33-46): botón «Ver el mapa», `referrerpolicy="no-referrer"`, nada sale al proveedor hasta que se pulsa.
  Los 5 pasos de factibilidad están en [emergencia-design §7.1](2026-11-04-emergencia-design.md); acá solo se
  ajusta: `scrollWheelZoom` apagado (como el mockup) y teclado.
- **Interacciones**: clic en un círculo o en «Más tensionados» → selecciona y centra; «Ver en el mapa» de
  Encontrar plaza → cambia de solapa, selecciona el dispositivo y lleva el foco a la solapa.
  Si el dispositivo elegido no está en el filtro vigente, el filtro se limpia (como hace el mockup).
- **Estados**: cerrado (estado vacío con «Ver el mapa»), cargando, **error** («No se pudo cargar el mapa»,
  `_alerta` danger con «Reintentar», sin perder el Resumen) y abierto.
- **Accesibilidad**: un mapa de Leaflet no es operable por teclado ni por lector de pantalla: la **lista
  «Más tensionados» es la alternativa equivalente** (botones con `aria-pressed`) y el mapa lleva
  `role="region"` con `aria-label`. Cada círculo lleva tooltip, pero no se puede depender de él.
- **Privacidad**: las coordenadas del recorte visible viajan a los mosaicos al abrir el mapa (emergencia §7.1);
  son las de **instituciones**, no de personas.

## 3. Diseño

### 3.1 Piezas canónicas que usa cada bloque

| Bloque | Pieza canónica | Ficha |
|---|---|---|
| Hero | `{% hero_inicio %}` (acotado por regla; lo estrena este tablero) | `componentes/hero_inicio.md` |
| Filtros | `components/_filtro_pildora.html` | `componentes/filtros.md` |
| Franja de métricas | `_stat_card.html` `variante="tablero"`, con `kpi_id`/`sufijo`/`nota` | `componentes/stat_card.md` |
| Solapas | `tabs.md` + `nodo-tabs.js` global | `componentes/tabs.md` |
| Necesita atención | `components/_alerta.html` | `componentes/alerta.md` |
| Tabla de la red y de estadías | `.tabla`, `nodo-thead-row`, `acciones`, `nodo-icon-btn`, `enlace-entidad` | `componentes/tabla.md` |
| Badges | `badge badge-{tono}` con ícono + texto | `componentes/botones_badges.md` |
| Estados vacíos | `_estado_vacio.html` | `componentes/estado_vacio.md` |
| Botones | `btn-nodo btn-secondary/tertiary/brand` | `componentes/botones_badges.md` |
| Mapa de plazas (enlace «Ver plazas») | pantalla existente | `componentes/mapa_plazas.md` |

### 3.2 Piezas nuevas que necesitan aprobación

Según `pendientes.md`, un tablero con gráficos es una **novedad** y no tiene golden: «frená y devolvé la tarea».
Esta tabla es lo que habría que aprobar antes de escribir el primer template.

| # | Pieza nueva | Dónde aparece | Qué falta definir | Propuesta |
|---|---|---|---|---|
| 1 | **Arquetipo Dashboard sin golden** | Toda la pantalla | Es el hueco de `arquetipos/pendientes.md`. Becas (`becas/config/_dashboard_panel.html`) no es molde | Esta pantalla pasa a ser la golden de «Dashboard de programa», con ficha `arquetipos/dashboard.md` |
| 2 | **Gráfico de barras pareadas** | 2.11 | Alternativa accesible y paleta serie | CSS puro como el mockup, con `title` por par y tabla `sr-only`; tokens `--serie-*` |
| 3 | **Mapa (Leaflet)** | 2.15 | CSP, vendorizado, estados | `components/_mapa.html` y ficha; los 5 pasos de emergencia §7.1; actualizar `componentes/ubicacion.md` (hoy «Prohibido: librerías de mapas») y `SinRecursosDeTercerosTests` |
| 4 | **Barra con marcas de umbral** | 2.7 | Cómo se ven las marcas con foco/alto contraste | Barra `.barra` + dos `.marca` (alerta/crítico) con leyenda en texto |
| 5 | **Fila de resultado de persona** | 2.12 | Jerarquía de la estadía anterior (indentada, tamaños 12 px) | Ficha propia; el mockup usa tamaños en línea que el audit rechaza |
| 6 | **Fila de plaza libre** | 2.13 | — | Ficha propia (nombre, badge, meta, libres, dos acciones) |
| 7 | **Píldora con campo de texto** | 2.12 | `_filtro_pildora.html` solo admite `<select>` | Extender la pieza con `tipo="busqueda"` |
| 8 | **Salto entre solapas** | 2.13 → 2.15 | Foco y selección al cambiar de panel | Evento de Alpine + `focus()` en la solapa (en el mockup: `enfocar('tab-mapa')`) |
| 9 | **Mini-stat de relevamientos** | 2.9 | Duplica la `_stat_card.html` chica | **No aprobar**: usar la chica canónica |
| 10 | **Lista de selección «Más tensionados»** (`item-lista`) | 2.15 | Es un botón-lista con `aria-pressed` | Ficha propia o `lista_tarjetas.md` si alcanza |

El mockup rotula con «Pieza nueva» solo cuatro; las tres últimas se detectaron al cruzar contra las fichas.

### 3.3 Accesibilidad aplicada

- Color nunca solo: todos los badges llevan ícono + texto; las marcas de umbral tienen leyenda textual.
- Navegación por solapas con flechas, Home y End (`nodo-tabs.js`); un solo `h1` (el del hero) y cada `surface`
  con `h2` vía `aria-labelledby`.
- Resultados dinámicos (`aria-live="polite"`) en buscar persona y encontrar plaza.
- Formularios con botón «Filtrar»/«Buscar» visible; no se filtra al cambiar un `<select>`.
- Tablas con `<caption class="sr-only">` donde corresponde, `scope="col"`, `aria-sort`, y columna de acciones
  con etiqueta `sr-only`.
- El mapa tiene una alternativa por teclado (lista) y estado de error con `role="alert"`.
- **Contraste**: el gradiente de marca con texto blanco del hero mide ~2,8:1 (según el brief); AA pide 4,5:1
  para texto normal y 3:1 para texto grande. El título de 30 px/800 califica como grande (pasa); la **bajada
  de 14,5 px y el eyebrow de 13 px no**. Verificar con el chequeador de contraste antes de aprobar
  (pregunta 4). El hero es pieza canónica, así que la corrección sería de la pieza, no de esta pantalla.

## 4. Autorización y datos personales

- **Capacidad del tablero**: hoy la pantalla principal exige `dispositivo.ver` y recorta por
  `dispositivos_visibles(user)`; `dispositivo.ver_todos` es de solo lectura sobre todos. **Propuesta**: el
  tablero usa `dispositivo.ver` (sin capacidad nueva) y agrega solo lo que el usuario ya ve. Si el PM quiere
  distinguir «ver el tablero» de «ver el listado», habría que crear una capacidad **nueva en el `CATALOGO` de
  `core/rbac.py`**, módulo `dispositivos` (l.63-84), alcance `programa` y programa `DISPOSITIVOS`, junto a la
  del resto del módulo. El código de esa capacidad lo define el PM; **no se inventa acá**.
- **Alcance**: todo cálculo parte de `dispositivos_visibles(user)`. Un operador de un solo dispositivo ve la
  red = su dispositivo; un coordinador ve los suyos; `dispositivo.ver_todos` ve todos. El hero y los KPIs
  deben decir «de tu alcance» si es menos que la red completa, para que nadie lea «tasa de la red» siendo la
  de un subconjunto.
- **Menú**: el grupo «Dispositivos» ya existe (`templates/includes/sidebar/opciones.html` l.580-670) con
  Instituciones (l.609), Relevamientos (l.622) y Configuración (l.635) y su versión colapsada (l.653). El
  tablero entra como **primer ítem**, con la misma condición que los demás
  (`puede_ver_dispositivos`). No toca el grupo «Programas» (nombre fijo, decisión del cliente, Cambio 3).
- **Buscar persona = datos del padrón.** El endpoint existente `PersonasSugeridasView` exige `dispositivo.admitir`
  **más** alcance al dispositivo y `ciudadano.ver` (`CAP_VER_CIUDADANO`, `estadias.py:125`; sin `ciudadano.ver`
  responde 403). Reglas propuestas:
  1. Misma exigencia mínima: `dispositivo.ver` + `ciudadano.ver` (+ alcance). Si hay que ser más estricto, se
     usa `dispositivo.admitir`, pero entonces la herramienta desaparece para un coordinador de solo lectura
     (pregunta 5). **El bloque se oculta** (no se muestra deshabilitado) a quien no puede usarlo.
  2. Solo estadías en dispositivos del alcance del usuario; el pie del mockup («Solo ves personas de los
     dispositivos de tu alcance») es verdad **solo** si el servicio filtra así.
  3. Mostrar lo mínimo: nombre, DNI, edad y lugar. **Sin** domicilio, teléfono, diagnóstico ni motivo de
     egreso (el mockup muestra motivo de egreso: «Retorno con su familia», «Alta médica»; **es un dato
     sensible en una pantalla de tablero**: sacarlo del tablero y dejarlo en el detalle de estadía).
  4. Mínimo 4 dígitos / 3 letras y tope de 5 resultados; sin enumeración por prefijo corto.
  5. Búsqueda por envío, nunca mientras se escribe; respuesta con `Cache-Control: no-store`.
  6. A confirmar: dejar rastro de la consulta (quién buscó qué DNI) en `TrazaDispositivo` o log de auditoría;
     para datos del padrón es recomendable y hoy no hay un registro de búsquedas.
- **Riesgos**: (a) el DNI en la URL queda en historiales y logs de acceso: usar POST o no persistir el
  parámetro; (b) un resultado «0 personas» en un alcance chico revela que esa persona no está allí, no que no
  exista; (c) «Ver legajo» lleva a `Ciudadano`: la pantalla destino ya aplica `ciudadano.ver`, pero el enlace no
  debe dibujarse si el usuario no la tiene; (d) el portal no participa: el `PortalCiudadanoMiddleware` ya
  expulsa a ciudadanos de todo lo que no es `/portal/`.
- **Mapa**: expone la ubicación de instituciones, no de personas. Las coordenadas pueden ser sensibles en
  dispositivos de **protección** (violencia, refugios): a confirmar si hay tipos cuya ubicación no debe
  mostrarse en un mapa ni al OSM (pregunta 8).
- **Salidas**: `Exportar` (si entra) lleva solo agregados por dispositivo, sin personas.

## 5. Rendimiento y ECOM

Restricciones que mandan (CLAUDE.md, *Gotchas*):

- **MariaDB en ECOM**: `UUIDField` con guiones (no se agrega ninguno) y **sin tablas de timezone**: nada de
  `TruncDate`/`TruncWeek` sobre `DateTimeField`; los ingresos/egresos por día y «hoy» se agrupan en Python con
  `core/utils_fechas.py`.
- **`read_timeout` y `write_timeout` de 10 s**: cada consulta del tablero tiene que ser barata; sin `IN` anidados
  grandes ni decodificar JSON en Python por fila.

Qué se calcula en la vista (una vez por request, con el conjunto filtrado):

| Dato | Consultas | Cómo |
|---|---|---|
| Censo de la red y por dispositivo/tipo/localidad | **3 fijas** | `ocupacion_de_plazas(ids)`; luego se agrega en Python por `tipo` y `localidad` |
| Semáforo de relevamientos | **3 fijas** | `semaforos_de_dispositivos(ids)` |
| Movimientos de 14 días | 2 | rango por `fecha_ingreso` / `fecha_egreso`, conteo por día en Python |
| Estadías largas | 1 | `Estadia.objects.activas()` filtrado por antigüedad, `select_related` del ciudadano y del lugar |
| Reservas que vencen hoy | 1 | `ReservaPlaza.objects.vigentes()` del día, `select_related` |
| Dispositivos y tipos | 1–2 | `select_related("tipo")` sobre `dispositivos_visibles(user)` filtrado |

Total del Resumen sin herramientas: **~9 consultas fijas, independientes de la cantidad de dispositivos**.
Las alertas, la tabla, «Ocupación por tipo», «Libres por localidad», el semáforo y el mapa **leen del mismo
censo**: no se recalcula nada por bloque. El orden de la tabla es en Python.

Qué se pide **a demanda** (no se calcula al cargar):

- **Buscar persona** y **Encontrar plaza libre**: solo al enviar el formulario. La plaza libre filtra
  `Plaza.tipo` y `disponibles` sobre el mismo censo ya calculado más una consulta por tipo de plaza si hace falta.
- **El mapa**: la solapa no calcula puntos propios; los puntos salen del conjunto ya filtrado y los mosaicos se
  piden cuando se pulsa «Ver el mapa» (SEC-33).
- **Estadías largas y reservas**: dentro del Resumen pero con tope; si el costo crece, pasan a carga diferida
  (`$dispatch`, `tabs.md`).

**Caché**: patrón de `dashboard_becas.py` (clave con sha256 de filtros + huella de alcance, 5 min,
freno de recálculo con `cache.add`, degradación a sin caché si Redis falla). Para Dispositivos el cuidado es
la **huella de alcance**: dos usuarios con alcances distintos nunca comparten clave. Como las cifras son el
estado operativo del día, la caché corta (60–120 s a confirmar) es mejor que 5 min; el rótulo «Actualizado a
las HH:MM» la hace visible. **No se cachea** buscar persona (datos personales).

**Presupuestos de queries**: ya existen `test_dispositivos_ocupacion` (5), `_censo` (6), `_listado` (2),
`_alertas` (2), `_personas_red` (5) y `_relevamientos_listado` (2) en `programas/tests/`, con
`@tag("performance")`. **No hay uno para el tablero** (a crear). El test tiene que sembrar N y 2N dispositivos
y verificar el mismo número de consultas, como los otros. Correr también `--tag performance` y el job de
migraciones/CI efímero si el tablero agrega un índice.

**Índices**: a confirmar contra el modelo si `Estadia.fecha_ingreso` / `fecha_egreso` y `ReservaPlaza.hasta`
tienen índice; si hace falta, es una migración que sigue el contrato de `scripts/check_migraciones.py`
(expand/contract, `RunSQL` con reversa, idempotente con los helpers de `core/migraciones.py`). Si no hace falta,
el plan no incluye migraciones.

## 6. Plan de implementación

Cada task es un PR razonable (criterio del repo: ~45-50 % del equivalente convencional; la fila es un
entregable, no un día). Todas incluyen su caso de `programas/tests/`, `ruff`, `manage.py check`,
`design_audit.py --ratchet` en 0 nuevos y la entrada en `docs/internal/requerimientos.md`.

| # | Task | Depende de | Archivos probables | Horas |
|---|---|---|---|---|
| T0 | **Decisiones del PM y aprobación de piezas** (preguntas 1-8 y la tabla 3.2). No es código | — | este documento | — |
| T1 | **Ruta, vista esqueleto, menú, capacidad** y alta en `HERO_PANTALLAS`; si hay capacidad nueva, `CATALOGO` + seed + migración de permiso | T0 | `programas/dispositivos_urls.py`, `programas/views/dispositivos_tablero.py`, `templates/includes/sidebar/opciones.html`, `core/rbac.py` (si hace falta), `scripts/design_audit.py` | 3 |
| T2 | **Servicio de red**: censo agregado por tipo/localidad/dispositivo, KPIs, tensión por tipo, semáforo, atención, filtros, orden; caché con huella de alcance | T1 | `programas/services/tablero_dispositivos.py`, `programas/tests/test_dispositivos_tablero_servicio.py` | 6 |
| T3 | **Resumen · estructura y bloques con datos del censo**: hero, píldoras, franja de métricas, solapas, Necesita atención, tabla, relevamientos, libres por localidad; estados vacíos; CSS compilado (`npm run build:tailwind`) | T2 | `programas/templates/programas/dispositivos/tablero/*.html`, `static/custom/css/…`, `core/templatetags/` | 9 |
| T4 | **Barra con marcas de umbral** (Ocupación por tipo) + ficha de la pieza | T3 | include de la barra, `.claude/design/componentes/…`, `.claude/agents/chaco-design-system.md` (inventario) | 3 |
| T5 | **Ingresos y egresos**: selector de 14 días (agrupa en Python) + gráfico de barras + ficha | T3 | `programas/selectors/…`, template del gráfico | 4 |
| T6 | **Estadías largas y reservas que vencen**: dos selectores nuevos + tabla | T3 | `programas/services/tablero_dispositivos.py`, template | 3,5 |
| T7 | **Encontrar plaza libre**: consulta por `Plaza.tipo`, distancia (según decisión), fila de plaza + ficha; «Reservar» según pregunta 2 | T3 | servicio, vista parcial, template | 4,5 |
| T8 | **Buscar persona**: endpoint con alcance, reglas de §4, píldora con texto, fila de persona + ficha, auditoría | T3 | `programas/views/…`, `programas/selectors/…`, `programas/services/…`, tests de permisos y mutación | 5,5 |
| T9 | **Mapa: infraestructura** (los 5 pasos de emergencia §7.1): vendorizar Leaflet en `static/vendor/leaflet/`, host de mosaicos en `MAPA_HOSTS` (`config/middlewares/security_headers.py`, solo `img-src`), `components/_mapa.html` y ficha, actualizar `componentes/ubicacion.md` y `SinRecursosDeTercerosTests` (`portal/tests/test_seguridad_publica.py`) | T1 | `static/vendor/leaflet/`, `config/middlewares/security_headers.py`, `templates/components/_mapa.html`, `.claude/design/componentes/` | 6 (rango 4–6 del spec) |
| T10 | **Solapa Mapa**: puntos del conjunto filtrado, ficha del seleccionado, «Más tensionados», estados cerrado/cargando/error, salto desde Encontrar plaza | T3, T9 | template de la solapa, JS propio | 5 |
| T11 | **Cierre**: presupuesto de queries del tablero, test de alcance con mutación (ver [tests que pasan por el motivo equivocado]), golden de arquetipo Dashboard (`arquetipos/dashboard.md`), actualizar `pendientes.md`, QA en testing | T3-T10 | `programas/tests/test_dispositivos_tablero_perf.py`, `.claude/design/arquetipos/`, `docs/internal/requerimientos.md` | 4 |

**Total: 53,5 h** en 11 tasks de código (T1-T11). T9 incluye las 4-6 h del spec de emergencia; el resto del
mapa va en T10.

Orden y paralelismo: T1 → T2 → T3 es la cadena crítica (18 h). Después, T4, T5, T6, T7 y T8 son independientes
entre sí (máximo 3 implementadores en paralelo); T9 puede arrancar apenas termina T1. T10 espera a T3 y T9; T11
cierra todo.

Riesgos de calendario: la tabla 3.2 (piezas nuevas) bloquea T3 en adelante y es la decisión que más demora;
T8 es el de mayor riesgo de revisión (datos personales) y conviene `/auditoria pr` con rúbrica de seguridad.

## 7. Casos de QA

**Ambiente: https://datanach.ecomdev.ar (testing)** para todos los casos. El WAF de ECOM puede bloquear una ruta
nueva desde internet: si pasa, registrar «BLOQUEADO POR FIREWALL» y probar con el dato alternativo.

| # | Bloque | Caso |
|---|---|---|
| QA-1 | Franja de métricas | **Dado** una red con 18 dispositivos y plazas fuera de servicio y reservadas, **cuando** abro el tablero, **entonces** «Plazas libres» es la suma de `disponibles` (operativas − ocupadas − reservadas) y no `capacidad − ocupadas`. |
| QA-2 | Umbral por tipo | **Dado** un tipo con umbral rojo 90 y un dispositivo al 88 %, **cuando** abro el tablero, **entonces** NO figura crítico; **cuando** bajo el umbral a 85 en `dispositivos:tipos`, **entonces** pasa a crítico. |
| QA-3 | Sin plazas | **Dado** un dispositivo sin plazas operativas, **cuando** miro la tabla, **entonces** dice «Sin plazas», sin 0 %, y no aparece en Plazas libres. |
| QA-4 | Filtros | **Dado** el filtro Tipo = Hogar elegido pero sin pulsar «Filtrar», **cuando** cambio de píldora, **entonces** la página no recarga; **cuando** pulso «Filtrar», **entonces** todos los bloques (hero, KPIs, tabla, mapa) reflejan el filtro. |
| QA-5 | Necesita atención | **Dado** 7 alertas, **cuando** abro el tablero, **entonces** se ven 4, el pie dice «Mostrando 4 de 7» y «Ver en la tabla» deja solo los que necesitan atención. |
| QA-6 | Vacío | **Dado** un filtro sin resultados, **cuando** pulso «Filtrar», **entonces** veo el estado vacío con «Limpiar filtros» y la bajada dice «Ningún dispositivo coincide con el filtro.». |
| QA-7 | Ingresos/egresos | **Dado** un ingreso hecho hoy a las 23:30 hora de Argentina, **cuando** abro el tablero, **entonces** cuenta en el día de hoy y no en mañana (sin desfase UTC). |
| QA-8 | Buscar persona (permiso) | **Dado** un usuario sin `ciudadano.ver`, **cuando** abre el tablero, **entonces** el bloque Buscar persona no se dibuja y el endpoint responde 403. |
| QA-9 | Buscar persona (alcance) | **Dado** una persona alojada en un dispositivo fuera de mi alcance, **cuando** busco su DNI completo, **entonces** veo «Ninguna persona coincide», igual que si no existiera. |
| QA-10 | Buscar persona (reglas) | **Cuando** escribo 3 dígitos o 2 letras y envío, **entonces** veo la ayuda y no hay consulta; **cuando** la búsqueda devuelve más de 5, **entonces** dice «Mostrando 5 de N». No aparece motivo de egreso. |
| QA-11 | Plaza libre | **Dado** Tipo de plaza = Cupo, **cuando** pulso «Buscar plaza», **entonces** solo salen dispositivos con plazas de tipo Cupo libres, ordenados por cercanía (o por el criterio decidido). |
| QA-12 | Estadías y reservas | **Dado** una reserva vigente que vence hoy y una estadía de 61 días, **cuando** abro el tablero, **entonces** ambas aparecen, la reserva primero con su hora. |
| QA-13 | Mapa a pedido | **Cuando** abro la solapa Mapa, **entonces** no hay ninguna petición a `tile.openstreetmap.org` hasta pulsar «Ver el mapa» (verificar en la pestaña Red). |
| QA-14 | Mapa en error | **Dado** el bloqueo de red a los mosaicos, **cuando** pulso «Ver el mapa», **entonces** aparece la alerta «No se pudo cargar el mapa» con «Reintentar» y el Resumen sigue intacto. |
| QA-15 | Mapa y teclado | **Cuando** uso solo el teclado en «Más tensionados», **entonces** puedo elegir un dispositivo y la ficha cambia; las flechas, Home y End mueven entre solapas. |
| QA-16 | Dispositivo sin coordenadas | **Dado** un dispositivo sin latitud/longitud, **cuando** abro el mapa, **entonces** no se dibuja y el contador avisa «1 sin ubicación». |
| QA-17 | Salto desde plaza libre | **Cuando** pulso «Ver en el mapa» en una plaza libre, **entonces** paso a la solapa Mapa con ese dispositivo seleccionado y el foco en la solapa. |

## 8. Supuestos y preguntas para el PM

Supuestos tomados (corregibles): el tablero cuenta solo dispositivos `ACTIVO`; reutiliza `dispositivo.ver`
y el alcance existente; usa los umbrales **por tipo** y el vocabulario del código (Normal / Exigida / Crítica);
«hoy» y los 14 días son días argentinos; el umbral de estadía larga es 60 días; el tablero no escribe nada,
salvo que se defina «Reservar».

Preguntas (las cinco primeras bloquean el plan):

1. **Mapeo de tipos de plaza.** El mockup deduce Cama ← Hogar, Parador y Residencia; Cupo ← Comunidad
   terapéutica; Turno ← Centro de día (este último **inventado** en el mockup). En el código `Plaza.tipo` ya es
   CAMA/CUPO/TURNO y cada tipo de dispositivo declara `tipos_plaza_admitidos`. ¿Se filtra por el dato real
   (propuesta, sin mapeo) o se quiere el mapeo del mockup? ¿Existe de verdad un tipo «Centro de día»?
2. **Flujo de «Reservar».** ¿Reserva a una persona concreta (la busca ahí mismo) o abre el mapa de plazas del
   dispositivo? ¿Con qué vigencia (`hasta`)? ¿Quién puede (`dispositivo.admitir`)? Hasta decidir, el botón
   lleva a `dispositivos:sectores`.
3. **«Cerca de» y distancia.** La localidad es texto libre y no hay coordenadas por localidad. ¿Se agrega una
   tabla de localidades con coordenadas, se usa otro dispositivo como origen, o se omite la distancia en v1?
4. **Contraste AA del hero.** El gradiente con texto blanco da ~2,8:1: pasa solo para el título grande. ¿Se
   oscurece el gradiente (cambia la marca en toda la app) o se acepta para el título y se corrige la bajada y
   el eyebrow?
5. **Quién puede buscar personas** y si se registra cada búsqueda. ¿`dispositivo.ver` + `ciudadano.ver`, o
   solo quien admite (`dispositivo.admitir`)? ¿Se muestra el motivo de egreso? (propuesta: no).
6. **Nombre e ítem en el menú.** El grupo del sidebar es «Dispositivos» (con Instituciones, Relevamientos y
   Configuración); el mockup suma «Tablero» arriba. ¿El nombre es «Tablero»? ¿Es la primera pantalla del
   programa (entrada del grupo, redirección desde `dispositivos:lista`) o un ítem más? Hoy la entrada del
   grupo es `dispositivos:lista`.
7. **Vocabulario**: ¿«Crítica / Exigida / Normal» (código) o «Crítico / En alerta / Normal» (mockup)?
   ¿«Necesitan atención» incluye «exigida» o solo crítica + relevamiento vencido?
8. **Logo real y dispositivos sensibles.** `Dispositivo` no tiene logo (el mockup usa un ícono de espiga);
   ¿qué logo lleva la marca del shell? ¿Hay tipos de dispositivo de protección cuya ubicación no debe
   dibujarse en el mapa ni enviarse a OSM?

Otras dudas menores: filtros dentro de cada panel o uno solo arriba (§2.2); si «Exportar» entra en v1;
si OBSERVADO cuenta como dispositivo activo; el comportamiento de un dispositivo sin edificio (sin
relevamiento); qué incluye «Necesita atención» además de críticos y relevamientos vencidos.

### 8.1 Decisiones (juez, por delegación del PM, 08-nov-2026)

El PM delegó las respuestas. Cada una se puede revertir antes de arrancar la T1.

| # | Decisión | Por qué |
|---|---|---|
| 1 | **Se filtra por el dato real, sin mapeo.** «Tipo de plaza» usa `Plaza.tipo` (CAMA/CUPO/TURNO) y «Tipo de dispositivo» usa los `TipoDispositivo` configurados. Los nombres del mockup son de ejemplo. | El dato ya existe y cada tipo declara `tipos_plaza_admitidos`. Un mapeo fijo se desincroniza en cuanto alguien configura un tipo nuevo. |
| 2 | **En v1, «Reservar» no reserva desde el tablero.** Lleva al mapa de plazas del dispositivo (`dispositivos:sectores`), donde ya está el flujo de reserva con su vigencia. Se muestra solo con `dispositivo.admitir`. | El tablero queda de solo lectura y no se duplica un flujo que escribe. La T7 baja de 4,5 a 3,5 h. |
| 3 | **Distancia con las coordenadas que ya tiene `Dispositivo` (`latitud`/`longitud`).** El origen de «Cerca de» es el centro de los dispositivos activos de esa localidad. Los dispositivos sin coordenadas van al final como «sin ubicación». Si la localidad no tiene ninguno con coordenadas, se ordena por plazas libres y no se muestra la distancia. No se crea una tabla de localidades. | Sale con datos existentes. La distancia es en línea recta y así se rotula («a 12 km en línea recta»). |
| 4 | **No se cambia el gradiente de marca.** En el hero, el eyebrow, la bajada y el título quedan sobre la mitad violeta (`#5059bc` con blanco ≈ 5,6:1), así que pasan AA. En la T3 se mide con píxeles reales. El problema de contraste del botón `btn-brand` sobre el extremo rosa es de toda la app: va en un issue aparte y no en este tablero. | Cambiar la marca excede el tablero. El riesgo real está en el botón, no en el hero. |
| 5 | **Buscar persona exige `dispositivo.ver` + `ciudadano.ver`**, y los resultados se limitan a los dispositivos del alcance del usuario. Sin las dos capacidades, la tarjeta no se dibuja. Pide al menos 4 dígitos o 3 letras, con tope de 20 resultados. **No se muestra el motivo de egreso.** Cada búsqueda queda registrada: quién, cuándo y cuántos resultados, **sin el término buscado en claro**. Si `programas/selectors/auditoria_dispositivo.py` no tiene dónde escribir, se usa un log estructurado. | Es el padrón: mínimo necesario, por alcance y con trazabilidad. La T8 necesita `/auditoria pr` con la rúbrica de seguridad. |
| 6 | **El ítem del menú se llama «Tablero»** y va primero dentro del grupo Dispositivos. En v1 la entrada del grupo sigue siendo `dispositivos:lista`. | Es suficiente para la regla del hero, porque es la pantalla de inicio del programa. Cambiar adónde llega cada usuario se decide después de usarlo. |
| 7 | **Se usa el vocabulario del código: Crítica / Exigida / Normal.** «Necesita atención» = crítica + relevamiento vencido + reserva que vence hoy. Exigida no entra. | Una sola fuente de verdad. Si entrara «exigida», la lista se llenaría y dejaría de servir. |
| 8 | **El shell no cambia:** se usa la marca actual de DATAÑACH y el ícono del mockup es provisorio. El mapa dibuja los dispositivos `ACTIVO` con coordenadas. Leaflet pide a OSM los mosaicos del recorte visible, no las coordenadas de los puntos. | Lo único que queda abierto para el PM: si existe algún tipo de dispositivo de protección cuya ubicación no deba verse, se agrega un indicador en `TipoDispositivo` antes de la T10. |

Dudas menores: hay **una sola barra de filtros**, arriba. **Exportar queda fuera de v1.** El tablero cuenta solo
dispositivos `ACTIVO`, porque `OBSERVADO` es un estado de validación y no de operación. Un dispositivo sin
relevamiento se muestra con el badge gris «Sin relevamiento».

**Respuesta del PM a la decisión 8 (08-nov-2026): sí, hay tipos de dispositivo de protección.** Queda así:

- **Indicador nuevo `ubicacion_reservada`** (booleano) en `TipoDispositivo`, editable en *Dispositivos → Configuración* y apagado por defecto. El PM marca qué tipos lo llevan. La migración agrega la columna `NOT NULL` con `DEFAULT` real en la base, según el contrato de `scripts/check_migraciones.py`.
- **Si el tipo está marcado:**
  - No se dibuja en el mapa ni entra en «Más tensionados».
  - En «Encontrar plaza libre» aparece sin distancia y rotulado «ubicación reservada». Nunca se usa como origen de «Cerca de».
  - Sus coordenadas no llegan al template: se filtran en el servicio, no se ocultan con CSS.
  - Sigue contando en los KPI, en la tabla de la red y en las alertas, porque esos bloques no muestran la ubicación.
- **Test de mutación:** se marca un tipo y se verifica que sus coordenadas no aparezcan en la respuesta del mapa.
- **T9b (nueva, antes de la T10):** indicador, migración, formulario de configuración y filtro en el servicio. **2 h.**

**Total ajustado: 54,5 h.** La T7 baja 1 h por la decisión 2 y se suma la T9b, de 2 h.

## 9. Alternativas exploradas (no aprobadas)

El mismo lienzo trae cuatro caminos todavía no aprobados que no entran en este plan: un **panel en vivo**
(actualización automática sin recargar, que pediría polling o WebSocket y cambia el presupuesto de consultas),
el **detalle de un dispositivo** (la ficha del seleccionado ya existe como `dispositivos:detalle`), el **modo
sala de situación** (pantalla grande para proyectar, con otra jerarquía visual) y la **vista móvil** (el
backoffice es de escritorio y notebook, y la app de campo es otra superficie). Si el PM quiere alguno, es un
spec aparte. Una **versión transversal a todos los programas** ya se descartó.
