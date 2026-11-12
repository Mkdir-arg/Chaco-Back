# Emergencia · Etapa 2 — Tomar y derivar (la mesa de operaciones)

Reglas de rol: `00-reglas-de-usuario.md`. Etapa anterior: `01-relevar.md`.
Mockups: `E2` (bandeja), `E3` (ficha + panel derivar), `E3-modal` (cerrar sin
alojamiento), `E3-alojada` (cómo queda después de la etapa 3).

## 1. Objetivo

Que la mesa vea cada familia relevada en cuanto llega, la tome una sola persona, decida
a qué dispositivo va con datos reales de plazas y distancia, y que cada minuto de demora
quede medido contra un objetivo.

Resultado: el caso pasa `NUEVO → EN_GESTION → DERIVADO` con una `Derivacion`
`PENDIENTE` que el dispositivo va a aceptar en la etapa 3, o se cierra sin alojamiento.

## 2. Actores

| Rol | Pantallas | Capacidad |
|---|---|---|
| Operador de mesa | E2, E3 | `emergencia.operar` |
| Supervisor de mesa | E2, E3 (sin tomar), reasignar | `emergencia.supervisar` |

## 3. Pantallas

### E2 · Bandeja de casos (arquetipo listado, golden lista)

- Encabezado del programa «Emergencia · Casos» con botón «Nuevo caso» (HU-1.4).
- Solapas con conteo: **Abiertos** (todo menos cerrados) · Nuevos · En gestión · Derivados ·
  Ingreso en curso · **Fuera de SLA** · Ingreso directo · Cerrados.
- Filtros: estado, prioridad, localidad, operador («Míos»), SLA (en término / por vencer /
  fuera), texto libre (N.° de caso, DNI o apellido del responsable).
- Columnas: Familia (apellido responsable · N personas · N.° de caso) · Localidad ·
  Prioridad (chip) · Estado (chip) · Tomado por · **Tiempo en estado** (semáforo texto +
  color) · Acción («Tomar» si `NUEVO`; «Abrir» si no).
- Orden por defecto: fuera de SLA primero, después por prioridad, después más viejo
  primero.
- Marcas en la fila: «Posible duplicado», «Ingreso parcial», «Ingreso directo», «Relevado
  14:20 · enviado 16:05», «Ubicación aproximada».
- Paginado a 50; sin `TruncDate`; el conteo de solapas sale de una sola consulta
  agregada por estado y el «fuera de SLA» se calcula en Python sobre los abiertos (que
  son cientos, no miles).

### E3 · Ficha del caso + Derivar (arquetipo detalle con `split`)

Arriba: N.° de caso, familia, prioridad (editable si RU-12), estado, **reloj del tramo**
(«Derivar vence en 8 min» / «Fuera de SLA · 42 min»), botones según estado (§5).

Izquierda:
1. Lo que cargó territorio: traslado, responsable (nombre, DNI, teléfono, edad), dirección,
   localidad, GPS con precisión y link al mapa, relevado por / cuándo, origen.
2. Personas: tabla del paso 2, dependientes, mayores dependientes, lactantes, flags.
3. Integrantes: vacío con «Se completa cuando el dispositivo confirma las fichas»; en
   etapa 3 se llena.
4. Fotos (miniaturas, abren en modal).
5. Contactos con la familia: lista + formulario inline (canal, resultado, observación).
6. Traza (TrazaCaso, más reciente arriba).

Derecha (solo cuando el caso está `EN_GESTION` y lo tengo tomado o soy supervisor):
- Panel «Derivar»: plazas a reservar (prellenado con `total_declarado`, editable ≥ 1).
- Lista de dispositivos (`dispositivos_para_derivar`, RU-14): nombre, localidad, plazas
  libres / reservadas, distancia en km, marca **Alcanza / Faltan N plazas / Sin plazas**.
  Orden: alcanza primero, después por distancia. Filtro por localidad y texto.
- Botón «Derivar a <dispositivo>» (deshabilitado con «Sin plazas»; con «Faltan N» pide
  confirmación «Vas a reservar 5 de 7 plazas. ¿Seguís?»).

Cuando está `DERIVADO`: la derecha muestra la derivación vigente (dispositivo, plazas,
derivada por, vence a las HH:MM, «esperando aceptación») y «Cancelar derivación» (motivo).

### E3-modal · Cerrar sin alojamiento

Motivo (select obligatorio): No requiere alojamiento · Sin contacto con la familia ·
Asistido en domicilio · Se alojó por su cuenta · Otro (texto). Observación opcional.

## 4. Historias de usuario y criterios de aceptación

**HU-2.1** Como operador quiero tomar un caso para que nadie más lo trabaje al mismo
tiempo.
- Dado un caso `NUEVO`, cuando toco «Tomar», entonces pasa a `EN_GESTION`, `tomado_por` =
  yo, `tomado_en` = ahora, y la fila muestra mi nombre.
- Dado que otro operador lo tomó un segundo antes, cuando toco «Tomar», entonces veo
  «Tomado por Ana López hace 0 min» y nada cambia (RN-2.1).

**HU-2.2** Como operador quiero ver qué dispositivo tiene lugar y queda cerca.
- Dado un caso con GPS, cuando abro E3, entonces la lista muestra solo dispositivos
  `ACTIVO` con `tipo.maneja_camas`, con distancia desde el caso y plazas libres reales.
- Dado un dispositivo con 5 libres y un caso de 7, cuando lo miro, entonces veo «Faltan 2
  plazas» y puedo derivar igual con confirmación.
- Dado un dispositivo con 0 libres, cuando lo miro, entonces «Sin plazas» y el botón está
  deshabilitado.

**HU-2.3** Como operador quiero derivar y que el dispositivo lo vea de inmediato.
- Dado un caso `EN_GESTION` tomado por mí, cuando derivo, entonces el caso pasa a
  `DERIVADO`, se crea `Derivacion` `PENDIENTE` con `vence_en` = ahora + vigencia (E7), y
  en M2/E6 del dispositivo la búsqueda por DNI del responsable la encuentra.
- Dado una derivación `PENDIENTE`, cuando el operador la cancela con motivo, entonces pasa
  a `CANCELADA` y el caso vuelve a `EN_GESTION` con el mismo `tomado_por`.

**HU-2.4** Como operador quiero registrar que hablé con la familia.
- Dado un caso tomado por mí, cuando registro un contacto, entonces queda en la lista con
  canal, resultado, hora y mi nombre, y en la traza.

**HU-2.5** Como supervisor quiero que un caso abandonado vuelva a la bandeja.
- Dado un caso `EN_GESTION` sin ninguna acción (traza) en N minutos (E7, «minutos sin
  avance»), cuando corre `procesar_vencimientos`, entonces vuelve a `NUEVO` con
  `tomado_por = NULL` y traza «Devuelto a bandeja por inactividad (Ana López)».
- Dado un caso `DERIVADO` cuya derivación venció sin respuesta, cuando corre el cron,
  entonces la derivación pasa a `VENCIDA`, el caso a `EN_GESTION` (mismo operador), y la
  bandeja lo muestra en «Fuera de SLA» con «Derivación vencida · volver a derivar».

**HU-2.6** Como supervisor quiero reasignar un caso.
- Dado cualquier caso abierto, cuando elijo otro operador, entonces `tomado_por` cambia,
  la traza dice «Reasignado de Ana a Juan por Supervisor» y el reloj del tramo **no** se
  reinicia (RN-2.9).

**HU-2.7** Como operador quiero cerrar un caso que no necesita alojamiento.
- Dado un caso `EN_GESTION` (o `DERIVADO` con la derivación cancelada), cuando cierro con
  motivo, entonces pasa a `CERRADO`, `cerrado_en` = ahora, y aparece en la solapa Cerrados
  con el motivo.

## 5. Transiciones y botones

| Estado actual | Acción | Quién | Estado nuevo | Efectos |
|---|---|---|---|---|
| `NUEVO` | Tomar | operar | `EN_GESTION` | `tomado_por`, `tomado_en`; traza |
| `EN_GESTION` | Soltar | dueño o supervisar | `NUEVO` | `tomado_por = NULL`; `tomado_en` se conserva (RN-2.9); traza |
| `EN_GESTION` | Derivar | dueño o supervisar | `DERIVADO` | `Derivacion` `PENDIENTE`, `derivado_en`; traza |
| `EN_GESTION` | Cerrar sin alojamiento | dueño o supervisar | `CERRADO` | `cerrado_en`, motivo; traza |
| `DERIVADO` | Cancelar derivación | dueño o supervisar | `EN_GESTION` | `Derivacion` `CANCELADA`; traza |
| `DERIVADO` | (dispositivo rechaza) | etapa 3 | `EN_GESTION` | `RECHAZADA` con motivo; aviso en bandeja |
| `DERIVADO` | (vence) | cron | `EN_GESTION` | `VENCIDA`; aviso en bandeja |
| `DERIVADO` | (dispositivo acepta) | etapa 3 | `INGRESO_EN_CURSO` | ver `03-alojar.md` |
| cualquiera abierto | Reasignar / cambiar prioridad / contacto | según RU §4 | igual | traza |

Un caso `DERIVADO` **no** se puede cerrar sin antes cancelar la derivación (RN-2.6).

## 6. Reglas de negocio

- **RN-2.1** Tomar = `SELECT … FOR UPDATE` sobre la fila del caso + chequeo `estado ==
  NUEVO and tomado_por is NULL` dentro de la transacción. Perdedor → excepción de dominio
  `CasoTomadoPorOtro` → mensaje RU-20.
- **RN-2.2** Elegibles para derivar: `Dispositivo.estado == ACTIVO` y
  `tipo.maneja_camas == True` y `tipo.activo`. Si el PM decide «solo Centro de
  evacuados» (decisión 5 del README), se agrega `tipo.codigo in (…)` en un solo lugar
  (`selectors/emergencia.py`).
- **RN-2.3** Plazas libres = plazas `CAMA` `OPERATIVA` del dispositivo sin `Estadia`
  abierta ni `ReservaPlaza` `VIGENTE` (misma cuenta que `services/ocupacion.py`; no
  reimplementar). Reservadas = `ReservaPlaza` `VIGENTE`.
- **RN-2.4** Distancia: haversine en Python entre lat/long del caso y del dispositivo;
  si el caso no tiene GPS, desde el centroide de su localidad; si el dispositivo no tiene
  coordenadas, «distancia desconocida» al final de la lista.
- **RN-2.5** Derivar con menos plazas que `total_declarado` es válido con confirmación;
  `plazas_pedidas` guarda lo pedido. Derivar con 0 libres no es válido (400).
- **RN-2.6** Un caso tiene **a lo sumo una** derivación `PENDIENTE` o `ACEPTADA`:
  columna `clave_vigente` = `caso_id` cuando está vigente, `NULL` cuando no, con
  `UniqueConstraint(fields=["clave_vigente"])` simple (patrón `Estadia.clave_alojamiento`).
  Nunca `UniqueConstraint(condition=…)` (MySQL/MariaDB la ignoran).
- **RN-2.7** `vence_en` = `derivado_en` + `SLAEmergencia.vigencia_derivacion_min`
  (default 720 = 12 h). La regla de vencimiento se registra en
  `programas/services/vencimientos_emergencia.py` con `core.services.vencimientos.registrar`
  y filtra `estado == PENDIENTE and vence_en <= now` (idempotente).
- **RN-2.8** Devolución a bandeja por inactividad: regla de vencimiento sobre casos
  `EN_GESTION` cuya última `TrazaCaso` es anterior a `now - sin_avance_min` (E7, default
  60). Se apaga con `sin_avance_min = 0`.
- **RN-2.9** Las marcas de tiempo del SLA se escriben **una sola vez** (la primera vez
  que el caso entra al estado). Soltar, reasignar o volver de una derivación vencida no
  las borra: el tramo sigue corriendo desde la primera vez. Es la decisión que hace que el
  SLA mida a la familia y no al operador.
- **RN-2.10** Tramos del SLA (E7, minutos): **tomar** = `tomado_en − creado_en`,
  **derivar** = `derivado_en − tomado_en`, **aceptar** = `aceptado_en − derivado_en`,
  **alojar** = `alojado_en − aceptado_en`. Un caso está «fuera de SLA» si su tramo
  **actual** (el que todavía no cerró) superó el objetivo; «por vencer» si pasó el 80 %.
  Defaults de los mockups: 15 / 30 / 120 / 60.
- **RN-2.11** Cambiar prioridad deja traza con valor anterior y nuevo. La prioridad no
  afecta ninguna regla automática: solo el orden de la bandeja.
- **RN-2.12** `ContactoCaso`: canal (LLAMADA / WHATSAPP / SMS / PRESENCIAL), resultado
  (ATENDIO / NO_ATENDIO / NUMERO_ERRONEO / OTRO), observación, `por`, `momento`. Sin
  envío automático (RU-21).
- **RN-2.13** Cerrar sin alojamiento: motivo obligatorio del select; `CERRADO` es
  terminal (no se reabre; si hace falta, se crea otro caso y la traza del nuevo enlaza al
  viejo).
- **RN-2.14** Marca «Posible duplicado»: otro caso abierto con el mismo
  `grupo.responsable` o con un `IntegranteGrupo.ciudadano` igual. Es informativa; la mesa
  decide (cerrar uno con motivo «Duplicado de N.° X»).
- **RN-2.15** Marca «Responsable alojado en X»: el responsable tiene una `Estadia` abierta
  en la red (`verificar_alojamiento_en_red`). No bloquea derivar, pero el dispositivo no
  va a poder confirmarle una cama hasta que lo egresen de X (regla de Dispositivos: una
  estadía abierta por persona).

## 7. Datos

| Tabla | Operación | Campos |
|---|---|---|
| `CasoEmergencia` | update | estado, tomado_por, tomado_en, derivado_en, cerrado_en, prioridad, motivo_cierre |
| `Derivacion` | insert / update | caso, dispositivo, estado, plazas_pedidas, vence_en, derivada_por, respondida_por, motivo, clave_vigente |
| `ContactoCaso` | insert | caso, canal, resultado, observacion, por, momento |
| `TrazaCaso` | insert | en cada acción |
| `SLAEmergencia` | read | objetivos, vigencia, sin_avance_min |

Al derivar **no** se reservan plazas todavía: la reserva la hace el dispositivo al aceptar
(etapa 3), porque es él quien elige qué camas. La mesa solo ve «reservadas» las de
derivaciones ya aceptadas.

## 8. Servicios (`programas/services/emergencia.py`)

```
tomar_caso(caso, usuario)                      -> caso        # RN-2.1
soltar_caso(caso, usuario)                     -> caso
reasignar_caso(caso, usuario, operador)        -> caso        # supervisar
cambiar_prioridad(caso, usuario, prioridad)    -> caso
registrar_contacto(caso, usuario, **datos)     -> ContactoCaso
derivar_caso(caso, usuario, dispositivo, plazas_pedidas, confirmar_faltantes=False) -> Derivacion
cancelar_derivacion(derivacion, usuario, motivo) -> Derivacion
cerrar_sin_alojamiento(caso, usuario, motivo, observacion="") -> caso
```

Selectores (`programas/selectors/emergencia.py`): `bandeja(filtros)`,
`dispositivos_para_derivar(caso)`, `estado_sla(caso, sla)` → `("EN_TERMINO" |
"POR_VENCER" | "FUERA", minutos, tramo)`.

Vistas (`programas/views/emergencia.py`): `BandejaCasosView`, `CasoDetalleView`,
`TomarCasoView`, `DerivarCasoView`, … Cada una `@requiere("emergencia.operar")` y las de
supervisor `@requiere("emergencia.supervisar")`. Sin lógica de dominio en la vista.

## 9. Casos borde

- Dos pestañas abiertas del mismo operador: la segunda intenta derivar un caso ya
  derivado → 409 «El caso ya fue derivado a X a las 14:22. Recargá la ficha».
- El dispositivo elegido pasa a `INACTIVO` después de derivar → la derivación sigue
  `PENDIENTE`; la bandeja marca «Dispositivo inactivo · volver a derivar»; el cron la
  vence normalmente.
- Caso sin GPS ni localidad con coordenadas → lista sin distancia, ordenada solo por
  plazas.
- Cambian los objetivos del SLA en E7 → el semáforo se recalcula con los nuevos valores
  para todos los casos abiertos (no se congela por caso).

## 10. Criterio de terminado

- [ ] Tests de servicio: RN-2.1 (concurrencia con dos conexiones, `TransactionTestCase`),
  2.2, 2.5, 2.6 (segunda derivación vigente → `IntegrityError` capturado), 2.7 y 2.8
  (reglas de vencimiento idempotentes), 2.9, 2.10 (tabla de estados del semáforo).
- [ ] Test de mutación RU §6 n.° 1 y 4.
- [ ] Migración de `Derivacion` con `clave_vigente` anulable + unique simple; verificado
  con `check_migraciones.py` y el job de ida y vuelta contra MariaDB.
- [ ] E2 y E3 clonadas de sus goldens; `design_audit.py --ratchet` en 0 nuevos; fichas
  nuevas en `.claude/design/` para: semáforo de SLA, tarjeta de dispositivo con plazas y
  distancia, reloj del tramo.
- [ ] Presupuesto de queries de E2 con 500 casos abiertos (test `--tag performance`).
- [ ] Entrada en `requerimientos.md`; casos de QA en la task.
