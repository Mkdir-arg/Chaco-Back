# Emergencia · Etapa 1 — Relevar (el agente carga una familia desde la PWA)

Reglas de rol: `00-reglas-de-usuario.md`. Modelo completo: `README.md` §6 y spec §3.
Mockups: `M1-1` a `M1-5` (PWA) y `E2` (dónde aparece en la mesa).

## 1. Objetivo

Que un agente en el barrio registre, en menos de 3 minutos y con o sin señal, **una familia
que hay que evacuar**, con lo mínimo que la mesa necesita para derivarla: quién responde,
cuántas personas son, cuántas necesitan asistencia, dónde están.

Resultado: un `CasoEmergencia` en estado `NUEVO`, origen `TERRITORIO`, visible en la
bandeja E2 con la prioridad sugerida.

## 2. Actores

| Rol | Superficie | Capacidad |
|---|---|---|
| Agente territorial | PWA, módulo Emergencia, «Ingreso de familias» | `emergencia.relevar` |
| Operador de mesa | Backoffice E2 «Nuevo caso» (mismo formulario, para lo que llega por teléfono) | `emergencia.operar` |

## 3. Precondiciones

- El usuario inició sesión en la PWA y el login devolvió `"emergencia"` en `modulos` (RU-4).
- GPS y cámara con permiso (`src/services/permisos.js`); si el GPS está apagado se puede
  seguir con dirección escrita (RN-1.12).

## 4. Pantallas (Formulario 1 · Ingreso de familias)

Cuatro pasos con stepper arriba y «Continuar» abajo. Volver atrás conserva lo cargado.

### Paso 1 · Traslado y responsable (M1-1)

| Campo | Tipo | Obligatorio | Regla |
|---|---|---|---|
| Fuerza que traslada | select: Bomberos · Ejército · Defensa Civil · Policía · Municipio · Autoevacuado · Otra | sí | «Otra» abre un texto corto |
| DNI del responsable | numérico, escáner de DNI (`CameraModal.js`) o tipeo | sí | Al salir del campo consulta `POST /api/becas/personas/consultar/` y muestra «Nombre Apellido · 42 años» debajo |
| Nombre y apellido | texto | ◐ | Solo si la consulta no encontró a la persona; se guarda como alta mínima |
| Teléfono de contacto | texto | no | Para el `ContactoCaso` de la mesa |
| N.° de ingreso | solo lectura | — | «Lo asigna el sistema al enviar» |

No se elige albergue: lo asigna la mesa (RN-1.1).

### Paso 2 · Personas que ingresan juntas (M1-2)

Tabla de cantidades, enteros ≥ 0, con totales por fila y columna calculados en vivo:

| | Femenino | Masculino |
|---|---|---|
| Menores de 16 | `menores_f` | `menores_m` |
| Adultos (16 a 59) | `adultos_f` | `adultos_m` |
| Mayores (60+) | `mayores_f` | `mayores_m` |

Total = suma de las seis. El responsable está **incluido** en el total (el formulario lo
dice en una línea bajo la tabla).

### Paso 3 · Necesitan asistencia (M1-3)

| Campo | Tipo | Regla |
|---|---|---|
| Personas con dependencia (movilidad, discapacidad) | entero ≥ 0 | ≤ total |
| Mayores dependientes | entero ≥ 0 | ≤ mayores |
| Lactantes | entero ≥ 0 | ≤ menores |
| Embarazo · Electrodependiente · Medicación crítica · Mascotas | casillas | flags de `necesidades` |
| Prioridad sugerida | solo lectura: ALTA / MEDIA / BAJA | calculada (RN-1.4); el agente no la cambia |

### Paso 4 · Ubicación y fotos (M1-4)

| Campo | Tipo | Obligatorio | Regla |
|---|---|---|---|
| Posición GPS | lectura automática (`ubicacion.js`), muestra precisión en metros | ◐ | Se reintenta hasta 15 s; si no hay fix, sigue sin GPS con aviso |
| Dirección | texto | sí | Calle, número o referencia («frente a la capilla») |
| Localidad | select de `core.Localidad` (cacheado en la app) | sí | Se preselecciona la más cercana al GPS si hay fix |
| Foto de la vivienda · Foto del acceso | cámara o galería, JPEG (HEIC→JPEG como hoy) | no | Máximo 2 fotos, 3 MB cada una después de comprimir |
| Observaciones | texto largo | no | |

### Envío (M1-5)

Pantalla de confirmación: «Enviado · 7 personas · Caso N.° 2026-000184» cuando hay señal;
«Guardado sin señal · se envía solo cuando vuelva la conexión» cuando no (RN-1.8). Botón
«Cargar otra familia» y «Ver mis envíos».

«Mis envíos»: lista local con estado por caso (Pendiente de envío · Enviado · Error) y
reintento manual, igual que `getEnvios` / `reintentarFallidas` de Dispositivos.

## 5. Historias de usuario y criterios de aceptación

**HU-1.1** Como agente quiero cargar una familia en cuatro pasos para no perder tiempo en el
lugar.
- Dado un usuario con `emergencia.relevar`, cuando completa los 4 pasos y envía con señal,
  entonces ve el N.° de caso y en la bandeja E2 aparece el caso `NUEVO` con prioridad,
  localidad y «hace 0 min».
- Dado el paso 2 con total 0, cuando toca «Continuar», entonces no avanza y ve «Cargá al
  menos una persona».

**HU-1.2** Como agente quiero que el DNI me traiga el nombre para no tipearlo.
- Dado un DNI que existe en la Base de Personas, cuando sale del campo, entonces ve nombre
  y edad y el campo nombre queda oculto.
- Dado un DNI que no existe, cuando sale del campo, entonces aparece el campo nombre
  obligatorio y el caso se crea con alta mínima del `Ciudadano`.
- Dado que no hay señal, cuando sale del campo, entonces ve «Sin conexión: el nombre se
  completa al enviar» y el campo nombre aparece opcional.

**HU-1.3** Como agente quiero enviar sin señal para no volver al lugar.
- Dado que no hay conexión, cuando envía, entonces el caso queda en la cola local con su
  `uuid_cliente` y las fotos copiadas al almacenamiento de la app.
- Dado que vuelve la conexión, cuando la app sincroniza (`syncPendientes`), entonces el caso
  se crea una sola vez y «Mis envíos» pasa a Enviado con el N.° de caso.
- Dado un envío que el servidor rechazó (400), cuando el agente abre «Mis envíos», entonces
  ve el motivo y puede corregir y reenviar (mismo `uuid_cliente`).

**HU-1.4** Como operador de mesa quiero cargar un caso que llegó por teléfono.
- Dado un usuario con `emergencia.operar`, cuando usa «Nuevo caso» en E2, entonces se crea
  con origen `MESA`, `relevado_por` = él, sin GPS, con `tomado_por` = él (nace tomado).

## 6. Reglas de negocio

- **RN-1.1** El albergue no se elige en territorio. Nunca aparece en el Formulario 1.
- **RN-1.2** `total_declarado` = suma de las seis cantidades del paso 2, calculado en el
  servidor (no se confía en el total que manda la app). Es el **tamaño del grupo** para
  toda la vida del caso (plazas a pedir, fichas a confirmar).
- **RN-1.3** Validaciones del paso 3: dependientes ≤ total; mayores dependientes ≤
  mayores; lactantes ≤ menores. Se validan en la app y otra vez en el servidor.
- **RN-1.4** Prioridad sugerida: ALTA si (lactantes > 0) o (mayores dependientes > 0) o
  embarazo o electrodependiente o medicación crítica; MEDIA si dependientes > 0 o
  menores > 0 o mayores > 0; BAJA en el resto. Se guarda en `prioridad` y la mesa la puede
  cambiar (etapa 2).
- **RN-1.5** `Ciudadano` del responsable: se busca por DNI; si no existe, alta mínima con
  nombre, apellido y DNI (misma función que el asistente de ingreso de Dispositivos,
  `IngresoPersonaView`, acción `alta_minima`). Sexo: se infiere del paso 2 solo si es
  una familia de una persona; si no, queda sin dato y lo completa la ficha de la etapa 3.
- **RN-1.6** `localidad` es FK a `core.Localidad`, no texto. La app cachea la lista al
  entrar al módulo y la refresca una vez por día.
- **RN-1.7** GPS: se guarda `latitud`, `longitud` y `precision_m`. Con precisión > 100 m
  la mesa ve «ubicación aproximada». Sin fix, los tres quedan `NULL` y la distancia a
  dispositivos (etapa 2) se calcula desde el centroide de la localidad.
- **RN-1.8** Offline: el envío es `POST /api/emergencia/casos/` idempotente por
  `uuid_cliente` (RU-16). `relevado_en` es la hora del teléfono al tocar «Enviar»;
  `creado_en` es la del servidor al recibirlo. La bandeja muestra «relevado 14:20 ·
  enviado 16:05» cuando difieren más de 5 min.
- **RN-1.9** Fotos: hasta 2, JPEG, ≤ 3 MB cada una después de comprimir en el cliente;
  el servidor rechaza > 5 MB o tipo distinto (mismos límites que el contrato de
  inspecciones). Se guardan en `media/emergencia/casos/<uuid>/` detrás de login.
- **RN-1.10** El caso nace `NUEVO`, `tomado_por = NULL`, `origen = TERRITORIO`,
  `relevado_por = user`. Primera fila de `TrazaCaso`: «Relevado en territorio».
- **RN-1.11** Un agente puede cargar la misma familia dos veces por error: el servidor
  **no** lo bloquea (puede ser otra evacuación), pero la bandeja marca «Posible duplicado:
  mismo DNI responsable con caso abierto N.° X» (etapa 2, RN-2.14).
- **RN-1.12** Sin GPS ni dirección no se puede enviar: la dirección escrita es el mínimo.

## 7. Datos que se escriben

| Tabla | Filas | Campos clave |
|---|---|---|
| `legajos.Ciudadano` | 0 o 1 (alta mínima) | dni, nombre, apellido |
| `GrupoFamiliar` | 1 | responsable, traslado, 6 cantidades, dependientes, mayores_dependientes, lactantes, total_declarado |
| `CasoEmergencia` | 1 | grupo, origen, estado=NUEVO, prioridad, localidad, lat/long/precision_m, direccion, necesidades, situacion (JSON: observaciones, teléfono, traslado_otro), relevado_por, relevado_en, uuid_cliente |
| Adjuntos del caso | 0 a 2 | archivo, tipo (VIVIENDA / ACCESO) |
| `TrazaCaso` | 1 | «Relevado en territorio» |

## 8. API (PWA → servidor)

| Método y ruta | Cuerpo | Respuesta | Errores |
|---|---|---|---|
| `GET /api/emergencia/localidades/` | — | `[{id, nombre, latitud, longitud}]` | 401 |
| `POST /api/becas/personas/consultar/` (existe) | `{dni}` | `{encontrado, nombre, apellido, edad, sexo}` | 401, 404 |
| `POST /api/emergencia/casos/` (multipart) | Formulario 1 completo + `uuid_cliente` + `relevado_en` + `fotos[]` | `201 {id, numero, prioridad, total_declarado}`; `200` con el mismo cuerpo si el `uuid_cliente` ya existía | 400 con errores por campo; 403 sin `emergencia.relevar` (cuerpo explicativo) |
| `GET /api/emergencia/casos/mios/` | — | últimos 50 casos del agente: `{numero, estado, total_declarado, creado_en}` | 401 |

Token DRF en `Authorization: Token …`, como el resto de la app. El test de contrato
(`programas/tests/test_becas_api_contrato.py` o uno nuevo `test_emergencia_api_contrato.py`)
fija las claves de cada respuesta y las del login (`modulos` ahora puede traer
`"emergencia"`: actualizar `CLAVES_LOGIN` y los tests que afirman la lista exacta).

## 9. Cambios en la PWA (`Chaco-mobile`)

1. `src/services/modulos.js`: `MODULOS` suma `'emergencia'`, `NOMBRE_MODULO.emergencia =
   'Emergencia'`; `ModuloSelectorScreen` suma el ícono.
2. `src/services/emergenciaService.js` (nuevo): cola local (`AsyncStorage` + archivos como
   `dispositivosBorrador.js`), `enviarCaso`, `syncPendientes`, `getEnvios`,
   `reintentarFallidas`, `getLocalidades` con caché diario.
3. Pantallas: `EmergenciaHomeScreen` (accesos según rol), `IngresoFamiliaScreen` (4 pasos),
   `MisEnviosScreen`.
4. Reusar: `CameraModal.js` (DNI), `ubicacion.js` (GPS), `imagePicker.js` + compresión,
   `identityLookup.js` (consulta por DNI).

## 10. Casos borde

- DNI del responsable ya tiene una `Estadia` abierta en otro dispositivo → el caso se crea
  igual y la mesa ve «Responsable alojado hoy en X» (lo resuelve la etapa 2).
- Responsable sin DNI (extraviado) → casilla «No tiene documento» habilita nombre, apellido
  y fecha de nacimiento aproximada; `Ciudadano` con `documento_en_mano=False`.
- El teléfono cambia de hora entre relevar y enviar → `relevado_en` queda como estaba; el
  servidor no la corrige, solo la muestra.
- La app se cierra con el formulario a medias → borrador local por `uuid_cliente`, se
  retoma al volver (como `dispositivosBorrador`).

## 11. Fuera de esta etapa

Elegir albergue, ingreso individual separado (es M1 con total 1), fotos de cada persona,
firma del responsable.

## 12. Criterio de terminado

- [ ] Tests de servicio: RN-1.2, 1.3, 1.4 (tabla de casos), 1.8 (idempotencia), 1.9
  (límites), 1.12.
- [ ] Test de contrato de la API con las claves exactas; `CLAVES_LOGIN` actualizado.
- [ ] Test de mutación RU §6 n.° 3 (un rol de Becas no abre `"emergencia"`).
- [ ] `manage.py check`, `check_migraciones.py`, `makemigrations --check` con
  `DJANGO_SYNCDB_PROJECT_APPS=False`.
- [ ] En la PWA: tests de `emergenciaService` (cola, idempotencia, reintento) como los de
  `src/services/__tests__/`.
- [ ] Entrada en `docs/internal/requerimientos.md`, etiqueta `emergencia`.
- [ ] Casos de QA en la task, primera línea «Ambiente: testing (datanach.ecomdev.ar)».
