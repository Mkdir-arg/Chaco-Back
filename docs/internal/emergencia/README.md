# Módulo Emergencia — panorama completo para el desarrollo

Fecha: 2026-11-05. Estado: documento de trabajo, sin código ni issues todavía. Complementa el
diseño de [`docs/superpowers/specs/2026-11-04-emergencia-design.md`](../../superpowers/specs/2026-11-04-emergencia-design.md)
(modelo de datos y reglas en detalle) y los mockups de Claude Design (`Emergencia Mockups`,
exportación offline en la carpeta del video). Los dos videos narrados (panorama y proceso paso a
paso) salen de este mismo material.

Para quién es: el equipo que va a desarrollar el módulo (backend, app de campo, QA) y el PM
que tiene que validar el alcance con el Ministerio.

**Documentación funcional por etapas** (06-nov; cada archivo trae pantallas, historias con
criterios de aceptación, reglas numeradas, datos, API, casos borde y criterio de terminado):

| Archivo | Qué cubre |
|---|---|
| [`00-reglas-de-usuario.md`](00-reglas-de-usuario.md) | Roles, superficies (PWA y backoffice), capacidades, matriz de acciones, reglas transversales (RU-n) |
| [`01-relevar.md`](01-relevar.md) | Etapa 1: el agente carga el Formulario 1 desde la PWA, con o sin señal |
| [`02-tomar-y-derivar.md`](02-tomar-y-derivar.md) | Etapa 2: bandeja, tomar, derivar, contactos, cierre sin alojamiento, SLA, vencimientos |
| [`03-alojar.md`](03-alojar.md) | Etapa 3: el dispositivo acepta, confirma fichas y camas, aloja, diferencia, ingreso directo, egreso. **PWA y backoffice con paridad** |
| [`04-kits.md`](04-kits.md) | Etapa 4: entregas de la mesa y recepción en la PWA |
| [`05-seguir-y-configurar.md`](05-seguir-y-configurar.md) | Etapa 5: tablero del supervisor, avisos, configuración E7 |

Este README es el panorama; ante una diferencia con un archivo de etapa, gana el archivo de etapa.

---

## 1. La idea en una página

**Qué problema resuelve.** Ante una crecida, el Ministerio arma una *mesa de operaciones* que
tiene que saber, minuto a minuto: qué familias fueron evacuadas, dónde están, cuántas camas
quedan en cada centro de evacuados y qué insumos salieron hacia cada uno. Hoy eso corre por
teléfono, planillas y WhatsApp: no hay un lugar donde el caso de una familia exista desde que
se la releva en el barrio hasta que duerme en un dispositivo.

**Qué es Emergencia.** Un programa nuevo dentro de DATAÑACH (entra en el menú «Programas»,
como Becas, Dispositivos y Merenderos) con dos carriles:

| Carril | Quién empieza | Quién termina | Qué queda registrado |
|---|---|---|---|
| **Casos** (familias) | Agente territorial, desde la app de campo | Dispositivo que aloja a la familia | Una familia, sus integrantes, el dispositivo y la cama de cada persona, con los tiempos de cada paso |
| **Kits** (insumos) | Mesa de operaciones, desde el backoffice | Dispositivo que recibe | Qué salió, qué llegó y las diferencias |

**Qué NO es.** No es la plataforma de la propuesta ejecutiva de octubre
(`docs/client/propuestas/mesa-situacion-el-nino.md`: mapa de criticidad, cuatro mesas, FUSE,
stock). Es un recorte chico que **vive adentro de DATAÑACH y reutiliza Dispositivos tal como
está**. Lo que queda afuera (§9) sigue siendo alcance de esa propuesta.

**Principio de diseño.** Nada que ya exista se duplica: la persona es `Ciudadano`, la cama es
`Plaza`, el alojamiento es `Estadia`, la reserva es `ReservaPlaza`, la autorización es una
capacidad de `core/rbac.py`, la app es un módulo más de `Chaco-mobile`. Emergencia agrega el
*caso* (el hilo que une todo eso en el tiempo) y la *entrega de kits*.

---

## 2. Cómo interviene: el proceso en cinco etapas

```
 TERRITORIO              MESA DE OPERACIONES              DISPOSITIVO
 (app de campo)          (backoffice)                     (app o backoffice)

 1 RELEVAR ──caso──▶ 2 TOMAR y DERIVAR ──derivación──▶ 3 ALOJAR
   Formulario 1          bandeja → ficha → derivar        buscar DNI → aceptar
   con o sin señal       SLA por tramo                    1 ficha por persona + cama
                                                           N de N → ALOJADO
                         4 KITS ───entrega──────────────▶ 4 KITS
                           armar → en camino               recibir → diferencias
                                   ◀──diferencias──────────
                         5 SEGUIR
                           tablero del supervisor
```

### Etapa 1 · Relevar (app de campo, pantallas M1-1 a M1-5)

El agente carga el **Formulario 1 · Ingreso de familias** en cuatro pasos:

1. **Traslado y responsable**: fuerza que traslada (Bomberos, Ejército, Defensa Civil,
   Policía, Municipio, Autoevacuado, Otra) y DNI del responsable, escaneado o tipeado. El
   sistema lo busca en la Base de Personas / RENAPER y trae el nombre. El albergue **no** se
   elige acá: lo asigna la mesa. El N.° de ingreso lo da el sistema al enviar.
2. **Personas que ingresan juntas**: solo cantidades, por grupo etario (menores de 16,
   adultos, mayores) y género. **El total declarado es el tamaño del grupo**: es lo que la
   mesa pide como plazas y lo que el dispositivo tiene que confirmar como fichas.
3. **Necesitan asistencia**: dependientes, adultos mayores dependientes, lactantes
   (incluidos en el total). Con eso la app **sugiere la prioridad**; la mesa la puede cambiar.
4. **Ubicación y fotos**: GPS con precisión, dirección, localidad, fotos de vivienda y
   acceso. **Sin señal se envía igual**: queda en la cola de la app y sale sola al volver la
   conexión (mismo patrón de outbox que las inspecciones). La mesa lo ve como «enviado sin
   señal» con la hora real del relevamiento.

Resultado: un `CasoEmergencia` en estado `NUEVO` con origen `TERRITORIO`.

### Etapa 2 · Tomar y derivar (backoffice, E2 y E3)

- **Bandeja de casos (E2)**: filtros por estado, prioridad, localidad, operador y SLA;
  solapas Abiertos / Nuevos / En gestión / Derivados / Ingreso en curso / Fuera de SLA /
  Ingreso directo / Cerrados. Cada fila: familia (responsable + N personas + N.° de caso),
  localidad, prioridad, estado, tomado por, **tiempo en estado con semáforo** (en término ·
  por vencer al 80 % del objetivo · fuera de SLA; siempre texto + color).
- **Tomar**: `select_for_update` sobre el caso. Mientras un operador lo tiene, nadie más
  puede tomarlo («Tomado por otro operador»). El supervisor reasigna. Un caso tomado que no
  avanza en N minutos vuelve a la bandeja con aviso (cron).
- **Ficha del caso (E3)**: lo que cargó territorio (traslado, responsable, dirección,
  relevado), tabla de personas, necesitan asistencia, integrantes (vacío hasta que el
  dispositivo confirme), fotos, contactos con la familia (registro de llamada / WhatsApp /
  presencial; **no** hay envío automático en esta etapa) y traza. Arriba, el reloj del tramo:
  «Derivar vence en 8 min».
- **Derivar**: panel con los dispositivos **activos cuyo tipo admite camas**, ordenados por
  plazas libres y distancia al caso (lat/long contra la del dispositivo), con la marca
  «Alcanza / Faltan N plazas / Sin plazas». Plazas a reservar = total declarado (editable). Al
  derivar: caso → `DERIVADO`, se crea la `Derivacion` `PENDIENTE` con vencimiento (propuesta
  12 h) y empieza a correr el objetivo para que el dispositivo acepte.
- **Cerrar sin alojamiento** (modal con motivo obligatorio): no requiere alojamiento, sin
  contacto con la familia, asistido en domicilio, se alojó por su cuenta.

### Etapa 3 · Alojar (dispositivo: **PWA M2-1 a M2-6 como vía principal**, o backoffice E6 con las mismas funciones)

1. **Llega la familia**: la operadora del dispositivo busca por DNI del responsable **o de
   cualquier integrante**. Ve la derivación vigente (familia, personas declaradas, quién
   derivó, cuándo vence) y la **acepta** (o rechaza con motivo). Caso → `INGRESO_EN_CURSO`.
   Al aceptar se crean las `ReservaPlaza` por persona.
2. **Fichas individuales (Formulario 2)**, una por persona declarada, contador «3 de 7
   confirmadas». Cada ficha: parentesco con el responsable, datos personales (DNI con
   consulta a Base de Personas; «no, extraviado en inundación» como alternativa), y la
   **cama elegida en el mapa de plazas del aula** (el mismo mapa de Dispositivos, con las
   reservadas para la familia resaltadas). Secciones: 1 datos personales · 2 educación · 3
   vacunación · 4 salud y medicación · 5 trabajo · 6 observaciones. **Mínimo para confirmar**:
   parentesco, datos personales y los avisos críticos de salud (embarazo, discapacidad,
   electrodependiente, medicación sin dosis); el resto queda como «Ficha incompleta» y se
   termina después desde la lista de integrantes. Confirmar la ficha crea la `Estadia` de
   esa persona y consume su reserva.
3. **7 de 7 → Familia alojada**: se completa la sección 4 del Formulario 1 (sector/ala,
   aula o dormitorio, tarjeta familiar entregada y su número, encargado). Caso → `ALOJADO`.
   La mesa lo ve así y la bitácora del turno registra el ingreso.
4. **Diferencias**: si llegan menos, «Cerrar ingreso con diferencia» con motivo (uno quedó
   con familiares, no llegó al centro, derivado a salud, otro): se liberan las reservas
   sobrantes y la mesa ve «ingreso parcial». Si llegan más, «Agregar persona»: el total pasa
   a N+1 y hace falta una plaza libre más.
5. **Sin derivación** («DNI sin derivación vigente»): si el dispositivo tiene plazas,
   «Ingresar igual»: carga el Formulario 1 ahí mismo y sigue con las fichas; la mesa lo ve
   como **ingreso directo** (origen `DISPOSITIVO`, nace `ALOJADO`). También puede «Avisar a
   la mesa».

### Etapa 4 · Kits (mesa E4/E5, dispositivo M3-1/M3-2)

1. **Mesa, «Nueva entrega»** en tres pasos: dispositivo destino (muestra personas alojadas
   y última entrega) → ítems y cantidades del catálogo (kit alimentario, kit de higiene,
   colchón, agua 6 l…) → confirmar. Estado `PREPARADA`; después «Marcar en camino»
   (transporte y hora opcionales).
2. **Dispositivo, «Recepción de kit»** (app o backoffice): la lista viene **precargada con
   lo enviado**; se corrige lo que llegó distinto, foto del remito (obligatoria),
   observación, confirmar. Si alguna cantidad difiere → `RECIBIDA_CON_DIFERENCIAS`.
3. **Mesa, detalle de la entrega (E5)**: enviado · recibido · diferencia por ítem,
   observación del dispositivo, remito, quién recibió, traza. Y decide si repone con una
   entrega nueva.

**Sin stock en esta etapa**: solo qué salió y qué llegó. Stock por depósito, parciales y
devoluciones son ampliación (§9).

### Etapa 5 · Seguir (tablero E1, supervisor)

Hero del programa («Crecida del río»: casos abiertos, fuera de SLA, plazas libres en N
dispositivos), seis indicadores (casos nuevos sin tomar con el más viejo, en gestión, fuera
de SLA desglosado por tramo, familias alojadas hoy con personas e ingresos directos, plazas
libres en la red con reservadas, entregas en camino con diferencias), casos por localidad
(nuevos, en gestión, fuera de SLA, alojadas hoy, plazas libres), entregas en camino y los
**avisos que piden acción** (una entrega con diferencias, una familia fuera de tiempo).
Solapa «Mapa de la emergencia» reservada para la ampliación.

**Configuración (E7)**: minutos objetivo por tramo (tomar, derivar, aceptar, alojar),
vigencia de la derivación, catálogo de kits. Solo el supervisor.

---

## 3. Actores y permisos

| Actor | Dónde | Capacidad (`core/rbac.py`, módulo `emergencia`, alcance `programa`) | Qué hace |
|---|---|---|---|
| Agente territorial | App de campo | `emergencia.relevar` — va a `CAPACIDADES_DE_CAMPO` (`core/rbac.py:893`), hoy `{"becas.campo", "inspeccion.relevar"}` | Carga el Formulario 1 |
| Operador de mesa | Backoffice | `emergencia.operar` | Toma, deriva, registra contactos, cierra casos; arma entregas |
| Supervisor de mesa | Backoffice | `emergencia.supervisar` | Tablero, reasigna, configura SLA y catálogo |
| Operador del dispositivo | **PWA** (principal) y backoffice | `dispositivo.admitir` (ya existe) + `emergencia.recibir_kit` (nueva), **con alcance por dispositivo** vía `puede_operar_dispositivo` (`programas/services/dispositivos.py:150`) y `MiembroEquipoDispositivo` | Acepta derivaciones, asigna camas, recibe kits **solo de su dispositivo** |

Reglas que no cambian: se autoriza por capacidad, nunca por nombre de grupo; `is_superuser`
tiene bypass; el nuevo módulo entra al `CATALOGO` de `core/rbac.py` (alimenta seed, ABM de
roles y modelo ancla); los roles los configura el PM, no el código. Las capacidades con
alcance de programa se evalúan contra el programa `EMERGENCIA` (`RolMeta.programa`); ojo con
`CAPS_ADMIN_PROGRAMA`, que se mueve en cuatro lugares a la vez.

---

## 4. Cómo trabaja con los otros módulos

| Módulo | Qué toma Emergencia | Qué le agrega / qué toca |
|---|---|---|
| **Dispositivos** (`programas`) | `Dispositivo` activo con `Sector` y `Plaza` tipo `CAMA` (`models/__init__.py:930`); plazas libres (`services/ocupacion.py`); `ReservaPlaza` (`:1305`, `reservar_plaza` en `services/estadias.py:778`); `Estadia` (`:1043`, `ingresar_persona :430`, `egresar_persona :529`; una abierta por persona en toda la red); mapa de plazas (`sectores/sectores.html`) y asistente de ingreso (`views/dispositivos_ingreso.py`); `EntradaBitacora` (`:1651`); `TrazaDispositivo` como modelo de traza inmutable (`:745`) | Nada de esto se modifica. Emergencia **llama** a los servicios. El mapa de plazas se usa en modo multiselección (nuevo parámetro, no otra pantalla). Si el PM elige «solo tipo Centro de evacuados», es un `TipoDispositivo` más; si no, cualquier tipo con camas. |
| **Legajos / Ciudadanos** | `Ciudadano` por DNI, consulta a Base de Personas / RENAPER (`programas/services/ingreso.py`, `POST /api/becas/personas/consultar/`), sugerencias (`selectors/personas_sugeridas.py`), `VinculoFamiliar` (`legajos/models/contactos.py`) | Se escribe `VinculoFamiliar` par a par con el responsable, pero el **grupo** es nuevo (`GrupoFamiliar`): los vínculos no alcanzan para «7 personas que ingresan juntas». Persona sin documento: `documento_en_mano=False` + motivo. |
| **Becas (constructor de formularios)** | `DisenoFormulario` / `MomentoFormulario` (`services/formularios_tipo.py`), P17 de Dispositivos v2 | **Opción**: el Formulario 2 (ficha individual, secciones 2 a 6) como formulario del momento `ingreso` del tipo de dispositivo. El Formulario 1 es fijo (ModelForm) porque sus cantidades alimentan la lógica. Decidir antes del primer PR. |
| **Becas (vencimientos)** | Registro + `procesar_vencimientos` (cierre por fecha) | Mismo mecanismo para: derivación que vence sin aceptación, caso tomado que no avanza. Se extiende, no se copia. |
| **Core / RBAC** | `puede`, `puede_alguna`, `@requiere`, alcance por programa | Módulo `emergencia` en el `CATALOGO`; cuatro capacidades (§3). |
| **App de campo (`Chaco-mobile`)** | Login con token DRF, módulos `becas` / `dispositivos`, cola offline (outbox), escaneo de DNI (`CameraModal.js`), GPS (`ubicacion.js`), formularios dinámicos | Módulo nuevo `emergencia` con tres flujos (M1 agente; M2 y M3 **operador del dispositivo, que gestiona los ingresos y las recepciones desde la PWA con paridad con el backoffice**, RU-1) y el **mismo patrón de outbox y `uuid_cliente`** de las inspecciones para lo que puede ir sin señal (Formulario 1 e ingreso directo). Necesita la API nueva (§5). |
| **Notificaciones** | Campañas por SES, transaccionales por SMTP | **No se usa en esta etapa**: el aviso a la familia es registro del contacto. Ampliación: SMS/WhatsApp. |
| **Dashboard / Reportes** | Patrón de `dashboard_becas.py` (agrupar en Python, nunca `Trunc*` sobre `DateTimeField`) | Tablero E1 propio del programa. |
| **Portal ciudadano** | — | No interviene. |

---

## 5. Contrato de la API para la app (nuevo, `programas/api/`)

Hoy `/api/dispositivos/` solo expone inspecciones edilicias (`views_inspecciones.py`,
contrato en `docs/internal/contrato-app-dispositivos.md`). Ingreso, egreso y búsqueda por
DNI son vistas web con sesión. Para Emergencia hay que exponer, con token DRF y las
capacidades de §3:

| Pantalla | Endpoint | Notas |
|---|---|---|
| M1 enviar | `POST /api/emergencia/casos/` | Idempotente por `uuid_cliente` (como inspecciones). Cuerpo: Formulario 1 completo + GPS + fotos (multipart o adjuntos separados como §6 del contrato de inspecciones). Respuesta: N.° de caso. |
| M1 responsable | `POST /api/becas/personas/consultar/` (existe) | Nombre desde Base de Personas / RENAPER por DNI. |
| M2 buscar | `GET /api/emergencia/derivaciones/?dni=` | Solo derivaciones `PENDIENTE` de **mi** dispositivo (alcance). Si no hay, devuelve plazas libres para «Ingresar igual». |
| M2 aceptar / rechazar | `POST …/derivaciones/{id}/aceptar/` · `rechazar/` (motivo) | Crea reservas; caso → `INGRESO_EN_CURSO`. |
| M2 fichas | `GET …/casos/{id}/integrantes/` · `POST …/integrantes/{id}/confirmar/` (ficha + `plaza_id`) · `POST …/casos/{id}/integrantes/` (agregar persona) · `POST …/casos/{id}/cerrar-diferencia/` | Confirmar = `ingresar_persona` con la reserva. |
| M2 mapa | `GET /api/dispositivos/{id}/plazas/` | Plazas del sector con estado (libre / ocupada / reservada para esta familia / fuera de servicio). |
| M2 alojar | `POST …/casos/{id}/alojar/` (sección 4: sector, aula, tarjeta, encargado) | Solo con N de N confirmadas. |
| M3 | `GET …/entregas/?pendientes=1` · `POST …/entregas/{id}/recibir/` (cantidades + remito + observación) | Alcance por dispositivo. |

Reglas que heredan del contrato de inspecciones: accesos denegados con cuerpo explicativo,
límites de tamaño de fotos, y **el test de contrato se actualiza en el mismo diff** que toca
`programas/api/serializers.py` (gate de CI).

---

## 6. Modelo de datos (resumen; detalle en el spec §3)

Todo en `programas`, heredando `core.models.TimeStamped`:

- `GrupoFamiliar` (responsable, traslado, cantidades declaradas, `total_declarado`) y
  `IntegranteGrupo` (ciudadano, parentesco, `estadia`, `ficha` JSON, `ficha_completa`,
  `confirmada_en`).
- `CasoEmergencia` (grupo, origen, estado, prioridad, `localidad` FK, lat/long, dirección,
  `situacion` JSON, fotos detrás de login, `tomado_por`, `relevado_por`, necesidades,
  **una marca de tiempo por transición**, `uuid_cliente`).
- `Derivacion` (caso, dispositivo, estado, `plazas_pedidas`, `vence_en`, motivo). **A lo
  sumo una vigente por caso**: constraint sobre columna anulable `clave_vigente`, como
  `Estadia.clave_alojamiento`. No `UniqueConstraint` condicional (MySQL/MariaDB la ignoran y
  SQLite la crea: el CI pasa y en prod no existe; ya cobró tres veces).
- `ContactoCaso`, `TipoKit` + `ItemKit`, `EntregaKit` + `LineaEntrega`, `SLAEmergencia`
  (una fila por programa), `TrazaCaso` inmutable.

Estados del caso:

```
NUEVO ─tomar─▶ EN_GESTION ─derivar─▶ DERIVADO ─aceptar─▶ INGRESO_EN_CURSO ─N de N─▶ ALOJADO ─egreso de todos─▶ CERRADO
                 ▲  │                   │                       │
                 │  └─cerrar sin alojamiento (motivo)           └─cerrar con diferencia → ALOJADO (parcial)
                 └──rechazo / vencimiento (motivo) ◀────────────┘
origen DISPOSITIVO: nace ALOJADO (ingreso directo)
```

---

## 7. Reglas de la casa que aplican a este desarrollo

- **Migraciones**: columna nueva `null=True` o `DEFAULT` real (`check_migraciones.py`);
  expand en N, contract en N+2; `atomic=False` ⇒ cada paso idempotente con los helpers de
  `core/migraciones.py`; `UUIDField` nuevo → `char(36)` (patrón `programas.0073`) y búsqueda
  con `q_uuid_en_texto`.
- **MariaDB en ECOM**: sin tablas de timezone → nada de `TruncDate` / `TruncWeek` sobre
  `DateTimeField` (agrupar en Python); `read_timeout` 10 s → el tablero resuelve alcance a
  ids y no decodifica JSON en Python sobre miles de filas.
- **Concurrencia**: tomar = `select_for_update`; confirmar ficha = la misma transacción
  que `ingresar_persona` (ya protege «una estadía abierta por persona»).
- **UI**: cada pantalla se clona de la golden de su arquetipo (`.claude/agents/chaco-design-system.md`):
  E1 dashboard, E2 listado, E3/E5 detalle con `split`, E4 listado + asistente, E6 reutiliza
  `ingreso/paso_persona.html` + mapa de plazas P5, E7 formulario. **Lote = las piezas
  primero**: relevar antes del primer PR qué includes faltan (semáforo de SLA, contador «N de
  N», tarjeta de dispositivo con plazas y distancia, stepper de 4 pasos). `design_audit.py
  --ratchet` en 0 nuevos; snapshots de Becas si se toca una pieza compartida.
- **App**: HEIC→JPEG, outbox, `uuid_cliente`, permisos de cámara y GPS como hoy.
- **Datos personales**: fotos y fichas detrás de login (`media/` no está exento del
  middleware del portal); nada de documentos de persona en `docs/client/`.
- **Requerimientos**: cada PR deja su entrada en `docs/internal/requerimientos.md`
  (etiqueta nueva `emergencia`), y el test de contrato de la API se actualiza en el mismo diff.

---

## 8. Plan de desarrollo propuesto (PRs chicos, en orden)

| # | Entregable | Depende de | Qué se puede probar al terminar |
|---|---|---|---|
| 1 | Programa `EMERGENCIA`, módulo en el `CATALOGO` de RBAC (4 capacidades), `SLAEmergencia`, catálogo de kits, pantalla E7 | — | Roles configurables; configuración guardada |
| 2 | Modelos `GrupoFamiliar`, `IntegranteGrupo`, `CasoEmergencia`, `Derivacion`, `ContactoCaso`, `TrazaCaso` + migraciones + servicios de transición (tomar, derivar, cerrar) con tests de mutación sobre las guardas | 1 | Suite verde, `check_migraciones`, ida y vuelta contra MariaDB |
| 3 | Backoffice E2 (bandeja) + E3 (ficha y derivar) + «Nuevo caso» desde la mesa | 2 | Un operador carga un caso a mano, lo toma y lo deriva |
| 4 | API `POST /api/emergencia/casos/` + app M1 (Formulario 1, offline) | 2 | Un agente releva desde el teléfono sin señal y el caso aparece en la bandeja |
| 5 | Dispositivo: aceptar / rechazar, fichas, cama, alojar, diferencia, ingreso directo. Backoffice E6 + API M2 + app M2 | 3 | Una familia derivada queda alojada con una estadía por persona; la mesa ve «Alojada» |
| 6 | Vencimientos (derivación, caso sin avance) con el mecanismo de Becas | 5 | Una derivación no aceptada vence sola y el caso vuelve a la bandeja |
| 7 | Kits: modelos, E4, E5, API M3, app M3 | 1 | Una entrega sale, se recibe con diferencia y la mesa la ve |
| 8 | Tablero E1 + semáforos de SLA en bandeja y ficha | 5, 7 | Supervisor ve el estado de la emergencia |
| 9 | Casos de QA por task, plan de pruebas de la épica, manual del módulo | todo | QA en testing (`datanach.ecomdev.ar`) |

Cada PR: `/auditoria pr <N>` antes del merge, entrada en requerimientos, contrato de API
actualizado. Modo juez (2+ PRs, migraciones, RBAC).

---

## 9. Fuera de alcance de esta etapa

Mapa de criticidad e incidentes, stock y FUSE, traslados entre dispositivos, aviso
automático a la familia (SMS/WhatsApp), entregas parciales y devoluciones, ingreso
individual (es M1 con un solo integrante). Todo eso sigue en la propuesta de octubre.

---

## 10. Decisiones que necesita tomar el PM antes del PR 2

1. **Mínimo de la ficha individual** para confirmar y dar la cama. Propuesta: parentesco,
   datos personales y avisos críticos de salud (embarazo, discapacidad, electrodependiente,
   medicación sin dosis).
2. **Aviso a la familia**: ¿registro del contacto alcanza, o envío automático desde el
   primer día?
3. **Vigencia de la derivación** antes de liberar las plazas. Propuesta: 12 h.
4. **Ingreso directo** sin pasar por la mesa: ¿sí, si hay plazas? Propuesta: sí, marcado.
5. **Dispositivos elegibles**: cualquier tipo con camas, o un tipo nuevo «Centro de
   evacuados».
6. **Formulario 2 por constructor** (P17) o fijo. Afecta el PR 2 y la app.
7. **Objetivos de SLA iniciales** (minutos): tomar 15, derivar 30, aceptar 120, alojar
   60. Son los que muestran los mockups; confirmar.
8. **Tablero E1 solo para el supervisor** o también para el operador (hoy: solo
   supervisor, RU §4).
