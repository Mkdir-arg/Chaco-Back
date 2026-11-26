# Análisis funcional 010 — Stock y entregas a personas

**Estado:** Definido (decisiones del PM del 25/11/2026; los criterios marcados «por defecto» los confirma el juez)
**Fecha de análisis:** 2026-11-25
**Analista:** planificador (arquitectura y contrato de datos), revisión del juez
**Sprint asociado:** Sin asignar
**Módulo/App:** `programas` (Dispositivos · edificio operativo · Emergencia/kits), `users` (capacidades), `core.rbac`, API `/api/emergencia/`, app `Chaco-mobile`

---

## 1. Contexto y motivación

Hoy el sistema sabe qué kits mandó la mesa de Emergencia a cada institución y qué llegó (Cambio 471), pero no sabe qué
queda en el lugar: una entrega es un remito y nada más (RN-4.6), y la solapa «Abastecimiento» de E8 **estima** el consumo
con reglas, rotulado «no es stock» (RNF-009-13). Las instituciones que reparten insumos a personas (agua, colchones,
módulos alimentarios, pañales) no tienen dónde registrar a quién le dieron qué, ni cuánto les queda, ni lo que les llega por
fuera de la mesa (donaciones, municipio). El PM pidió el 25/11/2026 un módulo de stock por edificio, alimentado por la
recepción de kits y por carga manual, que descuente con cada entrega a una persona identificada por DNI, que permita
traspasar entre edificios y corregir con ajustes trazados, sin quedar nunca en negativo, en la web y en la app de campo.

El diseño parte de lo que ya está y quedó bien: la ficha de la institución con su sección «Edificios · N» y sus tarjetas
(Cambios 570, 572), la página operativa del edificio con sus solapas y avisos (574, 581, 583), la pantalla única de
entregas de kits y la recepción en la solapa Kits del edificio (586), y el patrón de la API de campo de plazas (596-598).
Nada de eso cambia de forma: se le agrega una solapa, una fila de la tarjeta y un efecto a la recepción.

---

## 2. Actores involucrados

| Actor | Rol en el sistema | Qué puede hacer en esta funcionalidad |
|---|---|---|
| Guardia / operador de la institución | Rol «Dispositivos — Operador / Guardia» en el Equipo, alcance Institución o Edificios | Ver el stock de sus edificios, entregar a personas por DNI; recibir kits (suma sola al stock) |
| Coordinador de la institución | Rol «Dispositivos — Coordinador de institución» | Lo anterior, más ingresos manuales, traspasos y ajustes |
| Administrador del programa Dispositivos | `programa.configurar` | Todo, en todas las instituciones; activa `maneja_stock` en el tipo de institución |
| Supervisión de la red | `dispositivo.ver_todos` + `stock.ver` | Ver el stock de toda la red, sin operar |
| Mesa de Emergencia | `emergencia.operar` / `supervisar` | No opera stock; ve el stock registrado junto a la estimación en E8 → Abastecimiento |
| Persona que recibe | `legajos.Ciudadano` (DNI) | Recibe insumos; queda su historial de entregas |

---

## 3. Descripción funcional

### Flujo principal

1. El administrador del programa tilda «Lleva stock de insumos» en el tipo de institución (Configuración → Tipos de
   dispositivo). Es independiente de las plazas: un tipo puede tener solo plazas, solo stock, o las dos.
2. La mesa envía kits a una institución de ese tipo: la entrega lleva edificio obligatorio. Cuando la guardia confirma la
   recepción (web o app), **lo recibido** de cada ítem se suma al stock de ese edificio, en la misma transacción.
3. Lo que llega por fuera de la mesa se carga como «Ingreso manual» con su origen y, si hay, el número de comprobante.
4. La primera vez, el coordinador carga el conteo real con un **ajuste** de motivo «Inventario inicial».
5. La guardia entrega a una persona: escribe el DNI, el sistema la encuentra en el legajo (o en el Registro de Personas, o
   pide nombre y apellido), muestra lo que ya recibió, y la guardia carga qué le da. El stock baja; si no alcanza, se
   rechaza y nada cambia.
6. Si un edificio necesita lo que otro tiene, el coordinador registra un traspaso: sale de uno y entra en el otro en la
   misma operación.
7. Todo movimiento queda en un libro inmutable por edificio; la solapa «Stock» muestra el saldo y los últimos movimientos.

### Flujos alternativos

**Entrega de kits vieja, sin edificio, a una institución con stock**
- Condición: la `EntregaKit` no tiene edificio (anterior al Cambio 523 o armada antes de activar el stock).
- Comportamiento: al recibirla, la guardia elige el edificio entre los activos vinculados a la institución y dentro de su
  alcance; lo recibido entra ahí. Sin ningún edificio activo vinculado, la recepción se rechaza con el mensaje de qué
  resolver (decisión 6 del PM: sin edificio no opera).

**Persona que no está en el legajo**
- Condición: el DNI no tiene legajo.
- Comportamiento: se consulta el Registro de Personas con DNI y sexo. Si la encuentra, el legajo se da de alta con esos
  datos al confirmar la entrega; si no la encuentra o el servicio no responde, se piden nombre y apellido y se da el alta
  mínima (`estado_renaper` vacío), como el ingreso a un dispositivo. Si figura fallecida, no se entrega.

**Stock insuficiente**
- Condición: alguna línea pide más que el saldo del edificio al momento de confirmar (otra guardia entregó antes).
- Comportamiento: se rechaza la operación entera, con el saldo actual de cada ítem afectado. Nada se descuenta.

**Ajuste sobre un saldo que cambió**
- Condición: entre que se abrió el ajuste y se confirmó, hubo otro movimiento de ese ítem.
- Comportamiento: se rechaza («El saldo cambió: era N, ahora es M. Volvé a contar»), sin ajustar.

**Institución con stock sin edificio activo**
- Condición: tipo con `maneja_stock` y ningún edificio activo vinculado.
- Comportamiento: la ficha muestra un aviso; no hay solapa donde operar; la mesa no puede enviarle kits hasta que se
  vincule uno.

---

## 4. Requerimientos

### Requerimientos funcionales

| ID | Requerimiento | Prioridad | Notas |
|---|---|---|---|
| RF-010-01 | `TipoDispositivo.maneja_stock` se edita en la configuración del tipo y es independiente de las plazas | Alta | Desactivarlo con saldo > 0 se rechaza (RN-010-16) |
| RF-010-02 | Solapa «Stock» en la página operativa del edificio: saldo por insumo y últimos 20 movimientos | Alta | Solo si el tipo lleva stock y quien mira tiene `stock.ver` sobre el edificio |
| RF-010-03 | Fila «Stock» en la tarjeta del edificio de la ficha de la institución | Media | «N insumos · M sin existencia» o «Sin stock cargado»; `None` sin permiso o sin stock |
| RF-010-04 | Recibir una entrega de kits suma lo recibido al saldo del edificio de la entrega | Alta | Misma transacción que la recepción |
| RF-010-05 | Ingreso manual de uno o más insumos con origen y comprobante opcional | Alta | |
| RF-010-06 | Entrega a persona por DNI, con varias líneas, mostrando su historial | Alta | |
| RF-010-07 | Traspaso entre dos pares (institución, edificio) con stock | Alta | |
| RF-010-08 | Ajuste por conteo con motivo obligatorio | Alta | «Inventario inicial» es un motivo |
| RF-010-09 | Historial completo de movimientos del edificio, con filtros | Media | Listado paginado |
| RF-010-10 | API de campo para todo lo anterior (lectura y escritura) | Alta | §12 |
| RF-010-11 | E8 → Abastecimiento muestra el stock registrado junto a la estimación en las instituciones con stock | Media | Revierte RNF-009-13 solo ahí |
| RF-010-12 | Aviso en la ficha de una institución con stock sin edificio activo | Media | |

### Requerimientos no funcionales

| ID | Requerimiento | Categoría |
|---|---|---|
| RNF-010-01 | El saldo nunca es negativo: validación bajo candado en el servicio **y** `CHECK (cantidad >= 0)` en la base | Integridad |
| RNF-010-02 | El libro de movimientos y las operaciones son inmutables (sin `update`, `delete` ni `save` sobre una fila existente) | Auditoría |
| RNF-010-03 | `saldo = Σ movimientos` por (institución, edificio, insumo), verificable con un selector de conciliación | Integridad |
| RNF-010-04 | Costo constante: la solapa, la tarjeta y la API no hacen consultas por insumo ni por movimiento | Performance |
| RNF-010-05 | Funciona igual en MySQL 8 y MariaDB: `uuid_cliente` en `char(36)` y búsqueda con `q_uuid_en_texto`; sin `Trunc*` | Compatibilidad |
| RNF-010-06 | Se autoriza solo por capacidad y alcance (`puede_operar_edificio`), nunca por nombre de grupo | Seguridad |
| RNF-010-07 | El historial de una persona no revela en qué otra institución recibió (ni nombre ni localidad) | Privacidad |
| RNF-010-08 | Toda escritura de la API es idempotente por `uuid_cliente` | Confiabilidad |

---

## 5. Reglas de negocio

| ID | Regla | Consecuencia si no se cumple |
|---|---|---|
| RN-010-01 | **Quién lleva stock.** Solo las instituciones cuyo `tipo.maneja_stock` es verdadero. Es independiente de `maneja_plazas`. | Sobre otra institución no hay solapa, ni fila, ni API (404 / 409 `STOCK_NO_HABILITADO`, §12) |
| RN-010-02 | **Clave del saldo: (institución, edificio, insumo).** El edificio tiene que estar vinculado a la institución. Dos instituciones del mismo predio tienen saldos separados. El insumo es `TipoKit` (en pantalla «Insumo»): no hay otro catálogo. | `ValidationError` «El edificio no es de esta institución» |
| RN-010-03 | **Nunca negativo.** Toda salida (entrega, traspaso, ajuste hacia abajo) se valida contra el saldo **leído bajo candado**. Si una sola línea no alcanza, no se mueve ninguna. Respaldo en la base: `CHECK (cantidad >= 0)`. | `SaldoInsuficiente` → web: error arriba con el saldo actual; API: 409 `SALDO_INSUFICIENTE` |
| RN-010-04 | **Cantidades enteras > 0**, hasta `CANTIDAD_MAXIMA` (la de `services/kits.py`), cada insumo una sola vez por operación, al menos una línea. | `ValidationError` en `lineas` |
| RN-010-05 | **Libro inmutable.** Cada operación (`OperacionStock`) deja uno o más movimientos (`MovimientoStock`) con el delta firmado y el saldo posterior. No se editan ni se borran: lo mal cargado se corrige con un ajuste. | El manager y `save()` levantan `ValidationError` (patrón `TrazaEntrega`) |
| RN-010-06 | **Ingreso por kit.** Recibir una `EntregaKit` de una institución con stock suma `cantidad_recibida` de cada línea con cantidad > 0 al saldo de (institución, `entrega.edificio`, ítem), en la misma transacción que la recepción. Lo enviado no suma; una reposición suma cuando se recibe; una línea en 0 no deja movimiento. Una entrega suma **una sola vez**: `OperacionStock.entrega_kit` es única y la recepción idempotente devuelve antes de sumar. | Sin esto el stock y el remito divergen; el UNIQUE corta una doble suma |
| RN-010-07 | **Edificio obligatorio en entregas de kits a instituciones con stock** (criterio a del PM). `crear_entrega` exige edificio activo cuando el destino lleva stock (con uno solo, queda fijo, como hoy); un destino con stock y sin edificios vinculados se rechaza. Una entrega que llegue sin edificio la recibe la guardia **eligiendo** el edificio (activo, vinculado, dentro de su alcance de `emergencia.recibir_kit`); la elección se guarda en `EntregaKit.edificio` en la misma transacción. | Web: error en el campo edificio; API: 400 `VALIDACION` con clave `edificio_id` |
| RN-010-08 | **Ingreso manual.** Insumos **activos**, origen obligatorio de un catálogo cerrado (Donación, Municipio, Compra, Otro programa, Otro), detalle de origen obligatorio con «Otro», número de comprobante opcional (texto ≤ 60). Sin fecha retroactiva: el momento es el de la carga (criterio b). | `ValidationError` por campo |
| RN-010-09 | **Entrega a persona.** DNI obligatorio y normalizado (`core.dni.normalizar_dni`). Persona = `buscar_ciudadano_por_dni`; si no hay legajo, Registro de Personas con sexo (`buscar_en_registro_de_personas`); si no responde o no la encuentra, alta mínima con nombre y apellido. El alta del legajo ocurre **dentro** de la transacción de la entrega (si la entrega falla, no queda legajo huérfano), con la tolerancia a la carrera por DNI de `ingreso._crear_legajo`. Persona fallecida: rechazo. Observación opcional (≤ 200). | Web: vuelve al paso de la persona con el motivo; API: 400 `VALIDACION` / `PERSONA_SIN_DATOS` |
| RN-010-10 | **Historial al entregar, sin límite automático** (criterio c). Se muestran las últimas 20 entregas a esa persona en toda la red: fecha, insumos y cantidades; la institución se nombra solo si es la misma desde la que se entrega; si no, «Otra institución». Nunca se bloquea una entrega por el historial. | — |
| RN-010-11 | **Traspaso.** Origen y destino son pares (institución, edificio) distintos, los dos con stock, con la institución destino `ACTIVO` y el edificio destino activo. Sale y entra en la misma operación (dos movimientos por insumo: `TRASPASO_SALIDA` y `TRASPASO_ENTRADA`). El destino tiene que estar dentro del alcance de `stock.ingresar` de quien lo hace (por defecto, ver §10). Es inmediato: el destino no confirma. | `ValidationError` en `destino`; saldo insuficiente → RN-010-03 |
| RN-010-12 | **Ajuste por conteo.** Se informa la **cantidad contada** de un insumo (absoluta) y el saldo que se vio al abrir; el sistema calcula el delta. Motivo obligatorio de un catálogo cerrado (Inventario inicial, Conteo periódico, Rotura o vencimiento, Pérdida o robo, Corrección de carga, Otro) y detalle obligatorio con «Otro» o «Corrección de carga». Si el saldo actual difiere del visto: rechazo. Contar lo mismo que hay: rechazo (no deja un movimiento en cero). Admite insumos inactivos con saldo. | Web: error en el modal; API: 409 `SALDO_CAMBIO` / 400 `VALIDACION` |
| RN-010-13 | **Capacidades** (módulo nuevo `dispositivos_stock` del `CATALOGO`, alcance programa, acotado a DISPOSITIVOS): `stock.ver`, `stock.entregar`, `stock.ingresar` (ingreso manual y traspasos), `stock.ajustar`. Se evalúan con `puede_operar_edificio(user, dispositivo, edificio_id, cap)`. Cada acción exige su capacidad **y** `stock.ver` sobre el mismo edificio; entregar exige además `ciudadano.ver` (como el ingreso de personas, `puede_ingresar_persona`). `dispositivo.ver_todos` amplía `stock.ver` a toda la red (se suma a `_CAPS_LECTURA_RED`), nunca las de operar. Recibir kits sigue siendo `emergencia.recibir_kit`: la suma al stock es consecuencia de la recepción y no pide capacidad de stock. | Web: 403 (sin la capacidad en ningún lado) o 404 (edificio fuera de alcance); API: §12 |
| RN-010-14 | **Estado de la institución y del edificio.** Ingreso manual, entrega a persona y entrada de traspaso exigen institución `ACTIVO` y edificio activo. Salida de traspaso y ajuste se permiten con la institución no activa (para vaciar lo que queda). | Mensaje «La institución no está activa: solo se puede traspasar o ajustar» |
| RN-010-15 | **Edificio con stock.** «Inactivar edificio» y «Desvincular edificio» se rechazan si alguna institución tiene saldo > 0 en ese edificio, junto con los otros motivos de bloqueo del Cambio 583 («Traspasá o ajustá el stock antes»). | Sin esto queda stock inoperable en un edificio que no se ofrece |
| RN-010-16 | **Dejar de llevar stock.** Destildar `maneja_stock` en un tipo se rechaza si alguna institución de ese tipo tiene saldo > 0. Con saldo 0 se permite; el libro queda y se sigue viendo en el historial de la persona. | Error en el formulario del tipo con la cantidad de instituciones afectadas |
| RN-010-17 | **Insumo desactivado** (`TipoKit.activo = False`). No se ofrece en el ingreso manual. Sí entra por recepción de kit (salió activo), y mientras tenga saldo se entrega, se traspasa y se ajusta; con saldo 0 no se muestra en la tabla de saldo. Un insumo con movimientos de stock no cambia de nombre ni de unidad (se extiende la regla de «usado en alguna entrega»). | — |
| RN-010-18 | **Idempotencia por `uuid_cliente`** (criterio d). Toda operación lleva un identificador que nace en el formulario (web, oculto) o en el teléfono (app). Reenviarlo **el mismo usuario** devuelve la operación ya hecha sin mover nada (`ya_existia`). Usado por otro usuario, o por una operación de otro tipo: rechazo `UUID_EN_USO`. Dos envíos a la vez los ordena el UNIQUE de la columna (patrón `crear_entrega`). | API: 200 con la misma operación, o 409 `UUID_EN_USO` |
| RN-010-19 | **Orden de candados** (único para todo el módulo): entrega de kits (si la hay) → `Dispositivo`(s) por pk → `Edificio`(s) por pk → `SaldoStock` por (dispositivo_id, edificio_id, item_id) ascendente → INSERT de operación y movimientos. Es compatible con `crear_entrega` (original → Dispositivo → Edificio → numerador), `recibir_entrega` (entrega → Dispositivo) e inactivar/desvincular edificio (Dispositivo → Edificio). Los saldos inexistentes se crean antes de bloquearlos con `bulk_create(ignore_conflicts=True)` (sin `get_or_create` bajo `FOR UPDATE`, que en InnoDB toma *gap locks* y se traba entre dos altas). Nunca `UniqueConstraint` condicional. | Interbloqueos; se prueba registrando los modelos bloqueados (patrón `OrdenDeCandadosTests`) y con `@tag("mysql")` |
| RN-010-20 | **Abastecimiento en E8** (criterio e). En las instituciones cuyo tipo lleva stock, cada fila muestra «Stock registrado» (Σ saldos de sus edificios por insumo) al lado de la estimación, rotulado así y nunca «estimado». El cálculo del faltante **no** cambia. En las demás, todo sigue rotulado «estimado». | — |
| RN-010-21 | **Sin edificio no se opera** (decisión 6). Una institución con stock y sin edificio activo vinculado muestra el aviso en su ficha y no ofrece operar; la API no la lista. | — |

---

## 6. Modelos y campos

Todos en `programas/models/__init__.py`, junto a los de kits. Migraciones solo *expand* (§13).

### 6.1 `TipoDispositivo.maneja_stock` (columna nueva)

`BooleanField(default=False, db_default=False, verbose_name="Lleva stock de insumos")`, con ayuda «Sus instituciones
llevan stock por edificio: lo recibido de la mesa, ingresos, entregas a personas, traspasos y ajustes». Mismo patrón que
`ubicacion_reservada` (`NOT NULL` con `DEFAULT` real en la base): el código viejo da de alta tipos sin conocerla.

### 6.2 `SaldoStock` (tabla nueva, hereda `TimeStamped`)

| Campo | Tipo | Notas |
|---|---|---|
| `dispositivo` | FK `Dispositivo`, `PROTECT`, `related_name="saldos_stock"` | |
| `edificio` | FK `Edificio`, `PROTECT`, `related_name="saldos_stock"` | |
| `item` | FK `TipoKit`, `PROTECT`, `related_name="saldos_stock"` | |
| `cantidad` | `PositiveIntegerField(default=0, db_default=0)` | |
| `ultimo_movimiento_en` | `DateTimeField(null=True)` | Para la tabla de saldo sin leer el libro |

`UniqueConstraint(dispositivo, edificio, item, name="saldo_stock_clave_unica")` y
`CheckConstraint(cantidad__gte=0, name="saldo_stock_no_negativo")` (MySQL ≥ 8.0.16 y MariaDB ≥ 10.2 la hacen cumplir).
Es la **fila que se bloquea**: sin ella, «nunca negativo» exigiría sumar el libro bajo un candado de otra tabla. Solo la
escribe `programas.services.stock` (con `update_fields`, sin `full_clean`).

### 6.3 `OperacionStock` (tabla nueva, inmutable)

Una fila por acción de una persona. No hereda `TimeStamped` (no se modifica).

| Campo | Tipo | Notas |
|---|---|---|
| `tipo` | `CharField(20)`, choices `INGRESO_KIT`, `INGRESO_MANUAL`, `ENTREGA_PERSONA`, `TRASPASO`, `AJUSTE` | |
| `dispositivo`, `edificio` | FK `PROTECT` | Donde ocurre; en un traspaso, el origen |
| `destino_dispositivo`, `destino_edificio` | FK `PROTECT`, `null=True` | Solo traspaso |
| `usuario` | FK `User`, `PROTECT` | Quien la hizo (en `INGRESO_KIT`, quien recibió) |
| `creado_en` | `DateTimeField(auto_now_add=True)` | Sin fecha retroactiva |
| `ciudadano` | FK `legajos.Ciudadano`, `PROTECT`, `null=True` | Solo entrega a persona |
| `entrega_kit` | FK `EntregaKit`, `PROTECT`, `null=True`, **`unique=True`** | Solo `INGRESO_KIT`; varios `NULL` admitidos en MySQL/MariaDB |
| `origen` | `CharField(20)`, choices, `blank=True`, `db_default=""` | Solo ingreso manual |
| `origen_detalle` | `CharField(120)`, `blank=True`, `db_default=""` | |
| `comprobante` | `CharField(60)`, `blank=True`, `db_default=""` | Número o referencia del comprobante |
| `motivo` | `CharField(20)`, choices, `blank=True`, `db_default=""` | Solo ajuste |
| `observacion` | `CharField(200)`, `blank=True`, `db_default=""` | Detalle del ajuste u observación de la entrega |
| `uuid_cliente` | `UUIDField(null=True, unique=True, editable=False)` | `char(36)` en MySQL/MariaDB (migración aparte, patrón `0136`); entra al ratchet de `test_becas_models` |

Índices: `(dispositivo, edificio, creado_en)` (historial del edificio), `(ciudadano, creado_en)` (historial de la
persona). No hay índice por `(tipo, creado_en)`: ninguna consulta prevista filtra por tipo sin edificio.

### 6.4 `MovimientoStock` (tabla nueva, inmutable)

| Campo | Tipo | Notas |
|---|---|---|
| `operacion` | FK `OperacionStock`, `PROTECT`, `related_name="movimientos"` | |
| `tipo` | `CharField(20)`: `INGRESO_KIT`, `INGRESO_MANUAL`, `ENTREGA_PERSONA`, `TRASPASO_SALIDA`, `TRASPASO_ENTRADA`, `AJUSTE` | El sentido del traspaso vive acá |
| `dispositivo`, `edificio`, `item` | FK `PROTECT` | La clave del saldo que movió |
| `cantidad` | `IntegerField` | Delta firmado; `CheckConstraint(~Q(cantidad=0))` |
| `saldo_posterior` | `PositiveIntegerField` | El saldo después de este movimiento (historial sin recalcular) |
| `creado_en` | `DateTimeField(auto_now_add=True)` | |

Índices: `movstock_clave_idx` `(dispositivo, edificio, item, creado_en)` (historial de un insumo) y `movstock_edificio_idx` `(dispositivo, edificio, creado_en)` (últimos movimientos del edificio y filtro por fechas).

La inmutabilidad de las dos tablas usa un `QuerySet`/`Manager` que levanta en `update`, `delete` y `bulk_update`, más
`save()`/`delete()` que rechazan una fila existente: la séptima copia del bloque de `TrazaEntrega`. Se escribe **una
vez** como mixin (`programas/models/inmutable.py` o al lado de los modelos) y la usan solo las dos tablas nuevas; migrar
las seis viejas queda para la auditoría (MINOR 10 del Cambio 471).

### 6.5 Invariantes

- Para cada clave, `SaldoStock.cantidad == Σ MovimientoStock.cantidad == saldo_posterior del último movimiento`.
  Selector `programas.selectors.stock.diferencias_de_saldo()` (una consulta agrupada) y test que lo verifica tras cada
  servicio.
- `OperacionStock` de tipo `TRASPASO` tiene, por insumo, una salida y una entrada de la misma cantidad absoluta.

### 6.6 Estados

No hay máquina de estados: una operación existe o no existe, y no cambia. La «corrección» es un ajuste nuevo. Lo único
con estado es lo que ya existía (`EntregaKit`, `Edificio.activo`, `Dispositivo.estado`).

---

## 7. Servicios, selectores y permisos

- **`programas/services/stock.py`** (toda regla vive acá; web y API llaman lo mismo): `lleva_stock(dispositivo)`,
  `puede_ver_stock` / `puede_entregar` / `puede_ingresar` / `puede_ajustar` (sobre `puede_operar_edificio`),
  `ingresar_manual`, `entregar_a_persona`, `traspasar`, `ajustar`, `sumar_recepcion_de_kit` (la llama
  `kits.recibir_entrega`, no una vista), `saldo_bloqueado(...)` (RN-010-19) y las excepciones `SaldoInsuficiente`
  (con `saldos_actuales`), `SaldoCambio`, `StockNoHabilitado`. Cada función exige su capacidad sin confiar en la vista y
  devuelve la operación con `ya_existia`.
- **`programas/services/stock_personas.py`**: `resolver_persona(dni, sexo, nombre, apellido)` sobre
  `ingreso.buscar_ciudadano_por_dni`, `buscar_en_registro_de_personas` y un `alta_desde_registro` público (hoy
  `_alta_desde_registro`); no duplica la lógica del ingreso.
- **`programas/selectors/stock.py`**: `saldos_de(dispositivo, edificio)`, `movimientos_de(..., filtros)`,
  `historial_de_persona(ciudadano, desde_dispositivo)`, `resumen_de_insumos_por_edificio(dispositivo, edificio_ids)` (la tarjeta
  y el botón de la solapa: una consulta agrupada, insumos y sin existencia), `stock_por_dispositivo_e_item(dispositivo_ids)` (E8: una consulta), `diferencias_de_saldo()`.
- **`programas/services/edificio_stock.py`**: arma la solapa (como `edificio_kits.py`).
- **RBAC.** `core/rbac.py`: módulo `dispositivos_stock` con las cuatro capacidades. `users.0053`: `AlterModelOptions` de
  `Capacidad` con la lista entera + siembra al «Administrador» protegido (patrón `users.0052`).
  `programas/services/roles_sembrados.py`: Administrador y Coordinador las cuatro; Operador/Guardia `ver` y `entregar`;
  Consulta y Supervisión de la red `ver`. `programas/services/dispositivos.py`: `stock.ver` en `_CAPS_LECTURA_RED`.

---

## 8. Pantallas (web)

Toda pantalla se declara con su *Plan de pantalla* antes de escribir (agente `chaco-design-system`). Si el plan trae una
clase, include, variante o valor nuevo, se frena y vuelve al juez.

| # | Pantalla | Arquetipo y golden que se clona | Dónde se cuelga |
|---|---|---|---|
| S1 | **Solapa «Stock»** de la página operativa del edificio: tabla de saldo (Insumo, Unidad, Hay, Último movimiento), acciones del panel («Entregar a persona», «Ingresar», «Traspasar»; «Ajustar» por fila) y los últimos 20 movimientos con «Ver todos» | Panel de solapa del **Detalle** (`becas/cupo/segmento_detail.html`, ficha `detalle.md`), tabla canónica (`tabla.md`), estado vacío (`estado_vacio.md`) | `SOLAPAS` de `edificio_operativo.py`: `("sectores", "estadias", "kits", "stock", "equipo", "edilicio", "historial")`; existe solo con `lleva_stock` y `stock.ver` sobre el edificio. Badge: «N insumos». Deep link `?tab=stock` |
| S2 | **Entregar a persona**: GET con DNI (y sexo si hace falta) que resuelve la persona sin escribir; con la persona, el POST con la tabla de una fila por insumo con saldo (columna «Hay» y la cantidad), observación, y el historial de la persona en el panel lateral | **Formulario** variante «Formulario de un destino con tabla de cantidades» (Cambio 586, evidencia `emergencia/kits/nueva.html`), con el destino = la persona. El historial va en un `aside` de la variante «asistencia lateral»: si el agente de diseño lo considera combinación nueva, se dibuja debajo como tercera surface con la tabla canónica | `dispositivos/<pk>/edificios/<e>/stock/entregar/`; botón del panel S1 y, con `stock.entregar`, ítem «Entregar insumos» de «Más acciones» de la página del edificio |
| S3 | **Ingreso manual**: origen, detalle, comprobante y tabla de una fila por insumo **activo** con la cantidad | **Formulario** variante «destino con tabla de cantidades» (sin GET de destino: el edificio es el de la URL) | `.../stock/ingresar/`; botón del panel S1 |
| S4 | **Traspaso**: GET de destino (select de pares institución · edificio permitidos) y POST con la tabla de insumos con saldo | **Formulario** variante «destino con tabla de cantidades», idéntica a «Nueva entrega» | `.../stock/traspasar/`; botón del panel S1 |
| S5 | **Ajustar** un insumo: cantidad contada, motivo, detalle; muestra «Hay N» | **Modal** con motivo (`becas/config/programa_list.html`, ficha `modal.md`) | ⋮ de cada fila del saldo en S1; POST a `.../stock/ajustar/` |
| S6 | **Movimientos del edificio**: tabla paginada con filtros (tipo, insumo, desde/hasta), columnas Fecha, Tipo, Insumo, Cantidad (+/−), Queda, Quién, Detalle (persona con `ciudadano.ver`, origen, destino del traspaso, motivo) | **Listado** (`becas/revision/personas_list.html`, ficha `listado.md`) | `.../stock/movimientos/`; «Ver todos» de S1 |
| S7 | **Fila «Stock» de la tarjeta del edificio** en la ficha de la institución: «N insumos · M sin existencia» o «Sin stock cargado» | Pieza canónica `components/_tarjeta_edificio.html` (clave nueva `stock`, mismo contrato que `kits`: `texto`, `clase`, `None` = sin fila) | `ficha_edificios.completar_tarjetas` con `alcance_stock`; la ficha `tarjeta_edificio.md` se actualiza en el mismo diff |
| S8 | **Aviso** de institución con stock sin edificio activo | `components/_alerta.html` (`alerta.md`), igual que los avisos de kits y derivaciones (Cambio 581) | Ficha de la institución (`legajo/detail.html`), arriba de «Edificios · N» |
| S9 | **Recepción de kits**: en una entrega sin edificio a una institución con stock, select «¿A qué edificio entró?»; y una línea informativa «Lo recibido se suma al stock del edificio» | Sin pieza nueva: campo canónico en el formulario de recepción existente (solapa Kits y `kits/recibir.html`) | Recepción actual (Cambio 586) |
| S10 | **Configuración del tipo**: checkbox «Lleva stock de insumos» | Campo canónico en `config/_tipo_form_fields.html` | Configuración → Tipos de dispositivo |
| S11 | **E8 → Abastecimiento**: columna «Stock registrado» en las filas de instituciones con stock; la nota de arriba aclara que ese número no es estimado | Tabla existente de `emergencia/situacion/_abastecimiento.html` | Situación de Emergencia |
| S12 | **E7 → Insumos**: el texto «No es stock: el sistema no lleva inventario ni descuenta al enviar» pasa a «La regla estima el consumo. Enviar no descuenta nada; el stock real se lleva solo en las instituciones cuyo tipo lo tiene activado» | Alerta existente | Configuración de la mesa |

No hay entrada nueva en el sidebar: el stock se opera desde el edificio (decisión del lote «el edificio como unidad
operativa»). Una vista de stock de toda la red queda fuera de alcance (§9).

Presupuestos de consultas (`scripts/perf_budgets.json`, `--tag performance`): clave nueva
`dispositivos_edificio_operativo_stock` (S1, medido con 1 y 30 insumos); S7 suma **una** consulta agrupada a
`dispositivos_detalle_con_edificios` solo cuando el tipo lleva stock y quien mira tiene `stock.ver`.

---

## 9. Fuera de alcance

- Depósito central o stock de la mesa de Emergencia: la mesa sigue sin stock; enviar no descuenta nada.
- Vista de stock consolidada de toda la red (fuera de E8) y exportación.
- Límites automáticos por persona o por familia, y alertas de stock mínimo.
- Anular una operación: lo mal cargado se corrige con un ajuste (§10).
- Foto del comprobante del ingreso manual (solo número/referencia, §10).
- Carga retroactiva con fecha (criterio b).
- Escrituras de stock sin conexión en la app (§10).
- Cambiar el cálculo del faltante de E8 con el stock real.

---

## 10. Preguntas abiertas (todas con propuesta por defecto; el juez las da por cerradas si el PM no dice otra cosa)

| # | Pregunta | Propuesta por defecto | Estado |
|---|---|---|---|
| 1 | ¿A qué destinos se puede traspasar? | Solo a pares (institución, edificio) dentro del alcance de `stock.ingresar` de quien traspasa; el admin del programa, a cualquiera | Abierta |
| 2 | ¿El traspaso lo confirma el destino? | No: es inmediato y queda en el libro de los dos edificios | Abierta |
| 3 | ¿Se puede anular una entrega a persona cargada por error? | No en este lote: ajuste con motivo «Corrección de carga» y detalle; el historial de la persona conserva la entrega | Abierta |
| 4 | Comprobante del ingreso manual | Número/referencia de texto; sin foto (la foto exige ruta de `media/` y regla de acceso nuevas) | Abierta |
| 5 | Catálogos de origen y de motivo de ajuste | Los de RN-010-08 y RN-010-12 | Abierta |
| 6 | Qué roles sembrados reciben qué | Admin y Coordinador: las cuatro; Guardia: ver y entregar; Consulta y Supervisión de la red: ver | Abierta |
| 7 | ¿La migración tilda las capacidades en los roles ya creados en ECOM? | Solo en el «Administrador» protegido (patrón `users.0052`); el resto lo tilda el PM en Roles (paso de puesta en marcha) | Abierta |
| 8 | Destildar «Lleva stock» con saldo > 0 | Se rechaza (RN-010-16) | Abierta |
| 9 | Inactivar o desvincular un edificio con saldo > 0 | Se rechaza (RN-010-15) | Abierta |
| 10 | ¿La app guarda entregas sin conexión? | No: las escrituras de stock son con conexión (como recibir kits); el `uuid_cliente` cubre los reintentos por red inestable | Abierta |
| 11 | Historial de la persona | Últimas 20 entregas de toda la red; otra institución sin nombre («Otra institución») | Abierta |
| 12 | ¿`dispositivo.ver_todos` ve el stock de la red? | Sí, si su rol tiene además `stock.ver` (solo lectura) | Abierta |
| 13 | Mesa que envía kits a una institución con stock sin edificios | Se rechaza el envío con «Vinculá un edificio a la institución antes de enviarle kits» (decisión 6 + criterio a) | Abierta |
| 14 | Entrega vieja sin edificio a una institución sin edificio activo | No se puede recibir hasta vincular uno (decisión 6) | Abierta |
| 15 | Ajuste por delta o por conteo | Por conteo (cantidad absoluta), con control del saldo visto | Abierta |

---

## 11. Casos límite y excepciones

| Caso | Comportamiento esperado |
|---|---|
| Dos guardias entregan el último colchón a la vez | Las dos toman el candado del saldo en orden; la segunda lee 0 y recibe `SaldoInsuficiente` / 409 con el saldo actual. Probado con dos conexiones (`@tag("mysql")`) y, en SQLite, con el registro del orden de candados |
| Recepción de kit y entrega a persona a la vez sobre el mismo ítem | Mismo orden (Dispositivo → Edificio → Saldo): se serializan; el saldo final es la suma exacta |
| Traspaso A→B y B→A simultáneos | Candados por pk ascendente de dispositivos, edificios y saldos: sin ciclo |
| Doble clic / reenvío de la app | Mismo `uuid_cliente` y usuario → la misma operación, `ya_existia = True`, sin movimientos nuevos |
| Mismo `uuid_cliente` de otro usuario o de otra acción | 409 `UUID_EN_USO` |
| Edificio compartido por dos instituciones con stock | Saldos separados por institución; la solapa de cada una muestra solo el suyo; traspaso entre ellas permitido si quien lo hace alcanza las dos |
| Guardia con alcance Edificios | Ve y opera solo sus edificios; un edificio ajeno da 404 con el mismo cuerpo que uno inexistente |
| Institución que deja de llevar stock (con saldo 0) | Desaparecen la solapa, la fila y la API; el libro queda; el historial de la persona sigue mostrando sus entregas |
| Institución no `ACTIVO` | Solo traspaso de salida y ajuste (RN-010-14) |
| Edificio inactivado (sin saldo) | No se ofrece como destino de traspasos ni de kits; la solapa del edificio inactivo muestra el saldo (0) y el historial, sin acciones |
| `TipoKit` desactivado con saldo | Sigue en la tabla y se entrega, traspasa y ajusta; no aparece en el ingreso manual |
| Persona sin RENAPER (no figura o servicio caído) | Alta mínima con nombre y apellido, `estado_renaper` vacío; API 400 `PERSONA_SIN_DATOS` si faltan |
| Persona fallecida según el Registro | No se entrega: «La persona figura fallecida en el Registro de Personas» |
| DNI con separadores en el legajo | `buscar_ciudadano_por_dni` lo encuentra (misma regla que el ingreso) |
| Recepción con cantidad recibida 0 en una línea | No deja movimiento para esa línea |
| Recepción de más (recibido > enviado) | Suma lo recibido: el stock es lo que entró |
| Reposición de una diferencia | Suma cuando se recibe, como cualquier entrega |
| Entrega de kits cancelada | No sumó nunca (solo se suma al recibir) |
| Cantidad enorme o no entera | `ValidationError` (RN-010-04) |
| Ajuste a la misma cantidad | Rechazo: «Contaste lo mismo que hay; no hay nada que ajustar» |
| Persona con muchas entregas | Historial acotado a 20, sin bloqueo (criterio c) |
| Historial con entregas en una institución de ubicación reservada | «Otra institución», sin nombre ni localidad (RNF-010-07) |

---

## 12. API para la app (contrato, va como §17 de `contrato-app-emergencia.md`)

Base `/api/emergencia/`, mismo token y mismos códigos que el resto (§2 del contrato). Todas con `Cache-Control: no-store`.

### 12.1 Permiso nuevo «stock» y perfil

| Permiso | Regla | 403 |
|---|---|---|
| **Stock** | Abre el módulo **y** tiene `stock.ver` con alcance en alguna institución cuyo tipo lleva stock (Equipo o admin del programa) | `{"detail": "El usuario no lleva stock en ningún dispositivo. …", "code": "SIN_MODULO"}` |

- `GET perfil/` suma `"stock": bool` (aditiva, como `plazas`).
- `modulo_habilitado` / `_es_de_la_guardia` suman a quien integra el Equipo con `stock.ver`: el login empieza a traer
  `"emergencia"` para un usuario que **solo** lleva stock (cambio aditivo del §1).

### 12.2 Extremos

| Método y ruta | Permiso | Para qué |
|---|---|---|
| `GET stock/` | stock | Los pares (institución, edificio) con stock en su alcance: `[{dispositivo:{id,nombre}, edificio:{id,nombre}, insumos_con_saldo, puede:{entregar, ingresar, ajustar}}]` |
| `GET dispositivos/{d}/edificios/{e}/stock/` | stock | Saldo: `{dispositivo, edificio, puede, saldos:[{item_id, nombre, unidad, cantidad, activo}], insumos_activos:[{item_id, nombre, unidad}]}` |
| `GET dispositivos/{d}/edificios/{e}/stock/movimientos/?tipo=&item=&cursor=` | stock | Libro, de a 50, más nuevo primero: `{resultados:[{id, tipo, item_id, nombre, unidad, cantidad, saldo_posterior, creado_en, usuario, detalle}], siguiente}` |
| `GET dispositivos/{d}/edificios/{e}/stock/persona/?dni=` | `stock.entregar` + `ciudadano.ver` | `{persona:{dni, nombre, apellido} \| null, historial:[{creado_en, institucion, lineas:[{nombre, unidad, cantidad}]}]}`; descuenta de la cubeta `personas_campo` (consulta de identidad) |
| `POST dispositivos/{d}/edificios/{e}/stock/entregas/` | `stock.entregar` + `ciudadano.ver` | `{uuid_cliente, dni, sexo?, nombre?, apellido?, lineas:[{item_id, cantidad}], observacion?}` |
| `POST dispositivos/{d}/edificios/{e}/stock/ingresos/` | `stock.ingresar` | `{uuid_cliente, origen, origen_detalle?, comprobante?, lineas:[…], observacion?}` |
| `GET dispositivos/{d}/edificios/{e}/stock/destinos-traspaso/` | `stock.ingresar` | `[{dispositivo:{id,nombre}, edificio:{id,nombre}}]` |
| `POST dispositivos/{d}/edificios/{e}/stock/traspasos/` | `stock.ingresar` | `{uuid_cliente, destino_dispositivo_id, destino_edificio_id, lineas:[…], observacion?}` |
| `POST dispositivos/{d}/edificios/{e}/stock/ajustes/` | `stock.ajustar` | `{uuid_cliente, item_id, cantidad_contada, saldo_visto, motivo, observacion?}` |
| `POST entregas/{id}/recibir/` (existente, §12) | kits | Campo nuevo **opcional** `edificio_id`; `GET dispositivos/{id}/entregas/` suma por entrega `requiere_edificio` y `edificios:[{id,nombre}]` |

Respuesta de toda escritura: **201** `{"operacion": {id, tipo, creado_en, lineas:[{item_id, nombre, unidad, cantidad, saldo_posterior}]}, "saldos": [...], "ya_existia": false}`;
el reenvío con el mismo `uuid_cliente` devuelve **200** con la misma operación y `"ya_existia": true`. El cuerpo del
reenvío se valida en su forma (como en §12 de kits; corregir el texto del §12 que dice «no importa qué traiga», MINOR 6 del
Cambio 471).

### 12.3 Errores

| HTTP | `code` | Cuándo | Qué hace la app |
|---|---|---|---|
| 403 | `SIN_MODULO` | Sin el permiso «stock» en ningún lado | Mostrar `detail`; no reintentar |
| 403 | `SIN_PERMISO` | Ve el edificio pero no tiene la capacidad de la acción (o `ciudadano.ver` para entregar) | Mostrar `detail`; no ofrecer la acción |
| 404 | — | Institución o edificio inexistente, no vinculados entre sí, o fuera del alcance de `stock.ver`; ítem inexistente | Recargar `stock/` |
| 409 | `STOCK_NO_HABILITADO` | El tipo dejó de llevar stock, o la institución no está activa / el edificio está inactivo para esa acción (RN-010-14) | Mostrar `detail`; recargar `stock/` |
| 409 | `SALDO_INSUFICIENTE` | Una línea pide más de lo que hay; trae `saldos:[{item_id, cantidad}]` actuales | Mostrar y dejar corregir; reenviar con **otro** `uuid_cliente` |
| 409 | `SALDO_CAMBIO` | Ajuste con `saldo_visto` distinto del actual; trae `cantidad_actual` | Volver a contar |
| 409 | `UUID_EN_USO` | El identificador ya es de otro usuario u otra acción | Regenerar el identificador una vez |
| 400 | `VALIDACION` | Campos inválidos (forma de la API de campo: `code`, `detail`, una clave por campo, `non_field_errors`) | Corregir y reenviar con el **mismo** `uuid_cliente` |
| 400 | `PERSONA_SIN_DATOS` | Sin legajo y sin datos del Registro: faltan `nombre` y `apellido` (o `sexo` para consultar) | Pedirlos y reenviar con el mismo `uuid_cliente` |
| 429 | — | Tope de consultas de identidad (`personas_campo`) | Esperar `Retry-After` |

Las claves de cada respuesta se fijan con igualdad exacta en `programas/tests/base_emergencia_api.py` (`CLAVES_STOCK_*`)
y el barrido de rutas de `test_emergencia_api_contrato.py` suma las nuevas.

---

## 13. Base de datos y despliegue

- `programas.0144_stock` (expand): `AddField TipoDispositivo.maneja_stock` (`db_default=False`) y `CreateModel` de
  `SaldoStock`, `OperacionStock`, `MovimientoStock`, con sus `UniqueConstraint`, `CheckConstraint` e índices.
- `programas.0145_stock_uuid_char36` (`atomic = False`, `modificar_columna` a `char(36)`, reversa que normaliza a hex,
  patrón `0136`).
- `users.0053_capacidades_stock`: `AlterModelOptions` de `Capacidad` + siembra al Administrador, reversa real.
- Ninguna columna se borra ni cambia de tipo en tablas existentes. Rollback de la release: el código viejo ignora las
  tablas nuevas y da de alta tipos con el `DEFAULT` de `maneja_stock`.
- Puesta en marcha: tildar las capacidades en los roles de ECOM desde Roles (o correr la siembra de roles si el PM la
  extiende) y activar «Lleva stock» en los tipos que correspondan. Cargar el inventario inicial con ajustes.

---

## 14. Qué se revierte de decisiones anteriores

| Decisión vigente | Dónde | Queda así |
|---|---|---|
| **RN-4.6** «Una entrega, una recepción; sin stock: las cantidades son lo que dice el remito» (Cambio 471, decisión 1) | `services/kits.py` (docstring del módulo y de `recibir_entrega`), `EntregaKit` (docstring), `docs/internal/analisis/009` | «Una entrega, una recepción. La entrega sigue siendo un remito (enviado / recibido / diferencia no cambian). **En las instituciones cuyo tipo lleva stock, la recepción suma lo recibido al stock del edificio de la entrega en la misma transacción** (RN-010-06). La mesa no tiene stock ni depósitos: enviar no descuenta nada.» |
| **RN-4.6 en `crear_entrega`** «un destino sin edificios vinculados la deja sin edificio» | `services/kits.py:_edificio_de_la_entrega` | Sigue igual para destinos sin stock; con stock, edificio obligatorio (RN-010-07) |
| **RNF-009-13** «Todo número de Abastecimiento se rotula estimado; ninguna etiqueta dice stock, inventario ni hay» | `docs/internal/analisis/009` §3.9 y §4, `services/abastecimiento_emergencia.py`, `pantalla_abastecimiento_emergencia.py` | «Todo número **calculado** se rotula estimado. En las instituciones cuyo tipo lleva stock se muestra además el **stock registrado**, rotulado así; el faltante sigue siendo estimado» (RN-010-20) |
| Texto de E7 «No es stock: el sistema no lleva inventario ni descuenta al enviar» (Cambio 574) | `emergencia/configuracion.html` | S12 |
| `TipoKit.regla_cantidad` «No es stock» (Cambio 574) | `models` | Se mantiene: la regla de consumo sigue sin ser stock |
| Auditoría perf nov-2026 «no hay stock (RN-4.6)» | `docs/internal/auditoria-2026-11-perf/emergencia.md` | Nota al pie que remite a este análisis; no se reescribe el informe |

Cada PR que toque esos textos lo registra en su Cambio; el que cambia `recibir_entrega` registra la reversión de RN-4.6.

---

## 15. Dependencias

- Cambios 523 (edificio de la entrega), 570/572 (ficha y tarjeta), 574/581/583 (avisos, inactivar edificio), 586
  (recepción en la solapa Kits), 596-598 (patrón de la API de plazas).
- `programas.services.ingreso` (persona por DNI y alta) y `CiudadanosService.consultar_renaper`.
- App `Chaco-mobile` (repo `I-CORE-TEC/Chaco-mobile`), rama base `test`, después de que entren `claude/plazas-lectura`
  y `claude/plazas-acciones`.

---

## 16. Criterios de aceptación

- [ ] Dado un tipo con «Lleva stock», cuando la guardia recibe una entrega de 10 colchones de los que llegaron 8, entonces
  el saldo de colchones del edificio de la entrega sube 8 y el libro muestra «Ingreso por kit 2026-K-…».
- [ ] Dado un saldo de 1 colchón, cuando dos guardias entregan 1 a la vez, entonces una entrega se registra y la otra se
  rechaza con «Hay 0»; el saldo queda en 0.
- [ ] Dado un DNI sin legajo que el Registro encuentra, cuando se confirma la entrega, entonces se crea el legajo y la
  entrega en la misma transacción; si la entrega falla, no queda el legajo.
- [ ] Dado un usuario con `stock.ver` y sin `stock.entregar`, cuando abre la solapa, entonces no ve «Entregar a persona»
  y el POST directo responde 403.
- [ ] Dado un guardia con alcance sobre el edificio A, cuando pide el stock del edificio B de la misma institución, entonces
  recibe 404.
- [ ] Dado un ajuste abierto con «Hay 5», cuando otra guardia entrega 1 antes de confirmar, entonces el ajuste se rechaza
  con «El saldo cambió».
- [ ] Dado el mismo `uuid_cliente` reenviado por la app, entonces la respuesta es 200 con la misma operación y el saldo no
  cambia.
- [ ] Dado un edificio con saldo > 0, cuando se intenta inactivarlo, entonces se rechaza con el motivo del stock.
- [ ] Dada una institución con stock en E8, entonces su fila de Abastecimiento muestra «Stock registrado» junto a la
  estimación; una sin stock no muestra esa columna con valor.

---

## 17. Historial de cambios del análisis

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-25 | Versión inicial | Decisiones del PM del 25/11/2026 y plan del juez |
