# Emergencia · Etapa 3 — Alojar (el dispositivo recibe a la familia, desde la PWA o el backoffice)

Reglas de rol: `00-reglas-de-usuario.md` (en especial RU-1 a RU-5: **la PWA es la vía
principal del dispositivo**). Etapa anterior: `02-tomar-y-derivar.md`.
Mockups PWA: `M2-1` (buscar DNI), `M2-2` (derivación vigente), `M2-3` (integrantes «3 de
7»), `M2-4` (ficha individual con cama), `M2-5` (familia alojada), `M2-6` (sin derivación /
ingresar igual). Backoffice: `E6`, `E6-integrantes`, `E6-diferencia`, `E6-alojada`.

## 1. Objetivo

Que la guardia del centro de evacuados, con el teléfono en la mano, convierta «una familia
en la puerta» en **una estadía por persona con su cama**, en el mismo mapa de plazas que ya
usa Dispositivos, y que la mesa lo vea al instante.

Resultado: `DERIVADO → INGRESO_EN_CURSO → ALOJADO`, N `Estadia` abiertas, N
`IntegranteGrupo` confirmados, reservas consumidas, bitácora del turno con el ingreso.

## 2. Actores

| Rol | Superficie | Capacidad |
|---|---|---|
| Operador del dispositivo | **PWA M2** (principal) y backoffice E6 (misma función) | `dispositivo.admitir` en su dispositivo (RU-8); `dispositivo.egresar` para egresos |

La mesa no interviene en esta etapa: solo mira (E3 se actualiza) y recibe los avisos de
rechazo, diferencia e ingreso directo.

## 3. Pantallas

Las dos superficies siguen **el mismo guion** y llaman a los mismos servicios (RU-2). Abajo
se describe la PWA; E6 es la misma secuencia dentro del backoffice, reutilizando
`ingreso/paso_persona.html` y el mapa de plazas de `sectores/sectores.html`.

### M2-1 · Buscar a la familia

Campo DNI (escáner o tipeo) + «Buscar». Busca por DNI del responsable **o de cualquier
integrante ya confirmado** (RN-3.1). Tres resultados posibles:

1. **Derivación vigente para mi dispositivo** → M2-2.
2. **Sin derivación vigente** → M2-6 («Ingresar igual» si hay plazas, o «Avisar a la
   mesa»).
3. **Persona ya alojada** (en este u otro dispositivo) → aviso «Alojada en X desde
   el 3/11» y nada más (RN-3.2).

### M2-2 · Derivación vigente

Tarjeta: familia (apellido del responsable), «7 personas declaradas», prioridad, derivada
por / a las, **vence a las HH:MM**, necesidades (chips), y abajo el resumen de la tabla del
paso 2. Botones: **Aceptar** · Rechazar (motivo obligatorio: Sin plazas · No cumple perfil
· No llegó · Otro).

Al aceptar: el caso pasa a `INGRESO_EN_CURSO`, se reservan `plazas_pedidas` camas (RN-3.4)
y se abre M2-3.

### M2-3 · Integrantes («3 de 7 confirmadas»)

Lista de **N filas = `total_declarado`**, cada una «Persona 1 · sin confirmar» o «Juan
Pérez · cama B-12 · ficha incompleta». Contador arriba. Botones: «Agregar persona» (RN-3.8),
«Cerrar ingreso con diferencia» (RN-3.9, habilitado con ≥ 1 confirmada). Al llegar a N de N
aparece **«Familia alojada»** (M2-5).

### M2-4 · Ficha individual (Formulario 2) + cama

Secciones colapsables; las tres primeras forman el **mínimo** (RN-3.6):

| # | Sección | Campos | Mínimo |
|---|---|---|---|
| 1 | Parentesco | Jefe/a de hogar · Cónyuge/pareja · Hijo/a · Otro (texto) | sí |
| 2 | Datos personales | DNI (consulta a Base de Personas; «No tiene documento» → nombre, apellido, fecha de nacimiento aproximada, motivo) · sexo · fecha de nacimiento · teléfono | sí |
| 3 | Avisos críticos de salud | embarazo · discapacidad · electrodependiente · medicación crítica (nombre y si tiene dosis) · alergias graves | sí (todas pueden ser «no») |
| 4 | Educación | nivel, escuela, asiste | no |
| 5 | Vacunación | esquema al día, observación | no |
| 6 | Salud y medicación (detalle) | obra social, enfermedades crónicas, medicación habitual | no |
| 7 | Trabajo | ocupación, ingresos | no |
| 8 | Observaciones · mascotas · adulto responsable (si es menor) | texto / sí-no | no |

**Cama**: botón «Elegir cama» abre el mapa de plazas del dispositivo (sector → plazas),
con tres estados visibles: libre, **reservada para esta familia** (resaltada, son las
elegibles por defecto), ocupada / fuera de servicio (no elegibles). Se puede elegir una
libre no reservada si la familia creció (RN-3.8).

Botón **«Confirmar persona»**: válido con mínimo + cama. Crea la `Estadia` (RN-3.7). Si las
secciones 4 a 8 están vacías, la fila queda «ficha incompleta» y se puede terminar después
desde M2-3 (o desde el backoffice, E6-integrantes).

### M2-5 · Familia alojada (sección 4 del Formulario 1)

Con N de N confirmadas: sector/ala (preseleccionado con el de las camas), aula o
dormitorio, **tarjeta familiar entregada** (sí/no) y su número, encargado que recibe
(prellenado con el usuario). «Alojar» → `ALOJADO`. Pantalla final: «Familia Pérez alojada
· 7 de 7 · Aula 3». Botón «Buscar otra familia».

### M2-6 · Sin derivación vigente

«No hay una derivación para este DNI en tu dispositivo». Dos botones:
- **Ingresar igual** (si plazas libres ≥ 1): abre el Formulario 1 (los 4 pasos de M1, con
  localidad y dirección opcionales, sin fotos obligatorias) y sigue con M2-3. El caso nace
  `origen = DISPOSITIVO` (RN-3.10).
- **Avisar a la mesa**: crea el caso `NUEVO` con origen `DISPOSITIVO`, marca «esperando
  derivación», y la familia espera en el lugar; la mesa lo ve en la bandeja con la marca
  «En la puerta de X».

## 4. Historias de usuario y criterios de aceptación

**HU-3.1** Como operador del dispositivo quiero encontrar la derivación con el DNI de
cualquiera de la familia.
- Dado un caso derivado a mi dispositivo, cuando busco el DNI del responsable, entonces
  veo M2-2 con los datos del caso.
- Dado el mismo caso derivado a **otro** dispositivo, cuando busco, entonces veo M2-6 y la
  respuesta no nombra al otro dispositivo (RU-9).
- Dado que no tengo `dispositivo.admitir` en este dispositivo, cuando busco, entonces 403
  con «No formás parte del equipo de este dispositivo».

**HU-3.2** Como operador quiero aceptar y que las camas queden reservadas para la familia.
- Dado una derivación `PENDIENTE` de 7 plazas y 9 libres, cuando acepto, entonces el caso
  pasa a `INGRESO_EN_CURSO`, `aceptado_en` = ahora, hay 7 `ReservaPlaza` `VIGENTE` a
  nombre del responsable (RN-3.4) y las 7 camas aparecen «reservadas para esta familia».
- Dado 7 pedidas y 5 libres, cuando acepto, entonces se reservan 5 y veo «Reservé 5 de 7
  · faltan 2 camas»; puedo seguir.
- Dado 0 libres, cuando intento aceptar, entonces no puedo: «Sin plazas · rechazá con
  motivo o liberá camas».
- Dado una derivación vencida hace 10 min que el cron todavía no procesó, cuando acepto,
  entonces **se acepta igual** (RN-3.3): la familia está en la puerta.

**HU-3.3** Como operador quiero confirmar a cada persona con lo mínimo y la cama.
- Dado la ficha con parentesco, datos personales y avisos críticos y una cama reservada,
  cuando confirmo, entonces existe una `Estadia` abierta de esa persona en esa cama, la
  reserva pasa a `CONSUMIDA`, el contador suma 1 y la bitácora del turno tiene «Ingreso ·
  Juan Pérez · cama B-12 · Emergencia caso N.° X» (automática).
- Dado una ficha sin sección 3, cuando confirmo, entonces «Falta: avisos de salud» y no
  se crea nada.
- Dado una persona que ya tiene una estadía abierta en otro dispositivo, cuando confirmo,
  entonces el servicio de Dispositivos lo rechaza y veo «Juan Pérez figura alojado en X
  desde el 3/11. Pedí que lo egresen de X o cerrá el ingreso con diferencia».

**HU-3.4** Como operador quiero cerrar con diferencia si llegaron menos.
- Dado 5 de 7 confirmadas, cuando cierro con motivo «uno quedó con familiares, otro
  derivado a salud», entonces el caso pasa a `ALOJADO` con `total_alojado = 5`, marca
  «Ingreso parcial», las 2 reservas sobrantes pasan a `LIBERADA`, y la mesa lo ve en E3
  con la diferencia y el motivo.

**HU-3.5** Como operador quiero agregar a alguien que no estaba declarado.
- Dado 7 de 7 declaradas, cuando agrego una persona, entonces `total_declarado` pasa a 8,
  aparece una fila nueva y la cama se elige entre las **libres** (no hay reserva).
- Dado 0 libres, cuando agrego, entonces la fila se crea pero «Confirmar» avisa «Sin cama
  libre · liberá una o cerrá con diferencia».

**HU-3.6** Como operador quiero ingresar a una familia que llegó sola.
- Dado un DNI sin derivación y 3 plazas libres, cuando toco «Ingresar igual» y completo
  el Formulario 1 y las fichas, entonces el caso existe con origen `DISPOSITIVO`, nace
  `INGRESO_EN_CURSO` sin pasar por la mesa, y al terminar está `ALOJADO` con la marca
  «Ingreso directo» en la bandeja y el tablero.
- Dado el mismo escenario sin señal (RU-3), cuando toco «Ingresar igual», entonces el
  Formulario 1 se guarda en la cola y veo «Las fichas y las camas se cargan cuando vuelva
  la conexión»; al sincronizar, el caso se crea y M2-3 queda disponible.

**HU-3.7** Como operador quiero egresar a una persona y que el caso se cierre cuando no
queda nadie.
- Dado una familia alojada, cuando egreso a un integrante (flujo existente de
  Dispositivos, `egresar_persona`), entonces el `IntegranteGrupo` queda «egresado el …», y
  cuando el último egresa el caso pasa a `CERRADO` con motivo «Todos egresados» (RN-3.12).

## 5. Transiciones

| Estado actual | Acción | Estado nuevo | Efectos |
|---|---|---|---|
| `DERIVADO` | Aceptar | `INGRESO_EN_CURSO` | `Derivacion.ACEPTADA`, `aceptado_en`, N reservas, traza, bitácora `GENERAL` «Derivación aceptada» |
| `DERIVADO` | Rechazar (motivo) | `EN_GESTION` | `Derivacion.RECHAZADA`, aviso en bandeja, traza |
| `INGRESO_EN_CURSO` | Confirmar persona | igual | `IntegranteGrupo` confirmado, `Estadia`, reserva `CONSUMIDA`, bitácora `INGRESO` |
| `INGRESO_EN_CURSO` | Agregar persona | igual | `total_declarado + 1`, fila nueva |
| `INGRESO_EN_CURSO` | Alojar (N de N) | `ALOJADO` | `alojado_en`, sección 4, traza, bitácora `GENERAL` «Familia alojada 7 de 7» |
| `INGRESO_EN_CURSO` | Cerrar con diferencia (motivo) | `ALOJADO` | `alojado_en`, `total_alojado < total_declarado`, reservas sobrantes `LIBERADA`, marca parcial |
| `INGRESO_EN_CURSO` | Cancelar ingreso (motivo; 0 confirmadas) | `EN_GESTION` | reservas `LIBERADA`, `Derivacion.RECHAZADA`, vuelve a la mesa |
| `ALOJADO` | Egreso de un integrante | igual | `Estadia` cerrada, `IntegranteGrupo.egresado_en` |
| `ALOJADO` | Egreso del último | `CERRADO` | `cerrado_en`, motivo «Todos egresados» |
| (sin caso) | Ingresar igual | `INGRESO_EN_CURSO` (origen `DISPOSITIVO`) | caso + grupo + derivación `ACEPTADA` implícita hacia el propio dispositivo (RN-3.10) |

## 6. Reglas de negocio

- **RN-3.1** Búsqueda: `Derivacion` `PENDIENTE` o `ACEPTADA` cuyo caso tiene
  `grupo.responsable.dni == dni` **o** un `IntegranteGrupo.ciudadano.dni == dni`, y
  `dispositivo in dispositivos_en_alcance(user, "dispositivo.admitir")`. Nada más.
- **RN-3.2** Si la persona buscada tiene `Estadia` abierta en la red, se informa dónde
  solo si es **este** dispositivo; si es otro, «alojada en otro dispositivo» sin nombre
  (RU-9), salvo que el usuario tenga `dispositivo.ver_todos`.
- **RN-3.3** Aceptar una derivación `PENDIENTE` vale aunque `vence_en` haya pasado,
  mientras el cron no la haya marcado `VENCIDA`. Una `VENCIDA` no se acepta: M2-6.
- **RN-3.4** Al aceptar se reservan hasta `plazas_pedidas` camas con `reservar_plaza`
  (`services/estadias.py:778`), tipo `RESERVA`, `ciudadano = responsable`, `motivo =
  "Emergencia caso N.° X"`, `hasta = NULL`; se eligen automáticamente: sector con más
  camas libres contiguas primero (orden de `Plaza.codigo`). El operador puede cambiarlas al
  confirmar cada ficha. Reservar menos de lo pedido es válido con aviso; 0 libres →
  no se puede aceptar.
- **RN-3.5** Las reservas de Emergencia son a nombre del responsable porque los integrantes
  todavía no existen como `Ciudadano`. Al confirmar la ficha de otra persona, la reserva se
  **reasigna** a ese ciudadano y después se consume en `ingresar_persona(reserva=…)`. Si
  `reservar_plaza` exige que la reserva y el ingreso sean de la misma persona (verificar
  en `_bloquear_reserva_propia`), el servicio de Emergencia libera y vuelve a reservar en
  la misma transacción antes de ingresar: **no** se modifica Dispositivos.
- **RN-3.6** Mínimo para confirmar (decisión 1 del README, propuesta): parentesco; DNI o
  «sin documento» con nombre, apellido y nacimiento aproximado; sexo; y las cinco
  preguntas de avisos críticos respondidas. `ficha_completa` = todas las secciones con al
  menos un dato o marcadas «sin datos».
- **RN-3.7** Confirmar persona = **una transacción**: `Ciudadano` (buscar o alta mínima;
  `documento_en_mano=False` + motivo si no tiene), `VinculoFamiliar` con el responsable
  según parentesco, `IntegranteGrupo` (ficha JSON, `confirmada_en`), `ingresar_persona(
  ciudadano, dispositivo, usuario, plaza, reserva)` (`services/estadias.py:430`), que ya
  valida «una estadía abierta por persona en la red», plaza libre y alcance. La `Estadia`
  queda en `IntegranteGrupo.estadia`.
- **RN-3.8** Agregar persona: `total_declarado += 1`, traza «Agregada persona por el
  dispositivo». La cama se elige entre libres. La mesa ve «llegaron 8 sobre 7 declaradas».
- **RN-3.9** Cerrar con diferencia: requiere ≥ 1 confirmada y motivo (Quedó con
  familiares · No llegó al centro · Derivado a salud · Otro). `total_alojado` =
  confirmadas. Reservas `VIGENTE` sobrantes → `liberar_reserva` (`:884`). El caso pasa a
  `ALOJADO` igual (es el estado de «la familia está acá»), con marca parcial.
- **RN-3.10** Ingreso directo: el caso se crea con `origen = DISPOSITIVO`, `relevado_por` =
  el operador, `localidad` = la del dispositivo si no se cargó otra, y una `Derivacion`
  `ACEPTADA` hacia el propio dispositivo (para que toda la lógica posterior sea la misma).
  `tomado_en` y `derivado_en` = `creado_en` (el tramo de la mesa es 0 y no cuenta para el
  SLA de la mesa; el tablero los separa como «ingreso directo»).
- **RN-3.11** Offline en el dispositivo (RU-3): solo el Formulario 1 del ingreso directo
  se encola. Aceptar, confirmar y alojar exigen conexión y la app lo dice antes de
  empezar («Sin conexión: no podés reservar camas»).
- **RN-3.12** Egreso: se hace con el flujo de Dispositivos que ya existe. Un receptor de
  señal (o un chequeo en `egresar_persona` vía hook de servicio, nunca en la vista) marca
  `IntegranteGrupo.egresado_en`; cuando ningún integrante tiene estadía abierta, el caso
  pasa a `CERRADO` con `cerrado_en` y traza. Egreso = cierre, no «traslado» (fuera de
  alcance).
- **RN-3.13** Rechazar con motivo manda el caso a `EN_GESTION` con el mismo `tomado_por`
  y una marca «Rechazado por X: sin plazas» en la bandeja hasta la próxima acción.
- **RN-3.14** Todo lo que pasa en esta etapa deja `EntradaBitacora` `AUTOMATICA` en el
  dispositivo: aceptación (`GENERAL`), cada ingreso (`INGRESO`, lo deja `ingresar_persona`
  ya), alojamiento final (`GENERAL`), diferencia (`GENERAL` con motivo).

## 7. API (PWA ↔ servidor)

Todas con token DRF, alcance por `dispositivos_en_alcance`, `uuid_cliente` en las
escrituras que crean filas.

| Método y ruta | Cuerpo | Respuesta |
|---|---|---|
| `GET /api/emergencia/mis-dispositivos/` | — | dispositivos donde tengo `admitir` o `recibir_kit`: `[{id, nombre, plazas_libres, derivaciones_pendientes, entregas_pendientes}]` |
| `GET /api/emergencia/dispositivos/{id}/buscar/?dni=` | — | `{resultado: "DERIVACION" \| "SIN_DERIVACION" \| "ALOJADA", derivacion?: {...}, plazas_libres, alojada_aca?: bool}` |
| `POST …/derivaciones/{id}/aceptar/` | `{uuid_cliente}` | `{caso, reservadas, faltantes, integrantes: [...]}` |
| `POST …/derivaciones/{id}/rechazar/` | `{motivo, observacion}` | `{caso_estado}` |
| `GET …/casos/{id}/integrantes/` | — | `[{n, estado, ciudadano?, plaza?, ficha_completa}]`, `confirmadas`, `total_declarado` |
| `GET …/dispositivos/{id}/plazas/?caso=` | — | sectores → plazas con `{codigo, estado: LIBRE \| RESERVADA_FAMILIA \| OCUPADA \| FUERA_SERVICIO}` |
| `POST …/casos/{id}/integrantes/{n}/confirmar/` | ficha (mínimo + opcionales) + `plaza_id` + `uuid_cliente` | `{integrante, confirmadas, total_declarado}` |
| `PATCH …/casos/{id}/integrantes/{n}/` | secciones 4 a 8 | `{ficha_completa}` |
| `POST …/casos/{id}/integrantes/` | `{uuid_cliente}` | fila nueva, `total_declarado` |
| `POST …/casos/{id}/alojar/` | sección 4 | `{estado: "ALOJADO"}` |
| `POST …/casos/{id}/cerrar-diferencia/` | `{motivo, observacion}` | `{estado, total_alojado, liberadas}` |
| `POST …/casos/{id}/cancelar-ingreso/` | `{motivo}` | `{estado: "EN_GESTION"}` |
| `POST /api/emergencia/dispositivos/{id}/ingreso-directo/` (multipart) | Formulario 1 + `uuid_cliente` | `{caso, integrantes}` (idempotente) |
| `POST /api/becas/personas/consultar/` (existe) | `{dni}` | persona |

Errores: 403 con cuerpo explicativo (alcance), 409 con `{"detail", "estado_actual"}`
cuando el estado cambió (otra guardia aceptó desde el backoffice), 400 por campo. El
cliente, ante 409, recarga la pantalla con `estado_actual`.

## 8. Backoffice E6 (misma secuencia)

- Entrada: menú del dispositivo → «Emergencia · Llegadas» (visible con `admitir`).
- E6 = M2-1 + M2-2 en una pantalla (arquetipo formulario + tarjeta); E6-integrantes =
  M2-3 + M2-4 con `split` (lista a la izquierda, ficha a la derecha, mapa de plazas en
  modal reutilizando `sectores.html` con un parámetro `modo=emergencia&caso=`);
  E6-diferencia = modal; E6-alojada = M2-5.
- Las vistas llaman a los mismos servicios que la API. No hay segunda validación.

## 9. Cambios en la PWA

1. `emergenciaService.js`: `buscarPorDni`, `aceptar`, `rechazar`, `integrantes`,
   `plazas`, `confirmarIntegrante`, `agregarIntegrante`, `alojar`, `cerrarDiferencia`,
   `ingresoDirecto` (este último con cola offline; el resto exige `NetInfo` conectado y
   muestra el aviso RN-3.11).
2. Pantallas: `LlegadaBuscarScreen` (M2-1/M2-6), `DerivacionScreen` (M2-2),
   `IntegrantesScreen` (M2-3), `FichaIntegranteScreen` (M2-4, con `MapaPlazasModal`),
   `FamiliaAlojadaScreen` (M2-5). Selección de dispositivo previa si hay más de uno
   (patrón `DispositivosListaScreen`).
3. `MapaPlazasModal`: grilla por sector, tres estados, selección única; recibe los datos
   de `…/plazas/?caso=`.

## 10. Casos borde

- Dos guardias confirman la misma persona a la vez (PWA y backoffice) → `ingresar_persona`
  gana una; la otra recibe 409 y recarga.
- La cama reservada quedó fuera de servicio entre aceptar y confirmar → al confirmar, 400
  «La cama B-12 está fuera de servicio · elegí otra»; la reserva se libera sola.
- El responsable no viene (llegó la familia sin él) → se confirma a los demás; el
  responsable queda sin confirmar; se cierra con diferencia «no llegó al centro».
- Llega una persona de la familia **antes** de que la mesa derive → M2-6 → «Avisar a la
  mesa»: caso `NUEVO` con marca «En la puerta de X», la mesa deriva a X y la guardia
  busca de nuevo.
- Menor sin adulto → sección 8 «adulto responsable» obligatoria si edad < 16 (validación
  del mínimo ampliada por edad).
- Mismo DNI dos veces en la misma familia → 400 «Ya confirmaste a Juan Pérez en la cama
  B-12».

## 11. Criterio de terminado

- [ ] Tests de servicio: RN-3.1 (tres resultados + alcance), 3.3, 3.4 (reserva parcial,
  0 libres), 3.5 (reasignación de reserva sin tocar Dispositivos), 3.6 (mínimo), 3.7
  (transacción atómica: si `ingresar_persona` falla, no queda `IntegranteGrupo` ni
  `Ciudadano` huérfano), 3.8, 3.9, 3.10, 3.12 (egreso del último cierra).
- [ ] Tests de mutación RU §6 n.° 2 (alcance de dispositivo) y uno nuevo: un usuario con
  `admitir` en el dispositivo A no acepta una derivación del B aunque conozca el id.
- [ ] Tests de concurrencia (`TransactionTestCase`): doble confirmación, doble aceptación.
- [ ] Contrato de la API (claves exactas de cada respuesta) y de `…/plazas/`.
- [ ] Mapa de plazas en modo emergencia: ficha de componente nueva en `.claude/design/`
  (tres estados), sin tocar la golden de sectores.
- [ ] Presupuesto de queries de `…/integrantes/` y `…/plazas/` con un dispositivo de 300
  camas.
- [ ] PWA: tests de `emergenciaService` (409 → recarga; offline solo en ingreso directo).
- [ ] Entrada en `requerimientos.md`; casos de QA (**probar en la PWA de testing y en el
  backoffice**, los dos).
