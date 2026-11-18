# Análisis funcional 009 — Emergencia: tablero estratégico «Situación» con mapa (E8)

**Estado:** En análisis
**Fecha de análisis:** 2026-11-18
**Analista:** functional-analyst (sesión con el PM)
**Sprint asociado:** Sin asignar
**Módulo/App:** `programas` (Emergencia: selectores, servicios, vista y template nuevos), `core` (tabla nueva de
ubicación de localidades y capacidad nueva en `core/rbac.py`), `users` (migración de la capacidad)
**Mock-ups:** a armar con el layout y los datos de ejemplo de la §12 («Pantalla»)

> **Numeración.** El 008 lo ocupa `008-dispositivos-v2-segunda-etapa.md` en la rama `ccr-98cf5793-ouuaub`
> (sin mergear): este análisis toma el **009** para no chocar.
>
> **Base.** El código de `development` al 18/11/2026 (merge #1160), el Cambio 472 (tablero E1) y sus pendientes,
> los Cambios 463 y 464, el análisis del módulo (`docs/internal/emergencia/` en la rama `docs/emergencia-analisis`,
> sobre todo `05-seguir-y-configurar.md`) y la propuesta de octubre
> (`docs/client/propuestas/mesa-situacion-el-nino.md`). Ante una diferencia entre este documento y el código, gana el
> código y este documento se corrige.

---

## 1. Contexto y motivación

El módulo Emergencia ya tiene un tablero: **E1**, en `/emergencia/tablero/` (Cambio 472). Es una pantalla
**operativa** pensada para el supervisor de la mesa: le dice qué tiene que resolver *ahora* —casos nuevos sin
tomar, casos fuera de SLA, derivaciones por vencer, familias en la puerta, entregas con diferencias— y lo lleva al
caso. Mira una ventana corta (los casos abiertos y lo alojado o cerrado en las últimas 24 h, RN-5.1) y no tiene
gráficos, mapa ni tendencia. La solapa «Mapa de la emergencia» que pedía la especificación quedó afuera y sin
prometer (Cambio 472, pendiente 5).

El PM pidió primero «mejorar el módulo del tablero de Emergencia, agregando un mapa», y después lo precisó: «no
solo el mapa: tiene que ser un **tablero estratégico con información útil**». La diferencia importa. Quien
coordina la emergencia y las autoridades del Ministerio no preguntan «¿qué caso tomo?», preguntan: ¿dónde está
el problema?, ¿la red de albergues da abasto y por cuánto tiempo?, ¿estamos mejorando o empeorando?, ¿dónde se
traba el circuito?, ¿a quién estamos alojando?, ¿llegan los insumos? Esas preguntas se responden con agregados,
tendencia y territorio, no con una lista de casos; y las tiene que poder ver alguien que **no opera** la mesa
(un secretario, el ministro, la coordinación con Defensa Civil) sin quedar habilitado a reasignar casos o
cambiar el SLA, que es lo que hoy implica `emergencia.supervisar` (Cambio 463, decisión 4).

La propuesta de octubre ya ponía el mapa provincial como pantalla principal de una mesa de situación (zonas,
criticidad, filtros por departamento y localidad, semáforos), pero sobre datos que DATAÑACH **no tiene**
(incidentes, alertas pluviales, criticidad cargada por los equipos, stock, cuatro mesas). Este análisis toma de
esa propuesta **solo lo que se puede calcular hoy** con los datos reales del módulo —casos con localidad y GPS,
familias declaradas, fichas individuales, camas y estadías, derivaciones con sus tiempos, entregas de kits— y
deja el resto como fuera de alcance explícito (§9).

Hay una restricción de base que condiciona el mapa: **ninguna tabla geográfica del sistema tiene coordenadas.**
`core.Localidad` y `core.Municipio` son solo nombres (`core/models/base.py`), no existe `Departamento`, y la
jerarquía cargada para Chaco (fixture `core/fixtures/localidad_municipio_provincia.json`: 79 «municipios», 778
localidades, 62 nombres de localidad repetidos) mezcla municipios con departamentos («Comandante Fernández»,
«Tapenagá», «1° de Mayo»…). Lo que sí tiene coordenadas es el **caso** (`CasoEmergencia.latitud/longitud/precision_m`,
GPS del relevamiento), el **dispositivo** (`Dispositivo.latitud/longitud`) y el **edificio**
(`Edificio.latitud/longitud`). Las coordenadas de la familia, además, son dato personal: el mapa no las puede
dibujar. La §3.4 resuelve de dónde salen las posiciones de las localidades.

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
| Rendimiento | La solapa se calcularía con E1 (16 consultas hoy) o pediría carga diferida | Presupuesto propio (§4, RNF-009-03); E1 queda en 16 |
| Impresión | Una solapa no se imprime bien | Hoja propia con estilo de impresión |
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

### 3.3 Flujo principal

1. El usuario entra a **Emergencia › Situación**.
2. Ve el **hero** con el nombre del evento (`SLAEmergencia.nombre_evento`) y una frase con los tres números que
   resumen la situación: personas alojadas, personas esperando lugar y camas libres con la ocupación de la red.
3. Debajo, la **barra de filtros**: departamento, localidad y ventana (72 h o 7 días), y el botón **Imprimir**.
4. Cuatro **indicadores** grandes: personas alojadas, personas esperando, camas libres, horas hasta saturar.
5. **Alertas estratégicas** (a lo sumo seis, ordenadas por severidad), calculadas al leer y sin estado.
6. El **mapa** de la provincia con la presión por localidad (círculos), los dispositivos con su semáforo de
   ocupación (cuadrados) y, opcional, las entregas en camino; al costado, la leyenda y el panel de la localidad
   elegida. Tocar un círculo recarga la pantalla con esa localidad en el panel (`?ver=<id>`): cuántas familias y
   personas esperan, cuántas están fuera de SLA, cuántas personas de ahí ya están alojadas, las camas libres
   cercanas y los tres dispositivos más cercanos con sus camas libres. Con `supervisar`, el panel trae «Ver los
   N casos en la bandeja» (E2 filtrada por `localidad`).
7. La **tabla «Presión por localidad»**: el mismo dato del mapa en filas, ordenado por presión. Es la alternativa
   accesible del mapa y lo que sale impreso.
8. **Evolución** (7 días por día operativo, o 72 h en bloques de 6 h): casos nuevos y familias alojadas por
   período (barras) y personas alojadas al cierre de cada período (línea).
9. **Capacidad de la red**: barra apilada de camas (ocupadas, reservadas, libres; fuera de servicio aparte) y
   los dispositivos más exigidos.
10. **Embudo del circuito** de la ventana: relevados → tomados → derivados → aceptados → alojados, con la
    conversión de cada paso, la mediana de cada tramo contra su objetivo y lo que salió del circuito (cerrados
    sin alojar, por motivo; derivaciones rechazadas y vencidas).
11. **Perfil de las personas**, alojadas y esperando, siempre en agregado.
12. **Logística de kits** de la ventana: entregas por estado, enviado contra recibido por ítem, tránsito mediano
    y dispositivos con gente que no recibieron insumos.
13. Al pie, «Cómo se calcula» (plegable) con las definiciones y las fuentes del mapa.

### 3.4 El mapa: opciones y recomendación

**Qué hace falta en cualquier opción:** (1) la **posición de cada localidad** —ninguna tabla la tiene— y (2) el
**contorno de la provincia** para orientar. Lo primero se resuelve igual en las tres opciones; lo segundo cambia.

**Posición de las localidades.** Tres fuentes posibles:

| Fuente | Pros | Contras | Veredicto |
|---|---|---|---|
| Centroide calculado de los GPS de los casos | Sin carga inicial | Sesgado; no existe para localidades sin casos con GPS; con 1 o 2 casos el «centroide» **es la casa de la familia** | Descartada (privacidad) |
| Columnas `latitud/longitud` en `core.Localidad` | Una sola tabla | `ALTER` sobre una tabla compartida de 8.779 filas de todo el país, que usan Legajos, Becas y SIIS; solo se llenarían las de Chaco | Descartada |
| **Tabla nueva `core.UbicacionLocalidad`** cargada una vez desde un dataset oficial | Solo *expand* (tabla nueva, cero riesgo de rollback); trae además el **departamento**; sirve también a RN-2.4 (distancia desde el centroide de la localidad cuando el caso no tiene GPS, pendiente 4 del Cambio 463) | Requiere conciliar nombres una vez | **Elegida** |

`UbicacionLocalidad(TimeStamped)`: `localidad` (OneToOne a `core.Localidad`), `latitud`, `longitud`
(`DecimalField(9,6)`), `departamento` (texto), `fuente` (texto), `id_fuente` (el id del dataset). Se carga con un
comando idempotente desde un CSV versionado en el repo, extraído una vez del servicio Georef de datos.gob.ar
(localidades de la provincia del Chaco, con centroide y departamento; fuente BAHRA/INDEC, licencia abierta con
atribución). La conciliación es por nombre normalizado + municipio; lo que no concilia queda listado en la salida
del comando y **sin posición** (el caso aparece en la tabla, no en el mapa; el mapa dice «N casos de localidades
sin ubicación»). Mismo patrón que `AliasLocalidadSiis` para lo ambiguo.

**Opciones de mapa:**

| | (a) **Mapa vectorial propio en SVG, dibujado en el servidor** | (b) Leaflet o MapLibre autohospedado + teselas de OpenStreetMap | (c) Teselas propias |
|---|---|---|---|
| Qué es | Contorno de la provincia (y, como referencia, los límites de departamento) en un `<path>` versionado en `static/`; localidades y dispositivos proyectados en Python (equirectangular con corrección `cos φ₀`, φ₀ ≈ −26,4°: error < 1 % a escala provincial) y dibujados como `<circle>`/`<rect>` | Librería JS en `static/vendor/`, fondo de calles de `tile.openstreetmap.org` | Generar y servir las teselas de Chaco (raster o vectoriales/PMTiles) desde nuestro servidor |
| CSP | **Sin cambios** | Ampliar `img-src` a `https://tile.openstreetmap.org` (hoy `MAPA_HOSTS` solo tiene `www.openstreetmap.org` para el iframe de Becas) | Sin terceros, pero `connect-src`/rangos HTTP según el formato |
| Privacidad | Las coordenadas no salen del servidor: el HTML trae solo agregados ya posicionados | Cada tesela pide a la OSMF desde el navegador del usuario (IP y zona mirada); los datos del mapa viajan como JSON al navegador | Igual que (a) |
| Terceros en una emergencia | Ninguno | Depende de la disponibilidad de OSM y de que la red del Ministerio salga a internet. La política de uso de teselas de OSM no ofrece SLA, exige atribución y desaconseja uso intensivo | Ninguno, pero hay que operarlo |
| Costo | Bajo: un asset, un selector de proyección, una pieza de template | Medio: librería, integración JS, CSP, revisión de seguridad | Alto: ~7.500 teselas raster z6–z13 (≈150 MB) o un pipeline vectorial, actualización y atribución ODbL |
| Imprime | Nítido (vectorial) | Mal (teselas a medio cargar, escala) | Según el formato |
| Testeable | Con aserciones sobre el HTML (`<circle aria-label=…>`) | Solo en navegador | Solo en navegador |
| Detalle de calles | **No** (no hace falta para decidir a escala provincial) | Sí | Sí |
| Precedente | E1 y la decisión C-14 de Dispositivos v2 («sin mapa embebido: coordenadas + enlace ver en el mapa») | Ninguno en el backoffice | Ninguno |

**Recomendación: (a).** El tablero responde «dónde está el problema» a escala provincial y de aglomerado, no
«cómo llego»; para eso un SVG con el contorno, los círculos y un recuadro ampliado del Gran Resistencia alcanza,
no abre la CSP, no depende de terceros en el peor momento, no manda coordenadas al navegador, se imprime bien y
se prueba como cualquier template. El detalle de calles sigue a un clic: cada dispositivo ya tiene «Ver en el
mapa» (`components/_ubicacion.html`, enlace a openstreetmap.org en pestaña nueva). Si el Ministerio pidiera
navegación de calles dentro de la pantalla, (b) queda como ampliación con su propio análisis de CSP y ADR.

**Contorno:** capa de provincia y de departamentos del IGN (licencia abierta con atribución), simplificada a
< 60 KB, convertida una vez a `path` SVG en coordenadas ya proyectadas y versionada en
`static/custom/geo/chaco.svg` (o como constante del selector). La atribución va al pie del mapa: «Límites: IGN.
Localidades: BAHRA/Georef».

### 3.5 Capas del mapa

| Capa | Qué dibuja | Fuente | Por defecto |
|---|---|---|---|
| **Presión por localidad** | Un círculo por localidad con demanda o alojados, en su centroide. **Tamaño** = personas esperando (√, radio 4–18 px); **color** = nivel de presión (RN-009-06); anillo grueso en «crítica» para no depender solo del color | Foto de casos + `UbicacionLocalidad` | Encendida |
| **Dispositivos** | Un cuadrado por dispositivo elegible con coordenadas, color = tensión de ocupación de camas con los umbrales de su tipo (`tension_de_ocupacion(conteo, tipo=…)`); `<title>` con «Club Sarmiento · 120/120 camas · Crítica» | Red de dispositivos | Encendida |
| **Entregas en camino** | Ícono de camión con el número de entregas `EN_CAMINO` junto al dispositivo destino | `EntregaKit` | Apagada |
| **Densidad de relevamientos** (fase 2) | Grilla de celdas de 0,05° (~5 km) con la cantidad de casos con GPS de precisión ≤ 1.000 m; **solo celdas con 5 casos o más** | `CasoEmergencia.latitud/longitud/precision_m` | Apagada; PR opcional |

Las capas se prenden y apagan con parámetros GET (`?capas=localidades,dispositivos`), sin JS obligatorio.
**Recuadro «Gran Resistencia»** (Resistencia, Barranqueras, Fontana, Puerto Vilelas): a escala provincial los
cuatro círculos se pisan; el recuadro los muestra ampliados en una esquina del mapa.

**Interacción.** Círculo → `?ver=<localidad_id>` y el panel lateral con el detalle (§3.3 paso 6); con
`supervisar`, enlace a `emergencia:bandeja?localidad=<id>`. Cuadrado → ficha del dispositivo
(`dispositivos:detalle`) solo si el usuario la puede ver por Dispositivos; si no, solo el `<title>`. Cada
elemento es un `<a>` dentro del SVG con `aria-label` completo («Barranqueras: 38 familias, 133 personas
esperando, presión crítica»), alcanzable con teclado.

**Accesibilidad.** El SVG lleva `role="group"` con título y descripción; **el mapa nunca es la única vía**: la
tabla «Presión por localidad» tiene exactamente los mismos números, y la leyenda nombra cada nivel en texto.

**Privacidad.** El mapa nunca dibuja la posición de una familia; las coordenadas del caso no se envían al
navegador; la posición que se dibuja es la del centroide oficial de la localidad o la del dispositivo. La capa
de densidad agrega en celdas y suprime las de menos de 5 casos.

### 3.6 Flujos alternativos

**Sin casos todavía**
- Condición: el programa no tiene casos en la ventana ni abiertos.
- Comportamiento: indicadores en cero, «—» en horas hasta saturar, mapa con los dispositivos solos y estado vacío
  «Todavía no hay casos» en presión, embudo y perfil. Sin divisiones por cero.

**Filtro por departamento o localidad**
- Condición: el usuario elige un departamento o una localidad.
- Comportamiento: se acotan los bloques de **demanda** (indicador de esperando, alertas por localidad, presión,
  evolución, embudo, perfil de esperando). Los de **capacidad** (camas, horas hasta saturar, capacidad de la red)
  siguen siendo **provinciales** y lo dicen («Red provincial»): `Dispositivo.localidad` es texto libre y no hay
  forma confiable de asignar un dispositivo a un departamento (§9, pregunta 4). El mapa centra el departamento.

**Localidad sin ubicación**
- Condición: casos de una `core.Localidad` sin fila en `UbicacionLocalidad` o casos sin localidad.
- Comportamiento: aparecen en la tabla («Sin ubicación en el mapa» / «Sin localidad») y el mapa avisa cuántos son.

**Dispositivo sin coordenadas**
- Condición: dispositivo elegible con `latitud`/`longitud` nulas.
- Comportamiento: no se dibuja; cuenta en la red y, para «camas cercanas», se asigna por el nombre de su
  localidad normalizado (la regla actual de E1) y queda marcado «sin coordenadas» en el bloque de capacidad.

**Usuario sin `supervisar`**
- Condición: solo `ver_situacion`.
- Comportamiento: misma pantalla, sin enlaces a E1, E2 ni E3. Ningún bloque cambia de números.

**Impresión**
- Condición: «Imprimir» o Ctrl+P.
- Comportamiento: hoja A4 apaisada; se ocultan sidebar, filtros y botones; se imprimen los filtros aplicados
  como subtítulo, el mapa, la tabla de presión completa y los «Cómo se calcula» desplegados; pie «Documento de
  trabajo · datos agregados, sin datos personales · impreso el …».

---

## 4. Requerimientos

### Requerimientos funcionales

| ID | Requerimiento | Prioridad | Notas |
|---|---|---|---|
| RF-009-01 | Pantalla E8 «Situación» en `/emergencia/situacion/`, ítem del grupo Emergencia del sidebar, visible con `ver_situacion` o `supervisar` | Alta | §3.1 |
| RF-009-02 | Capacidad `emergencia.ver_situacion` en el `CATALOGO`; supervisar la implica; migración para Administrador | Alta | §3.2 |
| RF-009-03 | Hero con nombre del evento, personas alojadas, personas esperando, camas libres y ocupación, y hora de actualización | Alta | `{% hero_inicio %}` |
| RF-009-04 | Filtros: departamento, localidad (dependiente del departamento) y ventana 72 h / 7 días; por GET, combinables | Alta | RN-009-12 |
| RF-009-05 | Cuatro indicadores: personas alojadas, personas esperando, camas libres, horas hasta saturar | Alta | §5.1 bloque B |
| RF-009-06 | Alertas estratégicas calculadas al leer, sin estado, ordenadas por severidad, a lo sumo seis | Alta | RN-009-09 |
| RF-009-07 | Mapa SVG con las capas de presión por localidad y dispositivos, recuadro del Gran Resistencia, leyenda y panel de la localidad elegida | Alta | §3.4–3.5 |
| RF-009-08 | Tabla «Presión por localidad» con los mismos datos del mapa | Alta | Alternativa accesible |
| RF-009-09 | Evolución por día operativo (7 días) o por bloques de 6 h (72 h): casos nuevos, familias alojadas y personas alojadas | Alta | |
| RF-009-10 | Capacidad de la red en camas (ocupadas, reservadas, libres, fuera de servicio) y los cinco dispositivos más exigidos | Alta | |
| RF-009-11 | Embudo de la ventana con conversión, medianas por tramo y salidas del circuito | Alta | |
| RF-009-12 | Perfil agregado de personas alojadas y esperando | Media | RN-009-11 (supresión) |
| RF-009-13 | Logística de kits de la ventana: entregas por estado, enviado/recibido por ítem, tránsito, dispositivos sin entrega | Media | |
| RF-009-14 | Capa «Entregas en camino» | Baja | |
| RF-009-15 | Imprimir con estilo de impresión propio (sin PDF del servidor) | Media | §3.6 |
| RF-009-16 | Enlaces E1 ↔ E8; en E8 los enlaces a E1/E2 solo con `supervisar` | Media | |
| RF-009-17 | Tabla `core.UbicacionLocalidad` + comando de carga idempotente desde CSV versionado + reporte de no conciliadas | Alta | Prerrequisito del mapa |
| RF-009-18 | Capa de densidad de relevamientos en grilla | Baja | Fase 2 |
| RF-009-19 | Resolver en el mismo lote los pendientes 1, 3, 4, 5, 6, 7, 8, 9, 10 y 11 del Cambio 472 | Alta | §8.2 |

### Requerimientos no funcionales

| ID | Requerimiento | Categoría |
|---|---|---|
| RNF-009-01 | E8 es **no nominal** para todos los usuarios: ni nombres, ni DNI, ni direcciones, ni números de caso, ni coordenadas de familias en el HTML (test que lo verifica sobre la respuesta) | Privacidad |
| RNF-009-02 | Sin cambios de CSP ni librerías nuevas: SVG del servidor; Alpine solo si hace falta un detalle de interacción | Seguridad |
| RNF-009-03 | Presupuesto: selectores y alertas de E8 en **≤ 12 consultas**, la vista completa en **≤ 18** (con SLA y shell), constantes con 5.000 casos en la ventana, 3.000 personas alojadas, 50 dispositivos y 500 entregas; < 2 s. Test `@tag("performance")` | Performance |
| RNF-009-04 | Todo se calcula al leer (espíritu de RN-5.1): sin tabla de métricas, sin snapshot, sin job | Arquitectura |
| RNF-009-05 | Sin `Trunc*` ni `CONVERT_TZ`: días operativos y bloques de 6 h se arman en Python con `dia_operativo()` y se filtra por rango (RN-5.2; gotcha de ECOM). Test que captura el SQL | Compatibilidad |
| RNF-009-06 | Funciona igual en MySQL 8 y MariaDB: lecturas de JSON con transformaciones de clave probadas en los dos motores o, si no, la sección traída entera y contada en Python | Compatibilidad |
| RNF-009-07 | Selectores puros respecto de `ahora` (lo reciben por parámetro), como `selectors/emergencia_tablero.py` | Testabilidad |
| RNF-009-08 | La pantalla funciona sin JS (filtros, capas y selección por GET) | Accesibilidad / Robustez |
| RNF-009-09 | Colores solo del sistema de diseño (tonos `danger`/`warning`/`success`/`gray`/`brand`); el nivel se dice también en texto | Diseño / Accesibilidad |
| RNF-009-10 | Índices a medir con `EXPLAIN` en `scripts/perf_mysql/` antes de mergear el selector (§4.1) | Performance |

### 4.1 Rendimiento: qué es caro y cómo se lee

| Lectura | Consulta | Riesgo | Mitigación |
|---|---|---|---|
| Casos de la ventana ampliada (abiertos + creados, alojados o cerrados desde el inicio de la ventana) | 1 `values_list` sin JSON salvo las cuatro claves de `necesidades` | El `OR` sobre `creado`, `alojado_en` y `cerrado_en` (ninguna tiene índice; `creado` tampoco) recorre la tabla. Es el mismo problema del pendiente 10 del Cambio 472 | Medir. Si pesa: índices simples sobre `creado`, `alojado_en`, `cerrado_en` (una migración `AddIndex`, aparte) y, si el optimizador no hace *index merge*, partir en tres consultas por índice y unir en Python (+2, dentro del presupuesto) |
| Red de dispositivos (camas) | 4 (`red_de_dispositivos`: candidatos + 3 de `ocupacion_de_plazas` en lote) | Ninguno nuevo | Reusar; agregar el filtro por tipo de plaza (§8.2) |
| Personas alojadas por la emergencia (perfil + línea de evolución) | 1: `IntegranteGrupo` con `estadia` no nula y (`egresado_en` nula o ≥ inicio de la ventana): `confirmada_en`, `egresado_en`, `ciudadano__fecha_nacimiento`, `ciudadano__genero` y la sección `ficha__avisos_salud` | Leer la ficha entera serían MB | Traer **solo** la sección `avisos_salud` (transformación de clave) y contar en Python. `confirmada_en`/`egresado_en` sin índice: medir |
| Ritmo de ingresos y egresos en camas | 1 agregado sobre `Estadia` de los dispositivos elegibles con plaza `CAMA`, ingresos y egresos de las últimas 6 h | `fecha_ingreso`/`fecha_egreso` sin índice; `(dispositivo, estado)` no alcanza para egresadas | Medir; índice si hace falta |
| Derivaciones de la ventana (rechazadas, vencidas, pendientes por dispositivo) | 1 | Ninguno: `(dispositivo, estado)` | — |
| Logística | 2: agregado de `LineaEntrega` por ítem y estado de las entregas de la ventana; última recepción por dispositivo | Ninguno | `(dispositivo, estado)` existe |
| Ubicaciones de localidad | 1, solo de los ids presentes | Ninguno (PK) | — |
| **Total dominio** | **11** (+2 si se parte la de casos) | | Presupuesto 12 |

La evolución histórica **rompe la ventana de 24 h** de RN-5.1 (hasta 7 días), pero no el principio: sigue siendo
una lectura acotada en el tiempo, nunca el histórico completo. Con un evento de varias semanas, 7 días son unos
miles de filas de cuatro fechas. Se **agrega por período en Python**; no se agrega una tabla de snapshot diario.
El snapshot queda como ampliación solo si se pide comparar eventos o semanas (§9).

Lo que **no** se puede reconstruir hacia atrás: la **capacidad** histórica (las plazas no tienen historia de
alta, baja ni fuera de servicio). Por eso la evolución muestra **personas alojadas** (exacto, desde
`confirmada_en`/`egresado_en`) y dibuja las camas operativas **de hoy** como referencia, rotulada así; no
muestra un «% de ocupación» histórico, que sería inventado.

---

## 5. Reglas de negocio

### 5.1 Qué responde cada bloque

Cada bloque dice qué muestra, cómo se calcula desde los modelos reales, de dónde sale, con qué ventana y filtro, y
qué decisión habilita. «Abiertos sin alojar» = estados `NUEVO`, `EN_GESTION`, `DERIVADO`, `INGRESO_EN_CURSO`.
«Ventana» = 72 h o 7 días según el filtro; «elegibles» = `dispositivo_elegible()` (RN-2.2,
`selectors/emergencia.py`).

| Bloque | Pregunta | Cálculo | Fuente | Ventana / filtro | Decisión que habilita |
|---|---|---|---|---|---|
| **B1 Personas alojadas** | ¿Cuánta gente tenemos a cargo? | Integrantes con `estadia` no nula y `egresado_en` nula. Nota: dispositivos con alguna y variación desde el inicio del día operativo | `IntegranteGrupo.estadia/confirmada_en/egresado_en` | Ahora / filtro por localidad del caso | Dimensionar raciones, personal, kits |
| **B2 Personas esperando lugar** | ¿Cuánta demanda sin resolver hay? | Suma de `GrupoFamiliar.total_declarado` de los casos abiertos sin alojar; nota: familias y fuera de SLA (`fuera_de_sla(foto)`) | `CasoEmergencia.estado`, `grupo.total_declarado`, semáforo `estado_sla` | Ahora / filtro | Abrir albergues, reforzar la mesa |
| **B3 Camas libres** | ¿Hay dónde ponerla? | Suma de `disponibles` de plazas **`CAMA`** de los elegibles; nota: % de ocupación (`ocupadas / operativas`) y reservadas | `ocupacion_de_plazas(…, tipos=(CAMA,))` | Ahora / **siempre provincial** | Habilitar dispositivos, liberar plazas |
| **B4 Horas hasta saturar** | ¿Por cuánto tiempo da abasto? | `libres / ritmo_neto`, con `ritmo_neto = (ingresos − egresos en camas de elegibles en las últimas 6 h) / 6`. Si el ritmo es ≤ 0: «No se satura al ritmo actual». Se muestra redondeado («≈ 11 h») con la nota del ritmo | `Estadia.fecha_ingreso/fecha_egreso`, `plaza__tipo` | Últimas 6 h / provincial | Anticipar la apertura de albergues **antes** de quedarse sin camas |
| **B5 Alertas estratégicas** | ¿Qué no puede esperar a la próxima reunión? | Reglas de RN-009-09 | Varias | Ver regla | Escalar |
| **B6 Mapa + B7 Presión por localidad** | ¿Dónde está el problema? | Por `localidad_id` del caso: familias y personas esperando, fuera de SLA, personas de esa localidad alojadas, **camas libres cercanas** (RN-009-05), presión (RN-009-06) | Foto de casos, red, `UbicacionLocalidad`, `distancia_km` | Ahora / filtro | Dónde mandar recursos, dónde abrir un albergue |
| **B8 Evolución** | ¿Mejoramos o empeoramos? | Por período: casos creados, casos con `alojado_en` en el período, casos cerrados sin alojar; personas alojadas al cierre de cada período = integrantes con `confirmada_en ≤ fin` y (`egresado_en` nula o `> fin`). Períodos: 7 días operativos o 12 bloques de 6 h, armados en Python | `CasoEmergencia.creado/alojado_en/cerrado_en`, `IntegranteGrupo` | 72 h / 7 días; filtro de demanda | Ver si la curva de nuevos baja; anticipar egresos |
| **B9 Capacidad de la red** | ¿Qué dispositivos están al límite? | Barra provincial de camas: ocupadas, reservadas, libres (fuera de servicio aparte). Top 5 por % de ocupación con su nivel (`tension_de_ocupacion` con los umbrales del tipo) y derivaciones pendientes hacia él | `ocupacion_de_plazas`, `TipoDispositivo.umbral_ocupacion_*`, `Derivacion` | Ahora / provincial | Redistribuir derivaciones |
| **B10 Embudo** | ¿Dónde se traba el circuito? | Cohorte = casos **creados en la ventana**, sin ingresos directos (definición única, §8.2). Etapas por marca (escritas una sola vez, RN-2.9, así que el embudo es monótono): relevados (todos), tomados (`tomado_en`), derivados (`derivado_en`), aceptados (`aceptado_en`), alojados (`alojado_en`). Conversión entre pasos; mediana y p90 por tramo dentro de la cohorte contra el objetivo de E7; salidas: cerrados sin alojar por `motivo_cierre`; derivaciones `RECHAZADA` (por motivo) y `VENCIDA` de la ventana; ingresos directos aparte | `CasoEmergencia` (marcas, `origen`, `situacion`, `motivo_cierre`), `Derivacion`, `SLAEmergencia` | Ventana / filtro | Reforzar el tramo que se traba (más operadores, hablar con un dispositivo que rechaza) |
| **B11 Perfil** | ¿A quién estamos alojando y quién espera? | **Alojados** (Formulario 2, confirmados): menores de 16 y mayores de 60 por `ciudadano.fecha_nacimiento` (edad al día de hoy); embarazo, discapacidad, electrodependiente, medicación crítica y medicación crítica **sin dosis** (`medicacion_critica_tiene_dosis` falso) desde `ficha.avisos_salud`. **Esperando** (Formulario 1, declarado): menores, mayores, lactantes, personas con dependencia y mayores dependientes de `GrupoFamiliar`; familias con embarazo, electrodependencia, medicación crítica y mascotas desde `CasoEmergencia.necesidades` | `IntegranteGrupo.ficha` (`ESQUEMA_FICHA`, `services/emergencia_ficha.py`), `GrupoFamiliar`, `CasoEmergencia.necesidades` (`NECESIDADES`, `services/emergencia_alta.py`) | Ahora / filtro, con supresión RN-009-11 | Pedir a Salud, insumos específicos (pañales, leche, generadores para electrodependientes) |
| **B12 Logística** | ¿Llegan los insumos? | Entregas con `despachada_en` en la ventana por estado; sobre las **recibidas**: enviado, recibido y diferencia por ítem (`TipoKit`), entregas con diferencias; tránsito mediano (`recibida_en − despachada_en`); dispositivos con personas alojadas por la emergencia y **sin entrega recibida en 48 h** | `EntregaKit`, `LineaEntrega`, `TipoKit` | Ventana / provincial | Corregir la distribución, revisar el transporte |

**Lo que no se puede calcular hoy, y por qué:**

| Pedido posible | Por qué no |
|---|---|
| Stock o faltantes en un albergue | No hay stock ni depósitos (RN-4.6): solo entregas |
| Población afectada (no evacuada) | El sistema solo conoce a quien se releva para alojar |
| Criticidad hídrica, cotas, alertas pluviales | No hay dato; la propuesta de octubre lo cargaba a mano |
| Incidentes, Mesas 1–4, FUSE | No existen en DATAÑACH |
| % de ocupación histórico | La capacidad no tiene historia (§4.1) |
| Filtro de capacidad por departamento o localidad | `Dispositivo.localidad` es texto libre, sin FK |
| Permanencia promedio por familia | Se puede (estadías egresadas), pero con un evento en curso la mayoría no egresó: el promedio engaña. Queda para el cierre del evento |
| Comparar contra eventos anteriores | Un solo `SLAEmergencia` por programa, sin fecha de inicio ni de cierre del evento |

### 5.2 Reglas numeradas

| ID | Regla | Consecuencia si no se cumple |
|---|---|---|
| RN-009-01 | Todo E8 se calcula al leer, sobre un `ahora` único que recibe cada selector; sin tablas de métricas, snapshot ni job | Números de distintos instantes en la misma pantalla |
| RN-009-02 | «Hoy» y los períodos de la evolución son días operativos de 06:00 a 06:00 hora Argentina (`dia_operativo()`, H8) o bloques de 6 h alineados a las 06:00, armados en Python; nunca `Trunc*` | `CONVERT_TZ` devuelve `NULL` en ECOM y la serie sale vacía solo en producción |
| RN-009-03 | Capacidad = plazas **`CAMA`** `OPERATIVA` de dispositivos elegibles (RN-2.3), con la cuenta única de `services/ocupacion.py` | Cupos y turnos inflan las camas libres (pendiente 1 del Cambio 472) |
| RN-009-04 | Casos por localidad se agrupan por `localidad_id`, nunca por nombre | Con 62 nombres repetidos en Chaco se suman localidades distintas y el enlace a E2 filtra una sola (pendiente 3 del Cambio 472) |
| RN-009-05 | **Camas libres cercanas** de una localidad = libres de los elegibles a ≤ **25 km** (`distancia_km`, haversine) de su centroide; un dispositivo sin coordenadas cuenta si el nombre normalizado de su localidad coincide. Las cercanas **no son exclusivas** (localidades vecinas comparten las mismas); el total real es B3 | Presión engañosa en aglomerados |
| RN-009-06 | Presión = personas esperando / camas libres cercanas. **Crítica**: > 1, o esperando > 0 y 0 camas cercanas. **Exigida**: ≥ 0,5. **Normal**: < 0,5. **Sin demanda**: 0 esperando (el círculo se dibuja chico y gris si hay alojados de ahí) | Semáforo sin regla |
| RN-009-07 | Horas hasta saturar = `libres / ritmo_neto` con ritmo de las últimas **6 h**; ritmo ≤ 0 → «No se satura al ritmo actual»; con libres = 0 → «Red saturada». Se rotula «proyección al ritmo actual, no es un pronóstico» | Un número que se lee como pronóstico |
| RN-009-08 | El embudo es de cohorte (casos creados en la ventana) y excluye ingresos directos, que se muestran aparte | Conversiones mayores al 100 % o tramos en cero que bajan las medianas |
| RN-009-09 | **Alertas estratégicas** (sin estado, al leer, a lo sumo 6, severidad alta antes que media; cada una nombra el dato y no enlaza a casos): **AE-1** saturación: horas hasta saturar < 12 o ocupación de camas ≥ 90 % (alta). **AE-2** localidad crítica: presión crítica con ≥ 10 personas esperando (alta; nombra hasta 3 localidades y «y N más»). **AE-3** demanda en alza: casos nuevos de las últimas 24 h ≥ 1,3 × el promedio de los tres períodos de 24 h anteriores, con al menos 20 casos (media). **AE-4** tramo trabado: p90 de un tramo en las últimas 24 h > 2 × su objetivo (media). **AE-5** dispositivo saturado con derivaciones pendientes: nivel crítico de su tipo y `Derivacion` `PENDIENTE` hacia él (alta). **AE-6** dispositivos con personas alojadas y sin entrega recibida en 48 h (media). **AE-7** personas alojadas con medicación crítica sin dosis ≥ 1 (alta; solo el número) | — |
| RN-009-10 | Las alertas estratégicas son distintas de los siete avisos operativos de E1 (`services/avisos_emergencia.py`), que no se mueven ni se repiten en E8. Con `supervisar`, E8 muestra «N avisos operativos en el tablero de la mesa» con enlace | Dos pantallas diciendo lo mismo con reglas distintas |
| RN-009-11 | **Supresión de números chicos**: los conteos del perfil (B11) se muestran como «menos de 5» cuando valen entre 1 y 4 y el filtro activo es una localidad o un departamento. A nivel provincial se muestran exactos. Los conteos operativos (casos, familias, personas esperando) no se suprimen: no revelan atributos de nadie | Con un filtro fino, «1 embarazo en Lote 18» identifica a una persona |
| RN-009-12 | Los filtros de departamento y localidad acotan solo la demanda; la capacidad es siempre provincial y lo dice | El usuario cree que «no hay camas en el departamento» cuando no se puede saber |
| RN-009-13 | E8 no muestra datos personales para ningún usuario (RNF-009-01); los enlaces a E1/E2 solo con `supervisar`; a la ficha de un dispositivo solo si Dispositivos lo permite | Exposición de datos de familias a autoridades que no los necesitan |
| RN-009-14 | Sin auto-refresh: «Actualizar» vuelve a pedir la pantalla (como E1, decisión 6 del Cambio 472) | — |

---

## 6. Historias de usuario y criterios de aceptación

**HU-9.1** Como autoridad del Ministerio quiero ver la situación sin poder operar la mesa.
- [ ] Dado un usuario con solo `ver_situacion`, cuando entra a Emergencia, entonces ve «Situación» y no ve
  bandeja, tablero ni configuración; `/emergencia/tablero/` le responde 403.
- [ ] Dado ese usuario, cuando abre E8, entonces la respuesta no contiene ningún apellido, DNI, dirección, número
  de caso ni coordenada de un caso sembrado, y no hay enlaces a `/emergencia/casos/`.
- [ ] Dado un usuario sin `ver_situacion` ni `supervisar`, cuando pide `/emergencia/situacion/`, entonces 403.
- [ ] Dado un supervisor sin `ver_situacion` tildada, cuando abre E8, entonces la ve (supervisar la implica).

**HU-9.2** Como coordinador quiero saber si la red da abasto y por cuánto tiempo.
- [ ] Dado 1.850 camas operativas, 1.633 ocupadas y 54 reservadas, cuando abro E8, entonces «Camas libres» dice
  163 y la nota «88 % ocupada · 54 reservadas».
- [ ] Dado un dispositivo elegible con 20 plazas `CUPO` libres y 0 `CAMA`, cuando abro E8, entonces esas 20 no
  suman a camas libres.
- [ ] Dado 132 ingresos y 41 egresos en camas en las últimas 6 h y 163 libres, cuando abro E8, entonces «Horas
  hasta saturar» dice «≈ 11 h» y la nota «+15 camas/h netas en las últimas 6 h», y aparece la alerta AE-1.
- [ ] Dado más egresos que ingresos en las últimas 6 h, cuando abro E8, entonces dice «No se satura al ritmo
  actual» y no hay AE-1 por horas.

**HU-9.3** Como coordinador quiero ver dónde está el problema en el mapa y en una tabla.
- [ ] Dado 38 familias (133 personas) esperando en Barranqueras y 41 camas libres a ≤ 25 km, cuando abro E8,
  entonces el círculo de Barranqueras es «crítica» y la fila de la tabla dice 38 · 133 · 41 · Crítica (3,2×).
- [ ] Dadas dos `core.Localidad` llamadas «La Esperanza» en municipios distintos, con casos en las dos, cuando
  abro E8, entonces hay dos filas y dos círculos, cada uno con su departamento.
- [ ] Dado un supervisor, cuando toca el círculo de Barranqueras, entonces el panel muestra su detalle y «Ver
  los 38 casos en la bandeja» lleva a E2 con `?localidad=<id de Barranqueras>`; con solo `ver_situacion`, el
  panel no tiene ese enlace.
- [ ] Dado un caso cuya localidad no tiene ubicación, cuando abro E8, entonces aparece en la tabla y el mapa dice
  «1 caso de localidades sin ubicación».
- [ ] Dado el HTML de E8, cuando lo reviso, entonces ningún elemento del SVG tiene la latitud o longitud de un caso.

**HU-9.4** Como coordinador quiero saber si estamos mejorando o empeorando.
- [ ] Dado casos creados a las 05:30 y a las 06:30 del 18/11, cuando miro la evolución de 7 días, entonces el
  primero cuenta en el día operativo del 17/11 y el segundo en el del 18/11.
- [ ] Dado 96 casos nuevos en las últimas 24 h y 70, 68 y 71 en los tres períodos anteriores, cuando abro E8,
  entonces aparece AE-3 «Casos nuevos en alza: 96 en 24 h, 38 % más que el promedio de los tres días anteriores».
- [ ] Dado la consulta de la evolución, cuando capturo el SQL, entonces no contiene `CONVERT_TZ`.

**HU-9.5** Como coordinador quiero ver dónde se traba el circuito.
- [ ] Dado 212 casos creados en las últimas 72 h (sin ingresos directos), 204 tomados, 181 derivados, 163
  aceptados y 149 alojados, cuando abro E8 con ventana 72 h, entonces el embudo muestra esos cinco números con
  96 %, 89 %, 90 % y 91 % de conversión.
- [ ] Dado un caso derivado, rechazado y vuelto a derivar, cuando abro E8, entonces cuenta una vez en
  «derivados» y su rechazo cuenta en «derivaciones rechazadas».
- [ ] Dado un ingreso directo creado en la ventana, cuando abro E8, entonces no está en la cohorte y suma en
  «Ingresos directos».

**HU-9.6** Como coordinador quiero saber a quién estamos alojando sin ver a nadie.
- [ ] Dado 54 personas alojadas con medicación crítica, 9 sin dosis, cuando abro E8 sin filtro, entonces el
  perfil dice 54 y «9 sin dosis», y aparece AE-7.
- [ ] Dado el filtro en una localidad con 2 embarazos entre los alojados, cuando abro E8, entonces dice «menos de 5».

**HU-9.7** Como coordinador quiero saber si llegan los insumos.
- [ ] Dado 70 entregas recibidas en la ventana con 1.240 colchones enviados y 1.226 recibidos, cuando abro E8,
  entonces la fila «Colchones» dice 1.240 · 1.226 · −14.
- [ ] Dado un dispositivo con 40 personas alojadas por la emergencia y su última entrega recibida hace 60 h,
  cuando abro E8, entonces figura en «Sin entrega en 48 h» y en AE-6.

**HU-9.8** Como coordinador quiero llevar la situación impresa a la reunión de la mesa.
- [ ] Dado E8 filtrada por el departamento San Fernando, cuando imprimo, entonces la hoja tiene el subtítulo
  «Departamento San Fernando · últimos 7 días», el mapa, la tabla de presión completa y el pie «Documento de
  trabajo · datos agregados, sin datos personales», y no tiene sidebar ni botones.

**HU-9.9** Como supervisor quiero que E1 siga siendo la pantalla de la mesa.
- [ ] Dado E1, cuando la abro, entonces sus números no cambian salvo las correcciones del §8.2, tiene el botón
  «Ver la situación» y no tiene solapa de mapa.
- [ ] Dado E1 con 3 dispositivos y ningún caso, cuando la abro, entonces la tabla de localidades muestra «Todavía
  no hay casos» (pendiente 4 del Cambio 472).

---

## 7. Casos límite y excepciones

| Caso | Comportamiento esperado |
|---|---|
| Programa sin casos | Ceros, «—» en horas hasta saturar, estados vacíos; sin división por cero en conversiones, medianas ni presión |
| Red sin camas operativas | B3 «0 camas», ocupación «sin camas» (no «0 %»), B4 «Red saturada», AE-1 |
| Localidad con esperando y 0 camas cercanas | Presión crítica sin cociente («sin camas a 25 km») |
| Ventana de 7 días con un evento de 3 días | Los días sin datos se dibujan en cero, no se omiten |
| Caso con `localidad` nula | Fila «Sin localidad», no en el mapa |
| Dispositivo con coordenadas fuera del Chaco (error de carga) | No se dibuja; el comando de chequeo / la pantalla lo cuentan como «sin coordenadas válidas» (bbox de la provincia ± 0,5°) |
| Gran Resistencia a escala provincial | Recuadro ampliado; en la vista provincial un solo círculo agregado «Gran Resistencia» con enlace al recuadro |
| `ficha` de versión distinta de 1 | Se lee con el esquema de su versión (`FICHA_VERSION`); una clave ausente no cuenta |
| Persona sin `fecha_nacimiento` | Cuenta en el total y en «edad sin dato», no en menores ni mayores |
| Filtro de localidad que no está en el departamento elegido | Se ignora la localidad y se avisa |
| Parámetros GET inválidos (`?ver=abc`, ventana desconocida) | Se ignoran (Django Form de filtros), nunca 500 |
| Dos supervisores con la pantalla abierta | Cada uno ve su foto; «Actualizar» la renueva |
| Muchísimas localidades con demanda (> 60) | Tabla paginada de a 25; el mapa las dibuja todas |

---

## 8. Dependencias

- Datos del módulo ya en `development`: Cambios 463 a 478.
- Dataset de localidades con centroide y departamento (Georef/BAHRA) y capas de provincia y departamentos (IGN),
  bajados **una vez** por un desarrollador y versionados; nada se pide en tiempo de ejecución.
- `services/ocupacion.py` con el filtro por tipo de plaza (§8.2).
- `scripts/perf_mysql/` para los `EXPLAIN` (RNF-009-10).
- Aprobación de las piezas de UI nuevas (§8.3): el arquetipo dashboard **no tiene golden** y la ficha de
  pendientes pide frenar.

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
  services/emergencia_programa.py   CAP_VER_SITUACION, puede_ver_situacion (supervisar ⇒ ver_situacion)
  mixins_emergencia.py              la vista pide puede_ver_situacion
  selectors/emergencia_situacion.py foto_de_situacion(sla, ahora, filtros) + resumen, presion_por_localidad,
                                    evolucion, capacidad, embudo, perfil, logistica (cada una 0 consultas con foto)
  selectors/mapa_situacion.py       proyección, posiciones, recuadro, radios y tonos (puro, sin consultas)
  services/alertas_situacion_emergencia.py   AE-1 a AE-7 (puras sobre la foto)
  forms/emergencia_situacion.py     FiltrosSituacionForm (departamento, localidad, ventana, capas, ver)
  views/emergencia_situacion.py     SituacionView
  templates/programas/emergencia/situacion.html
static/custom/geo/chaco.svg         contorno y departamentos, ya proyectados
templates/components/               piezas nuevas del §8.3
```

### 8.2 Pendientes del Cambio 472 que entran en el mismo lote

| # (Cambio 472) | Pendiente | Por qué entra acá | Resolución propuesta |
|---|---|---|---|
| 1 | «Plazas libres» cuenta todas las plazas, no solo camas (también Cambio 464, pendiente 2) | E8 hace de la cama su número principal (B3, B4) | Parámetro opcional `tipos` en `ocupacion_de_plazas` (por defecto, todas: las pantallas de Dispositivos no cambian); E1, E8 y el panel «Derivar» de E3 piden `(CAMA,)` |
| 3 | Casos por localidad agrupa por nombre | E8 agrupa por localidad; la misma regla en las dos pantallas | Agrupar por `localidad_id` (RN-009-04); los dispositivos se suman por nombre solo como respaldo |
| 4 | «Todavía no hay casos» no aparece con red cargada | Mismo estado vacío en E8 | Condicionar con `hay_casos` |
| 5 | Solapa «Mapa de la emergencia» | La reemplaza E8 | No se hace; E1 enlaza a E8 |
| 6 | `entregas_en_camino` carga todo | E8 lee entregas: una sola forma | Recortar en la base y tomar el total de la foto |
| 7 | Dos definiciones de ingreso directo | El embudo de E8 excluye ingresos directos | Una sola (`CasoEmergencia.es_ingreso_directo`, o su `Q`), usada por E1 y E8 |
| 8 | Copias (plazas libres en tres lugares, `TONOS`/`ICONOS`, `_foto`, `_plural`) | E8 sería la cuarta copia | Reusar las de origen antes de escribir E8 |
| 9 | `q_entrega_sin_revisar` fuera de su módulo; tuplas por posición | B12 lo usa | Mover a `selectors/kits.py`; `NamedTuple` |
| 10 | Ventana de RN-5.1 sin índice | E8 amplía esa misma ventana | `EXPLAIN` y, si pesa, índices en migración aparte (§4.1) |
| 11 | Comentario muerto en `test_nodo_ui_piezas.py` | Se toca al sumar las piezas | Borrarlo |

Queda afuera el pendiente 2 (revisión visual de E1), que es de QA.

### 8.3 Piezas de UI («lote = las piezas primero»)

E8 es un tablero con gráficos: el arquetipo **dashboard no tiene golden** (`.claude/design/arquetipos/pendientes.md`)
y el de Becas no es molde. E1 resolvió lo mismo como **Detalle apilado con hero** (Cambio 472, decisión 2, y
`HERO_PANTALLAS` de `scripts/design_audit.py`). La propuesta es la misma base para E8 —golden de Detalle
(`becas/cupo/segmento_detail.html`), variante «detalle + apilado» con `{% hero_inicio %}`, y E8 en
`HERO_PANTALLAS`— más las piezas nuevas, que se construyen **antes** de la pantalla, cada una con su ficha:

| Pieza | Estado | Uso en E8 | Ficha |
|---|---|---|---|
| `{% hero_inicio %}` | Existe | Bloque A | `componentes/hero_inicio.md` |
| `components/_stat_card.html` (`variante="tablero"`, `.nodo-stat-tablero`) | Existe | Bloque C (4 indicadores) y logística (chicas) | `componentes/stat_card.md` |
| `components/_alerta.html` | Existe | Bloque D | `componentes/alerta.md` |
| Tabla (`nodo-thead-row`, `nodo-th`, `nodo-td`) | Existe | Bloques F, J, K | `componentes/tabla.md` |
| Badges de tensión (`badge badge-{{ tono }}`) | Existe | Nivel de presión y de ocupación | `componentes/botones_badges.md` |
| Filtros (`list_filters` / patrón de filtros) | Existe | Bloque B | `componentes/filtros.md` |
| Chips de enlace | Existe | Ventana 72 h / 7 días, capas | `componentes/chips_enlace.md` |
| `components/_estado_vacio.html` | Existe | Sin casos | `componentes/estado_vacio.md` |
| `components/_ubicacion.html` | Existe | «Ver en el mapa» del dispositivo, en el panel | `componentes/ubicacion.md` |
| **Mapa territorial** `components/_mapa_territorial.html` + `nodo-mapa.css` | **Nueva** | Bloque E: SVG con contorno, círculos, cuadrados, recuadro, leyenda; recibe formas ya calculadas | `componentes/mapa_territorial.md` (no confundir con `mapa_plazas.md`, que es el plano de camas) |
| **Gráfico de evolución** `components/_grafico_series.html` | **Nueva** | Bloque G: barras agrupadas + línea, SVG del servidor, con tabla oculta para lectores de pantalla | `componentes/grafico_series.md` |
| **Embudo** `components/_embudo.html` | **Nueva** | Bloque I: barras horizontales con conversión y tiempo por paso | `componentes/embudo.md` |
| **Barra de capacidad** `components/_barra_capacidad.html` | **Nueva** | Bloque H: barra apilada ocupadas/reservadas/libres + versión chica por dispositivo | `componentes/barra_capacidad.md` |
| Panel lateral de detalle | **Nueva** (variante de tarjeta) | Bloque E, columna derecha | dentro de `mapa_territorial.md` |

**Por qué SVG del servidor y no Chart.js** (que ya está en `static/vendor/chartjs` y usan Inicio y el dashboard de
Becas): una sola técnica para mapa y gráficos, sin JSON con datos en el navegador, imprime nítido, se prueba con
aserciones sobre el HTML y funciona sin JS. Chart.js queda como alternativa si el diseño pide interacción (zoom,
tooltips ricos) que el SVG no da; la decisión va al Arquitecto con ADR.

Cada pieza nueva suma su fila en `.claude/agents/chaco-design-system.md` y su ficha en `.claude/design/` en el
mismo diff (`check_design_agent.py`), y `design_audit.py --ratchet` en 0 nuevos.

### 8.4 Corte en PRs

| PR | Contenido | Migración | Depende de | Tamaño |
|---|---|---|---|---|
| 1 | Deuda de E1 del §8.2 (camas, `localidad_id`, estado vacío, ingreso directo único, entregas recortadas, copias, `q_entrega_sin_revisar`, comentario) + `EXPLAIN` de la ventana | Solo si el `EXPLAIN` pide índices (aparte, `AddIndex`) | — | M |
| 2 | `core.UbicacionLocalidad` + comando + CSV + contorno SVG; reporte de conciliación revisado por el PM | `core.00NN` (tabla nueva) | — | M |
| 3 | `emergencia.ver_situacion` (catálogo, helper, mixin, sidebar), migración para Administrador | `users.00NN` | — | S |
| 4 | Piezas de UI del §8.3 con fichas, filas del agente canónico y tests de piezas | — | Aprobación de diseño | L |
| 5 | Selectores de E8, `mapa_situacion`, alertas AE-1 a AE-7, tests de cada número, presupuesto `--tag performance`, captura de SQL sin `CONVERT_TZ`, motores | Índices de §4.1 si hacen falta (aparte) | 1, 2 | L |
| 6 | Vista, form de filtros, template E8, impresión, enlaces E1 ↔ E8, tests de permisos y de no nominalidad | — | 3, 4, 5 | M |
| 7 (opcional) | Capa de densidad en grilla | — | 6 | S |

Cada PR con su Cambio en `requerimientos.md` al mergearse (este análisis no abre ninguno) y casos de QA.

---

## 9. Fuera de alcance

- Lo de la propuesta de octubre que **no tiene datos** en DATAÑACH: incidentes, alertas pluviales y fluviales,
  criticidad o semáforos cargados a mano por zona, polígonos de zonas afectadas, población afectada no evacuada,
  stock y faltantes, FUSE, Mesas 1 a 4, bitácora de la mesa, tableros por rol, actualización en vivo.
- Fondo de calles o mapa navegable (opciones b y c de §3.4).
- Coropletas por departamento o municipio (pintar polígonos): no hay asignación confiable de dispositivos a
  departamentos y los «municipios» cargados no son los oficiales. El contorno de departamentos es solo referencia.
- FK de `Dispositivo` a `core.Localidad` (es del dominio Dispositivos).
- Snapshot diario, comparación entre eventos o semanas, histórico del evento completo, % de ocupación histórico.
- Exportar a Excel o PDF generado en el servidor (la impresión del navegador cubre la reunión de mesa).
- Auto-refresh y «modo pared» (pregunta 6).
- Mover o duplicar en E8 los avisos operativos de E1.
- Usar `UbicacionLocalidad` en RN-2.4 (distancia en el panel Derivar): lo habilita, pero es otro cambio.
- Vista de E8 en la app de campo.

---

## 10. Preguntas abiertas

| # | Pregunta | Responsable de responder | Estado |
|---|---|---|---|
| 1 | ¿Quiénes reciben `ver_situacion`? ¿Se arma un rol «Autoridades» o se tilda en roles existentes? | PM / Ministerio | Abierta |
| 2 | Radio de «camas cercanas»: ¿25 km? ¿Distinto para el Gran Resistencia que para el interior? | PM / mesa | Abierta (propuesta: 25 km para todos) |
| 3 | Umbrales de las alertas: horas hasta saturar < 12 h, ocupación ≥ 90 %, alza ≥ 30 % con 20 casos, p90 > 2× objetivo, 48 h sin entrega. ¿Configurables en E7 o fijos? | PM | Abierta (propuesta: fijos en este lote) |
| 4 | ¿Hace falta filtrar la **capacidad** por departamento? Si sí, requiere FK de `Dispositivo` a localidad (Dispositivos) | PM | Abierta |
| 5 | ¿El evento tiene fecha de inicio? Con un `inicio_evento` en `SLAEmergencia` (columna nula, migración) E8 podría mostrar acumulados «desde el inicio» | PM | Abierta (propuesta: no en este lote; la ventana máxima es 7 días) |
| 6 | ¿Se proyecta en una pantalla de la mesa? Si sí, «modo pared» con recarga cada 5 min | PM / mesa | Abierta |
| 7 | Mínimo de supresión del perfil: ¿5? ¿Aplica también a nivel departamento? | PM / área legal o de datos | Abierta (propuesta: 5, con filtro de departamento o localidad) |
| 8 | ¿El Ministerio acepta la atribución de IGN y BAHRA al pie del mapa? | PM | Abierta |
| 9 | ¿Qué hacer con las localidades del fixture que no concilian con Georef (reporte del PR 2)? | PM | Abierta |
| 10 | Aprobación de las cuatro piezas nuevas (mapa, gráfico, embudo, barra) dado que dashboard no tiene golden | PM / diseño | Abierta |

---

## 11. Historial de cambios del análisis

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-18 | Versión inicial | Pedido del PM: «análisis funcional del mapa, no solo del mapa: un tablero estratégico con información útil» |

---

## 12. Pantalla

Base para el mockup. Datos **ficticios** pero coherentes entre bloques (los totales cierran). Escritorio ≥ 1280 px;
en tablet las columnas se apilan en el orden indicado. Momento: martes 18/11/2026 14:35, día operativo desde las
06:00. Evento: «Crecida del Paraná y del Negro · Noviembre 2026». Ventana elegida: 7 días.

### A · Hero (ancho completo)

- Eyebrow: «Programa Emergencia · Situación»
- Título: «Crecida del Paraná y del Negro · Noviembre 2026»
- Bajada: «**1.284** personas alojadas en **38** dispositivos · **412** esperando lugar · **163** camas libres
  (88 % de ocupación). Actualizado el 18/11/2026 14:35.»
- Acción: «Actualizar». (Con `supervisar`, enlace de texto «Ir al tablero de la mesa».)

### B · Filtros (ancho completo, una fila)

Departamento [Todos ▾] · Localidad [Todas ▾] · Ventana [72 h] [**7 días**] · botón «Imprimir».
Nota chica: «Los filtros acotan la demanda; las camas se muestran siempre para toda la provincia.»

### C · Cuatro indicadores (4 columnas, `_stat_card` variante tablero)

| Indicador | Valor | Nota | Tono |
|---|---|---|---|
| Personas alojadas | 1.284 | en 38 dispositivos · +146 desde las 06:00 | brand |
| Personas esperando lugar | 412 | 118 familias · 37 fuera de SLA | warning |
| Camas libres en la red | 163 | 88 % ocupada · 54 reservadas | danger |
| Horas hasta saturar | ≈ 11 h | +15 camas/h netas en las últimas 6 h | danger |

### D · Alertas estratégicas (ancho completo, lista `_alerta`)

1. **Alta** · «La red se satura en ≈ 11 h al ritmo actual» — «En las últimas 6 h ingresaron 132 personas y
   egresaron 41. Quedan 163 camas libres.»
2. **Alta** · «Presión crítica en 4 localidades: Juan José Castelli, Barranqueras y Resistencia, y 1 más» —
   «Barranqueras: 133 personas esperan y hay 41 camas libres a menos de 25 km, que comparte con Resistencia,
   Fontana y Puerto Vilelas.»
3. **Alta** · «Club Atlético Sarmiento (Resistencia) está lleno y tiene 2 derivaciones pendientes.»
4. **Alta** · «9 personas alojadas con medicación crítica no tienen dosis.»
5. **Media** · «Casos nuevos en alza: 96 en las últimas 24 h, 38 % más que el promedio de los tres días anteriores.»
6. **Media** · «El tramo “aceptar” está trabado: el p90 es 4 h 10 min contra un objetivo de 2 h.»

(Con `supervisar`, debajo: «Hay 11 avisos operativos en el tablero de la mesa →».)
«Dispositivos sin entrega en 48 h» (AE-6) no entra por el tope de seis; queda en el bloque K.

### E · Mapa (2/3) + panel (1/3)

**Mapa (izquierda):** contorno del Chaco con límites de departamento en gris claro. Capas: [✓] Presión por
localidad · [✓] Dispositivos · [ ] Entregas en camino · [ ] Densidad (fase 2).
- Círculos (tamaño por personas esperando, color por presión): Barranqueras (grande, rojo, anillo), Resistencia
  (grande, rojo), Puerto Vilelas (mediano, rojo), Fontana (chico, ámbar) —los cuatro en el **recuadro «Gran
  Resistencia»** abajo a la derecha—; Juan José Castelli (chico, rojo); Libertador General San Martín (chico,
  ámbar); Presidencia Roque Sáenz Peña (chico, verde); Quitilipi (muy chico, verde); Machagai (muy chico, rojo);
  Las Breñas (muy chico, rojo); Villa Ángela y Charata (muy chicos, verdes).
- Cuadrados (dispositivos, color por ocupación): 38; los más visibles: Club Atlético Sarmiento (Resistencia,
  rojo), EES N.° 9 (Barranqueras, rojo), Polideportivo Municipal (Fontana, rojo), Centro de Evacuados Puerto
  Vilelas (rojo), Gimnasio Provincial (Sáenz Peña, verde), Escuela N.° 1031 (Villa Ángela, verde), Salón Parroquial
  (Charata, verde).
- Pie del mapa: «4 casos de localidades sin ubicación en el mapa · Límites: IGN · Localidades: BAHRA/Georef».

**Leyenda (derecha, arriba):** Presión: ● Crítica (más personas esperando que camas cercanas) · ● Exigida (≥ la
mitad) · ● Normal · ○ Sin demanda. Tamaño = personas esperando. Dispositivos: ■ Crítica · ■ Exigida · ■ Normal ·
□ Sin camas.

**Panel (derecha, abajo) — localidad elegida: Barranqueras**
- «Barranqueras · Departamento San Fernando» · badge **Crítica (3,2×)**
- Esperando: **38 familias · 133 personas** · 14 fuera de SLA
- Ya alojadas de Barranqueras: 402 personas
- Camas libres a ≤ 25 km: **41** en 9 dispositivos
- Más cercanos: EES N.° 9 (Barranqueras, 1,2 km) · 4 libres de 90 · Club Atlético Sarmiento (Resistencia,
  6,8 km) · 0 de 120 · Polideportivo Municipal (Fontana, 11,4 km) · 8 de 80
- (Con `supervisar`) botón «Ver los 38 casos en la bandeja»

### F · Presión por localidad (ancho completo, tabla)

Columnas: Localidad · Departamento · Familias esperando · Personas esperando · Fuera de SLA · Personas de ahí
alojadas · Camas libres cercanas (≤ 25 km) · Presión. Orden: presión, después personas esperando.

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

### G · Evolución (1/2, izquierda)

Título «Evolución · últimos 7 días operativos». Barras agrupadas por día (casos nuevos / familias alojadas),
línea de personas alojadas al cierre, línea punteada «camas operativas hoy: 1.850».

| Día operativo | Casos nuevos | Familias alojadas | Personas alojadas al cierre |
|---|---:|---:|---:|
| Mié 12/11 | 18 | 9 | 212 |
| Jue 13/11 | 41 | 30 | 318 |
| Vie 14/11 | 63 | 52 | 496 |
| Sáb 15/11 | 70 | 61 | 702 |
| Dom 16/11 | 68 | 64 | 918 |
| Lun 17/11 | 71 | 66 | 1.138 |
| Mar 18/11 (hasta 14:35) | 54 | 44 | 1.284 |

Nota bajo el gráfico: «Los casos nuevos de las últimas 24 h (96) superan en 38 % el promedio de los tres días
anteriores.»

### H · Capacidad de la red (1/2, derecha)

Barra apilada provincial: Ocupadas 1.633 · Reservadas 54 · Libres 163 (total operativas 1.850) · aparte: 22
fuera de servicio · «2 dispositivos sin coordenadas».
Dispositivos más exigidos (barra chica por fila):

| Dispositivo | Localidad | Camas ocupadas | Nivel | Derivaciones pendientes |
|---|---|---|---|---:|
| Club Atlético Sarmiento | Resistencia | 120 / 120 · 100 % | Crítica | 2 |
| EES N.° 9 | Barranqueras | 86 / 90 · 96 % | Crítica | 1 |
| Polideportivo Municipal | Fontana | 72 / 80 · 90 % | Crítica | 0 |
| Centro de Evacuados Puerto Vilelas | Puerto Vilelas | 58 / 70 · 83 % | Crítica | 1 |
| Gimnasio Provincial | Presidencia Roque Sáenz Peña | 64 / 110 · 58 % | Normal | 0 |

### I · Embudo del circuito (1/2, izquierda) — ventana 72 h

| Paso | Casos | Conversión | Tramo | Mediana | p90 | Objetivo |
|---|---:|---:|---|---|---|---|
| Relevados | 212 | — | | | | |
| Tomados | 204 | 96 % | tomar | 9 min | 22 min | 15 min |
| Derivados | 181 | 89 % | derivar | 26 min | 58 min | 30 min |
| Aceptados | 163 | 90 % | aceptar | 1 h 35 min | **4 h 10 min** | 2 h |
| Alojados | 149 | 91 % | alojar | 48 min | 1 h 40 min | 1 h |

Salidas: cerrados sin alojar 17 (no requiere alojamiento 7 · sin contacto con la familia 6 · se alojó por su
cuenta 4). Derivaciones rechazadas 14 (sin camas 8 · no admite mascotas 3 · otros 3), vencidas 6. Ingresos
directos 9 (fuera del embudo).
(Nota para la ventana de 7 días: las medianas del bloque y las del E1 difieren porque E1 mira 24 h.)

### J · Perfil de las personas (1/2, derecha)

Dos columnas.

**Alojadas (1.284, ficha individual confirmada)**
- Menores de 16: 498 (39 %) · Mayores de 60: 167 (13 %) · Edad sin dato: 12
- Embarazo: 21 · Discapacidad: 38 · Electrodependientes: 6
- Medicación crítica: 54, **9 sin dosis**

**Esperando (412 personas, 118 familias, lo declarado al relevar)**
- Menores de 16: 161 · Mayores de 60: 58 · Lactantes: 12 · Con dependencia: 9 (3 mayores dependientes)
- Familias con: embarazo 7 · electrodependencia 2 · medicación crítica 11 · mascotas 23

Pie: «Agregado. Con un filtro de localidad o departamento, los valores de 1 a 4 se muestran como “menos de 5”.»

### K · Logística de kits (ancho completo)

Fila de 4 stat cards chicas: Entregas despachadas 86 · Recibidas 70 (9 con diferencias) · En camino 12 ·
Tránsito mediano 3 h 20 min. (Preparadas sin salir: 4.)

Tabla «Enviado y recibido (sobre las 70 entregas recibidas)»:

| Ítem | Enviado | Recibido | Diferencia |
|---|---:|---:|---:|
| Colchones | 1.240 | 1.226 | −14 |
| Frazadas | 2.100 | 2.100 | 0 |
| Kit de higiene | 980 | 962 | −18 |
| Agua (bidón 6 l) | 1.450 | 1.438 | −12 |
| Módulo alimentario | 1.120 | 1.120 | 0 |
| Pañales (paquete) | 310 | 296 | −14 |

Lista «Con personas alojadas y sin entrega recibida en 48 h»: Escuela N.° 1031 (Villa Ángela, 18 personas, última
hace 61 h) · Salón Parroquial (Charata, 12 personas, nunca) · Gimnasio Provincial (Presidencia Roque Sáenz Peña,
64 personas, última hace 52 h).

### L · Cómo se calcula (plegable, ancho completo)

Definiciones de cada número en una línea (camas = plazas tipo cama de dispositivos activos que admiten camas;
esperando = casos abiertos sin alojar; cercanas = 25 km; presión; ritmo de 6 h; día operativo desde las 06:00;
fuentes del mapa).
