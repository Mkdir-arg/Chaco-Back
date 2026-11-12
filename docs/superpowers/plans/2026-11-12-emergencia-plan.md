# Módulo Emergencia — plan de desarrollo

Fecha: 2026-11-12. Estado: **plan para revisión del PM**. No hay código, migraciones, issues ni
cambios en el Project.

Fuentes leídas enteras, en este orden: `docs/internal/emergencia/README.md`, `00-reglas-de-usuario.md`,
`01-relevar.md`, `02-tomar-y-derivar.md`, `03-alojar.md`, `04-kits.md`, `05-seguir-y-configurar.md` (rama
`docs/emergencia-analisis`, commit `44738c5d`) y `docs/superpowers/specs/2026-11-04-emergencia-design.md`.
Precedencia aplicada: **00 > etapa > README > spec**.

Código verificado contra `development` @ `e968b179`. `requerimientos.md` se consultó por etiqueta y
búsqueda (§2), nunca entero. La skill `superpowers:writing-plans` no está instalada en este entorno: el
plan sigue su forma (objetivo, archivos, pasos verificables, criterio de terminado por PR) a mano.

---

## 0. Resumen

- **13 PRs de backend con código** (`Chaco`: 0 a 11 más 9-API), **3 de PWA** (`Chaco-mobile`), uno de
  documentación (12) y el cierre de QA (13). Total **436 h** (328 de backend, docs y QA; 108 de PWA).
  Detalle en §6.
- **Va primero:** PR 1 (programa, RBAC y configuración) **y en paralelo** PR 0 (piezas de UI del lote).
- **Cambio de plan respecto del README §8:** el análisis supone que Emergencia «llama a los servicios
  de Dispositivos sin modificarlos». Para las reservas eso **no es posible** (hallazgo H1, §3). Se
  agrega un **PR 6, «Reservas de derivación» dentro de Dispositivos**, en el camino crítico, con modo
  juez y regresión completa de la concurrencia de Dispositivos.
- **Decisión del PM que hay que pedir ya:** la n.° 6 (Formulario 2 por constructor o fijo), junto con
  la nueva D-9 (autorizar el PR 6 dentro de Dispositivos). Las dos cambian el modelo del PR 2.

---

## 1. Reglas de la casa que gobiernan todos los PRs

Valen para cada PR y no se repiten en cada ficha:

- **Capas.** `models/` → `selectors/` (lectura) → `services/` (escritura y reglas) → `views/` y
  `api/` (orquestación). **RU-2:** la vista web y el endpoint de la API llaman a la **misma** función
  de servicio. Una regla que solo vive en una vista o en un serializer es un defecto de review.
- **RBAC.** Solo por capacidad (`core/rbac.py`). Lo nuevo entra al `CATALOGO`, la capacidad se siembra
  con una migración de `users` (patrón `users.0045_capacidad_dispositivo_ver_todos`) y ningún código
  pregunta por el nombre de un grupo.
- **Migraciones.** Se crean en el mismo commit que el modelo y pasan `scripts/check_migraciones.py`:
  - Toda columna nueva sobre una tabla **existente** nace `null=True`. Las tablas nuevas no tienen
    filas viejas, pero igual llevan `DEFAULT` real o `null=True` en las columnas que el código viejo no
    escribe.
  - **UUID:** `uuid_cliente` como `UUIDField(null=True, unique=True)` más un `RunPython` que lo deja en
    `char(36)` con `core.migraciones.modificar_columna` y declara su reversa. El patrón exacto es
    `programas.0093_inspeccion_app_sin_conexion` (más cercano que la `0073` que cita el README, que es
    una barrera de reversa). Las búsquedas usan `core.db.q_uuid_en_texto`.
  - **Exclusión «a lo sumo una vigente»:** columna anulable `clave_vigente` con
    `UniqueConstraint(fields=["clave_vigente"])` **simple**, como `Estadia.clave_alojamiento`. Nunca
    `UniqueConstraint(condition=…)`: MySQL y MariaDB lo ignoran.
  - `RunPython`/`RunSQL` siempre con reversa o `# REVERSA-NOOP: <qué queda>`. Con `atomic = False`,
    cada paso idempotente con los helpers de `core/migraciones.py`.
  - Ningún `RemoveField` ni `RenameField` en este lote.
- **MariaDB en ECOM.** Nada de `Trunc*` sobre `DateTimeField`: «hoy» es un rango calculado en Python y
  filtrado con `__gte`/`__lt`. Con un `read_timeout` de 10 s, cada selector documenta arriba su
  presupuesto de consultas y lo fija un test `--tag performance`.
- **Concurrencia.** Toda transición de estado hace `select_for_update()` sobre la fila dueña dentro de
  `transaction.atomic()` y relee el estado. El orden de candados es el de `estadias.py` (plaza → reserva
  → persona); Emergencia agrega **caso → derivación** *antes* de plaza (§8, R1). Las carreras se prueban
  con `TransactionTestCase` y además corren en el job `Migrate ida y vuelta` / MariaDB.
- **UI.**
  - Cada pantalla se clona de la golden de su arquetipo y declara antes su «Plan de pantalla».
  - Las piezas que faltan se construyen **antes** de la primera pantalla (PR 0).
  - `design_audit.py --ratchet` en 0 nuevos, `compile_templates.py --bloques` en 0 y
    `check_design_agent.py --changed` en verde.
  - Si se toca una pieza canónica que los snapshots de Becas congelan (`_field.html`, `_alerta.html`,
    `_mapa_plazas.html`…), se corren los snapshots de `core/tests/test_nodo_ui_piezas.py` en el mismo PR.
- **Contrato de la API.**
  - Test de claves exactas por endpoint en `programas/tests/test_emergencia_api_contrato.py`, en el
    mismo diff que el serializer.
  - Documento vivo `docs/internal/contrato-app-emergencia.md`, hermano de `contrato-app-dispositivos.md`.
- **Cierre de cada PR.**
  - `manage.py check`, la suite de la app y `makemigrations --check --dry-run`.
  - Entrada en `docs/internal/requerimientos.md` con la etiqueta nueva `#emergencia`, que se suma al
    vocabulario del archivo en el PR 1; `requerimientos.py --check` OK.
  - `/auditoria pr <N>` antes del merge. Modo juez en los PRs con migraciones, RBAC o Dispositivos.

---

## 2. Requerimientos consultados y contradicciones con decisiones registradas

Consultas hechas: `--tag rbac`, `--tag dispositivos`, `--buscar "vencimiento"` y `--buscar "app de campo"`,
más `--buscar "emergencia"` y `--ver 409`.

- `--tag dispositivos` **no existe** en el vocabulario de etiquetas. Las entradas de Dispositivos
  cuelgan de `#ui #datos #rbac`. Las relevantes son:
  - 262: estadía, reserva y clave de alojamiento.
  - 272: asistente de ingreso.
  - 389: reservar, prestar y sacar de servicio.
  - 407 y 409: ingreso.
  - 410/446: el alcance es solo el Equipo.
  - 432: sin alcance, 404.
  - 437: acciones de la plaza ocupada.
- `--buscar "emergencia"` no trae decisiones funcionales sobre este módulo: no hay nada previo que
  rehacer.
- `--buscar "vencimiento"`: el registro de `core/services/vencimientos.py` (Cambio 41) y las reglas de
  aviso de Dispositivos (281) son el mecanismo que el análisis pide extender. No hay contradicción.
- `--buscar "app de campo"`: Cambio 49 («la app de campo solo sirve a Becas») quedó superado por las
  tasks 38/39 (agente edilicio). Emergencia es el tercer módulo de la app. No hay contradicción.

**Contradicciones encontradas:**

| # | Decisión registrada | Qué dice el análisis | Cómo lo resuelve el plan |
|---|---|---|---|
| C1 | **Cambio 409, D2 (PM, 02/11):** al ingresar a una persona se liberan **todas** sus reservas abiertas, en cualquier dispositivo (`ingreso._reservas_abiertas_de`, `confirmar_ingreso`). | RN-3.4/3.5: las N reservas de la familia van **a nombre del responsable**. | Si el responsable entra por el asistente normal de Dispositivos (o por `confirmar_ingreso`), D2 libera de un golpe las camas de toda la familia. El PR 6 marca las reservas de derivación y las **excluye** de D2 (H1). La D2 del PM no cambia para ninguna otra reserva. |
| C2 | **Cambio 432:** sin alcance sobre un dispositivo, **404** (igual que un id inexistente); sin la capacidad del módulo, 403. | HU-3.1 y HU-4.3: «403 con *No formás parte del equipo*» al abrir por id algo de otro dispositivo. | Se respeta 432. El 403 con cuerpo explicativo (RU-20) se usa solo cuando al usuario le falta la capacidad en **todo** el programa (`code: "SIN_MODULO"`, como el login). Abrir por id una derivación o una entrega de otro dispositivo da **404**. El test de mutación de RU §6 n.° 2 afirma 404 y que el cuerpo no nombra al otro dispositivo. |
| C3 | Inventario de diseño: **«Dashboard» no tiene golden** (`.claude/design/arquetipos/pendientes.md`: frenar) y el tablero de Becas «no es molde». | 05 §3: «E1 · arquetipo dashboard, golden del dashboard de Becas». | No se clona el dashboard de Becas. E1 se arma como **Detalle** (golden `becas/cupo/segmento_detail.html`) con `{% hero_inicio %}` (permitido en tableros de programa), la franja `_stat_card` `variante="tablero"` y tablas canónicas. **Sin gráficos**: un gráfico sería novedad y frena. Supuesto S-8. |
| C4 | Inventario de diseño: **SweetAlert2 es «legacy condicionado»**: no se suma a pantallas nuevas, que usan `ModernModal` y el arquetipo Modal. | RU-22: «SweetAlert2 en backoffice». | Las pantallas nuevas usan el arquetipo **Modal** (motivo obligatorio) y **Confirmación** (`ModernModal`). El fondo de RU-22 (motivo obligatorio, nunca `confirm()`) se cumple. Va en §9. |

---

## 3. Anclas del código: qué coincide y qué no

Se verificó cada ancla que cita el análisis.

### Coinciden

- `core/rbac.py`: `CATALOGO` (l. 36), `puede`/`puede_alguna`/`requiere`, módulos con
  `"alcance": "programa"` y `"programas": (...)`, `CAPACIDADES_DE_CAMPO = {"becas.campo",
  "inspeccion.relevar"}` (**l. 879**, el análisis dice 893) y `es_solo_campo`/`roles_solo_campo`.
  `CAPS_ADMIN_PROGRAMA` (l. 396) se lee en 620, 1054, 1086 y 1185 de `rbac.py` y en
  `users/selectors/usuarios.py:122`.
- `programas/services/dispositivos.py`: `puede_operar_dispositivo` (**l. 129**, no 150),
  `dispositivos_en_alcance` (l. 155) y `dispositivos_operados` (l. 174). El alcance es Equipo
  (`MiembroEquipoDispositivo` con rol **del programa DISPOSITIVOS**), y el admin del programa tiene
  alcance total.
- `programas/services/estadias.py`:

  | Función | Línea real | Línea que cita el análisis |
  |---|---|---|
  | `ingresar_persona` | 431 | 430 |
  | `egresar_persona` | 530 | 529 |
  | `reservar_plaza` | 784 | 778 |
  | `liberar_reserva` | 890 | 884 |
  | `_bloquear_reserva_propia` | 328 | — |

  Orden de candados plaza → reserva → persona. `verificar_alojamiento_en_red` recorta por alcance.
- `programas/services/ingreso.py`: `confirmar_ingreso` (l. 179) es servicio puro. La vista del asistente
  (`views/dispositivos_ingreso.py`, `IngresoBaseView`) guarda los pasos en la sesión, así que la API no
  puede reusar la vista, pero **sí** el servicio.
- `programas/services/ocupacion.py`: `ocupacion_de_plazas(dispositivos)` calcula **en lote** (sirve para
  RN-5.7 sin N+1), `estado_de_plazas` y `tension_de_ocupacion`.
- `core/services/vencimientos.py`: `ReglaVencimiento` + `registrar` (cierre por fecha, idempotente) y
  `ReglaAviso` + `registrar_aviso` + `avisos(ambito, …)` (sin estado, nunca bloquea). Las reglas se
  importan en `programas/apps.py:ready()`.
- `programas/api/views.py`: `ObtainCampoToken.post` (l. 209) arma `modulos` con `"becas"` (si tiene
  `becas.campo`) y `"dispositivos"` (si tiene `inspeccion.relevar` en el programa).
  `CLAVES_LOGIN = ["token", "user_id", "username", "modulos", "app"]`
  (`programas/tests/test_becas_api_contrato.py:636`).
- Modelos: `Plaza.Tipo.CAMA`/`Estado.OPERATIVA` (l. 948), `ReservaPlaza` (**l. 1323**, no 1305),
  `Estadia` (1061, `clave_alojamiento`), `EntradaBitacora` (1695, `Origen.AUTOMATICA`, tipos `GENERAL` e
  `INGRESO`), `TrazaDispositivo` (748), `VinculoFamiliar` (`legajos/models/contactos.py:110`) y
  `Ciudadano.dni_fisico` con `NO_TIENE` (`legajos/models/base.py:154`).
- Templates: `dispositivos/ingreso/paso_persona.html` y `dispositivos/sectores/sectores.html` existen.
  `docs/internal/contrato-app-dispositivos.md` existe.

### No coinciden (y cómo cambia el plan)

| # | Ancla del análisis | Lo que dice el código | Impacto en el plan |
|---|---|---|---|
| **H1** | **RN-3.5 / RN-3.4**: al aceptar se crean N `ReservaPlaza` a nombre del responsable con `reservar_plaza`. Al confirmar otra persona, la reserva se reasigna, o se «libera y se vuelve a reservar» **sin modificar Dispositivos**. | (a) `_bloquear_reserva_propia` (l. 328) rechaza con «La reserva es de otra persona» si `reserva.ciudadano_id != ciudadano.pk`: **una reserva del responsable no se puede consumir con el ingreso de otra persona**. (b) `reservar_plaza` → `_exigir_persona_sin_alojamiento_ni_reserva` (l. 846) rechaza la **segunda** reserva vigente de la misma persona en el mismo dispositivo: **no se pueden crear 7 reservas a nombre del responsable**, solo la primera. (c) La misma función rechaza la reserva si el responsable ya tiene estadía abierta (RN-2.15): la derivación no se podría aceptar. (d) Por C1, el ingreso del responsable por cualquier camino de `confirmar_ingreso` liberaría las otras N−1. `ReservaPlaza.ciudadano` es `NOT NULL`. | Sin tocar Dispositivos no se puede ni aceptar una derivación de más de una persona. La salida de RN-3.5 («liberar y volver a reservar») sirve para consumir (b no aplica al integrante), pero no para **crear** las N reservas. **El plan agrega el PR 6** (§5): una FK `ReservaPlaza.derivacion` (`null=True`) y dos funciones nuevas en `estadias.py`, `reservar_plazas_de_derivacion` y `consumir_reserva_de_derivacion`, con el mismo orden de candados. Además, `reserva_propia_vigente`, `ingreso._reservas_abiertas_de` y `_exigir_persona_sin_alojamiento_ni_reserva` **excluyen** las reservas con derivación. Ninguna firma existente cambia. Requiere la decisión D-9 (§7). |
| **H2** | 01 §8 y 03 §7: la PWA usa `POST /api/becas/personas/consultar/` (existe). | `consultar_persona_becas` (l. 496) exige `CampoBecasPermission` = **`becas.campo`**. Un agente con solo `emergencia.relevar`, o un operador de dispositivo, recibe 403 `SIN_MODULO`. Dársela rompería RU §6 n.° 3 al revés: el rol de Emergencia abriría Becas. | El PR 5 agrega `POST /api/emergencia/personas/consultar/` con permiso propio (`emergencia.relevar` **o** `dispositivo.admitir` con Equipo). Reusa el **servicio** de consulta y comparte `ConsultaPersonasThrottle`. El endpoint de Becas no cambia. |
| **H3** | 00 §3: `emergencia.recibir_kit` en el módulo `emergencia` (programa EMERGENCIA), evaluada con `puede_operar_dispositivo` (RU-8). | `puede_operar_dispositivo` evalúa `rbac.puede(user, cap, programa=DISPOSITIVOS)` y el Equipo filtra roles con `rol__meta__programa = DISPOSITIVOS` (`q_membresia_vigente`). Una capacidad de un módulo acotado a EMERGENCIA **no se puede otorgar** en un rol de DISPOSITIVOS (`modulo_permite_programa`, SEC-06): la guardia nunca la tendría. | `emergencia.recibir_kit` se cataloga en un módulo **acotado a DISPOSITIVOS** (`"programas": ("DISPOSITIVOS",)`, solapa «Dispositivos» del ABM de Roles), junto a `dispositivo.admitir`. El código de la capacidad se mantiene. Es una corrección técnica, no una decisión del PM (§9). |
| H4 | RN-1.6/1.7/2.4 y API `GET …/localidades/` → `{id, nombre, latitud, longitud}`: sin GPS, la distancia sale «del centroide de la localidad». | `core.Localidad` (`core/models/base.py:74`) tiene `nombre` y `municipio`. **No tiene coordenadas.** | Supuesto S-5: en esta etapa no hay centroide. Caso sin GPS → «distancia desconocida» y orden solo por plazas (el borde que ya prevé 02 §9). La API de localidades devuelve `{id, nombre}`. Sumar coordenadas a `core.Localidad` es una ampliación aparte (columnas nuevas + carga del dato). |
| H5 | 01 §10 y 03 RN-3.7: persona sin documento → `Ciudadano` con `documento_en_mano=False` + motivo. | `documento_en_mano` **no existe**. Existe `Ciudadano.dni_fisico` (`TIENE` / `EN_TRAMITE` / `NO_TIENE`). Además, `Ciudadano.dni` es `unique` y **NOT NULL**: no hay forma de dar de alta a alguien **sin número**. | «Perdió el documento pero sabe el número» → `dni_fisico = NO_TIENE`, sin migración en `legajos`. «No sabe su número» no tiene solución sin inventar DNI sintéticos, lo que rompe «DNI válido es una sola regla» (Cambio 168). Decisión nueva **D-10** (§7). Supuesto: esa persona no se confirma con cama y el ingreso se cierra con diferencia, motivo «Otro: sin número de documento». |
| H6 | RN-2.2: elegibles = `tipo.maneja_camas`. | `TipoDispositivo.maneja_camas` es el campo de la **v1**. En la v2 lo reemplaza `tipos_plaza_admitidos` (`maneja_plazas`, `admite_tipo_de_plaza`), y el form solo lo sincroniza al guardar. | El selector usa `tipo.activo and tipo.maneja_plazas and tipo.admite_tipo_de_plaza(Plaza.Tipo.CAMA)`, en un solo lugar (`selectors/emergencia.py`). |
| H7 | RU-15/RN-3.14: aceptar, alojar, diferencia y kit recibido dejan `EntradaBitacora` `AUTOMATICA` `GENERAL`. 00 §3: «`dispositivo.bitacora` no hace falta». | Solo hay dos escritores. `anotar_en_bitacora(movimiento)` escribe automáticas, pero **cuelga de un `MovimientoEstadia`** (uno a uno). `registrar_entrada` es **manual** y exige `dispositivo.bitacora`. No hay forma de escribir una `GENERAL` automática sin movimiento. Además, **sin turno vigente no se escribe nada** (no se inventa un turno). | El PR 6 agrega `bitacora.anotar_novedad_automatica(dispositivo, tipo, texto, momento)`: sin capacidad, `origen=AUTOMATICA`, el mismo «sin turno no escribe». El modelo admite `GENERAL` automática (`clean()` solo prohíbe tipos automáticos con origen manual). Los ingresos ya dejan su `INGRESO` por `ingresar_persona`. |
| H8 | RN-5.2: «verificar el helper del día operativo de 06:00 en `dashboard_becas.py`». | No existe. Becas usa `timezone.localtime(…).date()`. Las 06:00 solo aparecen en la ventana de turnos de `bitacora.py`/`censo.py`, que es **por dispositivo**. | `selectors/emergencia_tablero.py` define `DIA_OPERATIVO_DESDE = time(6, 0)` y calcula el rango en Python (hora de Argentina). Los tests usan momentos fijos. |
| H9 | RN-3.12: el egreso marca `IntegranteGrupo.egresado_en` por «un receptor de señal o un hook en `egresar_persona`». | `egresar_persona` no emite ninguna señal ni tiene hook. `programas/signals.py` solo tiene receptores de modelo. | El PR 6 agrega una señal de dominio `estadia_egresada` enviada **dentro** de la transacción de `egresar_persona`. Emergencia la recibe y cierra el caso si no queda nadie. Un receptor que falla deshace el egreso: es intencional y tiene test. |
| H10 | RU-4: login con `"emergencia"` si tiene `dispositivo.admitir` «en al menos un dispositivo de su equipo». | `dispositivos_operados(user, cap)` responde exactamente eso. El admin del programa (`programa.configurar`) opera todo **sin** Equipo, y `dispositivos_operados` no lo ve. | La regla del login es `puede(user, "emergencia.relevar", programa=EMERGENCIA) or dispositivos_operados(user, "dispositivo.admitir").exists() or puede_configurar_dispositivos(user)`. Va en una sola función, `emergencia.modulo_habilitado(user)`, que usan el login y los permisos de la API. |
| H11 | 01 §8 y criterio 01 §12: «actualizar `CLAVES_LOGIN`». | Las **claves** del login no cambian: cambia un **valor** posible dentro de `modulos`. | `CLAVES_LOGIN` queda igual. Se agregan tests de valores (`["emergencia"]`, `["becas","emergencia"]`, …) y no se toca `test_el_login_trae_modulos…`, que afirma `["becas"]` para el territorial. |

### PWA (`Chaco-mobile`) — anclas **sin verificar**

El repo no está en el checkout del PM. Se planifica con lo que dicen los archivos de etapa:

- `src/services/modulos.js` — **sin verificar**
- `src/services/dispositivosService.js` — **sin verificar**
- `src/services/dispositivosBorrador.js` — **sin verificar**

Nota informativa, no reemplaza la verificación. En un clon de solo lectura del repo público hecho en esta
sesión:
- Esos tres archivos aparecen **solo en la rama `test`** (62 commits adelante de `main`), no en `main`.
- `dispositivosService.js` cubre **solo** el relevamiento edilicio (outbox SQLite por `uuid_cliente`,
  `/api/dispositivos/inspecciones/`).
- `MODULOS = ['becas', 'dispositivos']`.

Antes del PR 5-PWA hay que confirmar contra qué rama se trabaja: es el supuesto S-11.

---

## 4. Piezas de UI del lote («lote = las piezas primero»)

Relevadas contra `.claude/agents/chaco-design-system.md` (inventario) y `.claude/design/` (fichas).

| Pieza que pide el análisis | Estado | Decisión |
|---|---|---|
| Semáforo de SLA (fila de E2: «Fuera de SLA · 42 min», texto + color, RU-19) | **Falta** | Construir `components/_semaforo_sla.html` (`estado` EN_TERMINO/POR_VENCER/FUERA, `minutos`, `tramo`; `badge badge-dot` + ícono + texto). La lógica sale de `selectors.emergencia.estado_sla`, nunca del template. Ficha nueva. |
| Reloj del tramo (cabecera de E3: «Derivar vence en 8 min») | **Falta** | Misma pieza con `variante="reloj"` (texto largo, `role="status"`). Una pieza, dos variantes: evita dos traducciones del mismo estado. |
| Tarjeta de dispositivo con plazas y distancia (panel Derivar de E3, paso 1 de E4) | **Falta** | Construir `components/_tarjeta_dispositivo_derivar.html` (nombre, localidad, libres/reservadas, distancia o «desconocida», marca Alcanza / Faltan N / Sin plazas en texto, acción). **No** se reutiliza `_tarjeta_edificio.html`: es otro dato y otra acción. Ficha nueva. |
| Contador «N de N» (M2-3/E6-integrantes) | **Falta** | `_ficha_avance.html` existe pero es porcentaje y «no se incluye suelto». Construir `components/_contador_avance.html` (`hechos`, `total`, `etiqueta`; `role="progressbar"` con `aria-valuemax=total` y texto «3 de 7 confirmadas»). Ficha nueva. |
| Mapa de plazas en modo emergencia | **Existe** (`_mapa_plazas.html` + `_leyenda_plazas.html`) | No se toca la pieza. La vista ya decide `estado`, `tono`, `url`/`click` y `seleccionada`. «Reservada para esta familia» es un **estado de texto** con tono `warning` y seleccionable. «Reservada» ajena queda no seleccionable. La selección es **única** (03 §9, que gana sobre la «multiselección» del README §4). Se actualiza la ficha `mapa_plazas.md` con el consumidor nuevo. Snapshots de la pieza en verde sin cambios. |
| Tabla enviado / recibido / diferencia (E5, M3-2) | **Parcial** (tabla densa canónica `nodo-tables.css`) | Construir solo la celda: `components/_celda_diferencia.html` (signo, texto «−2 · faltan» / «+1 · de más» / «sin diferencia», tono). Ficha nueva «tabla de conciliación» que manda a la tabla canónica. |
| Lista de avisos con severidad (E1) | **Existe por composición** (`_alerta.html` en bucle, como P4 `legajo/detail.html:87`) | No se crea pieza ni se extrae la de P4 (evita tocar una pantalla de Dispositivos y sus snapshots). E1 compone `_alerta` con `tono` por severidad. Se agrega un párrafo de consumidor en `alerta.md`. |
| Tabla de tiempos (E1) | Existe (tabla canónica) | Solo consumidor. |
| Stepper de 4 pasos (E4, «Nuevo caso» de E2) | Existe (`_stepper.html`, golden wizard) | Solo consumidor. |
| Stat cards del tablero | Existe (`_stat_card` `variante="tablero"`, `nota`) | Solo consumidor. |
| Hero del programa (E1) | Existe (`{% hero_inicio %}`, permitido en tableros de programa) | Solo consumidor. Ver C3. |
| Chips de prioridad/estado | Existe (`badge` + `TONOS` del módulo) | Tabla única `ESTADOS_VISIBLES_CASO` en `services/emergencia.py`, como `estadias.ESTADOS_VISIBLES`. |

**Se construyen antes de la primera pantalla (PR 0):** semáforo/reloj de SLA, tarjeta de dispositivo
para derivar, contador «N de N» y celda de diferencia. Son cuatro piezas, con su ficha y la fila en el
inventario del agente canónico (`check_design_agent.py` lo exige).

Arquetipos por pantalla:

| Pantalla | Arquetipo (golden) |
|---|---|
| E2 | Listado (`becas/revision/personas_list.html`) |
| E3, E5 | Detalle (`becas/cupo/segmento_detail.html`) con la grilla de «Formulario con asistencia lateral» para el `split` |
| E4 | Listado + Wizard (`configuracion/programa_wizard_paso4.html`) |
| «Nuevo caso» de E2 | Wizard |
| E6 | Wizard (buscar → derivación → integrantes) + modal de cama sobre `sectores.html` con `?modo=emergencia&caso=` |
| E7 | Formulario (`becas/config/segmento_form.html`) + formset |
| E1 | Detalle, por C3 |

---

## 5. PRs en orden

Convenciones de cada ficha: «B» = backend (`Chaco`), «P» = PWA (`Chaco-mobile`). Las horas incluyen
tests, auditoría y correcciones del review. No incluyen QA manual (PR 13).

### PR 0 — Piezas de UI del lote

- **Objetivo:** que ninguna pantalla del módulo tenga que decidir diseño en medio de la implementación.
- **B archivos:**
  - `templates/components/_semaforo_sla.html`, `_tarjeta_dispositivo_derivar.html`,
    `_contador_avance.html` y `_celda_diferencia.html`.
  - CSS solo si alguna necesita una clase que no exista; en ese caso, `npm run build:tailwind` y se
    commitea la salida.
  - Fichas en `.claude/design/componentes/` (semaforo_sla.md, tarjeta_dispositivo_derivar.md,
    contador_avance.md, conciliacion.md), filas en `.claude/agents/chaco-design-system.md` y notas de
    consumidor en `mapa_plazas.md` y `alerta.md`.
  - `scripts/design_audit.py` solo si una pieza nueva necesita su regla.
- **P:** —
- **Migraciones:** no.
- **Tests:** render de cada pieza con sus variantes (texto presente además del color, ARIA y tono
  desconocido → neutro) en `core/tests/test_nodo_ui_piezas.py`, más los snapshots existentes intactos.
- **Reglas:** RU-19 (texto + color), RN-2.10 (estados del semáforo, presentación) y RN-4.3 (diferencia
  visible).
- **Depende de:** nada. **Horas:** 14.

### PR 1 — Programa, RBAC y configuración (E7)

- **Objetivo:** que existan el programa EMERGENCIA, las capacidades, la configuración del SLA y el
  catálogo de kits, y que el PM pueda armar los roles.
- **B archivos:**
  - `core/rbac.py`:
    - Módulo `emergencia` con `alcance: programa` y `programas: ("EMERGENCIA",)`, capacidades
      `emergencia.relevar`/`operar`/`supervisar`.
    - `emergencia.recibir_kit` en un módulo acotado a DISPOSITIVOS (H3).
    - `CAPACIDADES_DE_CAMPO += {"emergencia.relevar"}`.
    - `CODIGO_PROGRAMA_EMERGENCIA`.
  - `programas/services/programa_cache.py` (o `services/emergencia.py`): `programa_emergencia(user)`,
    con la fachada de `programa_por_codigo`.
  - `programas/models/__init__.py`: `SLAEmergencia` (una fila por programa), `TipoKit`,
    `TrazaConfiguracion`.
  - `programas/services/configuracion_emergencia.py`: `guardar_sla` con traza por campo y
    `catalogo_kits`.
  - `programas/forms_emergencia.py`: ModelForm + formset.
  - `programas/views/emergencia_config.py`, `programas/emergencia_urls.py` (namespace `emergencia`),
    `config/urls.py`.
  - Template E7 (golden de formulario) y entrada «Emergencia» en el grupo «Programas» del sidebar, con el
    filtro por capacidad.
  - `users/management/commands/seed_datos_base.py` / `crear_programas`: crea el programa y la fila
    `SLAEmergencia` con defaults, sin pisar lo configurado (Cambio 104).
- **P:** —
- **Migraciones:**
  - `programas.01xx_emergencia_base`: tablas nuevas. `SLAEmergencia` con `DEFAULT` real en los minutos;
    `TipoKit.nombre` unique.
  - `programas.01xx_programa_emergencia` (`RunPython` que crea la fila `Programa`; reversa que la borra
    solo si no tiene roles; patrón `0012`).
  - `users.00xx_capacidades_emergencia` (siembra de permisos; reversa).
  - Ninguna columna sobre tabla existente.
- **Tests:**
  - El `CATALOGO` expone las 4 capacidades y `recibir_kit` se puede otorgar en un rol de Dispositivos y
    **no** en uno de Emergencia.
  - `es_solo_campo` con `emergencia.relevar`.
  - **Mutación RU §6 n.° 3 (mitad backoffice):** un rol de Becas no abre ninguna URL `emergencia:*`
    (barrido del URLconf, Cambio 122).
  - E7: 403 sin `supervisar`; guardar deja `TrazaConfiguracion`; vigencia < 30 rechazada; umbral entre
    50 y 95.
  - `TipoKit` se desactiva y no se borra.
  - Seed idempotente.
- **Reglas:** RU-6, 7 y 11, RN-4.7, RN-5.5 y 05 §4.
- **Depende de:** nada. **Horas:** 24.

### PR 2 — Modelo del caso y servicios de la mesa

- **Objetivo:** el dominio del caso, sin pantallas: crear, tomar, soltar, reasignar, priorizar,
  contactar, derivar, cancelar y cerrar, con las guardas probadas por mutación.
- **B archivos:**
  - `programas/models/__init__.py`: `GrupoFamiliar`, `IntegranteGrupo` (`ficha` JSON con esquema fijo
    por S-6), `CasoEmergencia` (marcas `tomado_en`/`derivado_en`/`aceptado_en`/`alojado_en`/`cerrado_en`
    escritas una sola vez, `relevado_en`, `uuid_cliente`, `numero`), `Derivacion` (`clave_vigente`),
    `ContactoCaso`, `AdjuntoCaso` (VIVIENDA/ACCESO, `media/emergencia/casos/<uuid>/`), `TrazaCaso`
    inmutable (manager sin update/delete, como `TrazaDispositivo`) y `NumeradorEmergencia` (fila
    contador por año y serie, `select_for_update`).
  - `programas/services/emergencia.py`: `crear_caso`, función única para M1, «Nuevo caso» e ingreso
    directo (calcula `total_declarado` y prioridad en el servidor y da de alta mínima al responsable con
    el servicio de `ingreso.py`). También `tomar_caso`, `soltar_caso`, `reasignar_caso`,
    `cambiar_prioridad`, `registrar_contacto`, `derivar_caso`, `cancelar_derivacion`,
    `cerrar_sin_alojamiento` y la tabla `ESTADOS_VISIBLES_CASO`.
  - `programas/selectors/emergencia.py`: `bandeja(filtros)`, con conteo de solapas en una consulta
    agregada y «fuera de SLA» en Python sobre los abiertos. `dispositivos_para_derivar(caso)` usa
    `ocupacion_de_plazas` en lote y haversine en Python (H4, H6). También `estado_sla(caso, sla, ahora)`
    y `posibles_duplicados`.
- **P:** —
- **Migraciones:** `programas.01xx_emergencia_casos`:
  - Tablas nuevas.
  - `uuid_cliente` como `UUIDField(null=True, unique=True)` + `RunPython` a `char(36)` con
    `modificar_columna` y reversa (patrón `0093`).
  - `Derivacion.clave_vigente` `PositiveIntegerField(null=True)` + `UniqueConstraint(fields=
    ["clave_vigente"])`.
  - `numero` único.
  - Índices `(estado, prioridad)`, `(tomado_por, estado)` y `(dispositivo, estado)` en `Derivacion`.
  - Sin columnas sobre tablas existentes.
- **Tests:**
  - **Mutación RU §6 n.° 1:** `operar` sin `supervisar` reasigna → `PermissionDenied` y la fila no
    cambia.
  - **Mutación RU §6 n.° 4 / RN-2.1:** dos conexiones toman el mismo caso (`TransactionTestCase`); gana
    una y la otra recibe `CasoTomadoPorOtro`.
  - RN-2.6: segunda derivación vigente → `IntegrityError` traducido a 409 de dominio, también contra
    MariaDB en el job de ida y vuelta.
  - RN-1.2 (total del servidor), RN-1.3, RN-1.4 (tabla de prioridad), RN-2.5, RN-2.9 (las marcas no se
    borran al soltar/reasignar/volver), RN-2.10 (tabla de estados del semáforo, con momentos fijos),
    RN-2.11 a RN-2.15.
  - Numerador concurrente.
  - RU-12/13 (dueño vs supervisor, traza «por supervisor»).
  - RU-15 (cada transición deja `TrazaCaso`).
- **Reglas:** RN-1.2 a 1.5, 1.10 y 1.11, RN-2.1 a 2.6 y 2.9 a 2.15, RU-12, 13 y 15.
- **Depende de:** PR 1. **Horas:** 34.

### PR 3 — Backoffice de la mesa: E2, E3 y «Nuevo caso»

- **Objetivo:** que un operador cargue un caso a mano, lo tome, hable con la familia, lo derive o lo
  cierre.
- **B archivos:**
  - `programas/views/emergencia.py`: `BandejaCasosView`, `CasoDetalleView`, `NuevoCasoWizard`,
    `TomarCasoView`, `SoltarCasoView`, `ReasignarCasoView`, `CambiarPrioridadView`, `ContactoCasoView`,
    `DerivarCasoView`, `CancelarDerivacionView`, `CerrarCasoView` y la vista de fotos detrás de login.
    Usan `@requiere("emergencia.operar")` o `supervisar` y no tienen lógica.
  - `programas/forms_emergencia.py`: Formulario 1 de la mesa, contacto, cierre y reasignar.
  - `programas/emergencia_urls.py`.
  - Templates `programas/emergencia/casos/` (lista, detalle, parciales de derivar y contactos, modales)
    clonados de sus goldens; consume las piezas del PR 0.
- **P:** —
- **Migraciones:** no.
- **Tests:**
  - Status code y redirect sin login por vista; 403 sin capacidad.
  - RU-12: el no dueño ve solo lectura + «Tomar».
  - 409 de la «segunda pestaña» (02 §9).
  - **Presupuesto de E2 con 500 casos abiertos** (`--tag performance`, `assertNumQueries`).
  - E3 sin N+1 en el panel de derivar con 50 dispositivos.
  - `design_audit --ratchet` 0 nuevos y `--arquetipo listado/detalle/wizard` sobre las pantallas nuevas.
- **Reglas:** HU-1.4, HU-2.1 a 2.4, 2.6 y 2.7, RU-10, 12, 13, 14, 19, 20 y 22.
- **Depende de:** PR 0 y PR 2. **Horas:** 32.

### PR 4 — Vencimientos de la mesa

- **Objetivo:** que la derivación no aceptada venza sola y que el caso abandonado vuelva a la bandeja.
- **B archivos:** `programas/services/vencimientos_emergencia.py` (dos `ReglaVencimiento`) y su import en
  `programas/apps.py:ready()`.
- **P:** —
- **Migraciones:** no.
- **Tests:**
  - RN-2.7: vence `PENDIENTE` con `vence_en <= now`; la segunda corrida no toca nada; una `ACEPTADA` no
    vence.
  - RN-2.8: la inactividad devuelve a `NUEVO`; `sin_avance_min = 0` la apaga.
  - Carrera con `aceptar` (aceptar y vencer bloquean la derivación; gana uno).
- **Reglas:** RN-2.7, RN-2.8, HU-2.5 y RN-3.3 (del lado del cron).
- **Depende de:** PR 2. **Horas:** 8.

### PR 5 — API base, login y M1 (backend)

- **Objetivo:** que la PWA sepa que el usuario tiene el módulo y que el agente envíe casos con o sin
  señal.
- **B archivos:**
  - `programas/api/views.py`: `ObtainCampoToken` acepta `emergencia.modulo_habilitado(user)` (H10) como
    tercera vía de acceso y suma `"emergencia"` a `modulos`.
  - `programas/api/views_emergencia.py`: `EmergenciaPermission` (relevar), `DispositivoEmergenciaPermission`
    (H10), `consultar_persona` (H2), `LocalidadesView` (`{id, nombre}`, H4), `CasoViewSet.create`
    (multipart, idempotente por `uuid_cliente`) y `casos/mios`.
  - `programas/api/serializers_emergencia.py`, `programas/api_emergencia_urls.py` (namespace
    `emergencia_api`) y `config/urls.py` (`api/emergencia/`).
  - `docs/internal/contrato-app-emergencia.md`.
- **P:** — (ver PR 5-P).
- **Migraciones:** no.
- **Tests:**
  - `test_emergencia_api_contrato.py`: claves exactas de cada respuesta. `CLAVES_LOGIN` sin cambios;
    valores nuevos de `modulos` (H11).
  - **Mutación RU §6 n.° 3 (mitad API):** un usuario con `becas.campo` no recibe `"emergencia"` y su
    token da 403 `SIN_MODULO` en `/api/emergencia/`.
  - **Mutación RU §6 n.° 5 / RN-1.8:** el mismo `uuid_cliente` dos veces crea **un** caso (200 la
    segunda).
  - RN-1.9 (> 5 MB o no JPEG → 400), RN-1.12 (sin dirección → 400).
  - El operador de dispositivo sin Equipo no abre el módulo.
  - El admin del programa Dispositivos sí lo abre.
  - El throttle de consulta de personas es compartido.
- **Reglas:** RU-3, 4, 16, 17 y 18, RN-1.6 a 1.9 y 1.12, HU-1.1 a 1.3 (lado servidor).
- **Depende de:** PR 2. **Horas:** 22.

### PR 5-P — PWA: módulo Emergencia y M1 (Formulario 1 offline)

- **P archivos** (anclas sin verificar, ver §3):
  - `src/services/modulos.js` (+`'emergencia'` y nombre) y `ModuloSelectorScreen` (ícono).
  - `src/services/emergenciaService.js`: cola local y borrador por `uuid_cliente` como
    `dispositivosBorrador.js`; `enviarCaso`, `syncPendientes`, `getEnvios`, `reintentarFallidas`,
    `getLocalidades` con caché diario y `consultarPersona` contra el endpoint nuevo (H2).
  - Pantallas `EmergenciaHomeScreen` (accesos según rol, RU-5), `IngresoFamiliaScreen` (4 pasos) y
    `MisEnviosScreen`.
  - Se reusan `CameraModal.js`, `ubicacion.js`, `imagePicker.js` (HEIC→JPEG, compresión a 3 MB) e
    `identityLookup.js`.
- **Tests:** `tests/emergencia*.test.cjs`: cola, idempotencia, reintento tras 400, borrador que
  sobrevive al cierre de la app, normalización de módulos con sesiones viejas.
- **Reglas:** RU-3, 4, 5 y 16, RN-1.1, 1.3 (también en cliente), 1.8 y 1.12.
- **Depende de:** PR 5 (el contrato puede empezar contra el documento). **Horas:** 40.

### PR 6 — Dispositivos: reservas de derivación, bitácora automática y señal de egreso

- **Objetivo:** abrir en Dispositivos los tres puntos de extensión que Emergencia necesita (H1, H7, H9)
  sin cambiar ninguna firma ni comportamiento existente.
- **B archivos:**
  - `programas/models/__init__.py`: `ReservaPlaza.derivacion = FK(Derivacion, null=True,
    on_delete=PROTECT)`.
  - `programas/services/estadias.py`:
    - `reservar_plazas_de_derivacion(derivacion, plazas, usuario)`: bloquea las plazas ordenadas por pk,
      exige plaza libre una por una y **no** aplica «una reserva por persona». Motivo «Emergencia caso
      N.° X», `hasta=NULL`.
    - `consumir_reserva_de_derivacion(reserva, ciudadano, usuario, …)`: plaza → reserva con bloqueo;
      exige `reserva.derivacion` vigente; reasigna `ciudadano` y llama a `ingresar_persona(reserva=…)`
      en la misma transacción.
    - `reserva_propia_vigente` y `_exigir_persona_sin_alojamiento_ni_reserva` filtran
      `derivacion__isnull=True`.
  - `programas/services/ingreso.py`: `_reservas_abiertas_de` filtra `derivacion__isnull=True` (C1).
  - `programas/services/bitacora.py`: `anotar_novedad_automatica` (H7).
  - `programas/services/estadias.py` + `programas/signals.py`: señal `estadia_egresada` en
    `egresar_persona`, dentro del `atomic` (H9).
  - `docs/internal/requerimientos.md`, que referencia C1.
- **P:** —
- **Migraciones:** `programas.01xx_reserva_plaza_derivacion`: columna nueva `null=True` sobre tabla
  existente (cumple el contrato sin marca) e índice `(derivacion, estado)`. Expand puro: el código viejo
  no la lee ni la escribe. Se prueba ida y vuelta contra MariaDB y MySQL.
- **Tests:**
  - **Regresión completa** de `programas.tests.test_dispositivos_concurrencia`, `OrdenDeLosCandadosTests`
    y los tests de ingreso/reserva de los Cambios 389, 407 y 409: deben seguir verdes **sin editarlos**.
  - Nuevos:
    - 7 reservas de derivación a nombre del mismo responsable.
    - Una reserva normal del responsable en el mismo dispositivo sigue bloqueando una segunda reserva
      **normal**.
    - El ingreso del responsable por `confirmar_ingreso` **no** libera las reservas de derivación (C1).
    - `consumir_reserva_de_derivacion` con otra persona → `Estadia` y reserva `CONSUMIDA`;
      `_bloquear_reserva_propia` sigue rechazando una reserva normal ajena (MAJOR 1 de #802 intacto).
    - Concurrencia: dos consumos de la misma reserva; consumo contra `liberar_reserva`; consumo contra
      un ingreso normal en la misma plaza.
    - La bitácora automática sin turno no escribe.
    - Un receptor de la señal que falla deshace el egreso.
  - `ocupacion` cuenta las reservas de derivación como reservadas (sin cambio de código, con test).
- **Reglas:** RN-3.4, 3.5, 3.7, 3.12 y 3.14, RU-15 (bitácora) y C1.
- **Depende de:** PR 2 (modelo `Derivacion`). **Horas:** 28. **Modo juez obligatorio.**

### PR 7 — Alojar en el backoffice (E6) y servicios de la etapa 3

- **Objetivo:** que la guardia, desde el backoffice, convierta una familia en N estadías con cama, y que
  la misma función quede lista para la API.
- **B archivos:**
  - `programas/services/emergencia_alojar.py`:
    - `buscar_por_dni(dispositivo, dni, usuario)`: tres resultados, sin nombrar el otro dispositivo
      (RU-9, RN-3.2).
    - `aceptar_derivacion`: caso → derivación → `reservar_plazas_de_derivacion`; acepta una `PENDIENTE`
      ya vencida si el cron no pasó (RN-3.3).
    - `rechazar_derivacion`, `confirmar_integrante`, `completar_ficha`, `agregar_integrante`,
      `alojar_familia`, `cerrar_con_diferencia`, `cancelar_ingreso`, `ingreso_directo` y
      `avisar_a_la_mesa`, más el receptor de `estadia_egresada`.
    - `confirmar_integrante` hace en una transacción: `Ciudadano` (búsqueda o alta mínima,
      `dni_fisico=NO_TIENE` si corresponde, H5), `VinculoFamiliar`, `IntegranteGrupo` y
      `consumir_reserva_de_derivacion`, o `ingresar_persona` sobre una plaza libre (RN-3.8). Si el
      ingreso falla, no queda nada huérfano (RN-3.7).
  - `programas/selectors/emergencia.py`: `plazas_para_caso(dispositivo, caso)` (estados LIBRE /
    RESERVADA_FAMILIA / OCUPADA / FUERA_SERVICIO desde `estado_de_plazas`) e `integrantes(caso)`.
  - `programas/views/emergencia_dispositivo.py` y templates `programas/emergencia/dispositivo/` (wizard
    + modal de cama sobre `sectores.html?modo=emergencia&caso=` + modales de diferencia/rechazo).
  - Entrada «Emergencia · Llegadas» en el menú del detalle del dispositivo, con
    `puede_operar_dispositivo(…, admitir)`.
- **P:** —
- **Migraciones:** no.
- **Tests:**
  - RN-3.1 (tres resultados + alcance), 3.3, 3.4 (parcial, 0 libres), 3.5 (por la vía del PR 6), 3.6
    (mínimo por S-6/D-1), 3.7 (atomicidad), 3.8, 3.9, 3.10, 3.12 (el egreso del último cierra) y 3.13.
  - **Mutación RU §6 n.° 2** y la nueva: `admitir` en A no acepta una derivación de B aunque conozca el
    id → 404 (C2).
  - **Concurrencia:** doble aceptación; doble confirmación de la misma persona; aceptar contra el
    vencimiento del PR 4.
  - Presupuesto de `integrantes` y `plazas_para_caso` con un dispositivo de 300 camas.
  - Los snapshots de `_mapa_plazas` siguen intactos.
- **Reglas:** RN-3.1 a 3.14, HU-3.1 a 3.7, RU-1, 2, 8, 9, 15 y 22.
- **Depende de:** PR 0, PR 3 (estados visibles y E3 que muestra lo alojado) y PR 6. **Horas:** 40.

### PR 8 — API M2 (backend)

- **Objetivo:** paridad total de la etapa 3 en la API (RU-1, RU-2).
- **B archivos:**
  - `programas/api/views_emergencia.py`: `mis-dispositivos`, `dispositivos/{id}/buscar`,
    `derivaciones/{id}/aceptar|rechazar`, `casos/{id}/integrantes` (GET/POST),
    `integrantes/{n}/confirmar`, `PATCH integrantes/{n}`, `alojar`, `cerrar-diferencia`,
    `cancelar-ingreso`, `dispositivos/{id}/plazas/?caso=` e `ingreso-directo` (multipart, idempotente).
    Llaman a las mismas funciones del PR 7, sin validar de nuevo.
  - Serializers y contrato.
- **P:** —
- **Migraciones:** no (si el ingreso directo idempotente necesita guardar su `uuid_cliente`, va en
  `CasoEmergencia.uuid_cliente`, que ya existe desde el PR 2).
- **Tests:**
  - Contrato de claves de cada respuesta, incluido `…/plazas/`.
  - 409 con `{detail, estado_actual}` cuando otra guardia actuó desde el backoffice (PWA contra web
    sobre el mismo servicio).
  - RU-16 en cada escritura que crea filas.
  - Alcance 404 (C2).
  - Presupuesto de `mis-dispositivos`.
- **Reglas:** RU-1, 2, 3, 9, 16 y 20, 03 §7.
- **Depende de:** PR 5 y PR 7. **Horas:** 24.

### PR 8-P — PWA: M2 (llegada de familias)

- **P archivos** (anclas sin verificar):
  - `emergenciaService.js`: `buscarPorDni`, `aceptar`, `rechazar`, `integrantes`, `plazas`,
    `confirmarIntegrante`, `agregarIntegrante`, `alojar`, `cerrarDiferencia` e `ingresoDirecto` (solo
    este con cola; el resto exige `NetInfo` conectado y muestra el aviso de RN-3.11).
  - Pantallas `LlegadaBuscarScreen`, `DerivacionScreen`, `IntegrantesScreen`, `FichaIntegranteScreen`,
    `FamiliaAlojadaScreen`, `MapaPlazasModal` (selección única, tres estados con texto) y selector de
    dispositivo previo (patrón `DispositivosListaScreen`).
- **Tests:** 409 → recarga con `estado_actual`; offline solo en el ingreso directo; contador «N de N».
- **Reglas:** RU-1, 3 y 5, RN-3.11, HU-3.1 a 3.6 en la app.
- **Depende de:** PR 8. **Horas:** 48.

### PR 9 — Kits: modelo, servicios y backoffice (E4, E5, recepción web)

- **Objetivo:** una entrega, una recepción, con diferencias visibles.
- **B archivos:**
  - `programas/models/__init__.py`: `EntregaKit` (`numero` del numerador del PR 2, o propio si el PR 9
    va antes; `uuid_cliente_recepcion`, `repone_a`), `LineaEntrega` (unique `(entrega, item)`, `unidad`
    copiada) y `TrazaEntrega`.
  - `programas/services/kits.py`: `crear_entrega`, `marcar_en_camino`, `cancelar_entrega`,
    `recibir_entrega` (con `select_for_update` de la entrega, idempotente por uuid y 409 si ya se
    recibió o se canceló) y `observar_recepcion`.
  - `programas/selectors/kits.py`.
  - Vistas `programas/views/emergencia_kits.py` y templates E4 (listado + wizard), E5 (detalle con
    `_celda_diferencia`) y la recepción web dentro del dispositivo (`recibir_kit` vía
    `puede_operar_dispositivo`, H3).
  - Bitácora `GENERAL` automática por el PR 6.
- **P:** —
- **Migraciones:** `programas.01xx_emergencia_kits`: tablas nuevas, `uuid_cliente_recepcion` en
  `char(36)` (patrón `0093`) y `numero` único.
- **Tests:**
  - RN-4.1, 4.3 (estado final según diferencias, positiva incluida), 4.4 (idempotencia + 409), 4.5, 4.6
    y 4.8.
  - Numeración concurrente.
  - **Mutación:** `recibir_kit` en A no recibe una entrega de B → 404.
  - Cancelación contra recepción en carrera.
  - «Reponer» precarga las diferencias.
- **Reglas:** RN-4.1 a 4.9, HU-4.1 a 4.6, RU-15 y 17.
- **Depende de:** PR 0, PR 1 y PR 6 (bitácora). El numerador del PR 2 es opcional. **Horas:** 34.

### PR 9-API — API M3 (backend)

- **B archivos:** `programas/api/views_emergencia.py` (`dispositivos/{id}/entregas`, `entregas/{id}` y
  `entregas/{id}/recibir`, multipart) y el contrato.
- **Tests:** contrato; 409 si ya recibida o cancelada; 404 por alcance; remito > 5 MB → 400.
- **Depende de:** PR 5 y PR 9. **Horas:** 8.

### PR 9-P — PWA: M3 (recepción de kits)

- **P archivos:** `emergenciaService.js` (`entregasPendientes`, `recibirEntrega` con conexión
  obligatoria), `EntregasScreen`, `RecepcionKitScreen` y `RecepcionConfirmadaScreen`; reusa
  `imagePicker.js`.
- **Tests:** precarga con lo enviado; falta foto → no envía; 409 → recarga.
- **Depende de:** PR 9-API. **Horas:** 20.

### PR 10 — Tablero E1 y avisos

- **Objetivo:** que el supervisor vea en una pantalla si la emergencia está bajo control.
- **B archivos:**
  - `programas/selectors/emergencia_tablero.py`: `resumen`, `por_localidad`, `tiempos` y
    `entregas_en_camino`, con el presupuesto documentado; «hoy» por H8; plazas de la red con
    `ocupacion_de_plazas` en lote (RN-5.7).
  - `programas/services/avisos_emergencia.py`: las 7 `ReglaAviso`, ámbito `emergencia`, registradas en
    `ready()`.
  - `TableroView` (`@requiere("emergencia.supervisar")`, S-12) y template E1 (C3).
- **P:** —
- **Migraciones:** no.
- **Tests:**
  - Cada número del hero y de las 6 tarjetas contra un escenario sembrado.
  - Cada `ReglaAviso` aparece y desaparece.
  - **RN-5.6:** ≤ 12 consultas con 500 casos, 50 dispositivos y 200 entregas (`--tag performance`).
  - **RN-5.2:** el SQL capturado no contiene `CONVERT_TZ`.
  - Programa vacío sin división por cero.
- **Reglas:** RN-5.1 a 5.7, HU-5.1 a 5.3 y RU-19.
- **Depende de:** PR 3, PR 7 y PR 9. **Horas:** 28.

### PR 11 — Semáforo en vivo de la bandeja y avisos de la mesa en E2/E3

- **Objetivo:** cerrar las marcas que dependen de las etapas 3 y 4 («Ingreso parcial», «Ingreso
  directo», «En la puerta de X», «Rechazado por X», «Dispositivo inactivo · volver a derivar»), que en el
  PR 3 no tienen todavía de dónde salir.
- **B archivos:** `selectors/emergencia.py` (marcas), templates E2/E3 (parciales) y tests de cada marca.
- **Migraciones:** no.
- **Depende de:** PR 7. **Horas:** 10.

### PR 12 — Documentación del módulo

- `docs/internal/contrato-app-emergencia.md` cerrado, manual del módulo para QA y entrada de cierre en
  `requerimientos.md`.
- **Horas:** 6.

### PR 13 — QA (no es código)

- Casos de QA por task (primera línea «Ambiente: testing (datanach.ecomdev.ar)»), plan de pruebas de la
  épica y prueba en **la PWA de testing y en el backoffice**.
- Lo genera `qa-analyst`.
- **Horas:** 16.

---

## 6. Horas, paralelismo y camino crítico

| PR | B | P | Depende de |
|---|---:|---:|---|
| 0 Piezas UI | 14 | | — |
| 1 Programa y RBAC | 24 | | — |
| 2 Caso y servicios | 34 | | 1 |
| 3 Mesa E2/E3 | 32 | | 0, 2 |
| 4 Vencimientos | 8 | | 2 |
| 5 API base + login | 22 | | 2 |
| 5-P PWA M1 | | 40 | 5 |
| 6 Dispositivos: reservas, bitácora, señal | 28 | | 2 |
| 7 E6 y servicios de alojar | 40 | | 0, 3, 6 |
| 8 API M2 | 24 | | 5, 7 |
| 8-P PWA M2 | | 48 | 8 |
| 9 Kits backoffice | 34 | | 0, 1, 6 |
| 9-API API M3 | 8 | | 5, 9 |
| 9-P PWA M3 | | 20 | 9-API |
| 10 Tablero | 28 | | 3, 7, 9 |
| 11 Marcas de bandeja | 10 | | 7 |
| 12 Documentación | 6 | | todos |
| 13 QA | 16 | | todos |
| **Total** | **328** | **108** | |

**Total: 436 h** (13 PRs de backend con código, 3 de PWA, más documentación y QA). El README §8 no
estima. La diferencia de alcance con él la explican H1 (PR 6) y la paridad de la PWA, que el README
resolvía en una sola fila.

**Tres implementadores, carriles:**

| Semana aprox. | Carril A (dominio y Dispositivos) | Carril B (pantallas de la mesa y kits) | Carril C (API y PWA) |
|---|---|---|---|
| 1 | PR 1 | PR 0 | Contrato `contrato-app-emergencia.md` (borrador) + PR 5-P sobre el contrato y mocks |
| 2 | PR 2 | PR 9 (necesita PR 6 solo para la bitácora: se integra el último día o con un stub) | PR 5-P |
| 3 | PR 6 (modo juez) | PR 3 | PR 5 |
| 4 | PR 7 | PR 4 → PR 9-API | PR 5-P (integración real) → PR 9-P |
| 5 | PR 11 → PR 10 | PR 10 (pantalla) | PR 8 |
| 6 | PR 12 | QA de mesa | PR 8-P |
| 7 | — | — | PR 8-P → PR 13 |

- **Se encadenan sí o sí:** 1 → 2 → 6 → 7 → 8 → 8-P (camino crítico ≈ 24 + 34 + 28 + 40 + 24 + 48 =
  **198 h** secuenciales). También 2 → 3 → 7, 9 → 9-API → 9-P y {3, 7, 9} → 10.
- **Van en paralelo:** 0 con 1; 4, 5 y 6 entre sí después del 2; 9 con 2/3; 5-P con todo el
  backend desde el día 1 contra el contrato.
- **Puntos de conflicto de merge:** `programas/models/__init__.py` (PR 1, 2, 6 y 9) y `core/rbac.py`
  (PR 1). Las migraciones de `programas` se numeran al mergear (rebase y `makemigrations --merge`
  prohibido: se renumera). Una sola migración por PR.

---

## 7. Decisiones abiertas del PM

| # | Decisión (README §10 + nuevas) | Bloquea | Supuesto con el que se avanza |
|---|---|---|---|
| 1 | Mínimo de la ficha para confirmar | PR 7 (`confirmar_integrante`), PR 8-P | La propuesta de RN-3.6: parentesco, DNI o «perdió el documento», sexo, las 5 preguntas críticas, y adulto responsable si es menor de 16. Un solo validador (`ficha_minima_valida`): cambiarlo después es un PR chico. |
| 2 | Aviso automático a la familia | Ninguno | Registro manual del contacto (RU-21). El envío es ampliación. |
| 3 | Vigencia de la derivación | Ninguno (es un valor de E7) | 720 min por default en el seed. |
| 4 | Ingreso directo sin la mesa | PR 7 y PR 8 (una parte) | **Sí**, marcado. Se implementa al final de cada PR, detrás de su propia vista o endpoint, para poder sacarlo sin tocar el resto. |
| 5 | Dispositivos elegibles | PR 2 (selector) | Cualquier tipo activo que admita `CAMA` (H6). Si el PM elige «Centro de evacuados», es un filtro en un solo lugar. |
| **6** | **Formulario 2 por constructor (P17) o fijo** | **PR 2 (modelo de `IntegranteGrupo.ficha`), PR 7, PR 8-P** | **Fijo** (S-6): esquema JSON versionado con `version` dentro de la ficha. El constructor no tiene renderer en la app para Dispositivos (el de Becas en la app sigue pendiente, Cambio 58/#348), así que elegir constructor suma al menos 40 h de PWA y un contrato nuevo. **Hay que pedirla ya:** cambia el PR 2. |
| 7 | Objetivos de SLA iniciales | Ninguno | 15 / 30 / 120 / 60 en el seed. |
| 8 | Tablero solo para el supervisor | Ninguno | Solo `supervisar` (S-12). Cambiarlo es un decorador. |
| **D-9 (nueva)** | **Autorizar el PR 6: tocar `estadias.py`, `ingreso.py` y `bitacora.py` de Dispositivos** (el análisis dice «nada de esto se modifica»; H1 muestra que sin eso no se puede aceptar una derivación de más de una persona). | PR 6 y todo lo que cuelga (7, 8, 8-P, 9, 10) | Se avanza con el diseño del PR 6 (extensión sin cambiar firmas, regresión sin editar tests viejos, modo juez). Si el PM prefiere otra salida, es reemplazar el PR 6 antes del PR 7. |
| D-10 (nueva) | Persona que **no sabe su número de documento** (H5). | PR 7 (una rama de `confirmar_integrante`) | No se confirma con cama. El ingreso se cierra con diferencia, motivo «Otro: sin número de documento», y la mesa lo ve. Sin DNI sintéticos. |
| D-11 (nueva, informativa) | Coordenadas de localidad para la distancia sin GPS (H4). | Ninguno | Sin centroide en esta etapa. |

---

## 8. Riesgos y mitigación

| # | Riesgo | Mitigación |
|---|---|---|
| R1 | **Concurrencia en tomar, aceptar y confirmar.** Dos operadores, o la PWA y el backoffice a la vez. Riesgo de deadlock al cruzar los candados de Emergencia (caso, derivación) con los de Dispositivos (plaza, reserva, persona). | Orden global fijo: **caso → derivación → plazas (por pk) → reservas → persona**. Toda función de Emergencia bloquea el caso primero y relee el estado. `aceptar` bloquea la derivación antes de reservar. `confirmar` bloquea caso → integrante → (plaza, reserva, persona por `consumir_reserva_de_derivacion`). Hay un test de orden de llamadas como `OrdenDeLosCandadosTests`, carreras con `TransactionTestCase` y la corrida contra MariaDB. `ERROR 1213` se registra con un test que lo provoca a propósito invirtiendo el orden (mutación). |
| R2 | **El read_timeout de 10 s en el tablero y la bandeja.** | Presupuestos con `assertNumQueries` (E2 con 500 casos, E1 ≤ 12 consultas, `integrantes`/`plazas` con 300 camas). La ventana del tablero es abiertos + últimas 24 h, nunca el histórico. La ocupación se calcula en lote. Ningún JSON se decodifica en Python sobre miles de filas (la ficha no entra al tablero). El alcance se resuelve a ids. Sin `Trunc*`. |
| R3 | **Alcance por dispositivo.** Fugas de datos de una familia hacia otro dispositivo, o un 403 que revela existencia. | Toda consulta de la guardia parte de `dispositivos_en_alcance`/`puede_operar_dispositivo`. 404 por alcance (C2). `buscar_por_dni` nunca nombra otro dispositivo (RN-3.2). Hay tests de mutación por cada «✖/◐» de 00 §4, y la capacidad `recibir_kit` está catalogada en DISPOSITIVOS (H3) para que el Equipo funcione. |
| R4 | **Contrato de la API y del login.** Romper la app instalada de Becas o del agente edilicio. | `CLAVES_LOGIN` no cambia (H11). `modulos` solo agrega un valor y la app vieja lo filtra (`normalizarModulos`, sin verificar). El login acepta una tercera vía sin cambiar las otras dos. El endpoint de Becas no cambia (H2). Test de contrato en el mismo diff que cada serializer y documento `contrato-app-emergencia.md`. La PWA mínima que entiende `emergencia` se declara en `APP_CAMPO_VERSION_MINIMA` solo si hace falta. |
| R5 | **Snapshots de Becas si se toca una pieza compartida.** | El plan no modifica ninguna pieza canónica: `_mapa_plazas`, `_alerta`, `_stat_card`, `_stepper` y `_field` se **consumen**. Las 4 piezas nuevas son archivos nuevos. Cada PR de UI corre los snapshots y `design_audit --goldens`. Si alguno exige tocar una pieza, sale de ese PR y va en un PR de pieza con su ficha. |
| R6 | **Regresión en Dispositivos por el PR 6.** | Ninguna firma existente cambia. Los filtros nuevos son `derivacion__isnull=True` sobre filas que antes no existían (todas `NULL`). La suite de concurrencia de Dispositivos corre sin editar, el PR va en modo juez y la columna es expand puro (rollback seguro). |
| R7 | **Ramas de la PWA** (`main` vs `test`, §3). | Supuesto S-11: se trabaja sobre la rama que hoy sale a testing de ECOM. Se confirma antes del PR 5-P. |
| R8 | **Bitácora que no se escribe por falta de turno** (H7). | Es el comportamiento de Dispositivos y se mantiene. La traza del caso (`TrazaCaso`) se escribe siempre, así que la mesa no pierde nada. Se documenta en el manual. |

---

## 9. Correcciones al análisis

No se modificaron los archivos de `docs/internal/emergencia/`. Estas son las correcciones para quien los
mantenga:

1. **RN-3.4/3.5 (03) y README §4 «Nada de esto se modifica»:** con el código actual no se pueden crear
   N reservas a nombre de una persona en un dispositivo, ni consumir una reserva con otra persona (H1).
   Además, el Cambio 409 D2 las liberaría al ingresar el responsable (C1). Corregir hacia el PR 6.
2. **00 §3:** `emergencia.recibir_kit` no puede vivir en un módulo acotado a EMERGENCIA si se evalúa con
   `puede_operar_dispositivo` (H3).
3. **01 §8 y 03 §7:** `POST /api/becas/personas/consultar/` exige `becas.campo`. Emergencia necesita su
   propio endpoint (H2).
4. **01 §8 y §12:** `CLAVES_LOGIN` no cambia; cambian los valores posibles de `modulos` (H11).
5. **01 RN-1.7, 02 RN-2.4, API de localidades:** `core.Localidad` no tiene coordenadas (H4).
6. **01 §10, 03 RN-3.7:** `Ciudadano.documento_en_mano` no existe. Usar `dni_fisico = NO_TIENE`. Sin
   número de DNI no hay `Ciudadano` (H5, D-10).
7. **02 RN-2.2:** `tipo.maneja_camas` es de la v1. Usar `tipos_plaza_admitidos` (H6).
8. **00 §3 / RN-3.14:** no existe escritor de bitácora `GENERAL` automática, y sin turno no se escribe
   (H7).
9. **05 RN-5.2:** no hay helper de día operativo en `dashboard_becas.py` (H8).
10. **03 RN-3.12:** `egresar_persona` no tiene hook ni señal (H9).
11. **00 RU-4:** también abren el módulo los admins del programa Dispositivos, que operan sin Equipo
    (H10).
12. **00 RU-22:** las pantallas nuevas no usan SweetAlert2 (legacy condicionado), sino el arquetipo
    Modal/Confirmación con `ModernModal` (C4).
13. **05 §3:** E1 no tiene golden de dashboard y el de Becas no es molde. E1 va como Detalle con hero y
    stat cards, sin gráficos (C3).
14. **HU-3.1, HU-4.3:** por el Cambio 432, un recurso de otro dispositivo da 404, no 403 (C2).
15. **README §1 vs 03 §5/RN-3.10:** el ingreso directo nace `INGRESO_EN_CURSO` (gana 03), no `ALOJADO`
    (README §2 y spec §4).
16. **README §4 (mapa en multiselección) vs 03 §9 (selección única):** gana 03.
17. **README §7:** el patrón de UUID para columnas nuevas es `programas.0093` (`modificar_columna` a
    `char(36)`); la `0073` es una barrera de reversa.
18. **Líneas citadas desactualizadas:**

    | Símbolo | Línea real | Línea citada |
    |---|---|---|
    | `CAPACIDADES_DE_CAMPO` | 879 | 893 |
    | `puede_operar_dispositivo` | 129 | 150 |
    | `reservar_plaza` | 784 | 778 |
    | `ingresar_persona` | 431 | 430 |
    | `egresar_persona` | 530 | 529 |
    | `liberar_reserva` | 890 | 884 |
    | `ReservaPlaza` | 1323 | 1305 |
    | `Estadia` | 1061 | 1043 |
    | `EntradaBitacora` | 1695 | 1651 |
    | `TrazaDispositivo` | 748 | 745 |

19. **Etiqueta `#dispositivos`:** no existe en el vocabulario de `requerimientos.md`. `#emergencia` se
    agrega en el PR 1.

---

## 10. Supuestos

- **S-5** — Sin centroide de localidad (H4).
- **S-6** — Formulario 2 fijo (D-6).
- **S-8** — E1 como Detalle (C3).
- **S-11** — Rama de la PWA de testing (R7).
- **S-12** — Tablero solo supervisor (D-8).
- **Más:**
  - Supuestos de §7 para las decisiones 1 a 5 y 7.
  - Un día operativo empieza a las 06:00 (H8).
  - El numerador de casos y de entregas comparte el modelo (`serie` C/K).
  - El ingreso directo se encola **solo** en el Formulario 1 (RU-3, RN-3.11).

---

## Cierre

1. **PRs:** 13 de backend con código (0 a 11 y 9-API), 3 de PWA (5-P, 8-P, 9-P), documentación (12) y QA (13).
2. **Total:** 436 h (328 de backend, 108 de PWA). Camino crítico ≈ 198 h (1 → 2 → 6 → 7 → 8 → 8-P).
3. **Va primero:** PR 1 (programa, RBAC y E7), y en paralelo PR 0 (las cuatro piezas de UI que faltan).
4. **Pedir ya al PM:** la decisión 6 (Formulario 2 fijo o por constructor, cambia el modelo del PR 2) y
   la nueva D-9 (autorizar el PR 6 dentro de Dispositivos).
5. **Ancla que no coincidió:** RN-3.5. Una reserva a nombre del responsable **no** se puede consumir con
   el ingreso de otra persona (`_bloquear_reserva_propia`), y tampoco se pueden crear varias reservas
   para la misma persona en un dispositivo (`_exigir_persona_sin_alojamiento_ni_reserva`).
