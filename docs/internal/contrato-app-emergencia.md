# Contrato de la app de campo de Emergencia

Qué le pide la app (`Chaco-mobile`) al back para el **módulo Emergencia** y qué recibe. Las claves de
cada respuesta están fijadas con igualdad exacta en `programas/tests/test_emergencia_api_contrato.py`
(constantes `CLAVES_*`): agregar una clave es seguro; renombrarla o sacarla es un release coordinado de
la app, y el test y este documento se tocan en el mismo diff. El esquema OpenAPI publicado
(`/api/schema/`) documenta los mismos extremos.

Base: `/api/emergencia/`. Autenticación: `Authorization: Token <token>`, el mismo token del resto de la
app.

Alcance de esta versión: login, perfil y **M1 · Ingreso de familias** (Formulario 1 del agente
territorial, PR 5), **M3 · Recepción de kits** en el dispositivo (PR 9-API, §9 a §12) y **M2 · Llegada de
familias** (PR 8, §13).

## Resumen de extremos

| Método y ruta | Quién | Para qué |
|---|---|---|
| `POST /api/becas/auth/token/` | cualquiera con usuario y clave | Login de la app; `modulos` puede traer `"emergencia"` |
| `GET /api/emergencia/` | módulo | Índice del namespace |
| `GET /api/emergencia/perfil/` | módulo | Qué accesos mostrar en la pantalla inicial |
| `POST /api/emergencia/personas/consultar/` | módulo | Nombre y edad a partir del DNI |
| `GET /api/emergencia/localidades/` | módulo | Lista de localidades para el Formulario 1 |
| `POST /api/emergencia/casos/` | agente | Enviar una familia (multipart, idempotente) |
| `GET /api/emergencia/casos/mios/` | agente | «Mis envíos» |
| `GET /api/emergencia/mis-dispositivos/` | módulo | Dispositivos donde el usuario es de la guardia, con sus entregas pendientes |
| `GET /api/emergencia/dispositivos/{id}/entregas/` | kits | Entregas de kits de un dispositivo (`?pendientes=1`: las que esperan recepción) |
| `GET /api/emergencia/entregas/{id}/` | kits | Una entrega con sus líneas |
| `POST /api/emergencia/entregas/{id}/recibir/` | kits | Confirmar la recepción (multipart, idempotente, con conexión) |
| `GET /api/emergencia/dispositivos/{id}/buscar/?dni=` | llegadas | Buscar a la familia por DNI (§13.2) |
| `POST /api/emergencia/derivaciones/{id}/aceptar/` | llegadas | Aceptar la derivación y reservar camas (§13.3) |
| `POST /api/emergencia/derivaciones/{id}/rechazar/` | llegadas | Rechazar la derivación con motivo (§13.4) |
| `GET /api/emergencia/casos/{id}/integrantes/` | llegadas | Las personas de la familia y el contador (§13.5) |
| `POST /api/emergencia/casos/{id}/integrantes/` | llegadas | Agregar una persona (idempotente) (§13.5) |
| `GET /api/emergencia/casos/{id}/integrantes/{n}/` | llegadas | Una persona con su ficha (§13.6) |
| `PATCH /api/emergencia/casos/{id}/integrantes/{n}/` | llegadas | Completar las secciones 4 a 8 (§13.6) |
| `GET /api/emergencia/dispositivos/{id}/plazas/?caso=` | llegadas | Mapa de camas para elegir (§13.7) |
| `POST /api/emergencia/casos/{id}/integrantes/{n}/confirmar/` | llegadas | Confirmar a la persona con su ficha y su cama (idempotente) (§13.8) |
| `POST /api/emergencia/casos/{id}/alojar/` | llegadas | «Familia alojada» (§13.9) |
| `POST /api/emergencia/casos/{id}/cerrar-diferencia/` | llegadas | Cerrar con diferencia (§13.9) |
| `POST /api/emergencia/casos/{id}/cancelar-ingreso/` | llegadas | Cancelar el ingreso (§13.9) |
| `POST /api/emergencia/dispositivos/{id}/ingreso-directo/` | llegadas | «Ingresar igual» (multipart, idempotente, se encola) (§13.10) |
| `POST /api/emergencia/dispositivos/{id}/avisar-mesa/` | llegadas | «Avisar a la mesa» (multipart, idempotente) (§13.10) |

«Módulo», «agente», «kits» y «llegadas» son los cuatro permisos del namespace (§2).

## 1. Login

`POST /api/becas/auth/token/` con `{"username", "password"}`. Es el login de siempre: **las claves del
cuerpo no cambian**; lo nuevo es un valor posible dentro de `modulos`.

```json
{"token": "05d464237bbd70934fe586144a27d808e022f889", "user_id": 7, "username": "agente",
 "modulos": ["emergencia"], "app": {"version_minima": null}}
```

`modulos` lista a qué módulos entra el usuario, **siempre en este orden**: `"becas"`, `"dispositivos"`,
`"emergencia"`. Trae `"emergencia"` cuando el usuario cumple alguna de estas:

- es **agente territorial**: capacidad `emergencia.relevar` en el programa Emergencia;
- es de la **guardia de un dispositivo**: integra el Equipo de algún dispositivo con un rol que tiene
  `dispositivo.admitir` o `emergencia.recibir_kit`;
- es **administrador del programa Dispositivos**.

La capacidad tildada en un rol **sin** estar en el Equipo de ningún dispositivo no abre el módulo.
Quien trabaja en la mesa (`emergencia.operar`, `emergencia.supervisar`) no abre la app por eso: la mesa
es del backoffice.

| Usuario | `modulos` |
|---|---|
| Agente con `emergencia.relevar` | `["emergencia"]` |
| Territorial de Becas | `["becas"]` |
| Territorial de Becas que además releva | `["becas", "emergencia"]` |
| Agente edilicio que además releva | `["dispositivos", "emergencia"]` |
| Guardia con `dispositivo.admitir` en su Equipo | `["emergencia"]` |
| Administrador del programa Dispositivos | `["emergencia"]` |

Errores del login (sin cambios): 400 credenciales inválidas; 403
`{"detail": "El usuario no tiene acceso a la app de campo."}` si no abre ningún módulo; 403
`{"codigo": "debe_cambiar_contrasena", "detail": "…"}` si tiene que cambiar la clave provisoria; 429 por
demasiados intentos fallidos.

## 2. Permisos y códigos de error

Cuatro permisos, los cuatro con el mismo `code` que el resto de la app:

| Permiso | Regla | 403 |
|---|---|---|
| **Módulo** | La misma del login (§1): agente, guardia o administrador de Dispositivos | `{"detail": "El usuario no tiene acceso al módulo Emergencia.", "code": "SIN_MODULO"}` |
| **Agente** | `emergencia.relevar` en el programa Emergencia | `{"detail": "El usuario no tiene permiso para relevar familias en Emergencia. Pedile a quien administra los usuarios que te sume el rol de agente territorial.", "code": "SIN_MODULO"}` |
| **Kits** | Abre el módulo **y** tiene `emergencia.recibir_kit` en el Equipo de algún dispositivo (o administra el programa Dispositivos con esa capacidad) | `{"detail": "El usuario no recibe kits en ningún dispositivo. Pedile a quien arma el equipo del dispositivo que te sume con un rol que reciba kits.", "code": "SIN_MODULO"}` |
| **Llegadas** | Abre el módulo **y** tiene `dispositivo.admitir` en el Equipo de algún dispositivo (o administra el programa Dispositivos con esa capacidad) | `{"detail": "El usuario no admite familias en ningún dispositivo. Pedile a quien arma el equipo del dispositivo que te sume con un rol que admita familias.", "code": "SIN_MODULO"}` |

**Alcance por dispositivo (kits y llegadas).** Los permisos «kits» y «llegadas» dicen que el usuario
recibe kits o admite familias *en algún lado*. Qué dispositivo, qué entrega, qué derivación y qué caso son
suyos se resuelve por alcance, y lo que no es suyo contesta **404** con el
mismo cuerpo que un id que no existe (`{"detail": "No encontrado."}`): la respuesta no confirma que la
entrega o el caso existen ni nombra al otro dispositivo. Un caso es «del usuario» si su **última**
derivación es hacia un dispositivo donde admite: el que la guardia rechazó y la mesa derivó a otro lado
deja de serlo. El 403 queda para quien no tiene el permiso en ningún
dispositivo.

El token no abre nada por sí solo: un usuario de Becas recibe 403 `SIN_MODULO` en todo
`/api/emergencia/`, y un usuario de Emergencia recibe 403 `SIN_MODULO` en todo `/api/becas/` y
`/api/dispositivos/`.

| Código HTTP | `code` | Cuándo | Qué hace la app |
|---|---|---|---|
| 401 | — | Sin token o token inválido | Volver al login |
| 403 | `SIN_MODULO` | El usuario no tiene el permiso de la ruta | Mostrar `detail`; no reintentar |
| 400 | `VALIDACION` | El envío no es válido (§6) | Mostrar el detalle por campo; el agente corrige y reenvía con el **mismo** `uuid_cliente` |
| 409 | `UUID_EN_USO` | Ese `uuid_cliente` ya creó un caso de **otro** usuario, o ya es el de la recepción de **otra** entrega | No reintentar con ese identificador |
| 409 | — (trae `estado_actual`) | La entrega ya fue recibida o la mesa la canceló (§12); el caso ya no está como la acción necesita: otra guardia actuó desde su teléfono o el backoffice, la mesa canceló, el cron venció (§13) | Mostrar `detail` y recargar con `estado_actual` (§13.1) |
| 404 | — | El dispositivo, la entrega, la derivación o el caso no existen, o no son del usuario | Recargar «mis dispositivos» |
| 429 | — | Tope de consultas de identidad (§4) | Seguir con carga manual del nombre |

## 3. Perfil

`GET /api/emergencia/perfil/` — qué accesos muestra la pantalla inicial del módulo.

```json
{"relevar": true, "dispositivo": false}
```

- `relevar`: agente territorial → «Ingreso de familias» (M1).
- `dispositivo`: **opera** en algún dispositivo —tiene `dispositivo.admitir` o `emergencia.recibir_kit`
  en su Equipo, o administra el programa Dispositivos **con** alguna de las dos— → «Llegada de familias»
  (M2) y «Recepción de kits» (M3). Qué dispositivos y qué ofrece cada uno, en «mis dispositivos» (§9).

Con los dos en `true` se muestran los tres accesos. Los dos en `false` solo le pasa al administrador del
programa Dispositivos que no tiene `dispositivo.admitir` ni `emergencia.recibir_kit` (PR 8): entra al
módulo (§1, el login no cambió) pero no tiene nada que hacer en la app; mostrar «No tenés tareas en la
app. Pedí que te sumen al equipo de un dispositivo».

## 4. Consulta de identidad

`POST /api/emergencia/personas/consultar/` (JSON). **Mismo cuerpo, misma respuesta y mismos códigos**
que `POST /api/becas/personas/consultar/`; existe aparte porque aquella exige `becas.campo`.

```json
{"dni": "30111222", "sexo": "F"}
```

`dni` se queda con los dígitos; `sexo` es `F` o `M` (admite minúscula). `relevamiento`, si viene, se
ignora: Emergencia no tiene padrones y consulta solo Base de Personas.

```json
{"success": true, "origen": "personas",
 "data": {"nombre": "Rosa", "apellido": "Benitez", "fecha_nacimiento": "1984-03-02",
          "localidad_id": null, "localidad_texto": "", "dni": "30111222", "sexo": "F"},
 "datos_api": {}}
```

| Código | Cuerpo | Cuándo |
|---|---|---|
| 400 | `{"success": false, "error": "DNI y sexo (F o M) son requeridos."}` | Falta el DNI o el sexo |
| 404 | `{"success": false, "error": "…"}` | La persona no figura: pedir nombre y apellido (alta mínima) |
| 404 | `{"success": false, "fallecido": true, "error": "…"}` | Base de Personas la informa fallecida |
| 429 | cuerpo estándar de DRF, con `Retry-After` | Se pasó el tope |
| 502 | `{"success": false, "error": "…"}` | Base de Personas no respondió |

El tope es **por usuario** (120 por hora) y la cubeta es **la misma** que la de la consulta de Becas:
quien tiene los dos módulos no suma dos cuotas.

## 5. Localidades

`GET /api/emergencia/localidades/` — las localidades de la provincia, por nombre, **sin paginar**. La
app guarda la lista entera al entrar al módulo y la refresca una vez por día.

```json
[{"id": 12, "nombre": "Barranqueras"}, {"id": 3, "nombre": "Resistencia"}]
```

No trae coordenadas: no se puede preseleccionar «la más cercana al GPS». El `id` es el que va en
`localidad` del envío.

## 6. Enviar una familia

`POST /api/emergencia/casos/` — `multipart/form-data` (también acepta JSON si no hay fotos).

| Campo | Tipo | Obligatorio | Regla |
|---|---|---|---|
| `uuid_cliente` | UUID | **sí** | Lo genera el celular al abrir el formulario. Identifica el envío (ver «Idempotencia») |
| `relevado_en` | fecha y hora ISO 8601 con zona | no | Hora del teléfono al tocar «Enviar». Ver «Hora del relevamiento» |
| `traslado` | texto | **sí** | `BOMBEROS`, `EJERCITO`, `DEFENSA_CIVIL`, `POLICIA`, `MUNICIPIO`, `AUTOEVACUADO`, `OTRA` |
| `traslado_otro` | texto | si `traslado` es `OTRA` | Hasta 60 caracteres |
| `dni` | texto | **sí** | DNI del responsable, 7 u 8 dígitos |
| `nombre`, `apellido` | texto | si la persona no está en el legajo | Alta mínima del responsable |
| `fecha_nacimiento` | `AAAA-MM-DD` | no | Solo se usa en el alta mínima |
| `telefono` | texto | no | Contacto para la mesa |
| `documento_extraviado` | booleano | no | Perdió el documento pero sabe el número |
| `menores_f`, `menores_m`, `adultos_f`, `adultos_m`, `mayores_f`, `mayores_m` | entero ≥ 0 | no (valen 0) | La suma tiene que ser ≥ 1. El responsable está incluido |
| `dependientes` | entero ≥ 0 | no | ≤ total |
| `mayores_dependientes` | entero ≥ 0 | no | ≤ mayores |
| `lactantes` | entero ≥ 0 | no | ≤ menores |
| `embarazo`, `electrodependiente`, `medicacion_critica`, `mascotas` | booleano | no | En multipart: `true` / `false` |
| `direccion` | texto | **sí** | Calle y número o una referencia. Hasta 240 caracteres |
| `localidad` | entero | no | `id` de §5 |
| `latitud`, `longitud` | decimal | no | Van juntas. Sin GPS no se mandan |
| `precision_m` | decimal | no | Precisión del GPS en metros |
| `observaciones` | texto | no | |
| `foto_vivienda`, `foto_acceso` | archivo | no | Ver «Fotos» |

Cualquier otra clave se ignora. En particular **`total` y `prioridad` no se leen**: los calcula el
servidor.

Respuesta **201** (creado) o **200** (ya existía), con el mismo cuerpo:

```json
{"id": 184, "numero": "2026-000184", "prioridad": "MEDIA", "total_declarado": 5}
```

`prioridad` es `ALTA`, `MEDIA` o `BAJA`. El caso nace `NUEVO`, sin tomar.

### Idempotencia

- El mismo `uuid_cliente` enviado otra vez por el mismo usuario devuelve **200** con el caso que ya
  existía. **No se vuelve a validar ni se escribe nada**: no importa qué traiga el segundo cuerpo.
- La cola sin señal reintenta con el mismo `uuid_cliente` hasta recibir 200 o 201.
- Tras un **400**, el agente corrige y reenvía con el **mismo** `uuid_cliente`: ese envío no creó nada.
- **409 `UUID_EN_USO`**: el identificador ya creó un caso de otro usuario. No es un reenvío.

```json
{"detail": "Ese identificador de envío ya se usó en otro caso.", "code": "UUID_EN_USO"}
```

### Fotos

- Hasta dos: `foto_vivienda` y `foto_acceso`, una de cada una, en el mismo request que el caso.
- **Solo JPEG** (extensión `.jpg` o `.jpeg` y contenido JPEG de verdad) y hasta **5 MB** cada una. HEIC,
  HEIF, PNG y WEBP se rechazan: la app convierte y comprime antes de enviar (objetivo: 3 MB).
- Una foto rechazada rechaza el envío entero (400): no queda un caso sin su foto.
- La respuesta no devuelve las fotos. Se guardan detrás de login y solo las ve la mesa.

### Hora del relevamiento

`relevado_en` es la **única** hora del teléfono que se guarda; ningún tiempo del SLA se calcula con
ella. La hora de recepción (`creado_en` en «Mis envíos») es del servidor.

| `relevado_en` | Qué pasa |
|---|---|
| No viene | Vale la hora del servidor |
| En el pasado, aunque sean días | Se guarda como vino (un envío puede esperar sin señal) |
| Adelantada hasta 5 minutos | Se guarda como vino |
| Adelantada entre 5 minutos y 24 horas | Se guarda la hora del servidor (reloj mal puesto) |
| Adelantada más de 24 horas | 400 en `relevado_en` |

### Errores del envío

400, con `code: "VALIDACION"`, un `detail` legible (el primer mensaje), `non_field_errors` con todos los
mensajes y **una clave por cada campo con error**, cada una con su lista de mensajes:

```json
{"total": ["Cargá al menos una persona."],
 "direccion": ["Escribí la dirección o una referencia: es el mínimo para ubicar a la familia."],
 "detail": "Cargá al menos una persona.",
 "non_field_errors": ["Cargá al menos una persona.",
                      "Escribí la dirección o una referencia: es el mínimo para ubicar a la familia."],
 "code": "VALIDACION"}
```

Las claves de campo son los nombres de la tabla de arriba, más `total` cuando las seis cantidades suman
cero. Los casos que la app tiene que esperar: falta `uuid_cliente`; `traslado` vacío o desconocido;
`traslado_otro` vacío con `OTRA`; `dni` inválido; `nombre` cuando la persona no está en el legajo;
`total`; `dependientes`, `mayores_dependientes` o `lactantes` fuera de rango; `direccion` vacía o larga;
`localidad` que no existe; `latitud` fuera de rango; `foto_vivienda` o `foto_acceso` que no es JPEG o
pasa de 5 MB; `relevado_en` ilegible o adelantada más de un día.

## 7. Mis envíos

`GET /api/emergencia/casos/mios/` — los últimos **50** casos que el agente relevó en territorio, del
más nuevo al más viejo, sin paginar.

```json
[{"numero": "2026-000185", "estado": "EN_GESTION", "total_declarado": 2,
  "creado_en": "2026-11-12T10:05:00-03:00"},
 {"numero": "2026-000184", "estado": "NUEVO", "total_declarado": 5,
  "creado_en": "2026-11-12T10:00:00-03:00"}]
```

`estado`: `NUEVO`, `EN_GESTION`, `DERIVADO`, `INGRESO_EN_CURSO`, `ALOJADO` o `CERRADO`. `creado_en` es
cuándo lo recibió el servidor. La lista local de la app (pendiente de envío, error) no sale de acá: esto
es lo que ya llegó.

## 8. Índice

`GET /api/emergencia/` — las rutas del namespace, con su URL absoluta. La app no la necesita.

```json
{"perfil": "https://…/api/emergencia/perfil/",
 "personas/consultar": "https://…/api/emergencia/personas/consultar/",
 "localidades": "https://…/api/emergencia/localidades/",
 "casos": "https://…/api/emergencia/casos/",
 "casos/mios": "https://…/api/emergencia/casos/mios/",
 "mis-dispositivos": "https://…/api/emergencia/mis-dispositivos/"}
```

Las rutas que llevan un id (entregas, dispositivos, derivaciones, casos) no figuran en el índice.

## 9. Mis dispositivos

`GET /api/emergencia/mis-dispositivos/` — los dispositivos donde el usuario es de la guardia de
Emergencia: tiene `dispositivo.admitir` **o** `emergencia.recibir_kit` en su Equipo (el administrador del
programa Dispositivos los ve todos). Por nombre, **sin paginar**. Con más de uno, la app pide elegir el
dispositivo primero (RU-5).

```json
[{"id": 7, "nombre": "Club Sarmiento", "entregas_pendientes": 2, "plazas_libres": 9, "derivaciones_pendientes": 1},
 {"id": 9, "nombre": "Escuela 12", "entregas_pendientes": 0, "plazas_libres": 3, "derivaciones_pendientes": 0}]
```

- `entregas_pendientes`: cuántas entregas de kits puede recibir el usuario en ese dispositivo (en camino
  o preparadas). Es `0` donde solo admite familias y no recibe kits.
- El agente territorial, que abre el módulo pero no es de ninguna guardia, recibe `[]`.
- `plazas_libres` (PR 8): camas libres ahora —la misma cuenta que `buscar` (§13.2)—. `0` donde el
  usuario solo recibe kits.
- `derivaciones_pendientes` (PR 8): derivaciones por aceptar o rechazar. `0` donde solo recibe kits.

## 10. Entregas de un dispositivo

`GET /api/emergencia/dispositivos/{id}/entregas/` — las entregas de kits del dispositivo `id`, que tiene
que ser uno donde el usuario recibe kits (si no, 404).

- Con `?pendientes=1`: las que esperan recepción —`EN_CAMINO` y también `PREPARADA`, por si llegó sin que
  la mesa la marcara—, de la más vieja a la más nueva, sin tope. Es la lista de M3-1.
- Sin el parámetro: las últimas **50** de cualquier estado, de la más nueva a la más vieja.

```json
[{"id": 31, "numero": "2026-K-000031", "estado": "EN_CAMINO",
  "despachada_en": "2026-11-12T10:00:00-03:00", "recibida_en": null,
  "observacion_mesa": "Entregar a la directora.", "observacion_dispositivo": "",
  "lineas": [{"item": 12, "nombre": "Colchón", "unidad": "unidad", "enviada": 10, "recibida": null},
             {"item": 14, "nombre": "Kit alimentario", "unidad": "kit", "enviada": 3, "recibida": null}]}]
```

| Clave | Qué es |
|---|---|
| `id` | El que va en las rutas de §11 y §12 |
| `numero` | Número legible de la entrega, «2026-K-000031» |
| `estado` | `PREPARADA`, `EN_CAMINO`, `RECIBIDA`, `RECIBIDA_CON_DIFERENCIAS` o `CANCELADA` |
| `despachada_en` | Cuándo salió. `null` si la mesa no la marcó en camino |
| `recibida_en` | Cuándo se confirmó la recepción (hora del servidor). `null` si todavía no |
| `observacion_mesa` | Nota de la mesa para quien recibe. Puede venir vacía |
| `observacion_dispositivo` | Lo que escribió quien la recibió. Vacía hasta la recepción |
| `lineas[].item` | `id` del ítem: es la clave de `cantidades[<id>]` en §12 |
| `lineas[].nombre`, `lineas[].unidad` | Para mostrar. La unidad es la del momento en que se armó la entrega |
| `lineas[].enviada` | Lo que salió: con esto se **precarga** la cantidad a confirmar |
| `lineas[].recibida` | Lo que se confirmó. `null` hasta la recepción |

La respuesta no trae la foto del remito: se guarda detrás de login y la ven la mesa y el equipo del
dispositivo desde el backoffice.

## 11. Una entrega

`GET /api/emergencia/entregas/{id}/` — **la misma forma** que cada elemento de §10. 404 si no existe o
es de un dispositivo donde el usuario no recibe kits.

## 12. Recibir una entrega

`POST /api/emergencia/entregas/{id}/recibir/` — `multipart/form-data`. **Requiere conexión**: no se
encola (la mesa está esperando la respuesta, y una recepción hecha mientras tanto desde el backoffice
daría 409).

| Campo | Tipo | Obligatorio | Regla |
|---|---|---|---|
| `uuid_cliente` | UUID | **sí** | Lo genera el celular al abrir la recepción. Identifica el envío (ver «Idempotencia») |
| `cantidades[<id del ítem>]` | entero ≥ 0 | **sí, uno por cada línea** | Cuánto llegó de ese ítem, aunque sea `0`. Ejemplo: `cantidades[12]=8` |
| `remito` | archivo | **sí** | Foto del remito. **Solo JPEG** (extensión `.jpg`/`.jpeg` y contenido JPEG de verdad), hasta **5 MB** |
| `observacion` | texto | no | Lo que la mesa tiene que saber |

Vale sobre una entrega `EN_CAMINO` y también sobre una `PREPARADA`. Respuesta **200**:

```json
{"estado": "RECIBIDA_CON_DIFERENCIAS",
 "diferencias": [{"item": 12, "enviada": 10, "recibida": 8}]}
```

- `estado`: `RECIBIDA` si todas las cantidades coinciden con lo enviado; `RECIBIDA_CON_DIFERENCIAS` si
  alguna difiere. **Llegar de más también es una diferencia.**
- `diferencias`: solo las líneas donde `recibida` es distinta de `enviada`; `[]` si llegó completa. El
  nombre del ítem sale de `lineas` (§10), por `item`.

Después de confirmada, la recepción **no se corrige**: no hay ruta para cambiar las cantidades.

### Idempotencia

- El mismo `uuid_cliente` enviado otra vez sobre la misma entrega devuelve **200** con el mismo cuerpo
  que la primera vez. **No se vuelve a validar ni se escribe nada**: no importa qué traiga el segundo
  cuerpo (ni siquiera hace falta el remito).
- Tras un **400**, se corrige y se reenvía con el **mismo** `uuid_cliente`: ese envío no escribió nada.
- **409 `UUID_EN_USO`**: ese identificador ya es el de la recepción de **otra** entrega.

```json
{"detail": "Ese identificador de envío ya se usó en otra recepción.", "code": "UUID_EN_USO"}
```

### La entrega ya no se puede recibir (409)

Otra guardia la confirmó —desde su teléfono, con otro `uuid_cliente`, o desde el backoffice— o la mesa
la canceló mientras se cargaba la recepción. No se escribe nada y el remito no se guarda.

```json
{"detail": "Entrega 2026-K-000031 cancelada por la mesa a las 15:02. Ya no se puede recibir.",
 "estado_actual": "CANCELADA"}
```

`estado_actual` es `RECIBIDA`, `RECIBIDA_CON_DIFERENCIAS` o `CANCELADA`. La app muestra `detail` y
recarga la lista de entregas.

### Errores de la recepción

400, con la misma forma que el de §6 (`code: "VALIDACION"`, `detail`, `non_field_errors` y una clave por
campo con error):

```json
{"remito": ["Falta la foto del remito."], "detail": "Falta la foto del remito.",
 "non_field_errors": ["Falta la foto del remito."], "code": "VALIDACION"}
```

| Clave | Cuándo |
|---|---|
| `uuid_cliente` | Falta o no es un UUID |
| `cantidades` | No viene ninguna; falta la de algún ítem de la entrega (el mensaje dice cuál); alguna no es un entero ≥ 0; viene la de un ítem que no es de la entrega |
| `remito` | Falta; no es JPEG; pasa de 5 MB |

404: la entrega no existe o es de un dispositivo donde el usuario no recibe kits. 403 `SIN_MODULO`: el
usuario no recibe kits en ningún dispositivo.

## 13. M2 · Llegada de familias

La guardia del dispositivo recibe a la familia: la busca por DNI, acepta o rechaza la derivación,
confirma a cada persona con su ficha mínima y su cama, y cierra el ingreso (N de N, o con diferencia).
Sin derivación, ingresa igual o avisa a la mesa. Es **la misma secuencia y las mismas reglas** que la
pantalla E6 del backoffice: las dos llaman a las mismas funciones del servidor (RU-1, RU-2), así que lo
que una guardia hace desde la PC la otra lo ve desde el teléfono, y al revés.

Todas las rutas exigen el permiso **llegadas** (§2) y el alcance por dispositivo. **Requieren conexión**
(RU-3, RN-3.11): aceptar, confirmar y alojar trabajan sobre camas compartidas con toda la red y no se
encolan. La app avisa antes de empezar («Sin conexión: no podés reservar camas»). Lo único que se encola
es el **ingreso directo** (§13.10).

### 13.1 Recorrido

```
mis-dispositivos ─► buscar?dni= ─┬─ DERIVACION (PENDIENTE) ─► aceptar ─► integrantes ─► confirmar × N ─► alojar
                                 │                          └► rechazar                └► cerrar-diferencia
                                 │   DERIVACION (ACEPTADA) ─────────────► integrantes        └► cancelar-ingreso
                                 ├─ SIN_DERIVACION ─┬─ plazas_libres ≥ 1 ─► ingreso-directo ─► integrantes …
                                 │                  └─ avisar-mesa
                                 └─ ALOJADA (fin)
```

El estado del recorrido es **el del caso en el servidor**, no el del teléfono: ante cualquier 409 la
app recarga la pantalla que corresponde a `estado_actual`.

| `estado_actual` | Pantalla a la que vuelve la app |
|---|---|
| `DERIVADO` | M2-2 (la derivación sigue pendiente) |
| `INGRESO_EN_CURSO` | M2-3, integrantes |
| `ALOJADO`, `CERRADO` | M2-3 en modo lectura (familia alojada) |
| `EN_GESTION`, `NUEVO` | M2-1: el caso volvió a la mesa; buscar de nuevo |

### 13.2 Buscar a la familia

`GET /api/emergencia/dispositivos/{id}/buscar/?dni=30111222` — el DNI del responsable **o de cualquier
persona ya confirmada** de la familia. `{id}` es un dispositivo de «mis dispositivos».

Las ocho claves vienen **siempre**; las que no aplican al resultado, en `null` (o `""`).

```json
{"resultado": "DERIVACION", "dni": "30111222", "plazas_libres": 9,
 "mensaje": "",
 "derivacion": {
   "id": 55, "estado": "PENDIENTE", "plazas_pedidas": 7,
   "vence_en": "2026-11-12T12:00:00-03:00", "vencida": false,
   "derivada_en": "2026-11-12T10:00:00-03:00", "derivada_por": "Ana López",
   "caso": {"id": 184, "numero": "2026-000184", "estado": "DERIVADO", "prioridad": "ALTA", "total_declarado": 7},
   "responsable": {"nombre": "Rosa", "apellido": "Benítez", "dni": "30111222"},
   "grupo": {"menores_f": 2, "menores_m": 3, "adultos_f": 1, "adultos_m": 1, "mayores_f": 0, "mayores_m": 0,
             "dependientes": 0, "mayores_dependientes": 0, "lactantes": 1},
   "necesidades": ["embarazo"], "telefono": "3624000000", "observaciones": "Vienen con un perro."},
 "alojada_aca": null, "alojada_en": "", "alojada_desde": null}
```

| `resultado` | Qué significa | Qué hace la app |
|---|---|---|
| `DERIVACION` | Hay una derivación `PENDIENTE` o `ACEPTADA` **hacia este dispositivo** | `PENDIENTE` → M2-2 (aceptar o rechazar). `ACEPTADA` → M2-3 con `derivacion.caso.id` |
| `SIN_DERIVACION` | No hay nada para este dispositivo. **Incluye** una derivación a otro: no se dice cuál ni que existe (RU-9) | M2-6: «Ingresar igual» si `plazas_libres ≥ 1`, y «Avisar a la mesa». Mostrar `mensaje` (si la derivación de acá venció, lo dice) |
| `ALOJADA` | La persona tiene una estadía abierta en la red | Mostrar `mensaje` y nada más. `alojada_aca`: si es en este dispositivo. `alojada_en` y `alojada_desde`, solo si el usuario puede ver ese dispositivo; si no, vacíos |

- `vencida: true` es una derivación pendiente con `vence_en` pasado que la mesa todavía no marcó: **se
  puede aceptar igual** (RN-3.3; la familia está en la puerta).
- `necesidades`: los avisos del Formulario 1 marcados en `true` (`embarazo`, `electrodependiente`,
  `medicacion_critica`, `mascotas`).
- 400 `dni` si viene vacío o no es un DNI.

### 13.3 Aceptar la derivación

`POST /api/emergencia/derivaciones/{id}/aceptar/` (JSON). `{id}` es `derivacion.id` de §13.2.

```json
{"uuid_cliente": "6b1f…"}
```

`uuid_cliente` es opcional y **no se guarda**: aceptar no es idempotente. Si la respuesta se pierde y la
app reintenta, recibe 409 con `estado_actual: "INGRESO_EN_CURSO"` y sigue a los integrantes, que es lo
mismo que habría hecho con el 200.

Respuesta **200**:

```json
{"caso": {"id": 184, "numero": "2026-000184", "estado": "INGRESO_EN_CURSO", "prioridad": "ALTA", "total_declarado": 7},
 "reservadas": 5, "faltantes": 2, "mensaje": "Reservé 5 de 7 · faltan 2 camas",
 "integrantes": [{"n": 1, "estado": "SIN_CONFIRMAR", …}, …]}
```

- Reserva **hasta** `plazas_pedidas` camas, elegidas por el servidor (el sector con más libres primero).
  Menos de las pedidas es válido: `faltantes > 0` y la app muestra `mensaje`. Se puede seguir.
- `integrantes`: las N filas de la familia (§13.5), todas sin confirmar.
- 400 `plazas`: el dispositivo no tiene **ninguna** cama libre («Sin plazas · rechazá con motivo o liberá
  camas»), o una cama se ocupó mientras se aceptaba (volver a tocar «Aceptar»).
- 409: otra guardia ya la aceptó (desde su teléfono o desde el backoffice), la mesa la canceló o el cron
  la venció.

### 13.4 Rechazar la derivación

`POST /api/emergencia/derivaciones/{id}/rechazar/` (JSON).

| Campo | Obligatorio | Regla |
|---|---|---|
| `motivo` | **sí** | `SIN_PLAZAS` (Sin plazas), `NO_CUMPLE_PERFIL` (No cumple perfil), `NO_LLEGO` (No llegó), `OTRO` |
| `observacion` | con `OTRO` | Qué pasó |

Respuesta **200** `{"caso_estado": "EN_GESTION"}`: el caso volvió a la mesa con el motivo. 400 `motivo`
u `observacion`; 409 si ya no estaba pendiente.

### 13.5 Integrantes (M2-3)

`GET /api/emergencia/casos/{id}/integrantes/` — `{id}` es `caso.id`.

```json
{"caso": {"id": 184, "numero": "2026-000184", "estado": "INGRESO_EN_CURSO", "prioridad": "ALTA", "total_declarado": 7},
 "integrantes": [
   {"n": 1, "estado": "CONFIRMADA", "ficha_completa": false,
    "persona": {"id": 9, "nombre": "Benítez, Rosa", "dni": "30111222"},
    "plaza": {"id": 41, "codigo": "B-12", "nombre": "B-12 (Pabellón B)"},
    "parentesco": "Jefe/a de hogar",
    "confirmada_en": "2026-11-12T10:20:00-03:00", "egresado_en": null},
   {"n": 2, "estado": "SIN_CONFIRMAR", "ficha_completa": false, "persona": null, "plaza": null,
    "parentesco": "", "confirmada_en": null, "egresado_en": null}],
 "confirmadas": 1, "total_declarado": 7, "declaradas_al_relevar": 7, "con_ficha_incompleta": 1}
```

| Clave | Qué es |
|---|---|
| `integrantes[].n` | Número de la persona en la familia (1 a `total_declarado`): va en las rutas de §13.6 a §13.8 |
| `integrantes[].estado` | `SIN_CONFIRMAR`, `CONFIRMADA` o `EGRESADA` (confirmada que ya se fue) |
| `integrantes[].ficha_completa` | Secciones 4 a 8 con algún dato o «sin datos». `false` → «ficha incompleta» |
| `integrantes[].plaza` | La cama **de hoy** (si la cambiaron desde el mapa, la nueva) |
| `confirmadas` / `total_declarado` | El contador «1 de 7 confirmadas» |
| `declaradas_al_relevar` | Lo que dijo el Formulario 1. Si `total_declarado` es mayor, «llegaron 8 sobre 7» |

Con `confirmadas == total_declarado` la app ofrece «Familia alojada» (§13.9); con `0 < confirmadas <
total_declarado`, «Cerrar con diferencia»; con `0`, «Cancelar ingreso».

Abre con el ingreso aceptado: `INGRESO_EN_CURSO`, `ALOJADO` o `CERRADO`. Antes de aceptar o después de
un rechazo o una cancelación, 409 con `estado_actual`.

**Agregar persona** (RN-3.8): `POST /api/emergencia/casos/{id}/integrantes/` con `{"uuid_cliente": "…"}`
(obligatorio). Respuesta **201** `{"integrante": {…fila…}, "total_declarado": 8}`; el reenvío del mismo
`uuid_cliente` devuelve **200** con la misma fila, sin sumar otra. La persona nueva no tiene cama
reservada: se elige una libre al confirmarla.

### 13.6 Una persona y su ficha

`GET /api/emergencia/casos/{id}/integrantes/{n}/` — la fila de §13.5 más:

- `ficha`: el Formulario 2 guardado (§13.11), para precargar la pantalla. `{}` sin confirmar.
- `secciones_incompletas`: los rótulos de las secciones 4 a 8 que faltan, en orden («Educación», …).

404 si `n` no es de la familia.

**Completar la ficha** (secciones 4 a 8, con el ingreso en curso o la familia ya alojada):
`PATCH /api/emergencia/casos/{id}/integrantes/{n}/` (JSON).

```json
{"ficha": {"educacion": {"nivel_educativo": "PRIMARIO", "asiste_escuela": true},
           "vacunacion": {"sin_datos": true}}}
```

Cada sección **que viene** reemplaza a la guardada; las que no vienen quedan como estaban. Las tres del
mínimo no se cambian por acá. Respuesta **200** `{"ficha_completa": false, "secciones_incompletas":
["Salud y medicación", "Trabajo", "Observaciones, mascotas y adulto responsable"]}`. 400 `orden` si la
persona todavía no se confirmó, o por campo si un valor no es del tipo.

### 13.7 Mapa de camas

`GET /api/emergencia/dispositivos/{id}/plazas/?caso=184` — para elegir la cama de una persona.

```json
{"caso": 184,
 "sectores": [
   {"sector": {"id": 3, "nombre": "Pabellón A", "perfil": "Familias"},
    "plazas": [
      {"id": 41, "codigo": "A-01", "nombre": "A-01 (Pabellón A)", "estado": "RESERVADA_FAMILIA",
       "elegible": true, "texto": "Reservada para esta familia", "tono": "warning", "detalle": ""},
      {"id": 42, "codigo": "A-02", "nombre": "A-02 (Pabellón A)", "estado": "OCUPADA",
       "elegible": false, "texto": "Ocupada", "tono": "info", "detalle": ""}],
    "total": 40, "libres": 12, "reservadas_familia": 7}]}
```

| `estado` | Elegible | Qué es |
|---|---|---|
| `RESERVADA_FAMILIA` | sí | Guardada para **esta** familia al aceptar. Son las que se eligen por defecto (resaltadas) |
| `LIBRE` | sí | Libre, sin reserva. Para cuando la familia creció o se cambia la cama |
| `OCUPADA` | no | Con una persona alojada |
| `FUERA_SERVICIO` | no | `detalle` trae el motivo |
| `RESERVADA` | no | Guardada para **otra** persona o familia. No se dice para quién |

- La app mira solo `elegible` para dejar elegir. `texto` y `tono` son los del backoffice: se pueden
  ignorar.
- `?caso=` tiene que ser un caso derivado a **este** dispositivo (si no, 404). Sin él, ninguna cama
  sale `RESERVADA_FAMILIA`.
- Sectores activos que tienen camas, por nombre; camas por código, **a lo sumo 200 por sector** (`total`
  dice cuántas hay).

### 13.8 Confirmar a una persona (M2-4)

`POST /api/emergencia/casos/{id}/integrantes/{n}/confirmar/` (JSON).

```json
{"uuid_cliente": "0c6e…",
 "plaza_id": 41,
 "ficha": {
   "parentesco": {"parentesco": "HIJO"},
   "datos_personales": {"dni": "45111222", "nombre": "Juan", "apellido": "Benítez", "sexo": "M",
                        "fecha_nacimiento": "2012-03-10"},
   "avisos_salud": {"embarazo": false, "discapacidad": false, "electrodependiente": false,
                    "medicacion_critica": false, "alergias_graves": false},
   "observaciones": {"adulto_responsable": "Rosa Benítez"}}}
```

| Campo | Obligatorio | Regla |
|---|---|---|
| `uuid_cliente` | **sí** | Lo genera el celular al abrir la ficha. Ver «Idempotencia» |
| `ficha` | **sí** | El Formulario 2 (§13.11): el mínimo y, si se quiere, las secciones 4 a 8 |
| `plaza_id` | **sí** | Una cama `elegible` de §13.7 |

En **una** transacción: alta mínima de la persona si no está en el legajo, su vínculo con el
responsable, la estadía en esa cama (la reserva de la familia se consume) y la fila confirmada. Si algo
falla no queda nada a medias.

Respuesta **201**:

```json
{"integrante": {"n": 2, "estado": "CONFIRMADA", "ficha_completa": false, "persona": {…}, "plaza": {…}, …},
 "confirmadas": 2, "total_declarado": 7, "reserva_liberada": false}
```

`reserva_liberada: true` cuando la persona entró en una cama `LIBRE` y la familia ya tenía más camas
reservadas que personas por confirmar: el servidor devolvió una (la familia nunca retiene camas de más).

**Idempotencia.** El mismo `uuid_cliente` otra vez sobre la misma persona devuelve **200** con la misma
fila, sin escribir nada. La persona confirmada por **otro** envío (otra guardia, desde el teléfono o el
backoffice) es **409**.

Errores 400 (`code: "VALIDACION"`, una clave por campo, **con el nombre plano del campo de la ficha**):

| Clave | Cuándo |
|---|---|
| `parentesco`, `parentesco_otro` | Falta el parentesco, o el texto con `OTRO` |
| `dni` | Falta o no es un número de DNI («Sin un número de DNI válido no se puede confirmar… cerrá con diferencia»); la persona ya está confirmada en esta familia; ya tiene una estadía abierta en la red (dice dónde solo si el usuario puede ver ese dispositivo) |
| `nombre`, `apellido`, `sexo`, `fecha_nacimiento` | Faltan (si la persona ya está en el legajo, alcanza con el DNI) |
| `embarazo`, `discapacidad`, `electrodependiente`, `medicacion_critica`, `alergias_graves` | Sin responder: las cinco van, aunque sea `false` |
| `medicacion_critica_nombre`, `medicacion_critica_tiene_dosis` | Con `medicacion_critica: true` |
| `adulto_responsable` | La persona tiene menos de 16 años |
| `plaza` | Sin `plaza_id`; la cama no es de este dispositivo, está ocupada, fuera de servicio o reservada para otra persona; no queda ninguna cama libre («Sin cama libre · liberá una o cerrá con diferencia») |
| `orden` | `n` no es de la familia |
| otra clave de la ficha | El valor no es del tipo (opción fuera de lista, fecha ilegible, texto largo) |

### 13.9 Cerrar el ingreso

**Familia alojada** (M2-5, con N de N confirmadas): `POST /api/emergencia/casos/{id}/alojar/` (JSON).

| Campo | Obligatorio | Regla |
|---|---|---|
| `sector` | no | `id` de un sector del dispositivo (los de §13.7). Preseleccionar el de las camas de la familia |
| `aula` | no | Aula o dormitorio, hasta 80 caracteres |
| `tarjeta_entregada` | no | Booleano |
| `tarjeta_numero` | con la tarjeta entregada | Hasta 40 caracteres |
| `encargado` | no | Quién recibe; vacío vale el usuario |

**Cerrar con diferencia** (RN-3.9, llegaron menos, con al menos una confirmada):
`POST /api/emergencia/casos/{id}/cerrar-diferencia/` con `{"motivo", "observacion"}`. `motivo`:
`QUEDO_CON_FAMILIARES`, `NO_LLEGO` (No llegó al centro), `DERIVADO_A_SALUD`, `OTRO` (con `observacion`
obligatoria). Es también el cierre para quien no sabe su número de DNI: `OTRO` y contarlo.

**Cancelar el ingreso** (sin nadie confirmado; el caso vuelve a la mesa):
`POST /api/emergencia/casos/{id}/cancelar-ingreso/` con `{"motivo"}` (texto obligatorio, hasta 200).

Las tres responden **200** con la misma forma:

```json
{"estado": "ALOJADO", "total_alojado": 5, "liberadas": 2}
```

| | `estado` | `total_alojado` | `liberadas` |
|---|---|---|---|
| Alojar | `ALOJADO` | N | Reservas que sobraban (la mesa pidió más camas que personas) |
| Diferencia | `ALOJADO` | Las confirmadas | Las reservas sin usar |
| Cancelar | `EN_GESTION` (o `NUEVO` si era un ingreso directo) | `null` | Todas las de la familia |

`estado` puede ser `CERRADO` si al alojar ya no quedaba nadie con estadía abierta. 400 por campo, o en
`non_field_errors` cuando la acción no corresponde al contador (alojar con alguien sin confirmar,
diferencia sin nadie o con todos confirmados, cancelar con alguien confirmado). 409 si el ingreso ya no
está en curso.

### 13.10 Sin derivación: ingresar igual o avisar a la mesa (M2-6)

**Ingresar igual**: `POST /api/emergencia/dispositivos/{id}/ingreso-directo/` — `multipart/form-data`,
el **mismo Formulario 1 de §6** con dos diferencias: **no** lleva `relevado_en`, y `direccion` y
`localidad` son opcionales (sin ellas valen las del dispositivo). Exige al menos una cama libre.

Respuesta **201**:

```json
{"caso": {"id": 190, "numero": "2026-000190", "estado": "INGRESO_EN_CURSO", "prioridad": "MEDIA", "total_declarado": 3},
 "reservadas": 3, "faltantes": 0, "integrantes": [{"n": 1, "estado": "SIN_CONFIRMAR", …}, …]}
```

El caso nace con origen dispositivo y el ingreso ya en curso (sin pasar por la mesa), con las camas que
alcanzaron reservadas: se sigue en §13.5. **Es lo único de M2 que se encola sin señal** (RU-3): la
cola reintenta con el **mismo** `uuid_cliente` hasta recibir 200 o 201; el reenvío devuelve **200** con
el mismo caso y lo que reservó la primera vez, sin volver a mirar las camas. 409 `UUID_EN_USO` si ese
identificador ya creó un caso de otro usuario. 400 como §6, más `plazas` (no hay camas libres; mostrar
«Avisar a la mesa») y `dispositivo` (no recibe familias).

**Avisar a la mesa**: `POST /api/emergencia/dispositivos/{id}/avisar-mesa/` — el mismo cuerpo. Crea el
caso `NUEVO` con la marca «En la puerta de …»; la mesa lo deriva y la guardia busca de nuevo. No exige
camas. Respuesta **201** (o **200** en el reenvío) `{"caso": {…}}`. Idempotente igual que el ingreso
directo.

### 13.11 La ficha individual (Formulario 2)

Esquema **fijo y versionado** (decisión 6 del PM). La única definición es
`ESQUEMA_FICHA` en `programas/services/emergencia_alojar.py`; lo de abajo es su copia para la app.
Se manda anidada por sección; lo que no es del esquema se ignora. Una pregunta sin responder **no se
manda** (o se manda `null` o `""`); `false` **es** una respuesta. Lo que se guarda lleva además
`"version": 1`.

| Sección | Campo | Tipo | Mínimo |
|---|---|---|---|
| `parentesco` | `parentesco` | `JEFE`, `CONYUGE`, `HIJO`, `OTRO` | **sí** |
| | `parentesco_otro` | texto ≤ 80 | con `OTRO` |
| `datos_personales` | `dni` | texto ≤ 12 (se queda con los dígitos) | **sí** |
| | `nombre`, `apellido` | texto ≤ 120 | **sí** (los completa el legajo si la persona existe) |
| | `sexo` | `F`, `M`, `X` | **sí** (ídem) |
| | `fecha_nacimiento` | `AAAA-MM-DD` | **sí** (ídem; vale aproximada) |
| | `fecha_nacimiento_aproximada` | booleano | no |
| | `telefono` | texto ≤ 40 | no |
| | `documento_extraviado` | booleano | no |
| `avisos_salud` | `embarazo`, `discapacidad`, `electrodependiente`, `medicacion_critica`, `alergias_graves` | booleano | **las cinco respondidas** |
| | `medicacion_critica_nombre` | texto ≤ 200 | con `medicacion_critica: true` |
| | `medicacion_critica_tiene_dosis` | booleano | con `medicacion_critica: true` |
| | `alergias_graves_detalle` | texto ≤ 200 | no |
| `educacion` | `nivel_educativo` | `SIN_INSTRUCCION`, `INICIAL`, `PRIMARIO`, `SECUNDARIO`, `TERCIARIO`, `UNIVERSITARIO` | no |
| | `escuela` | texto ≤ 200 | no |
| | `asiste_escuela` | booleano | no |
| `vacunacion` | `esquema_al_dia` | booleano | no |
| | `vacunacion_observacion` | texto ≤ 500 | no |
| `salud` | `obra_social` | texto ≤ 120 | no |
| | `enfermedades_cronicas`, `medicacion_habitual` | texto ≤ 500 | no |
| `trabajo` | `ocupacion`, `ingresos` | texto ≤ 200 | no |
| `observaciones` | `observaciones` | texto ≤ 1000 | no |
| | `mascotas` | booleano | no |
| | `adulto_responsable` | texto ≤ 200 | **sí si la persona tiene menos de 16 años** |

Las secciones 4 a 8 (`educacion` a `observaciones`) aceptan además `"sin_datos": true` («pregunté y no
hay nada que cargar»), que cuenta como sección completa. `ficha_completa` es `true` cuando las cinco
tienen algún dato o `sin_datos`. Los nombres de campo no se repiten entre secciones: por eso los
errores 400 usan el nombre plano del campo.
