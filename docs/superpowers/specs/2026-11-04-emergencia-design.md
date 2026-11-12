# Módulo Emergencia (mesa de operaciones) — diseño a grandes rasgos

Fecha: 2026-11-04. Estado: borrador para revisión del PM. No hay código ni issues.

## 0. Qué es

Un programa nuevo dentro de DATAÑACH, «Emergencia», para la mesa de operaciones del
Ministerio ante las crecidas en Chaco. Dos carriles:

1. **Casos**: un agente en territorio carga el *Ingreso de familia* desde la app de
   campo; la mesa toma el caso, lo deriva a un dispositivo de la red; el dispositivo lo
   acepta cuando la familia llega y le asigna camas.
2. **Kits**: la mesa arma una entrega de insumos para un dispositivo; el dispositivo
   confirma qué cantidad llegó.

La propuesta ejecutiva de octubre (`docs/client/propuestas/mesa-situacion-el-nino.md`)
planteaba una plataforma aparte, con mapa, cuatro mesas, FUSE y stock. Esto es otra cosa:
un recorte chico que vive **adentro** de DATAÑACH y reutiliza Dispositivos tal como está.
Lo que acá queda afuera (incidentes, mapa de criticidad, stock, traslados) sigue siendo
alcance de esa propuesta.

## 1. Qué ya existe y se reutiliza (verificado en el código)

| Pieza | Dónde | Cómo se usa |
|---|---|---|
| Dispositivo activo, con sectores y plazas (`CAMA`/`CUPO`/`TURNO`, operativa o fuera de servicio) | `programas/models/__init__.py` (`Dispositivo`, `Sector`, `Plaza`) | El dispositivo al que se deriva. La «cama» es la `Plaza` de tipo `CAMA`. |
| Ocupación y plazas libres | `programas/services/ocupacion.py` | La mesa ve cuántas plazas libres tiene cada dispositivo antes de derivar. |
| Reserva de plaza (`ReservaPlaza`, `RESERVA`/`PRESTAMO`, vigente → consumida) | mismo módulo, `estadias.reservar_plaza` | La derivación aceptada **reserva** plazas; el ingreso las consume. |
| Ingreso y egreso de una persona (`Estadia`, una abierta por persona en toda la red, con `MovimientoEstadia` y bitácora automática) | `programas/services/estadias.py` `ingresar_persona` / `egresar_persona` | Asignar cama = una `Estadia` por integrante. No se inventa otro «alojamiento». |
| Asistente de ingreso en 3 pasos y mapa de plazas | `programas/views/dispositivos_ingreso.py`, `sectores/sectores.html` | El paso «elegir camas» del dispositivo es el mismo mapa de plazas, en modo multi-selección. |
| Persona por DNI, consulta a Base de Personas / RENAPER, sugerencias | `legajos.Ciudadano`, `programas/services/ingreso.py`, `selectors/personas_sugeridas.py`, `POST /api/becas/personas/consultar/` | Identificar al titular y a cada integrante desde la app. |
| Vínculos entre personas (`VinculoFamiliar`, par a par) | `legajos/models/contactos.py` | Se registran al cargar la familia, pero **no alcanzan** como grupo: hace falta un `GrupoFamiliar` (ver §3). |
| Constructor de formularios por tipo y momento (`DisenoFormulario`, `MomentoFormulario`) | `programas/services/formularios_tipo.py` | Opcional: el *Ingreso de familia* puede tener una sección configurable; la ficha base es fija. |
| App de campo (Expo, PWA, token DRF, módulos `becas`/`dispositivos`, cola offline, escaneo de DNI, GPS, formularios dinámicos) | `Chaco-mobile` (`App.js`, `src/services/dispositivosService.js`, `CameraModal.js`, `ubicacion.js`) | Módulo nuevo `emergencia` con el mismo patrón de outbox y sincronización. |
| RBAC por capacidades con alcance por programa y por dispositivo (`puede_operar_dispositivo`, `MiembroEquipoDispositivo`) | `core/rbac.py`, `programas/services/dispositivos.py` | El usuario del dispositivo solo ve y acepta derivaciones de **su** dispositivo. |
| Bitácora de turno con entradas automáticas | `EntradaBitacora` | Aceptación, ingreso y recepción de kit dejan entrada. |
| Cierre por vencimiento (registro + `procesar_vencimientos`) | Becas | Reservas que vencen si la familia no llega. |

Hoy la API `/api/dispositivos/` solo expone inspecciones edilicias. Ingreso, egreso y
búsqueda por DNI son vistas web con sesión. Para el carril del dispositivo en la app hay que
**exponerlas por API** (lectura de derivación por DNI, aceptar, elegir plazas, confirmar
kit).

## 2. Actores y capacidades

| Actor | Dónde trabaja | Capacidades nuevas (`core/rbac.py`, módulo `emergencia`, alcance `programa` = `EMERGENCIA`) |
|---|---|---|
| Agente territorial | App de campo | `emergencia.relevar` (carga el Ingreso de familia). Es capacidad de campo (`CAPACIDADES_DE_CAMPO`). |
| Operador de mesa | Backoffice | `emergencia.operar` (tomar, derivar, contactar, cerrar casos; armar entregas de kits). |
| Supervisor de mesa | Backoffice | `emergencia.supervisar` (tablero, SLA, reasignar casos entre operadores, configurar SLA y catálogo de kits). |
| Operador del dispositivo | App de campo o backoffice | Usa las capacidades que ya tiene en Dispositivos: `dispositivo.admitir` (aceptar y asignar camas) y una nueva `emergencia.recibir_kit`. Alcance por dispositivo, como hoy. |

`is_superuser` sigue con bypass total. El grupo del sidebar sigue siendo «Programas»; ahí
entra «Emergencia» como un programa más (decisión del cliente, Cambio 3).

## 3. Modelo de datos (nuevo, en `programas`, heredando `TimeStamped`)

- **`GrupoFamiliar`**: `responsable` (FK `Ciudadano`), `traslado` (Bomberos / Ejército /
  Defensa Civil / Policía / Municipio / Autoevacuado / Otra), y las **cantidades declaradas**
  del Formulario 1: `menores_f/m`, `adultos_f/m`, `mayores_f/m`, `dependientes`,
  `mayores_dependientes`, `lactantes`; `total_declarado` calculado. **El total declarado es
  el tamaño del grupo**: plazas que pide la derivación y fichas que el dispositivo tiene que
  confirmar. **`IntegranteGrupo`**: una fila por ficha individual (Formulario 2):
  `grupo`, `ciudadano` (se crea o se encuentra por DNI; sin documento → `documento_en_mano=False`
  y motivo «extraviado en inundación»), `parentesco` (Jefe/a de hogar / Cónyuge-pareja /
  Hijo/a / Otro), `estadia` (FK, la cama confirmada), `ficha` (JSON con educación,
  vacunación, salud y medicación, trabajo, adultos responsables, mascotas, observaciones),
  `ficha_completa` (bool), `confirmada_en`. La ficha tiene un **mínimo obligatorio** para
  confirmar (parentesco, datos personales, avisos críticos de salud) y el resto se completa
  después. También se escribe `VinculoFamiliar` par a par con el responsable.
  **Opción de implementación**: el Formulario 2 encaja en el constructor existente como
  formulario del momento `ingreso` del tipo de dispositivo (`DisenoFormulario`, P17); el
  Formulario 1 es fijo (ModelForm), porque sus cantidades alimentan la lógica.
- **`CasoEmergencia`**: `grupo`, `origen` (`TERRITORIO` | `DISPOSITIVO` | `MESA`), `estado`
  (§4), `prioridad` (`ALTA`/`MEDIA`/`BAJA`, la propone el formulario y la mesa la puede
  cambiar), `localidad` (FK `core.Localidad`, no texto), `latitud`/`longitud`, `direccion`,
  `situacion` (JSON con las respuestas del formulario de ingreso), `fotos` (adjuntos
  detrás de login, como `media/`), `tomado_por` (User, nullable), `relevado_por`,
  `necesidades` (flags: salud, movilidad reducida, embarazo, menores, mascotas,
  medicación), **marcas de tiempo por transición** (`creado_en`, `tomado_en`,
  `derivado_en`, `aceptado_en`, `alojado_en`, `cerrado_en`) para el SLA,
  `uuid_cliente` (idempotencia desde la app, como las inspecciones).
- **`Derivacion`**: `caso`, `dispositivo`, `estado` (`PENDIENTE` → `ACEPTADA` |
  `RECHAZADA` | `VENCIDA` | `CANCELADA`), `plazas_pedidas`, `motivo_rechazo`, `vence_en`,
  `derivada_por`, `respondida_por`. Un caso tiene a lo sumo una derivación `PENDIENTE` o
  `ACEPTADA` (constraint sobre columna anulable `clave_vigente`, igual que
  `Estadia.clave_alojamiento`; no `UniqueConstraint` condicional, que MySQL/MariaDB
  ignoran). Al aceptar se crean `ReservaPlaza` por integrante; al ingresar se consumen.
- **`ContactoCaso`**: `caso`, `canal` (`LLAMADA`/`WHATSAPP`/`SMS`/`PRESENCIAL`),
  `resultado`, `momento`, `por`. El aviso a la familia es **registro del contacto**, no
  envío automático (ampliación posterior: SES/WhatsApp).
- **`TipoKit`** + **`ItemKit`** (catálogo: «Kit alimentario», «Kit higiene», «Colchón»,
  «Agua 6 l»…, con unidad). **`EntregaKit`**: `dispositivo`, `estado`
  (`PREPARADA` → `EN_CAMINO` → `RECIBIDA` | `RECIBIDA_CON_DIFERENCIAS` | `CANCELADA`),
  `armada_por`, `despachada_en`, `recibida_en`, `recibida_por`, `observaciones`,
  `remito` (adjunto). **`LineaEntrega`**: `entrega`, `item`, `cantidad_enviada`,
  `cantidad_recibida` (nullable hasta la recepción). Sin stock en esta etapa.
- **`SLAEmergencia`** (configuración, una fila por programa): minutos objetivo para
  *tomar*, *derivar*, *aceptar* y *alojar*, y minutos de vigencia de una derivación.
- **`TrazaCaso`** inmutable, como `TrazaDispositivo`.

Todo UUID nuevo nace `char(36)` (MariaDB en ECOM). Nada de `TruncDate` sobre
`DateTimeField` en el tablero: se agrupa en Python.

## 4. Ciclo de vida del caso

```
NUEVO ──tomar──▶ EN_GESTION ──derivar──▶ DERIVADO ──aceptar (dispositivo)──▶ INGRESO_EN_CURSO ──N de N fichas confirmadas──▶ ALOJADO ──egreso de todos──▶ CERRADO
  │                 │  ▲                     │                                   │
  │                 │  └──rechazo/vencimiento┘  (vuelve a EN_GESTION con motivo) │
  │                 └──cerrar sin alojamiento (no requiere / sin contacto / asistido en domicilio)
  └──(origen DISPOSITIVO: nace directamente ALOJADO)
```

Reglas:

- **Tomar** usa `select_for_update` sobre el caso: dos operadores no pueden tomar el
  mismo. El supervisor puede reasignar. Un caso tomado hace más de N minutos sin
  avanzar vuelve a la bandeja con aviso (cron, como `procesar_vencimientos`).
- **Derivar** solo a dispositivos `ACTIVO` cuyo tipo admite `CAMA` y con plazas libres ≥
  integrantes (o menos, con aviso explícito «faltan 2 plazas»). El selector ordena por
  plazas libres y distancia a la familia (lat/long del caso contra la del dispositivo).
- **Aceptar** lo hace el dispositivo cuando la familia **llega**: busca por DNI del
  responsable, ve la derivación («7 personas declaradas») y acepta. El caso pasa a
  **`INGRESO_EN_CURSO`** (estado nuevo entre ACEPTADO y ALOJADO) y se abren **tantas fichas
  individuales como personas declaradas**: contador «3 de 7 confirmadas». Cada ficha se
  confirma con una cama del mapa de plazas y crea la `Estadia` de esa persona (consume su
  reserva). Con 7 de 7 el caso pasa a `ALOJADO` y se registra la sección 4 del Formulario 1
  (sector, aula o dormitorio, tarjeta familiar entregada). **Diferencias**: si llegan menos,
  el operador cierra el ingreso con la diferencia y un motivo («llegaron 6 de 7 · uno quedó
  con familiares»), las reservas sobrantes se liberan y la mesa ve el caso con la marca
  «ingreso parcial»; si llegan más, agrega una ficha, el total pasa a 8 y necesita una plaza
  libre más. Si llega una familia **sin derivación**, el dispositivo puede ingresarla si
  tiene plazas (`dispositivo.admitir` ya lo permite): carga el Formulario 1 ahí mismo, sigue
  con las fichas, y la mesa lo ve como «ingreso directo».
- **Rechazar** exige motivo (sin plazas, no cumple perfil, no llegó). La derivación
  vence sola a las N horas sin aceptación; el caso vuelve a la mesa.
- **SLA**: cada transición guarda su marca de tiempo. La bandeja pinta semáforo por
  caso (texto + color, nunca solo color) contra `SLAEmergencia`. El tablero muestra
  mediana y percentil 90 de cada tramo y el conteo fuera de objetivo.
- Toda transición deja `TrazaCaso`; aceptación e ingreso dejan `EntradaBitacora` en el
  dispositivo.

## 5. Carril de kits

1. Mesa → «Nueva entrega»: dispositivo destino, ítems y cantidades, observaciones.
   Estado `PREPARADA`.
2. Mesa marca `EN_CAMINO` (opcional: transporte y hora).
3. El dispositivo ve la entrega pendiente (app o backoffice), carga la cantidad recibida
   por ítem (precargada con la enviada), adjunta foto del remito y confirma.
   Si alguna cantidad difiere → `RECIBIDA_CON_DIFERENCIAS`, con la diferencia visible
   para la mesa.
4. Sin stock ni reservas en esta etapa: una entrega, una recepción. Entregas parciales,
   devoluciones y stock por depósito quedan como ampliación (alternativa Integral de la
   propuesta).

## 6. Pantallas

Backoffice (extienden `includes/base.html`, se clonan de la golden de su arquetipo):

| # | Pantalla | Arquetipo / molde | Qué muestra |
|---|---|---|---|
| E1 | Tablero de Emergencia | dashboard (hero de programa + stat cards variante tablero, como P1/P22 del mockup) | Casos nuevos, en gestión, fuera de SLA, familias alojadas hoy, plazas libres en la red; lista por localidad; entregas en camino. |
| E2 | Bandeja de casos | listado (golden lista) | Filtros: estado, prioridad, localidad, operador, SLA. Columnas: familia (titular + N integrantes), localidad, prioridad, estado, tomado por, tiempo en estado con semáforo. Acción «Tomar». |
| E3 | Detalle del caso + Derivar | detalle con `split` (como P6/P7) | Izquierda: ficha de la familia, integrantes, necesidades, fotos, contactos, traza. Derecha: selector de dispositivos con plazas libres y distancia; botón «Derivar»; modal con motivo para cerrar/rechazar. |
| E4 | Entregas de kits | listado + asistente de 3 pasos (dispositivo → ítems → confirmar) | Estado por entrega, diferencias resaltadas. |
| E5 | Detalle de entrega | detalle | Líneas enviadas vs recibidas, remito, quién recibió. |
| E6 | Recepción en el dispositivo (backoffice) | reutiliza `ingreso/paso_persona.html` + mapa de plazas P5 | Buscar por DNI → derivación vigente («7 personas declaradas») → aceptar → lista de integrantes con contador «3 de 7» → una ficha individual (Formulario 2, solapas por sección, mínimo obligatorio) por persona, con su cama; «Agregar persona» y «Cerrar ingreso con diferencia» (modal con motivo). |
| E7 | Configuración | formulario | SLA en minutos, vigencia de la derivación, catálogo de kits. |

App de campo (390 × 844, módulo `emergencia`):

| # | Pantalla | Qué hace |
|---|---|---|
| M1 | Ingreso de familias (Formulario 1) | Pasos: traslado y responsable (escanear DNI o escribirlo, consulta a Base de Personas) → personas que ingresan juntas (tabla de cantidades por grupo etario y género, totales calculados) → personas que necesitan asistencia → ubicación (GPS + dirección) y fotos → enviar («Enviado · 7 personas»). Funciona sin señal: queda en cola y se sincroniza. |
| M2 | Dispositivo: llegada de una familia | Buscar por DNI → tarjeta «Derivación vigente: familia Pérez, 7 personas declaradas, derivada 14:20» → Aceptar → lista de integrantes «3 de 7 confirmadas» → ficha individual (Formulario 2, secciones colapsables, mínimo obligatorio) con elección de cama → «Familia alojada · 7 de 7». Si no hay derivación: «Ingresar igual» si hay plazas. |
| M3 | Dispositivo: recepción de kit | Lista de ítems con cantidad esperada; se corrige la recibida; foto del remito; confirmar. |

## 7. Fuera de alcance de esta etapa

Mapa de criticidad, incidentes, stock y FUSE, traslados entre dispositivos, aviso
automático a la familia por SMS/WhatsApp, ingreso individual (el formulario individual es
la misma M1 con un solo integrante: no hace falta otro formulario).

### 7.1. Mapa de criticidad: factibilidad (relevado 05-nov-2026)

Queda fuera de esta etapa, pero ya está evaluado contra el repo para cuando se pida.

**Se puede y es gratis.** Leaflet (licencia BSD) se vendoriza en `static/vendor/leaflet/`
como ya están Chart.js, vis-network y SweetAlert2; los mosaicos los da OpenStreetMap sin
clave ni costo para uso liviano (un backoffice entra), o Argenmap del IGN
(`wms.ign.gob.ar`) como alternativa argentina. Nada de esto pide tarjeta.

**No se implementa tal como viene el mockup.** El mockup carga Leaflet desde unpkg y los
mosaicos desde `tile.openstreetmap.org`; la CSP de `SecurityHeadersMiddleware` solo deja
código propio (`script-src 'self'`) y en `img-src` admite `www.openstreetmap.org`, que no
es el dominio de los mosaicos. Lo que hay que cambiar para que entre:

1. Vendorizar Leaflet (css + js + íconos del marcador). `script-src` y `connect-src` no
   cambian.
2. Sumar el host de mosaicos a `MAPA_HOSTS` en
   `config/middlewares/security_headers.py`; entra solo en `img-src`, porque Leaflet los
   carga como imágenes.
3. Cargar el mapa a pedido con el patrón de SEC-33 (Cambio 185): botón «Ver el mapa»,
   `referrerpolicy="no-referrer"`, nada viaja a OSM hasta que alguien lo abre.
4. Actualizar la ficha `.claude/design/componentes/ubicacion.md` (hoy dice «sin mapa» y
   prohíbe librerías de mapas) y la lista de permitidos de `SinRecursosDeTercerosTests`
   en `portal/tests/test_seguridad_publica.py`; sin eso el hook y el CI quedan rojos.
5. Pieza nueva `components/_mapa.html` con su ficha, y entrada en
   `docs/internal/requerimientos.md`.

**Comparado con el mapa de hoy.** Becas muestra un solo punto con un iframe de OSM
cargado a pedido (`programas/selectors/revision.py`, `mapa_de_la_toma`); Dispositivos no
tiene mapa, solo coordenadas y un enlace que abre OSM afuera. Leaflet es mejor únicamente
cuando hay que ver varios puntos a la vez, clic en un marcador con ficha y enlace al
legajo, filtros que agregan y sacan puntos, o arrastrar el marcador para corregir una
ubicación. Para un punto fijo en un detalle, el iframe hace lo mismo con cero código
propio y no se reemplaza.

**Privacidad.** Igual que SEC-33: al abrir el mapa, las coordenadas del recorte visible
viajan al proveedor de mosaicos; en un tablero son las de todos los puntos visibles. Si el
PM lo considera dato sensible, la salida es servir mosaicos propios, y eso sí tiene costo
de servidor.

**Estimación.** 4 a 6 h para un tablero con marcadores de dispositivos, más revisión.

## 8. Preguntas para el PM

1. **Ficha individual (Formulario 2)**: ¿qué campos son el mínimo obligatorio para
   confirmar a una persona y darle la cama? Propuesta: parentesco, datos personales y los
   avisos críticos de salud (embarazo, discapacidad, electrodependiente, medicación sin
   dosis); el resto se completa después con la marca «Ficha incompleta».
2. **Aviso a la familia**: ¿alcanza con registrar el contacto que hace el operador, o se
   espera envío automático desde el primer día?
3. **Vigencia de la derivación**: ¿cuántas horas espera el dispositivo antes de liberar
   las plazas reservadas? Propuesta inicial: 12 h.
4. **Ingreso directo**: ¿un dispositivo puede alojar a una familia sin pasar por la mesa?
   Propuesta: sí, si tiene plazas, y la mesa lo ve como «ingreso directo».
5. **Dispositivos elegibles**: ¿cualquier tipo con camas, o solo un tipo nuevo
   «Centro de evacuados»?
