# Análisis funcional 009 — Emergencia: tablero estratégico «Situación» con mapa (E8)

**Estado:** En análisis
**Fecha de análisis:** 2026-11-18
**Analista:** functional-analyst (sesión con el PM)
**Sprint asociado:** Sin asignar
**Módulo/App:** `programas` (Emergencia: selectores, servicios, vista y template nuevos), `core` (tabla nueva de
ubicación de localidades y capacidad nueva en `core/rbac.py`), `users` (migración de la capacidad)
**Mock-ups:** a armar con el layout y los datos de ejemplo de la §12 («Pantalla»), sobre el mockup aprobado del
tablero de Dispositivos (`docs/superpowers/specs/2026-11-08-tablero-dispositivos/mockup-tablero.dc.html`)

> **Numeración.** El 008 lo ocupa `008-dispositivos-v2-segunda-etapa.md` en la rama `ccr-98cf5793-ouuaub`
> (sin mergear): este análisis toma el **009** para no chocar.
>
> **Base.** El código de `development` al 18/11/2026 (merge #1160), el Cambio 472 (tablero E1) y sus pendientes,
> los Cambios 463 y 464, el análisis del módulo (`docs/internal/emergencia/` en la rama `docs/emergencia-analisis`,
> sobre todo `05-seguir-y-configurar.md`), la factibilidad del mapa de `2026-11-04-emergencia-design.md` §7.1
> (misma rama), la propuesta de octubre (`docs/client/propuestas/mesa-situacion-el-nino.md`) y, como **molde y
> fuente de las piezas compartidas**, el diseño aprobado del tablero de Dispositivos
> (`docs/superpowers/specs/2026-11-08-tablero-dispositivos-design.md`, en adelante **«spec de Dispositivos»**, con
> sus decisiones del 08-nov y la respuesta del PM sobre `ubicacion_reservada`). Ante una diferencia entre este
> documento y el código, gana el código; entre este documento y el spec de Dispositivos en una pieza compartida,
> gana el spec de Dispositivos salvo las diferencias justificadas de la §3.7.

---

## 1. Contexto y motivación

El módulo Emergencia ya tiene un tablero: **E1**, en `/emergencia/tablero/` (Cambio 472). Es una pantalla
**operativa** pensada para el supervisor de la mesa: le dice qué tiene que resolver *ahora* —casos nuevos sin
tomar, casos fuera de SLA, derivaciones por vencer, familias en la puerta, entregas con diferencias— y lo lleva al
caso. Mira una ventana corta (los casos abiertos y lo alojado o cerrado en las últimas 24 h, RN-5.1) y no tiene
gráficos, mapa ni tendencia. La solapa «Mapa de la emergencia» que pedía la especificación quedó afuera y sin
prometer (Cambio 472, pendiente 5).

El PM pidió primero «mejorar el módulo del tablero de Emergencia, agregando un mapa», y después lo precisó: «no
solo el mapa: tiene que ser un **tablero estratégico con información útil**». Quien coordina la emergencia y las
autoridades del Ministerio no preguntan «¿qué caso tomo?», preguntan: ¿dónde está el problema?, ¿la red de
albergues da abasto y por cuánto tiempo?, ¿estamos mejorando o empeorando?, ¿dónde se traba el circuito?, ¿a quién
estamos alojando?, ¿llegan los insumos? Esas preguntas se responden con agregados, tendencia y territorio, no con
una lista de casos; y las tiene que poder ver alguien que **no opera** la mesa (un secretario, el ministro, la
coordinación con Defensa Civil) sin quedar habilitado a reasignar casos o cambiar el SLA, que es lo que hoy
implica `emergencia.supervisar` (Cambio 463, decisión 4).

No arranca de cero. El 08-nov se aprobó el **tablero de Dispositivos** (spec de Dispositivos): hero, filtros en
píldora, franja de stat cards grandes, solapas **Resumen / Mapa**, «Necesita atención», tablas, barras con marcas
de umbral, barras pareadas y **un mapa con Leaflet vendorizado y mosaicos de OpenStreetMap cargados a pedido**.
Esa pantalla va a ser la golden del arquetipo «Dashboard de programa». E8 es el segundo tablero de programa y
**se arma con ese molde y esas piezas**; lo propio de Emergencia son los datos (casos, familias, fichas,
derivaciones, kits) y dos capas del mapa.

La propuesta de octubre ya ponía el mapa provincial como pantalla principal de una mesa de situación, pero sobre
datos que DATAÑACH **no tiene** (incidentes, alertas pluviales, criticidad cargada por los equipos, stock, cuatro
mesas). Este análisis toma de esa propuesta **solo lo que se puede calcular hoy** y deja el resto como fuera de
alcance explícito (§9).

Hay una restricción de base que condiciona el mapa: **ninguna tabla geográfica del sistema tiene coordenadas.**
`core.Localidad` y `core.Municipio` son solo nombres (`core/models/base.py`), no existe `Departamento`, y la
jerarquía cargada para Chaco (fixture `core/fixtures/localidad_municipio_provincia.json`: 79 «municipios», 778
localidades, 62 nombres de localidad repetidos) mezcla municipios con departamentos («Comandante Fernández»,
«Tapenagá», «1° de Mayo»…). Tienen coordenadas el **caso** (`CasoEmergencia.latitud/longitud/precision_m`, GPS
del relevamiento), el **dispositivo** (`Dispositivo.latitud/longitud`) y el **edificio**. Las coordenadas de la
familia son dato personal: el mapa no las puede dibujar ni mandar al navegador. La §3.5 resuelve de dónde salen
las posiciones de las localidades.

---

## 2. Actores involucrados

| Actor | Rol en el sistema | Qué puede hacer en esta funcionalidad |
|---|---|---|
| Autoridad / coordinación del Ministerio | Rol con la capacidad **nueva** `emergencia.ver_situacion` (programa EMERGENCIA) y nada más del módulo | Ver E8 completa (agregados, mapa, tendencia, perfil, logística), filtrar, imprimir. **No** ve casos, nombres ni direcciones, y los enlaces a la bandeja o a la ficha del caso no le aparecen |
| Supervisor de mesa | Rol con `emergencia.supervisar` | Todo lo anterior (supervisar implica ver la situación) **más** los enlaces de E8 a la bandeja E2 filtrada y a E1 |
| Operador de mesa | Rol con `emergencia.operar` | Nada nuevo: no ve E8 salvo que su rol tenga además `ver_situacion` (decisión del PM al armar los roles) |
| Equipo de un dispositivo | Roles del programa Dispositivos | Nada nuevo. El enlace del mapa a la ficha de un dispositivo respeta sus permisos de Dispositivos |
| Administrador | Rol protegido Administrador | Recibe `ver_situacion` por migración, como recibió `operar` y `supervisar` (`users.0047`) |

---

## 3. Descripción funcional

### 3.1 Decisión: pantalla nueva E8 «Situación», no solapa de E1

| Criterio | Solapa dentro de E1 | **Pantalla nueva E8** (elegida) |
|---|---|---|
| Quién la ve | Lo que vea E1: solo `supervisar` | Capacidad propia (`ver_situacion`): llega a las autoridades sin darles la mesa |
| Horizonte | Se mezcla «ahora» (24 h, avisos para actuar) con «tendencia» (72 h / 7 días) | Cada pantalla con su ventana; E1 no cambia de significado |
| Datos nominales | E1 muestra casos y familias («Familia Gómez») en sus avisos | E8 es **no nominal para todos**: se puede proyectar o imprimir en una reunión |
| Rendimiento | La solapa se calcularía con E1 (16 consultas hoy) o pediría carga diferida | Presupuesto propio (RNF-009-03); E1 queda en 16 |
| Molde | E1 es «Detalle apilado con hero»; meterle solapas y mapa la cambia de arquetipo | E8 nace como **Dashboard de programa**, el mismo arquetipo del tablero de Dispositivos |
| Pendiente 5 del Cambio 472 | Habría que construir la solapa | Se cierra: la solapa no se hace y E1 enlaza a E8 |

E8 vive en `/emergencia/situacion/` (`emergencia:situacion`), entra en el grupo «Emergencia» del sidebar
(Cambio 476) como **«Situación»**, visible con `ver_situacion`. E1 suma un botón «Ver la situación» y E8 uno «Ir
al tablero de la mesa» (este último solo con `supervisar`).

### 3.2 Decisión: capacidad nueva `emergencia.ver_situacion`

`emergencia.supervisar` no sirve para las autoridades: implica operar la mesa (Cambio 463, decisión 4), reasignar
casos y editar E7. Se agrega al `CATALOGO` de `core/rbac.py`, módulo `emergencia` (alcance programa EMERGENCIA,
evaluada con `puede_en_programa_emergencia`, falla cerrado sin el programa sembrado):

```
("emergencia.ver_situacion", "Ver la situación de la emergencia (tablero estratégico y mapa, sin datos personales)")
```

- **Supervisar implica ver la situación** (`puede_ver_situacion = ver_situacion or supervisar`), igual que
  supervisar implica operar: la regla no depende de cómo se armó el rol.
- Migración de `users` (patrón de `users.0047`): el `Permission` nace del catálogo y se le tilda al rol protegido
  Administrador. Ningún otro rol recibe nada; el rol «Autoridades» (o como se llame) lo arma el PM.
- No entra en `CAPACIDADES_DE_CAMPO`: la app de campo no muestra E8.
- Diferencia con Dispositivos, que reusa `dispositivo.ver` sin capacidad nueva (spec de Dispositivos §4): allá el
  que mira ya tiene el listado; acá la audiencia principal no tiene ninguna capacidad del módulo.

### 3.3 Decisión: molde visual = «Dashboard de programa» (golden: tablero de Dispositivos)

Hoy `.claude/design/arquetipos/pendientes.md` dice que el arquetipo dashboard **no tiene golden** y pide frenar.
Eso deja de ser cierto con el plan aprobado de Dispositivos: su pieza nueva 1 (spec de Dispositivos §3.2) convierte
el tablero de Dispositivos en la golden de **«Dashboard de programa»**, con ficha `arquetipos/dashboard.md`, y su
T11 actualiza `pendientes.md`. E8 se declara de ese arquetipo y **clona su esqueleto**, cambiando solo el dominio:

| Bloque del molde | Pieza (ficha) | En E8 |
|---|---|---|
| Hero | `{% hero_inicio %}` (`componentes/hero_inicio.md`); E1 ya está en `HERO_PANTALLAS`, E8 se suma | Nombre del evento y la frase de situación, armada en la vista |
| Filtros | `components/_filtro_pildora.html` con botón **Filtrar** visible, «Limpiar» y «Actualizado a las HH:MM»; **una sola barra arriba de las solapas** con el oculto `tab` (decisión menor del 08-nov) | Departamento, Localidad, Ventana |
| Franja de métricas | `_stat_card.html` `variante="tablero"`, una sola franja grande (`componentes/stat_card.md`) | 4 indicadores |
| Solapas | `tabs.md` + `nodo-tabs.js`, deep link `?tab=` | **Resumen / Mapa** |
| Necesita atención | `components/_alerta.html` (`componentes/alerta.md`) | Alertas estratégicas |
| Tablas | `.tabla`, `nodo-thead-row`, `acciones`, `aria-sort` (`componentes/tabla.md`) | Presión por localidad, capacidad, embudo, kits |
| Badges | `badge badge-{tono}` con **ícono + texto** (`botones_badges.md`) | Presión y tensión |
| Estado vacío | `_estado_vacio.html` con «Limpiar filtros» (`estado_vacio.md`) | Sin casos / filtro vacío |
| Barra con marcas de umbral | pieza nueva 4 del spec de Dispositivos (T4) | Capacidad de la red y barras simples del embudo y de presión |
| Gráfico de barras pareadas | pieza nueva 2 del spec de Dispositivos (T5) | Evolución: casos nuevos / familias alojadas |
| Mapa | `components/_mapa.html`, pieza nueva 3 (T9) | Solapa Mapa, con dos capas propias |
| Lista de selección (`item-lista`) | pieza nueva 10 | «Localidades con más presión» |

**Orden de dependencia.** Si el tablero de Dispositivos se construye antes, E8 reusa sus piezas y su golden tal
cual. Si E8 va primero, **construye esas piezas con las mismas fichas** que define el spec de Dispositivos (no
variantes propias), y Dispositivos las reusa. En ningún caso E8 clona a E1 ni al dashboard de Becas.

### 3.4 Flujo principal

1. El usuario entra a **Emergencia › Situación**.
2. Ve el **hero** con el nombre del evento (`SLAEmergencia.nombre_evento`) y una frase con personas alojadas,
   personas esperando lugar y camas libres con la ocupación de la red.
3. Debajo, la **barra de filtros en píldora**: Departamento, Localidad, Ventana (72 h / 7 días), botón **Filtrar**,
   «Limpiar», «Actualizado a las HH:MM» e **Imprimir**. Lo elegido queda pendiente hasta «Filtrar».
4. La **franja de cuatro indicadores**: personas alojadas, personas esperando, camas libres, horas hasta saturar.
5. Las **solapas Resumen / Mapa**. Abre en Resumen.
6. **Resumen**: Necesita atención (alertas estratégicas) · Presión por localidad · Evolución · Capacidad de la
   red · Embudo del circuito · Perfil de las personas · Logística de kits · Cómo se calcula.
7. **Mapa**: estado cerrado con el botón **«Ver el mapa»**; al pulsarlo se carga Leaflet y se piden los
   mosaicos. Se ven las localidades con demanda (círculos) y los dispositivos (círculos de color por tensión), la
   leyenda, el panel **«Localidad seleccionada»** y la lista **«Localidades con más presión»**. Tocar un círculo
   o un ítem de la lista selecciona la localidad, centra el mapa y llena el panel: familias y personas esperando,
   fuera de SLA, personas de ahí ya alojadas, camas libres cercanas y los tres dispositivos más cercanos. Con
   `supervisar`, el panel trae «Ver los N casos en la bandeja» (E2 con `?localidad=`). Tocar un dispositivo
   muestra su ficha corta con «Ver dispositivo» si el usuario lo puede ver por Dispositivos.

### 3.5 El mapa: opciones y recomendación

**La decisión de proyecto ya está tomada** (emergencia-design §7.1, spec de Dispositivos §2.15, T9): hay **una sola
pieza de mapa**, `components/_mapa.html`, con Leaflet vendorizado y mosaicos de OSM cargados a pedido. Este
análisis la adopta y no propone otra; la tabla queda para dejar registrado por qué.

| | **(a) Pieza única `_mapa.html`: Leaflet vendorizado + mosaicos OSM a pedido** (elegida) | (b) SVG propio dibujado en el servidor | (c) Mosaicos propios |
|---|---|---|---|
| Estado | Aprobada para Dispositivos (T9) | Propuesta de la versión inicial de este análisis | Salida de emergencia-design §7.1 si la ubicación vista fuera sensible |
| Qué es | Leaflet (BSD) en `static/vendor/leaflet/`; mosaicos de `tile.openstreetmap.org`; puntos del conjunto filtrado en `json_script` | Contorno y círculos proyectados en Python | Servir las teselas de Chaco desde nuestro servidor |
| CSP | `script-src` y `connect-src` no cambian; el host de mosaicos entra **solo en `img-src`** en una tupla propia **`MAPA_TILES_HOSTS`**: si se suma a `MAPA_HOSTS`, que hoy también alimenta `frame-src` (iframe de Becas), se abre `frame-src` a los mosaicos sin necesidad (MINOR conocido) | Sin cambios | Sin terceros |
| Privacidad | Nada sale hasta «Ver el mapa» (patrón SEC-33, `referrerpolicy="no-referrer"`); al abrir, OSM ve el recorte mirado y la IP, no los puntos. Los puntos son de **localidades** (centroide oficial) y de **instituciones** | Nada sale | Nada sale |
| Una sola pieza en el proyecto | **Sí** | No: segunda técnica de mapa | No |
| Costo para E8 | Solo las capas (la infraestructura la hace T9) | Asset + proyección + pieza propia | ~150 MB de teselas o un pipeline |
| Interacción | Zoom, centrar, seleccionar; `scrollWheelZoom` apagado | Recarga por GET | — |
| Imprime | Mal (teselas a medio cargar) | Bien | — |

**Recomendación: (a).** Una sola pieza de mapa en todo el proyecto, sin costo de servidor, con la privacidad ya
resuelta por SEC-33 y por el filtro de `ubicacion_reservada`. El SVG propio **se descarta**: sería una segunda
técnica de mapa para resolver solo la impresión, y la impresión se resuelve con la tabla (§3.8).

**Coordenadas de las localidades.** Los círculos de demanda necesitan la posición de cada localidad con casos.

| Fuente | Pros | Contras | Veredicto |
|---|---|---|---|
| Centro de los dispositivos activos de la localidad (decisión 3 del 08-nov de Dispositivos) | Sale con datos existentes | **No existe para localidades con demanda y sin dispositivos**: Juan José Castelli, Machagai o Las Breñas en el ejemplo, que son justo las que el tablero tiene que mostrar | Insuficiente para E8 |
| Centroide calculado de los GPS de los casos | Sin carga inicial | Sesgado; con 1 o 2 casos el «centroide» **es la casa de la familia** | Descartada (privacidad) |
| Columnas `latitud/longitud` en `core.Localidad` | Una sola tabla | `ALTER` sobre una tabla compartida de 8.779 filas de todo el país | Descartada |
| **Tabla nueva `core.UbicacionLocalidad`** cargada una vez desde un dataset oficial | Solo *expand*; trae el **departamento**; sirve también a RN-2.4 (distancia cuando el caso no tiene GPS, pendiente 4 del Cambio 463) | Conciliar nombres una vez | **Elegida** |

**Diferencia justificada con Dispositivos.** La decisión 3 del 08-nov dice «no se crea una tabla de localidades; el
origen de “Cerca de” es el centro de los dispositivos activos de esa localidad». Para Dispositivos alcanza, porque
el origen siempre es una localidad con dispositivos. E8 tiene que ubicar **la demanda**, que aparece justamente
donde no hay dispositivos; sin la tabla, esas localidades —las de presión más alta— no se podrían dibujar. Por eso
E8 la crea. **Propuesta, sin obligar:** cuando exista, Dispositivos puede usarla como origen de «Cerca de» para una
localidad sin dispositivos con coordenadas (hoy, en ese caso, ordena por libres y no muestra distancia).

`UbicacionLocalidad(TimeStamped)`: `localidad` (OneToOne a `core.Localidad`), `latitud`, `longitud`
(`DecimalField(9,6)`), `departamento` (texto), `fuente`, `id_fuente`. Se carga con un comando idempotente desde un
CSV versionado, extraído una vez del servicio Georef de datos.gob.ar (localidades del Chaco con centroide y
departamento; fuente BAHRA/INDEC, licencia abierta con atribución). Conciliación por nombre normalizado +
municipio; lo que no concilia queda listado en la salida del comando y **sin posición** (aparece en la tabla de
presión, no en el mapa, que avisa «N casos de localidades sin ubicación»). Mismo patrón que `AliasLocalidadSiis`.

### 3.6 Capas que Emergencia agrega sobre `_mapa.html`

La pieza `_mapa.html` (T9) dibuja puntos con color por nivel, leyenda, selección y estados. E8 le pasa dos
conjuntos de puntos; si la ficha de la pieza no admite más de una capa, **se extiende la ficha** (no se hace una
variante en E8).

| Capa | Qué dibuja | Posición | Tamaño / color | Por defecto |
|---|---|---|---|---|
| **Presión por localidad** | Un círculo por localidad con demanda o con personas alojadas | Centroide de `UbicacionLocalidad` | Tamaño = personas esperando (√); color = nivel de presión (RN-009-06) con el vocabulario y los tonos de la pieza; anillo marcado en «Crítica» | Encendida |
| **Dispositivos** | Un círculo chico por dispositivo elegible con coordenadas | `Dispositivo.latitud/longitud` | Color = `tension_de_ocupacion(conteo, tipo=dispositivo.tipo)`: **Crítica / Exigida / Normal / Sin plazas**, como Dispositivos | Encendida |
| Entregas en camino | Marca con el número de entregas `EN_CAMINO` junto al dispositivo destino | La del dispositivo | — | Apagada; opcional, si el control de capas de la pieza lo permite |
| Densidad de relevamientos | Celdas de 0,05° con ≥ 5 casos | Centro de la celda | — | **Fuera de alcance** de este lote (§9) |

**Reglas de privacidad del mapa** (se verifican con test sobre la respuesta, no se ocultan con CSS):

- Nunca viajan al template coordenadas de una familia: el `json_script` solo lleva centroides de localidad y
  coordenadas de dispositivos.
- **`TipoDispositivo.ubicacion_reservada`** (respuesta del PM del 08-nov, T9b): los dispositivos de un tipo
  marcado **no se dibujan**, sus coordenadas no llegan al template y no entran en «Localidades con más presión»
  como «cercano» con distancia (figuran como «ubicación reservada», sin distancia). **Siguen contando** en la
  franja de métricas, en capacidad de la red, en camas cercanas (la suma se hace en el servidor) y en las alertas.
- El mapa no se carga hasta «Ver el mapa» (SEC-33): ni Leaflet ni un mosaico salen antes.

**Interacción y accesibilidad** (las de la pieza, spec de Dispositivos §2.15): clic en un círculo o en un ítem de
la lista selecciona y centra; `scrollWheelZoom` apagado; `role="region"` con `aria-label`; estados cerrado /
cargando / **error** («No se pudo cargar el mapa», `_alerta` danger con «Reintentar», sin perder el Resumen) /
abierto. **El mapa nunca es la única vía:** la lista **«Localidades con más presión»** (`item-lista`, botones con
`aria-pressed`, las 8 de mayor presión) es la alternativa equivalente por teclado, y la tabla «Presión por
localidad» del Resumen tiene todos los números.

### 3.7 Diferencias justificadas con el spec de Dispositivos

| Tema | Dispositivos | E8 | Por qué |
|---|---|---|---|
| Capacidad | `dispositivo.ver` | `emergencia.ver_situacion` nueva | La audiencia no tiene ninguna capacidad del módulo (§3.2) |
| Coordenadas de localidad | Sin tabla (decisión 3) | `core.UbicacionLocalidad` | Hay que ubicar demanda sin dispositivos (§3.5) |
| Plazas que cuentan | Todas (`Conteo` del dispositivo) | Solo **`CAMA`** | Emergencia aloja familias en camas (RN-2.3); se resuelve con el mismo parámetro `tipos` que la T7 de Dispositivos necesita para «Encontrar plaza libre» (§8.2) |
| Caché | Patrón de Becas, 60–120 s | Sin caché en este lote | La foto es barata (RNF-009-03) y la mesa necesita el dato fresco; si se proyecta, se revisa (pregunta 6) |
| Mapa impreso | — | La tabla reemplaza al mapa | §3.8 |

Todo lo demás —vocabulario Crítica / Exigida / Normal / Sin plazas, umbrales del tipo, `disponibles`, solapas,
filtros, estados vacíos, carga a pedido del mapa— es igual.

### 3.8 Flujos alternativos

**Sin casos todavía**
- Condición: el programa no tiene casos en la ventana ni abiertos.
- Comportamiento: indicadores en cero, «—» en horas hasta saturar; Resumen con «Todavía no hay casos» en presión,
  embudo y perfil; el mapa muestra solo dispositivos. Sin divisiones por cero.

**Filtro por departamento o localidad**
- Condición: el usuario elige un departamento o una localidad y aprieta «Filtrar».
- Comportamiento: se acotan los bloques de **demanda** (indicador de esperando, alertas por localidad, presión,
  evolución, embudo, perfil). Los de **capacidad** (camas, horas hasta saturar, capacidad de la red) siguen siendo
  **provinciales** y lo dicen («Red provincial»): `Dispositivo.localidad` es texto libre. Los dos paneles usan el
  mismo filtro; el filtro no cambia de solapa.

**Filtro que vacía la demanda**
- Comportamiento: estado vacío con «Limpiar filtros» hacia la URL sin parámetros (`estado_vacio.md`).

**Localidad sin ubicación**
- Condición: casos de una `core.Localidad` sin fila en `UbicacionLocalidad`, o casos sin localidad.
- Comportamiento: aparecen en la tabla («Sin ubicación en el mapa» / «Sin localidad»); el mapa avisa cuántos son.

**Dispositivo sin coordenadas**
- Condición: dispositivo elegible con `latitud`/`longitud` nulas.
- Comportamiento: no se dibuja; el mapa dice «N dispositivos sin ubicación» (como Dispositivos). Cuenta en la red;
  para «camas cercanas» se asigna por el nombre normalizado de su localidad (regla actual de E1).

**El mapa no carga**
- Condición: sin salida a internet o error de mosaicos.
- Comportamiento: `_alerta` danger «No se pudo cargar el mapa» con «Reintentar»; la lista «Localidades con más
  presión» sigue funcionando (sale del HTML, no de OSM).

**Usuario sin `supervisar`**
- Condición: solo `ver_situacion`.
- Comportamiento: misma pantalla, sin enlaces a E1, E2 ni E3 (las URLs ni siquiera viajan en el `json_script`).

**Impresión**
- Condición: «Imprimir» o Ctrl+P.
- Comportamiento: hoja A4 apaisada con estilo de impresión: se ocultan sidebar, filtros, botones, la barra de
  solapas y el **mapa** (Leaflet con mosaicos a medio cargar no se imprime confiable). Se imprimen el hero, los
  filtros aplicados como subtítulo, la franja de métricas, **todo el panel Resumen** (aunque se esté mirando el
  Mapa), con la tabla «Presión por localidad» completa como reemplazo del mapa, y «Cómo se calcula» desplegado.
  Pie: «Documento de trabajo · datos agregados, sin datos personales · impreso el …». Si se quiere el mapa en el
  papel, se captura el recorte en pantalla; un mapa impreso propio queda fuera de alcance (§9).

---

## 4. Requerimientos

### Requerimientos funcionales

| ID | Requerimiento | Prioridad | Notas |
|---|---|---|---|
| RF-009-01 | Pantalla E8 «Situación» en `/emergencia/situacion/`, ítem del grupo Emergencia del sidebar, visible con `ver_situacion` o `supervisar` | Alta | §3.1 |
| RF-009-02 | Capacidad `emergencia.ver_situacion` en el `CATALOGO`; supervisar la implica; migración para Administrador | Alta | §3.2 |
| RF-009-03 | Arquetipo Dashboard de programa (golden: tablero de Dispositivos), con hero, filtros en píldora, franja de métricas y solapas Resumen / Mapa | Alta | §3.3 |
| RF-009-04 | Filtros: departamento, localidad (dependiente del departamento) y ventana 72 h / 7 días; por GET, aplicados con «Filtrar» | Alta | RN-009-12 |
| RF-009-05 | Cuatro indicadores: personas alojadas, personas esperando, camas libres, horas hasta saturar | Alta | §5.1 |
| RF-009-06 | «Necesita atención»: alertas estratégicas calculadas al leer, sin estado, ordenadas por severidad, a lo sumo seis, con «Mostrando N de M» | Alta | RN-009-09 |
| RF-009-07 | Solapa Mapa sobre `components/_mapa.html` con las capas de presión por localidad y de dispositivos, panel «Localidad seleccionada» y lista «Localidades con más presión» | Alta | §3.5–3.6 |
| RF-009-08 | Tabla «Presión por localidad» en Resumen con los mismos números del mapa | Alta | Alternativa accesible e impresa |
| RF-009-09 | Evolución por día operativo (7 días) o por bloques de 6 h (72 h): casos nuevos y familias alojadas (barras pareadas) y personas alojadas al cierre | Alta | |
| RF-009-10 | Capacidad de la red en camas con barra con marcas de umbral y los cinco dispositivos más tensionados | Alta | |
| RF-009-11 | Embudo de la ventana con conversión, medianas por tramo y salidas del circuito | Alta | |
| RF-009-12 | Perfil agregado de personas alojadas y esperando | Media | RN-009-11 (supresión) |
| RF-009-13 | Logística de kits de la ventana: entregas por estado, enviado/recibido por ítem, tránsito, dispositivos sin entrega | Media | |
| RF-009-14 | Capa «Entregas en camino» | Baja | Si la pieza admite control de capas |
| RF-009-15 | Imprimir con estilo de impresión propio (Resumen completo, sin mapa) | Media | §3.8 |
| RF-009-16 | Enlaces E1 ↔ E8; en E8 los enlaces a E1/E2 solo con `supervisar` | Media | |
| RF-009-17 | Tabla `core.UbicacionLocalidad` + comando de carga idempotente desde CSV versionado + reporte de no conciliadas | Alta | Prerrequisito de la capa de localidades |
| RF-009-18 | Resolver en el mismo lote los pendientes 1, 3, 4, 5, 6, 7, 8, 9, 10 y 11 del Cambio 472 | Alta | §8.2 |

### Requerimientos no funcionales

| ID | Requerimiento | Categoría |
|---|---|---|
| RNF-009-01 | E8 es **no nominal** para todos los usuarios: ni nombres, ni DNI, ni direcciones, ni números de caso, ni coordenadas de familias en el HTML ni en el `json_script` (test sobre la respuesta) | Privacidad |
| RNF-009-02 | El mapa es la pieza única `_mapa.html` (Leaflet vendorizado); el host de mosaicos va en `MAPA_TILES_HOSTS`, solo en `img-src`; nada sale a OSM antes de «Ver el mapa»; `referrerpolicy="no-referrer"` | Seguridad / Privacidad |
| RNF-009-03 | Presupuesto: selectores y alertas de E8 en **≤ 12 consultas**, la vista completa en **≤ 18** (con SLA y shell), constantes con 5.000 casos en la ventana, 3.000 personas alojadas, 50 dispositivos y 500 entregas; < 2 s. El panel Mapa no agrega consultas (usa la misma foto). Test `@tag("performance")` | Performance |
| RNF-009-04 | Todo se calcula al leer (espíritu de RN-5.1): sin tabla de métricas, snapshot ni job | Arquitectura |
| RNF-009-05 | Sin `Trunc*` ni `CONVERT_TZ`: días operativos y bloques de 6 h se arman en Python con `dia_operativo()` y se filtra por rango (RN-5.2; gotcha de ECOM). Test que captura el SQL | Compatibilidad |
| RNF-009-06 | Funciona igual en MySQL 8 y MariaDB: lecturas de JSON con transformaciones de clave probadas en los dos motores o, si no, la sección traída entera y contada en Python | Compatibilidad |
| RNF-009-07 | Selectores puros respecto de `ahora` (lo reciben por parámetro), como `selectors/emergencia_tablero.py` | Testabilidad |
| RNF-009-08 | El Resumen funciona sin JS; el Mapa necesita JS y tiene su alternativa en la lista y la tabla | Accesibilidad / Robustez |
| RNF-009-09 | Colores y vocabulario de tensión del sistema y del spec de Dispositivos (Crítica / Exigida / Normal / Sin plazas; badges con ícono + texto) | Diseño / Accesibilidad |
| RNF-009-10 | Índices a medir con `EXPLAIN` en `scripts/perf_mysql/` antes de mergear el selector (§4.1) | Performance |

### 4.1 Rendimiento: qué es caro y cómo se lee

| Lectura | Consulta | Riesgo | Mitigación |
|---|---|---|---|
| Casos de la ventana ampliada (abiertos + creados, alojados o cerrados desde el inicio de la ventana) | 1 `values_list` sin JSON salvo las cuatro claves de `necesidades` | El `OR` sobre `creado`, `alojado_en` y `cerrado_en` (ninguna tiene índice) recorre la tabla. Es el mismo problema del pendiente 10 del Cambio 472 | Medir. Si pesa: índices simples (una migración `AddIndex`, aparte) y, si el optimizador no hace *index merge*, tres consultas por índice unidas en Python (+2, dentro del presupuesto) |
| Red de dispositivos (camas) | 4 (`red_de_dispositivos`: candidatos con tipo + 3 de `ocupacion_de_plazas` en lote) | Ninguno nuevo | Reusar; parámetro `tipos=(CAMA,)` (§8.2); `ubicacion_reservada` viaja en el `select_related("tipo")` |
| Personas alojadas por la emergencia (perfil + evolución) | 1: `IntegranteGrupo` con `estadia` no nula y (`egresado_en` nula o ≥ inicio de la ventana): `confirmada_en`, `egresado_en`, `ciudadano__fecha_nacimiento` y la sección `ficha__avisos_salud` | Leer la ficha entera serían MB | Traer **solo** `avisos_salud` y contar en Python. Medir índices de `confirmada_en`/`egresado_en` |
| Ritmo de ingresos y egresos en camas | 1 agregado sobre `Estadia` de los elegibles con plaza `CAMA`, últimas 6 h | `fecha_ingreso`/`fecha_egreso` sin índice (el spec de Dispositivos tiene la misma duda para sus 14 días) | Medir una vez para los dos tableros; un índice sirve a ambos |
| Derivaciones de la ventana (rechazadas, vencidas, pendientes por dispositivo) | 1 | Ninguno: `(dispositivo, estado)` | — |
| Logística | 2: agregado de `LineaEntrega` por ítem; última recepción por dispositivo | Ninguno | `(dispositivo, estado)` existe |
| Ubicaciones de localidad | 1, solo de los ids presentes | Ninguno (PK) | — |
| **Total dominio** | **11** (+2 si se parte la de casos) | | Presupuesto 12 |

La evolución histórica **rompe la ventana de 24 h** de RN-5.1 (hasta 7 días), pero no el principio: sigue siendo
una lectura acotada, nunca el histórico completo. Se **agrega por período en Python**; no hay snapshot diario.

Lo que **no** se puede reconstruir hacia atrás es la **capacidad** (las plazas no tienen historia de alta, baja ni
fuera de servicio). Por eso la evolución muestra **personas alojadas** (exacto, desde `confirmada_en`/`egresado_en`)
con las camas operativas **de hoy** como referencia rotulada; no muestra un «% de ocupación» histórico.

---

## 5. Reglas de negocio

### 5.1 Qué responde cada bloque

«Abiertos sin alojar» = estados `NUEVO`, `EN_GESTION`, `DERIVADO`, `INGRESO_EN_CURSO`. «Ventana» = 72 h o 7 días
según el filtro. «Elegibles» = `dispositivo_elegible()` (RN-2.2, `selectors/emergencia.py`). La capacidad sigue a
la spec de Dispositivos §2.3: **`disponibles`** (operativas − ocupadas − reservadas, ya sin fuera de servicio) y
**`tension_de_ocupacion(conteo, tipo=...)`** con los umbrales del tipo; para un agregado de red sin tipo, el corte
general 60/80 de `ocupacion.py`.

| Bloque | Pregunta | Cálculo | Fuente | Ventana / filtro | Decisión que habilita |
|---|---|---|---|---|---|
| **B1 Personas alojadas** | ¿Cuánta gente tenemos a cargo? | Integrantes con `estadia` no nula y `egresado_en` nula. Nota: dispositivos con alguna y variación desde el inicio del día operativo | `IntegranteGrupo.estadia/confirmada_en/egresado_en` | Ahora / filtro por localidad del caso | Dimensionar raciones, personal, kits |
| **B2 Personas esperando lugar** | ¿Cuánta demanda sin resolver hay? | Suma de `GrupoFamiliar.total_declarado` de los casos abiertos sin alojar; nota: familias y fuera de SLA (`fuera_de_sla(foto)`) | `CasoEmergencia.estado`, `grupo.total_declarado`, `estado_sla` | Ahora / filtro | Abrir albergues, reforzar la mesa |
| **B3 Camas libres** | ¿Hay dónde ponerla? | Suma de `disponibles` de plazas **`CAMA`** de los elegibles; nota: % de ocupación (`ocupadas / operativas`) y reservadas; tono por `tension_de_ocupacion(total)` (60/80) | `ocupacion_de_plazas(…, tipos=(CAMA,))` | Ahora / **siempre provincial** | Habilitar dispositivos, liberar plazas |
| **B4 Horas hasta saturar** | ¿Por cuánto tiempo da abasto? | `disponibles / ritmo_neto`, con `ritmo_neto = (ingresos − egresos en camas de elegibles en las últimas 6 h) / 6`. Ritmo ≤ 0: «No se satura al ritmo actual». Redondeado («≈ 11 h») con la nota del ritmo | `Estadia.fecha_ingreso/fecha_egreso`, `plaza__tipo` | Últimas 6 h / provincial | Abrir albergues **antes** de quedarse sin camas |
| **B5 Necesita atención** | ¿Qué no puede esperar a la próxima reunión? | Reglas de RN-009-09 | Varias | Ver regla | Escalar |
| **B6 Mapa + B7 Presión por localidad** | ¿Dónde está el problema? | Por `localidad_id` del caso: familias y personas esperando, fuera de SLA, personas de esa localidad alojadas, **camas libres cercanas** (RN-009-05), presión (RN-009-06) | Foto de casos, red, `UbicacionLocalidad`, `distancia_km` | Ahora / filtro | Dónde mandar recursos, dónde abrir un albergue |
| **B8 Evolución** | ¿Mejoramos o empeoramos? | Por período: casos creados y casos con `alojado_en` en el período (barras pareadas); cerrados sin alojar; personas alojadas al cierre de cada período = integrantes con `confirmada_en ≤ fin` y (`egresado_en` nula o `> fin`). Períodos armados en Python | `CasoEmergencia.creado/alojado_en/cerrado_en`, `IntegranteGrupo` | 72 h / 7 días; filtro de demanda | Ver si la curva de nuevos baja |
| **B9 Capacidad de la red** | ¿Qué dispositivos están al límite? | Barra provincial de camas con marcas 60/80; los 5 más tensionados (orden **`porcentaje − umbral rojo` del tipo**, como «Más tensionados» de Dispositivos) con su barra con marcas de **su** tipo, nivel y derivaciones pendientes hacia él | `ocupacion_de_plazas`, `TipoDispositivo.umbral_ocupacion_*`, `Derivacion` | Ahora / provincial | Redistribuir derivaciones |
| **B10 Embudo** | ¿Dónde se traba el circuito? | Cohorte = casos **creados en la ventana**, sin ingresos directos (definición única, §8.2). Etapas por marca (escritas una vez, RN-2.9, el embudo es monótono): relevados, tomados, derivados, aceptados, alojados. Conversión; mediana y p90 por tramo contra el objetivo de E7; salidas: cerrados sin alojar por `motivo_cierre`; derivaciones `RECHAZADA` (por motivo) y `VENCIDA`; ingresos directos aparte | `CasoEmergencia`, `Derivacion`, `SLAEmergencia` | Ventana / filtro | Reforzar el tramo que se traba |
| **B11 Perfil** | ¿A quién alojamos y quién espera? | **Alojados** (Formulario 2): menores de 16 y mayores de 60 por `ciudadano.fecha_nacimiento`; embarazo, discapacidad, electrodependiente, medicación crítica y medicación crítica **sin dosis** (`medicacion_critica_tiene_dosis` falso) desde `ficha.avisos_salud`. **Esperando** (Formulario 1, declarado): menores, mayores, lactantes, dependientes y mayores dependientes de `GrupoFamiliar`; familias con embarazo, electrodependencia, medicación crítica y mascotas desde `CasoEmergencia.necesidades` | `IntegranteGrupo.ficha` (`ESQUEMA_FICHA`), `GrupoFamiliar`, `CasoEmergencia.necesidades` (`NECESIDADES`) | Ahora / filtro, con supresión RN-009-11 | Pedir a Salud, insumos específicos |
| **B12 Logística** | ¿Llegan los insumos? | Entregas con `despachada_en` en la ventana por estado; sobre las **recibidas**: enviado, recibido y diferencia por ítem; tránsito mediano (`recibida_en − despachada_en`); dispositivos con personas alojadas por la emergencia y **sin entrega recibida en 48 h** | `EntregaKit`, `LineaEntrega`, `TipoKit` | Ventana / provincial | Corregir la distribución |

**Lo que no se puede calcular hoy, y por qué:**

| Pedido posible | Por qué no |
|---|---|
| Stock o faltantes en un albergue | No hay stock ni depósitos (RN-4.6): solo entregas |
| Población afectada (no evacuada) | El sistema solo conoce a quien se releva para alojar |
| Criticidad hídrica, cotas, alertas pluviales | No hay dato; la propuesta de octubre lo cargaba a mano |
| Incidentes, Mesas 1–4, FUSE | No existen en DATAÑACH |
| % de ocupación histórico | La capacidad no tiene historia (§4.1) |
| Filtro de capacidad por departamento o localidad | `Dispositivo.localidad` es texto libre, sin FK |
| Permanencia promedio por familia | Con un evento en curso la mayoría no egresó: el promedio engaña. Queda para el cierre del evento |
| Comparar contra eventos anteriores | Un solo `SLAEmergencia` por programa, sin fecha de inicio ni de cierre |

### 5.2 Reglas numeradas

| ID | Regla | Consecuencia si no se cumple |
|---|---|---|
| RN-009-01 | Todo E8 se calcula al leer, sobre un `ahora` único que recibe cada selector; Resumen y Mapa leen la misma foto | Números de distintos instantes en la misma pantalla |
| RN-009-02 | «Hoy» y los períodos de la evolución son días operativos de 06:00 a 06:00 hora Argentina (`dia_operativo()`) o bloques de 6 h alineados a las 06:00, armados en Python; nunca `Trunc*` | `CONVERT_TZ` devuelve `NULL` en ECOM |
| RN-009-03 | Capacidad = plazas **`CAMA`** `OPERATIVA` de elegibles, con la cuenta única de `services/ocupacion.py`; libres = `disponibles`; nivel = `tension_de_ocupacion(conteo, tipo=…)` (agregado sin tipo: 60/80); vocabulario **Crítica / Exigida / Normal / Sin plazas**; sin plazas operativas el porcentaje es «—», nunca 0 | Cupos y turnos inflan las camas libres; dos tableros con semáforos distintos para el mismo dispositivo |
| RN-009-04 | Casos por localidad se agrupan por `localidad_id`, nunca por nombre | 62 nombres repetidos en Chaco (pendiente 3 del Cambio 472) |
| RN-009-05 | **Camas libres cercanas** de una localidad = `disponibles` (camas) de los elegibles a ≤ **25 km** (`distancia_km`) de su centroide; un dispositivo sin coordenadas cuenta si el nombre normalizado de su localidad coincide. Las de ubicación reservada cuentan (se suman en el servidor). Las cercanas **no son exclusivas**; el total real es B3 | Presión engañosa en aglomerados |
| RN-009-06 | Presión = personas esperando / camas libres cercanas. **Crítica**: > 1, o esperando > 0 y 0 camas cercanas. **Exigida**: ≥ 0,5. **Normal**: < 0,5. **Sin demanda**: 0 esperando. Mismos tonos e íconos que la tensión de ocupación | Semáforo sin regla |
| RN-009-07 | Horas hasta saturar = `disponibles / ritmo_neto` con ritmo de las últimas **6 h**; ritmo ≤ 0 → «No se satura al ritmo actual»; con 0 libres → «Red saturada». Rotulado «proyección al ritmo actual, no es un pronóstico» | Un número que se lee como pronóstico |
| RN-009-08 | El embudo es de cohorte (casos creados en la ventana) y excluye ingresos directos, que se muestran aparte | Conversiones mayores al 100 % |
| RN-009-09 | **Alertas de «Necesita atención»** (sin estado, al leer, a lo sumo 6 con «Mostrando N de M», alta antes que media; nombran el dato, no enlazan a casos): **AE-1** saturación: horas hasta saturar < 12 o red en nivel **Crítica** (≥ 80 %) (alta). **AE-2** localidad crítica: presión crítica con ≥ 10 personas esperando (alta; nombra hasta 3 y «y N más»). **AE-3** demanda en alza: casos nuevos de las últimas 24 h ≥ 1,3 × el promedio de los tres períodos anteriores, con al menos 20 (media). **AE-4** tramo trabado: p90 de un tramo en 24 h > 2 × su objetivo (media). **AE-5** dispositivo en nivel Crítica **de su tipo** con derivaciones pendientes hacia él (alta). **AE-6** dispositivos con personas alojadas y sin entrega recibida en 48 h (media). **AE-7** personas alojadas con medicación crítica sin dosis ≥ 1 (alta; solo el número) | — |
| RN-009-10 | Las alertas de E8 son distintas de los siete avisos operativos de E1 (`services/avisos_emergencia.py`), que no se mueven ni se repiten. Con `supervisar`, E8 muestra «N avisos operativos en el tablero de la mesa» | Dos pantallas diciendo lo mismo con reglas distintas |
| RN-009-11 | **Supresión de números chicos**: los conteos del perfil (B11) se muestran como «menos de 5» entre 1 y 4 cuando el filtro activo es una localidad o un departamento. A nivel provincial, exactos. Los conteos operativos no se suprimen | Con un filtro fino, «1 embarazo en Lote 18» identifica a una persona |
| RN-009-12 | Los filtros acotan solo la demanda; la capacidad es siempre provincial y lo dice. El filtro se aplica con «Filtrar» y no cambia de solapa | El usuario cree que «no hay camas en el departamento» |
| RN-009-13 | E8 no muestra datos personales (RNF-009-01); enlaces a E1/E2 solo con `supervisar`; a la ficha de un dispositivo solo si Dispositivos lo permite; las coordenadas de dispositivos con `TipoDispositivo.ubicacion_reservada` no llegan al template | Exposición de familias o de dispositivos de protección |
| RN-009-14 | Sin auto-refresh: «Actualizar» vuelve a pedir la pantalla (decisión 6 del Cambio 472) | — |

---

## 6. Historias de usuario y criterios de aceptación

**HU-9.1** Como autoridad del Ministerio quiero ver la situación sin poder operar la mesa.
- [ ] Dado un usuario con solo `ver_situacion`, cuando entra a Emergencia, entonces ve «Situación» y no ve
  bandeja, tablero ni configuración; `/emergencia/tablero/` le responde 403.
- [ ] Dado ese usuario, cuando abre E8, entonces la respuesta (HTML y `json_script`) no contiene ningún apellido,
  DNI, dirección, número de caso ni coordenada de un caso sembrado, y no hay URLs de `/emergencia/casos/`.
- [ ] Dado un usuario sin `ver_situacion` ni `supervisar`, cuando pide `/emergencia/situacion/`, entonces 403.
- [ ] Dado un supervisor sin `ver_situacion` tildada, cuando abre E8, entonces la ve.

**HU-9.2** Como coordinador quiero saber si la red da abasto y por cuánto tiempo.
- [ ] Dado 1.850 camas operativas, 1.633 ocupadas y 54 reservadas, cuando abro E8, entonces «Camas libres» dice
  163 y la nota «88 % ocupada · 54 reservadas», con tono de nivel Crítica.
- [ ] Dado un dispositivo elegible con 20 plazas `CUPO` libres y 0 `CAMA`, cuando abro E8, entonces esas 20 no
  suman a camas libres.
- [ ] Dado un tipo con umbral rojo 90 y un dispositivo de ese tipo al 85 %, cuando abro E8, entonces el
  dispositivo es «Exigida» (no «Crítica») en capacidad y en el mapa.
- [ ] Dado 132 ingresos y 41 egresos en camas en las últimas 6 h y 163 libres, cuando abro E8, entonces «Horas
  hasta saturar» dice «≈ 11 h» con la nota «+15 camas/h netas en las últimas 6 h», y aparece AE-1.
- [ ] Dado más egresos que ingresos en las últimas 6 h, cuando abro E8, entonces dice «No se satura al ritmo
  actual».

**HU-9.3** Como coordinador quiero ver dónde está el problema en el mapa y en una tabla.
- [ ] Dado E8 recién abierta, cuando miro la solapa Mapa, entonces está cerrada con «Ver el mapa» y la página no
  pidió ningún recurso a openstreetmap.org.
- [ ] Dado 38 familias (133 personas) esperando en Barranqueras y 41 camas libres a ≤ 25 km, cuando abro el mapa,
  entonces el círculo de Barranqueras es «Crítica», encabeza «Localidades con más presión», y la fila de la tabla
  del Resumen dice 38 · 133 · 41 · Crítica (3,2×).
- [ ] Dadas dos `core.Localidad` llamadas «La Esperanza» en municipios distintos, con casos en las dos, cuando
  abro E8, entonces hay dos filas y dos círculos.
- [ ] Dado Juan José Castelli con casos y sin ningún dispositivo en la localidad, cuando abro el mapa, entonces su
  círculo aparece en el centroide de `UbicacionLocalidad`.
- [ ] Dado un supervisor que selecciona Barranqueras, cuando mira el panel, entonces tiene «Ver los 38 casos en la
  bandeja» hacia E2 con `?localidad=<id>`; con solo `ver_situacion`, no.
- [ ] Dado un tipo con `ubicacion_reservada` y un dispositivo de ese tipo con coordenadas, cuando pido E8,
  entonces sus coordenadas no están en la respuesta, no se dibuja, figura como «ubicación reservada» sin distancia
  entre los cercanos, y sus camas cuentan en B3 y en las cercanas.
- [ ] Dado un caso cuya localidad no tiene ubicación, cuando abro el mapa, entonces aparece «1 caso de localidades
  sin ubicación» y el caso está en la tabla.

**HU-9.4** Como coordinador quiero saber si estamos mejorando o empeorando.
- [ ] Dado casos creados a las 05:30 y a las 06:30 del 18/11, cuando miro la evolución de 7 días, entonces el
  primero cuenta en el día operativo del 17/11 y el segundo en el del 18/11.
- [ ] Dado 96 casos nuevos en las últimas 24 h y 70, 68 y 71 en los tres períodos anteriores, cuando abro E8,
  entonces aparece AE-3 con «38 % más que el promedio de los tres días anteriores».
- [ ] Dado la consulta de la evolución, cuando capturo el SQL, entonces no contiene `CONVERT_TZ`.

**HU-9.5** Como coordinador quiero ver dónde se traba el circuito.
- [ ] Dado 212 casos creados en las últimas 72 h (sin ingresos directos), 204 tomados, 181 derivados, 163
  aceptados y 149 alojados, cuando abro E8 con ventana 72 h, entonces el embudo muestra esos números con 96 %,
  89 %, 90 % y 91 % de conversión.
- [ ] Dado un caso derivado, rechazado y vuelto a derivar, cuando abro E8, entonces cuenta una vez en
  «derivados» y su rechazo cuenta en «derivaciones rechazadas».
- [ ] Dado un ingreso directo creado en la ventana, cuando abro E8, entonces no está en la cohorte y suma en
  «Ingresos directos».

**HU-9.6** Como coordinador quiero saber a quién estamos alojando sin ver a nadie.
- [ ] Dado 54 personas alojadas con medicación crítica, 9 sin dosis, cuando abro E8 sin filtro, entonces el perfil
  dice 54 y «9 sin dosis», y aparece AE-7.
- [ ] Dado el filtro en una localidad con 2 embarazos entre los alojados, cuando abro E8, entonces dice «menos de 5».

**HU-9.7** Como coordinador quiero saber si llegan los insumos.
- [ ] Dado 70 entregas recibidas en la ventana con 1.240 colchones enviados y 1.226 recibidos, cuando abro E8,
  entonces la fila «Colchones» dice 1.240 · 1.226 · −14.
- [ ] Dado un dispositivo con 40 personas alojadas por la emergencia y su última entrega recibida hace 60 h,
  cuando abro E8, entonces figura en «Sin entrega en 48 h».

**HU-9.8** Como coordinador quiero llevar la situación impresa a la reunión de la mesa.
- [ ] Dado E8 en la solapa Mapa, filtrada por el departamento San Fernando, cuando imprimo, entonces la hoja tiene
  el subtítulo «Departamento San Fernando · últimos 7 días», la franja de métricas, todo el Resumen con la tabla de
  presión completa y el pie «Documento de trabajo · datos agregados, sin datos personales», y no tiene mapa,
  sidebar, solapas ni botones.

**HU-9.9** Como supervisor quiero que E1 siga siendo la pantalla de la mesa.
- [ ] Dado E1, cuando la abro, entonces sus números no cambian salvo las correcciones del §8.2, tiene el botón
  «Ver la situación» y no tiene solapa de mapa.
- [ ] Dado E1 con 3 dispositivos y ningún caso, cuando la abro, entonces la tabla de localidades muestra «Todavía
  no hay casos» (pendiente 4 del Cambio 472).

---

## 7. Casos límite y excepciones

| Caso | Comportamiento esperado |
|---|---|
| Programa sin casos | Ceros, «—» en horas hasta saturar, estados vacíos; sin división por cero |
| Red sin camas operativas | B3 «0», ocupación «—» con nivel «Sin plazas», B4 «Red saturada», AE-1 |
| Localidad con esperando y 0 camas cercanas | Presión Crítica sin cociente («sin camas a 25 km») |
| Ventana de 7 días con un evento de 3 días | Los días sin datos se dibujan en cero |
| Caso con `localidad` nula | Fila «Sin localidad», no en el mapa |
| Dispositivo con coordenadas fuera del Chaco | No se dibuja; cuenta como «sin ubicación» (bbox de la provincia ± 0,5°) |
| Gran Resistencia | Los círculos se pisan a escala provincial; el mapa abre con un encuadre de la provincia y la lista permite saltar a cada localidad |
| `ficha` de versión distinta de 1 | Se lee con el esquema de su versión; una clave ausente no cuenta |
| Persona sin `fecha_nacimiento` | Cuenta en el total y en «edad sin dato» |
| Localidad que no está en el departamento elegido | Se ignora la localidad y se avisa |
| Parámetros GET inválidos | Se ignoran (Django Form de filtros), nunca 500 |
| Más de 60 localidades con demanda | Tabla paginada de a 25; el mapa las dibuja todas; la lista muestra 8 |
| Sin salida a internet | Mapa en estado de error; Resumen, lista y tabla completos |

---

## 8. Dependencias

- Datos del módulo ya en `development`: Cambios 463 a 478.
- **Tablero de Dispositivos** (spec del 08-nov): golden del arquetipo, piezas compartidas y mapa (§8.3–8.4).
- Dataset de localidades con centroide y departamento (Georef/BAHRA), bajado una vez y versionado.
- `services/ocupacion.py` con el filtro por tipo de plaza (§8.2).
- `scripts/perf_mysql/` para los `EXPLAIN` (RNF-009-10).

### 8.1 Diseño técnico propuesto (para las tasks)

```
core/
  models/                UbicacionLocalidad(TimeStamped): localidad (OneToOne core.Localidad), latitud,
                         longitud, departamento, fuente, id_fuente — tabla nueva, solo expand
  management/commands/   cargar_ubicaciones_localidades (idempotente; reporta no conciliadas y ambiguas)
  data/                  localidades_chaco_georef.csv (versionado)
  rbac.py                + emergencia.ver_situacion en el módulo emergencia
users/migrations/        00NN: la capacidad al rol Administrador (patrón users.0047)
programas/
  services/ocupacion.py             ocupacion_de_plazas(..., tipos=None) (compartido con la T7 de Dispositivos)
  services/emergencia_programa.py   CAP_VER_SITUACION, puede_ver_situacion (supervisar ⇒ ver_situacion)
  selectors/emergencia_situacion.py foto_de_situacion(sla, ahora, filtros) + resumen, presion_por_localidad,
                                    evolucion, capacidad, embudo, perfil, logistica y puntos_del_mapa
                                    (0 consultas con foto; puntos sin ubicación reservada ni familias)
  services/alertas_situacion_emergencia.py   AE-1 a AE-7 (puras sobre la foto)
  forms/emergencia_situacion.py     FiltrosSituacionForm (departamento, localidad, ventana, tab)
  views/emergencia_situacion.py     SituacionView
  templates/programas/emergencia/situacion/   esqueleto del arquetipo + _resumen.html + _mapa.html (capas)
```

### 8.2 Pendientes del Cambio 472 que entran en el mismo lote

| # (Cambio 472) | Pendiente | Por qué entra acá | Resolución propuesta |
|---|---|---|---|
| 1 | «Plazas libres» cuenta todas las plazas, no solo camas (también Cambio 464, pendiente 2) | E8 hace de la cama su número principal | Parámetro opcional `tipos` en `ocupacion_de_plazas` (por defecto, todas: Dispositivos no cambia; su T7 lo usa para «Encontrar plaza libre» por `Plaza.tipo`); E1, E8 y el panel «Derivar» de E3 piden `(CAMA,)` |
| 3 | Casos por localidad agrupa por nombre | Misma regla en E1 y E8 | Agrupar por `localidad_id` (RN-009-04) |
| 4 | «Todavía no hay casos» no aparece con red cargada | Mismo estado vacío en E8 | Condicionar con `hay_casos` |
| 5 | Solapa «Mapa de la emergencia» | La reemplaza E8 | No se hace; E1 enlaza a E8 |
| 6 | `entregas_en_camino` carga todo | E8 lee entregas | Recortar en la base y tomar el total de la foto |
| 7 | Dos definiciones de ingreso directo | El embudo excluye ingresos directos | Una sola (`CasoEmergencia.es_ingreso_directo` o su `Q`) |
| 8 | Copias (plazas libres en tres lugares, `TONOS`/`ICONOS`, `_foto`, `_plural`) | E8 sería la cuarta copia | Reusar las de origen; los tonos de tensión salen de `Tension.tono` |
| 9 | `q_entrega_sin_revisar` fuera de su módulo; tuplas por posición | B12 lo usa | Mover a `selectors/kits.py`; `NamedTuple` |
| 10 | Ventana de RN-5.1 sin índice | E8 amplía esa ventana | `EXPLAIN` y, si pesa, índices en migración aparte (§4.1) |
| 11 | Comentario muerto en `test_nodo_ui_piezas.py` | Se toca al sumar piezas | Borrarlo |

Queda afuera el pendiente 2 (revisión visual de E1), que es de QA.

### 8.3 Piezas de UI («lote = las piezas primero»)

Con el molde de la §3.3, **E8 casi no trae piezas nuevas**: lo que el spec de Dispositivos marca como nuevo (§3.2)
ya está aprobado y se construye una sola vez para los dos tableros.

| Pieza | Para E8 | Ficha | La construye |
|---|---|---|---|
| Hero, `_filtro_pildora.html`, `_stat_card` tablero, `tabs.md`, `_alerta`, `.tabla`, badges con ícono, `_estado_vacio` | Existen | Las del inventario | — |
| Arquetipo Dashboard de programa (golden) | Compartida | `arquetipos/dashboard.md` (pieza 1, T11) | Dispositivos; E8 se declara de ese arquetipo |
| Barra con marcas de umbral (y sin marcas) | Compartida | pieza 4 (T4) | El primero que llegue |
| Gráfico de barras pareadas | Compartida | pieza 2 (T5) | El primero que llegue |
| Mapa `components/_mapa.html` | Compartida | pieza 3 (T9) | El primero que llegue |
| Lista de selección `item-lista` | Compartida | pieza 10 | El primero que llegue |
| **Varias capas en `_mapa.html`** (localidades + dispositivos, control de capas, leyenda por capa) | **Extensión de la pieza**, no pieza nueva | se agrega a la ficha del mapa en el PR que la use | E8 (si Dispositivos solo dibuja una capa) |
| **Panel «Localidad seleccionada»** | Variante del panel «Dispositivo seleccionado» de la solapa Mapa de Dispositivos | misma ficha del mapa | E8 |

El **embudo** se arma con barras sin marcas + tabla, y la **evolución** con barras pareadas + la cifra de personas
alojadas al cierre en la tabla equivalente: ninguno pide pieza propia. Lo que quede como novedad al cruzar con las
fichas (por ejemplo, la línea de personas alojadas sobre las barras, si el PM la quiere) se frena y se devuelve.

### 8.4 Corte en PRs

**Tareas compartidas con el tablero de Dispositivos** (las hace quien llegue primero; el otro las reusa):

| Tarea | Equivale a | Contenido | Horas (spec de Dispositivos) |
|---|---|---|---|
| C1 | T9 | Mapa: Leaflet en `static/vendor/leaflet/`, **`MAPA_TILES_HOSTS` solo en `img-src`**, `components/_mapa.html` y ficha, `componentes/ubicacion.md`, `SinRecursosDeTercerosTests` | 6 |
| C2 | T9b | `TipoDispositivo.ubicacion_reservada` (migración con `DEFAULT` real), configuración y filtro en el servicio | 2 |
| C3 | T4 | Barra con marcas de umbral + ficha | 3 |
| C4 | T5 (solo la pieza) | Gráfico de barras pareadas + ficha | ~2 de las 4 |
| C5 | pieza 10 | `item-lista` + ficha | (dentro de T10) |
| C6 | T11 (solo la golden) | `arquetipos/dashboard.md` y `pendientes.md` | (dentro de T11) |
| C7 | parte de T7 | Parámetro `tipos` en `ocupacion_de_plazas` | 1 |

**PRs propios de E8:**

| PR | Contenido | Migración | Depende de | Horas (estimación) |
|---|---|---|---|---|
| E-1 | Deuda de E1 del §8.2 (camas con C7, `localidad_id`, estado vacío, ingreso directo único, entregas recortadas, copias, `q_entrega_sin_revisar`, comentario) + `EXPLAIN` de la ventana | Solo si el `EXPLAIN` pide índices (aparte) | C7 | 6 |
| E-2 | `core.UbicacionLocalidad` + comando + CSV; reporte de conciliación revisado por el PM | `core.00NN` (tabla nueva) | — | 5 |
| E-3 | `emergencia.ver_situacion` (catálogo, helper, mixin, sidebar), migración para Administrador | `users.00NN` | — | 2 |
| E-4 | Selectores de E8 (incluidos los puntos del mapa con el filtro de `ubicacion_reservada`), alertas AE-1 a AE-7, tests de cada número, presupuesto `--tag performance`, SQL sin `CONVERT_TZ`, motores | Índices de §4.1 si hacen falta (aparte) | E-1, E-2, C2 | 8 |
| E-5 | Vista, form de filtros, esqueleto del arquetipo, **solapa Resumen** completa, impresión, enlaces E1 ↔ E8, tests de permisos y de no nominalidad | — | E-3, E-4, C3, C4, C6 | 8 |
| E-6 | **Solapa Mapa**: capas de localidades y dispositivos sobre `_mapa.html`, panel «Localidad seleccionada», «Localidades con más presión», estados, test de mutación de `ubicacion_reservada` | — | E-5, C1, C2, C5 | 5 |

**Total propio de E8: ~34 h.** Si Dispositivos no construyó antes las tareas compartidas, E8 suma las que use
(C1–C7, **~14 h**) y Dispositivos las descuenta después. Cada PR con su Cambio en `requerimientos.md` al mergearse,
`/auditoria pr`, casos de QA, `design_audit.py --ratchet` en 0 nuevos y `check_design_agent.py`.

**Orden.** E-1, E-2 y E-3 son independientes y pueden ir en paralelo. E-4 después de E-1 y E-2. E-5 espera las
piezas C3, C4, C6. E-6 espera el mapa (C1) y el indicador de ubicación reservada (C2). Si el tablero de
Dispositivos ya tiene hechas T9, T9b y T10, **E-6 solo agrega las capas** y baja a ~3 h.

---

## 9. Fuera de alcance

- Lo de la propuesta de octubre que **no tiene datos** en DATAÑACH: incidentes, alertas pluviales y fluviales,
  criticidad o semáforos cargados a mano por zona, polígonos de zonas afectadas, población afectada no evacuada,
  stock y faltantes, FUSE, Mesas 1 a 4, bitácora de la mesa, tableros por rol, actualización en vivo.
- Un mapa propio en SVG o mosaicos propios (§3.5); un mapa impreso (se imprime la tabla).
- Capa de densidad de relevamientos por grilla (ampliación: si se hace, celdas de ≥ 5 casos y el centro de la
  celda como única coordenada que viaja).
- Coropletas por departamento o municipio y contornos de departamento.
- FK de `Dispositivo` a `core.Localidad` (dominio Dispositivos).
- Obligar a Dispositivos a usar `UbicacionLocalidad` (queda propuesto, §3.5).
- Snapshot diario, comparación entre eventos o semanas, % de ocupación histórico.
- Exportar (igual que en Dispositivos v1) y PDF generado en el servidor.
- Auto-refresh, panel en vivo y «modo sala de situación» (alternativas no aprobadas también en Dispositivos §9).
- Mover o duplicar en E8 los avisos operativos de E1.
- Usar `UbicacionLocalidad` en RN-2.4 (distancia en el panel Derivar): lo habilita, es otro cambio.
- Vista de E8 en la app de campo.

---

## 10. Preguntas abiertas

| # | Pregunta | Responsable de responder | Estado |
|---|---|---|---|
| 1 | ¿Quiénes reciben `ver_situacion`? ¿Se arma un rol «Autoridades»? | PM / Ministerio | Abierta |
| 2 | Radio de «camas cercanas»: ¿25 km para todos? | PM / mesa | Abierta (propuesta: 25 km) |
| 3 | Umbrales de las alertas (12 h, nivel Crítica de la red, alza ≥ 30 % con 20 casos, p90 > 2× objetivo, 48 h sin entrega): ¿fijos o en E7? | PM | Abierta (propuesta: fijos en este lote) |
| 4 | ¿Hace falta filtrar la **capacidad** por departamento? Requiere FK de `Dispositivo` a localidad | PM | Abierta |
| 5 | ¿El evento tiene fecha de inicio? Con `inicio_evento` en `SLAEmergencia` habría acumulados «desde el inicio» | PM | Abierta (propuesta: no en este lote) |
| 6 | ¿Se proyecta en una pantalla de la mesa? Si sí, entra el «modo sala de situación» que Dispositivos también dejó afuera, y la caché | PM / mesa | Abierta |
| 7 | Mínimo de supresión del perfil: ¿5, también con filtro de departamento? | PM / área legal o de datos | Abierta (propuesta: 5) |
| 8 | ¿Se acepta la atribución BAHRA/Georef de las localidades (además de la de OSM del mapa)? | PM | Abierta |
| 9 | ¿Qué se hace con las localidades del fixture que no concilian con Georef? | PM | Abierta |
| 10 | ¿Quién construye primero las piezas compartidas (C1–C7): el tablero de Dispositivos o E8? | PM | Abierta |
| 11 | ¿Dispositivos adopta `UbicacionLocalidad` para «Cerca de» cuando la localidad no tiene dispositivos con coordenadas? | PM | Abierta (propuesta: sí, opcional) |

---

## 11. Historial de cambios del análisis

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-18 | Versión inicial | Pedido del PM: «análisis funcional del mapa, no solo del mapa: un tablero estratégico con información útil» |
| 2026-11-18 | Alineado con el diseño aprobado del tablero de Dispositivos y con emergencia-design §7.1: molde «Dashboard de programa» con solapas Resumen / Mapa; mapa = pieza única `_mapa.html` (Leaflet vendorizado, OSM a pedido, `MAPA_TILES_HOSTS` solo en `img-src`) en lugar del SVG propio; `ubicacion_reservada`; capacidad con `disponibles` y `tension_de_ocupacion` del tipo; `UbicacionLocalidad` como diferencia justificada; piezas compartidas y plan de PRs con las tareas de Dispositivos; impresión sin mapa | La versión inicial no había tenido en cuenta ese diseño |

---

## 12. Pantalla

Base para el mockup, sobre el esqueleto del mockup aprobado de Dispositivos. Datos **ficticios** pero coherentes
entre bloques. Momento: martes 18/11/2026 14:35, día operativo desde las 06:00. Evento: «Crecida del Paraná y del
Negro · Noviembre 2026». Ventana elegida: 7 días.

### Arriba de las solapas

**A · Hero.** Eyebrow «Programa Emergencia · Situación». Título «Crecida del Paraná y del Negro · Noviembre 2026».
Bajada: «**1.284** personas alojadas en **38** dispositivos · **412** esperando lugar · **163** camas libres (88 %
de ocupación).» Acción «Actualizar». (Con `supervisar`, enlace de texto «Ir al tablero de la mesa».)

**B · Filtros en píldora.** Departamento [Todos ▾] · Localidad [Todas ▾] · Ventana [7 días ▾] · **Filtrar** ·
Limpiar · «Actualizado a las 14:35» · Imprimir. Nota: «Los filtros acotan la demanda; las camas son siempre de toda
la provincia.»

**C · Franja de métricas** (4 stat cards grandes)

| Indicador | Valor | Nota | Tono |
|---|---|---|---|
| Personas alojadas | 1.284 | en 38 dispositivos · +146 desde las 06:00 | brand |
| Personas esperando lugar | 412 | 118 familias · 37 fuera de SLA | warning |
| Camas libres en la red | 163 | 88 % ocupada · 54 reservadas | danger (Crítica) |
| Horas hasta saturar | ≈ 11 h | +15 camas/h netas en las últimas 6 h | danger |

**D · Solapas:** **Resumen** | Mapa

### Solapa Resumen (bloques apilados, en este orden)

**R1 · Necesita atención** (`_alerta`, «Mostrando 6 de 7»)
1. Alta · «La red se satura en ≈ 11 h al ritmo actual» — «En las últimas 6 h ingresaron 132 personas y egresaron
   41. Quedan 163 camas libres.»
2. Alta · «Presión crítica en 4 localidades: Juan José Castelli, Barranqueras y Resistencia, y 1 más» —
   «Barranqueras: 133 personas esperan y hay 41 camas libres a menos de 25 km, que comparte con Resistencia,
   Fontana y Puerto Vilelas.»
3. Alta · «Club Atlético Sarmiento (Resistencia) está lleno y tiene 2 derivaciones pendientes.»
4. Alta · «9 personas alojadas con medicación crítica no tienen dosis.»
5. Media · «Casos nuevos en alza: 96 en las últimas 24 h, 38 % más que el promedio de los tres días anteriores.»
6. Media · «El tramo “aceptar” está trabado: el p90 es 4 h 10 min contra un objetivo de 2 h.»

(La 7.ª, «3 dispositivos con gente y sin entrega en 48 h», queda fuera por el tope y está en R7.) Con
`supervisar`, al pie: «Hay 11 avisos operativos en el tablero de la mesa →».

**R2 · Presión por localidad** (tabla `.tabla`, ancho completo; badge con ícono + texto)

| Localidad | Departamento | Familias | Personas | Fuera de SLA | Alojadas | Camas cercanas | Presión |
|---|---|---:|---:|---:|---:|---:|---|
| Barranqueras | San Fernando | 38 | 133 | 14 | 402 | 41 | Crítica · 3,2× |
| Juan José Castelli | General Güemes | 7 | 26 | 2 | 61 | 4 | Crítica · 6,5× |
| Resistencia | San Fernando | 31 | 104 | 9 | 356 | 41 | Crítica · 2,5× |
| Machagai | 25 de Mayo | 2 | 7 | 1 | 19 | 3 | Crítica · 2,3× |
| Puerto Vilelas | San Fernando | 14 | 52 | 6 | 97 | 41 | Crítica · 1,3× |
| Las Breñas | 9 de Julio | 1 | 3 | 0 | 7 | 0 | Crítica · sin camas a 25 km |
| Fontana | San Fernando | 9 | 33 | 3 | 88 | 41 | Exigida · 0,8× |
| Libertador General San Martín | Libertador General San Martín | 6 | 21 | 1 | 58 | 30 | Exigida · 0,7× |
| Presidencia Roque Sáenz Peña | Comandante Fernández | 5 | 17 | 1 | 71 | 46 | Normal · 0,4× |
| Quitilipi | Quitilipi | 3 | 9 | 0 | 24 | 46 | Normal · 0,2× |
| Villa Ángela | Mayor Luis J. Fontana | 1 | 4 | 0 | 18 | 18 | Normal · 0,2× |
| Charata | Chacabuco | 1 | 3 | 0 | 12 | 20 | Normal · 0,2× |
| Otras localidades (9) | — | 0 | 0 | 0 | 71 | — | Sin demanda |
| **Total** | | **118** | **412** | **37** | **1.284** | | |

**R3 · Evolución** (½ izquierda; barras pareadas casos nuevos / familias alojadas; tabla equivalente con la
columna de personas alojadas; referencia «camas operativas hoy: 1.850»)

| Día operativo | Casos nuevos | Familias alojadas | Personas alojadas al cierre |
|---|---:|---:|---:|
| Mié 12/11 | 18 | 9 | 212 |
| Jue 13/11 | 41 | 30 | 318 |
| Vie 14/11 | 63 | 52 | 496 |
| Sáb 15/11 | 70 | 61 | 702 |
| Dom 16/11 | 68 | 64 | 918 |
| Lun 17/11 | 71 | 66 | 1.138 |
| Mar 18/11 (hasta 14:35) | 54 | 44 | 1.284 |

**R4 · Capacidad de la red** (½ derecha). Barra con marcas en 60 % y 80 %: ocupadas 1.633 · reservadas 54 ·
libres 163 de 1.850 operativas (88 %, Crítica); aparte «22 fuera de servicio» y «2 sin ubicación». Más tensionados
(barra con las marcas **de su tipo**):

| Dispositivo | Tipo (umbrales) | Localidad | Camas | Nivel | Derivaciones pendientes |
|---|---|---|---|---|---:|
| Club Atlético Sarmiento | Centro de evacuados (70/85) | Resistencia | 120 / 120 · 100 % | Crítica | 2 |
| EES N.° 9 | Centro de evacuados (70/85) | Barranqueras | 86 / 90 · 96 % | Crítica | 1 |
| Polideportivo Municipal | Centro de evacuados (70/85) | Fontana | 72 / 80 · 90 % | Crítica | 0 |
| Centro de Evacuados Puerto Vilelas | Centro de evacuados (70/85) | Puerto Vilelas | 58 / 70 · 83 % | Exigida | 1 |
| Hogar San José | Hogar (50/80) | Resistencia | 33 / 40 · 83 % | Crítica | 0 |

(Tipos y umbrales de ejemplo: los configura el PM en `dispositivos:tipos`.)

**R5 · Embudo del circuito** (½ izquierda; ventana 72 h; barras sin marcas + tabla)

| Paso | Casos | Conversión | Tramo | Mediana | p90 | Objetivo |
|---|---:|---:|---|---|---|---|
| Relevados | 212 | — | | | | |
| Tomados | 204 | 96 % | tomar | 9 min | 22 min | 15 min |
| Derivados | 181 | 89 % | derivar | 26 min | 58 min | 30 min |
| Aceptados | 163 | 90 % | aceptar | 1 h 35 min | **4 h 10 min** | 2 h |
| Alojados | 149 | 91 % | alojar | 48 min | 1 h 40 min | 1 h |

Salidas: cerrados sin alojar 17 (no requiere alojamiento 7 · sin contacto 6 · se alojó por su cuenta 4).
Derivaciones rechazadas 14 (sin camas 8 · no admite mascotas 3 · otros 3), vencidas 6. Ingresos directos 9.

**R6 · Perfil de las personas** (½ derecha)
- Alojadas (1.284, ficha confirmada): menores de 16 498 (39 %) · mayores de 60 167 (13 %) · edad sin dato 12 ·
  embarazo 21 · discapacidad 38 · electrodependientes 6 · medicación crítica 54, **9 sin dosis**.
- Esperando (412 personas, 118 familias, declarado): menores 161 · mayores 58 · lactantes 12 · con dependencia 9
  (3 mayores dependientes) · familias con embarazo 7 · electrodependencia 2 · medicación crítica 11 · mascotas 23.
- Pie: «Agregado. Con un filtro de localidad o departamento, los valores de 1 a 4 se muestran como “menos de 5”.»

**R7 · Logística de kits** (ancho completo). Stat cards **chicas** (otra `surface`): despachadas 86 · recibidas
70 (9 con diferencias) · en camino 12 · tránsito mediano 3 h 20 min. Tabla sobre las 70 recibidas:

| Ítem | Enviado | Recibido | Diferencia |
|---|---:|---:|---:|
| Colchones | 1.240 | 1.226 | −14 |
| Frazadas | 2.100 | 2.100 | 0 |
| Kit de higiene | 980 | 962 | −18 |
| Agua (bidón 6 l) | 1.450 | 1.438 | −12 |
| Módulo alimentario | 1.120 | 1.120 | 0 |
| Pañales (paquete) | 310 | 296 | −14 |

«Con gente y sin entrega recibida en 48 h»: Escuela N.° 1031 (Villa Ángela, 18 personas, última hace 61 h) ·
Salón Parroquial (Charata, 12 personas, nunca) · Gimnasio Provincial (Presidencia Roque Sáenz Peña, 64 personas,
última hace 52 h).

**R8 · Cómo se calcula** (plegable): camas, esperando, cercanas a 25 km, presión, ritmo de 6 h, día operativo
desde las 06:00, fuentes (OSM para el fondo; BAHRA/Georef para las localidades).

### Solapa Mapa

**Cerrado:** estado vacío «El mapa se carga cuando lo pedís: hasta entonces no se le manda nada a OpenStreetMap»
con el botón **Ver el mapa**. La lista «Localidades con más presión» ya está visible.

**Abierto** (dos columnas: mapa ⅔, panel ⅓):
- **Mapa:** encuadre de la provincia; capas [✓] Localidades · [✓] Dispositivos · [ ] Entregas en camino.
  Círculos de localidad (tamaño por personas esperando): rojos en Barranqueras, Resistencia, Puerto Vilelas,
  Juan José Castelli, Machagai y Las Breñas; ámbar en Fontana y Libertador General San Martín; verdes en
  Presidencia Roque Sáenz Peña, Quitilipi, Villa Ángela y Charata. Dispositivos (círculos chicos con borde): 35
  dibujados, rojos Club Atlético Sarmiento, EES N.° 9, Polideportivo Municipal y Hogar San José; ámbar Centro de
  Evacuados Puerto Vilelas; verdes Gimnasio Provincial, Escuela N.° 1031, Salón Parroquial. Pie: «2 dispositivos
  sin ubicación · 1 con ubicación reservada · 4 casos de localidades sin ubicación».
- **Leyenda** (badges con ícono + texto): Presión Crítica / Exigida / Normal / Sin demanda · tamaño = personas
  esperando · Dispositivos Crítica / Exigida / Normal / Sin plazas.
- **Localidad seleccionada: Barranqueras · Dpto. San Fernando** — badge Crítica 3,2× · 38 familias, 133 personas
  esperando, 14 fuera de SLA · 402 personas de Barranqueras ya alojadas · 41 camas libres a ≤ 25 km en 9
  dispositivos · más cercanos: EES N.° 9 (1,2 km) 4 libres de 90 · Club Atlético Sarmiento (6,8 km) 0 de 120 ·
  Refugio Municipal (ubicación reservada) 6 libres · (con `supervisar`) «Ver los 38 casos en la bandeja».
- **Localidades con más presión** (`item-lista`, 8): Juan José Castelli 6,5× · Barranqueras 3,2× · Resistencia
  2,5× · Machagai 2,3× · Puerto Vilelas 1,3× · Las Breñas (sin camas a 25 km) · Fontana 0,8× · Libertador General
  San Martín 0,7×.
