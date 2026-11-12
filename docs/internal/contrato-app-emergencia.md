# Contrato de la app de campo de Emergencia

Qué le pide la app (`Chaco-mobile`) al back para el **módulo Emergencia** y qué recibe. Las claves de
cada respuesta están fijadas con igualdad exacta en `programas/tests/test_emergencia_api_contrato.py`
(constantes `CLAVES_*`): agregar una clave es seguro; renombrarla o sacarla es un release coordinado de
la app, y el test y este documento se tocan en el mismo diff. El esquema OpenAPI publicado
(`/api/schema/`) documenta los mismos extremos.

Base: `/api/emergencia/`. Autenticación: `Authorization: Token <token>`, el mismo token del resto de la
app.

Alcance de esta versión (PR 5): login, perfil y **M1 · Ingreso de familias** (Formulario 1 del agente
territorial). Lo del dispositivo (M2 y M3) está en «Próximos», al final.

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

«Módulo» y «agente» son los dos permisos del namespace (§2).

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

Dos permisos, los dos con el mismo `code` que el resto de la app:

| Permiso | Regla | 403 |
|---|---|---|
| **Módulo** | La misma del login (§1): agente, guardia o administrador de Dispositivos | `{"detail": "El usuario no tiene acceso al módulo Emergencia.", "code": "SIN_MODULO"}` |
| **Agente** | `emergencia.relevar` en el programa Emergencia | `{"detail": "El usuario no tiene permiso para relevar familias en Emergencia. Pedile a quien administra los usuarios que te sume el rol de agente territorial.", "code": "SIN_MODULO"}` |

El token no abre nada por sí solo: un usuario de Becas recibe 403 `SIN_MODULO` en todo
`/api/emergencia/`, y un usuario de Emergencia recibe 403 `SIN_MODULO` en todo `/api/becas/` y
`/api/dispositivos/`.

| Código HTTP | `code` | Cuándo | Qué hace la app |
|---|---|---|---|
| 401 | — | Sin token o token inválido | Volver al login |
| 403 | `SIN_MODULO` | El usuario no tiene el permiso de la ruta | Mostrar `detail`; no reintentar |
| 400 | `VALIDACION` | El envío no es válido (§6) | Mostrar el detalle por campo; el agente corrige y reenvía con el **mismo** `uuid_cliente` |
| 409 | `UUID_EN_USO` | Ese `uuid_cliente` ya creó un caso de **otro** usuario | No reintentar con ese identificador |
| 429 | — | Tope de consultas de identidad (§4) | Seguir con carga manual del nombre |

## 3. Perfil

`GET /api/emergencia/perfil/` — qué accesos muestra la pantalla inicial del módulo.

```json
{"relevar": true, "dispositivo": false}
```

- `relevar`: agente territorial → «Ingreso de familias» (M1).
- `dispositivo`: guardia de un dispositivo (o administrador de Dispositivos) → «Llegada de familias»
  (M2) y «Recepción de kits» (M3).

Con los dos en `true` se muestran los tres accesos. Nunca vienen los dos en `false`: ese usuario recibe
el 403 del módulo.

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
 "casos/mios": "https://…/api/emergencia/casos/mios/"}
```

## Próximos (PR 8 y 9-API)

### M2 · Llegada de familias (PR 8)

### M3 · Recepción de kits (PR 9-API)
