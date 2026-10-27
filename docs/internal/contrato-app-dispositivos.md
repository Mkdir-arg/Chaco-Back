# Contrato de la app de campo de Dispositivos (relevamiento edilicio)

Qué le pide la app al back para el **relevamiento edilicio** y qué recibe. Los JSON de abajo
**salen de las respuestas reales** de `programas/tests/test_api_campo_relevamiento_formulario.py` y
`programas/tests/test_api_campo_inspecciones.py` (se recortan los campos repetidos, nada más). El
esquema OpenAPI publicado (`/api/schema/`) documenta los mismos extremos.

Base: `/api/dispositivos/inspecciones/`. Autenticación: `Authorization: Token <token>`.

## Qué cambió respecto de lo que la app ya conoce

| Extremo | Cambio |
|---|---|
| Login | sin cambios (`modulos` ya traía `"dispositivos"`) |
| `GET /` (listado) | suma `formulario_version` |
| `GET /{id}/` (detalle) | suma `formulario` y `formulario_version` |
| `POST /{id}/resultado/` | suma `respuestas` y `version_capturada` (opcionales) |
| `POST /{id}/adjuntos/` | **nuevo** |
| `POST /{id}/fotos/` | sin cambios |
| 403 de cualquiera de las dos APIs de campo | suma `code: "SIN_MODULO"`; `detail` igual que antes |

Todo lo que ya existía (nombres, códigos `REASIGNADA`, `YA_REALIZADA`, `CANCELADA`,
`UUID_EN_USO`, `ESTADO_NO_ADMITE`, 404 para lo ajeno, idempotencia por `uuid_cliente`) se mantiene.

## 1. Login

`POST /api/becas/auth/token/` con `{"username", "password"}`.

```json
{"token": "05d464237bbd70934fe586144a27d808e022f889", "user_id": 2, "username": "agente",
 "modulos": ["dispositivos"], "app": {"version_minima": null}}
```

`modulos` lista a qué módulos entra el usuario: `"becas"` (territorial, capacidad `becas.campo`) y/o
`"dispositivos"` (agente, capacidad `inspeccion.relevar`). Un usuario con los dos ve los dos.

## 2. Listado

`GET /api/dispositivos/inspecciones/` — la agenda del agente: sus relevamientos **en curso**, por
vencimiento. Lo realizado, cancelado o reasignado sale de la lista.

```json
[{"id": 2,
  "edificio": {"id": 1, "codigo": "ED-PREDIO", "nombre": "Predio Resistencia", "calle": "", "numero": "",
               "piso_departamento": "", "localidad": "", "provincia": "Chaco", "codigo_postal": "",
               "latitud": null, "longitud": null},
  "estado": "ASIGNADA", "fecha_vencimiento": "2026-11-26", "vencida": false, "indicaciones": "",
  "formulario_version": 10}]
```

`formulario_version`: versión **vigente** del formulario «Relevamiento»; `null` si el relevamiento no
tiene formulario (el tipo de la institución no lo definió, o se dio de baja). Sirve para decidir si el
detalle cacheado sigue valiendo.

## 3. Detalle

`GET /api/dispositivos/inspecciones/{id}/` — un relevamiento asignado al agente, en **cualquier
estado**. Con formulario:

```json
{"id": 2, "edificio": {"...": "como en el listado"}, "estado": "ASIGNADA",
 "fecha_vencimiento": "2026-11-26", "vencida": false, "indicaciones": "", "formulario_version": 10,
 "formulario": {
   "version": 10,
   "definicion": {
     "version": 10, "canal": null, "destinos_siis": [],
     "items": [{
       "tipo": "grupo", "clave": "g-38702fe6", "titulo": "Estado del edificio", "subtitulo": "",
       "condicion": null, "canal": "ambos",
       "items": [
         {"tipo_item": "campo", "clave": "cp-63007229", "texto": "Estado del techo", "tipo": "SELECTOR",
          "opciones": ["Bueno", "Malo"], "obligatorio": true, "orden": 0, "condicion": null},
         {"tipo_item": "campo", "clave": "cp-d3983d25", "texto": "Cantidad de baños", "tipo": "INT",
          "opciones": [], "obligatorio": true, "orden": 1, "condicion": null},
         {"tipo_item": "campo", "clave": "cp-f75f4536", "texto": "Detalle del daño", "tipo": "STRING",
          "opciones": [], "obligatorio": true, "orden": 2,
          "condicion": {"modo": "todas", "reglas": [{"fuente": "cp-63007229", "op": "es", "valor": "Malo"}]}},
         {"tipo_item": "campo", "clave": "cp-9ff0a198", "texto": "Servicios", "tipo": "SELECTOR_MULTIPLE",
          "opciones": ["Agua", "Gas", "Cloaca"], "obligatorio": false, "orden": 3, "condicion": null},
         {"tipo_item": "campo", "clave": "cp-06ae90eb", "texto": "Última inspección", "tipo": "DATE",
          "opciones": [], "obligatorio": false, "orden": 4, "condicion": null},
         {"tipo_item": "campo", "clave": "cp-a95ebd93", "texto": "Observación técnica", "tipo": "STRING",
          "opciones": [], "obligatorio": false, "orden": 5, "condicion": null},
         {"tipo_item": "campo", "clave": "cp-371ff354", "texto": "Plano", "tipo": "ARCHIVO",
          "opciones": [], "obligatorio": true, "orden": 6, "condicion": null}
       ]}]},
   },
 "criticidad": "", "observaciones": "", "realizada_en": null, "uuid_resultado": null,
 "motivo_cancelacion": "", "fotos": []}
```

(En la respuesta real cada campo trae además `id`, `presentacion`, `alcance`, `subsegmento_id`,
`canal`, `origen`, `vinculo`, `grupo`: los mismos que el formulario de Becas.)

- `formulario` es `null` si no hay formulario; en ese caso el resultado es solo lo fijo.
- La definición es la **vigente al momento de la consulta** (D4), no la de cuando se asignó, y usa el
  mismo formato que los formularios de Becas y los formularios por tipo. Cada campo se identifica por
  su `clave`; hay **grupos** (`tipo: "grupo"`, con `items` adentro) y textos informativos.
- `condicion`: el campo solo se muestra (y solo se exige) si se cumple. Lo oculto no se manda.
- El detalle **no devuelve** lo ya respondido ni los adjuntos: la app conserva lo que envió.
  `fotos` lista las fotos recibidas.
- Tipos de campo que puede traer: `STRING`, `INT`, `SELECTOR`, `SELECTOR_MULTIPLE`, `DATE`, `ARCHIVO`.

## 4. Resultado

`POST /api/dispositivos/inspecciones/{id}/resultado/` (JSON). Idempotente por `uuid_cliente`.

```json
{"criticidad": "MEDIA", "observaciones": "Humedad", "uuid_cliente": "3bbf2065-e61b-4883-af9b-c8ee42e84ad9",
 "version_capturada": 10,
 "respuestas": {"cp-63007229": "Bueno", "cp-d3983d25": 3, "cp-9ff0a198": ["Agua", "Gas"],
                "cp-06ae90eb": "2026-09-01", "cp-a95ebd93": "Sin novedades"}}
```

Formato del valor de cada tipo de campo:

| Tipo | Valor en `respuestas` |
|---|---|
| `STRING` | string, hasta 500 caracteres |
| `INT` | entero (`3`) o string numérico (`"3"`) |
| `SELECTOR` | una de las `opciones`, como string |
| `SELECTOR_MULTIPLE` | lista de strings, todos de las `opciones` |
| `DATE` | string `AAAA-MM-DD` |
| `ARCHIVO` | **no va acá**: se manda a `adjuntos/` (lo que venga se ignora) |

Reglas:

- `respuestas` y `version_capturada` son opcionales. Sin formulario se ignoran.
- Con formulario, `respuestas` se valida contra la definición **vigente**: obligatorios, condiciones y
  tipos. Un obligatorio **oculto por su condición no se exige**. **Un ARCHIVO obligatorio no bloquea**
  el resultado: llega después por `adjuntos/` y el backoffice marca si falta.
- Una clave que la definición vigente ya no tiene **no se rechaza**: se conserva aparte y el informe lo
  anota. `version_capturada` distinta de la vigente tampoco se rechaza: se acepta y el informe marca la
  diferencia.
- Respuesta 200: el detalle del relevamiento (mismo cuerpo que el `GET`), con `estado: "REALIZADA"`. El
  reenvío con el **mismo** `uuid_cliente` devuelve 200 con el relevamiento como quedó.

### Errores de `resultado/`

400 por respuestas inválidas (agrega `claves`, `{clave: texto}`, para marcar cada campo):

```json
{"respuestas": ["«Estado del techo»: elegí una de las opciones del formulario.",
                "«Cantidad de baños» es obligatorio."],
 "detail": "«Estado del techo»: elegí una de las opciones del formulario.",
 "non_field_errors": ["..."],
 "claves": {"cp-63007229": "«Estado del techo»: elegí una de las opciones del formulario.",
            "cp-d3983d25": "«Cantidad de baños» es obligatorio."}}
```

Un 400 **no se reintenta**: el `detail` es lo que se le muestra al agente. El relevamiento queda en
curso, sin cambios.

409 (siempre con `code`; la app debe leer `code`, no `detail`):

```json
{"detail": "Este relevamiento ya tiene un resultado registrado.", "code": "YA_REALIZADA", "estado": "REALIZADA"}
{"detail": "El relevamiento fue cancelado: Ya no hace falta", "code": "CANCELADA", "estado": "CANCELADA"}
{"detail": "El relevamiento se reasignó a otro agente.", "code": "REASIGNADA"}
{"detail": "El relevamiento ya no admite esta operación.", "code": "ESTADO_NO_ADMITE", "estado": "..."}
```

## 5. Fotos (sin cambios)

`POST /api/dispositivos/inspecciones/{id}/fotos/` (multipart): `archivo`, `uuid_cliente`, `descripcion`
(opcional). JPEG, PNG o WEBP, hasta 5 MB.

```json
{"id": 1, "uuid_cliente": "d2b389b5-20a7-4663-818e-e12a2181f64a", "descripcion": "Fachada",
 "creado": "2026-10-27T07:01:01.644646-03:00"}
```

201 la primera vez, 200 en el reenvío del mismo `uuid_cliente`. 409 `UUID_EN_USO` si ese identificador ya
se usó para otra foto.

## 6. Adjuntos del formulario (nuevo)

`POST /api/dispositivos/inspecciones/{id}/adjuntos/` — **multipart**, **un archivo por request**, para un
campo `ARCHIVO` del formulario.

| Campo | |
|---|---|
| `clave` | la `clave` del campo ARCHIVO (hasta 60 caracteres) |
| `archivo` | JPG, PNG, WEBP, HEIC o PDF, hasta 5 MB |
| `uuid_cliente` | UUID generado en el celular; reenviarlo no duplica |

```json
{"id": 1, "clave": "cp-371ff354", "uuid_cliente": "53210103-12c9-4c14-aa2a-a1eab0c143c2",
 "creado": "2026-10-27T07:01:01.674446-03:00"}
```

- **201** la primera vez; **200** con el mismo cuerpo en el reenvío del mismo `uuid_cliente` (mismo agente
  y mismo relevamiento), aunque después se haya cancelado o reasignado.
- Se acepta con el relevamiento **en curso o ya realizado**: la app sin conexión puede mandarlo después
  del resultado. No se acepta si ya fue revisado por el coordinador.
- 400 si la `clave` no es un campo ARCHIVO del formulario (o el relevamiento no tiene formulario):

  ```json
  {"clave": ["Esa clave no es un campo de archivo del formulario de este relevamiento."],
   "detail": "Esa clave no es un campo de archivo del formulario de este relevamiento.",
   "non_field_errors": ["..."]}
  ```

- 400 por extensión, firma o tamaño: `{"archivo": ["Solo se aceptan archivos JPG, PNG, WEBP, HEIC o PDF."], "detail": "...", ...}`.
- 409 con `code`: `UUID_EN_USO` (ese identificador ya lo usa otro adjunto; el texto dice «foto» pero el
  `code` es el que vale), `CANCELADA`, `REASIGNADA`, `ESTADO_NO_ADMITE`.
- La `clave` vale si es un campo ARCHIVO de la definición vigente **o de la que quedó guardada con el
  resultado**: un archivo de un campo que existía cuando se capturó entra aunque el diseño cambie después.

## 7. Accesos denegados

Los dos namespaces de campo contestan 403 con el mismo cuerpo:

```json
{"detail": "El usuario no tiene acceso al relevamiento edilicio.", "code": "SIN_MODULO"}
{"detail": "El usuario no tiene acceso a la app de campo de Becas.", "code": "SIN_MODULO"}
```

- El territorial de Becas (`becas.campo`) recibe 403 `SIN_MODULO` en `/api/dispositivos/…`.
- El agente de Dispositivos (`inspeccion.relevar`) recibe 403 `SIN_MODULO` en `/api/becas/…`.
- Quien tiene los dos módulos entra a los dos; un 403 `SIN_MODULO` de un módulo **no** significa que la
  sesión caducó (eso es 401): corresponde volver al selector de módulos, no al login.
- Un relevamiento que no es del agente —o un id que no existe— es **404** `{"detail": "No encontrado."}`,
  idéntico en los dos casos. Un relevamiento que el agente tuvo y se reasignó es 409 `REASIGNADA`.

## 8. Límites y reglas a recordar

- Fotos: JPEG, PNG, WEBP, hasta 5 MB. Adjuntos: JPG, PNG, WEBP, HEIC, PDF, hasta 5 MB. Firma del archivo
  validada (un `.pdf` que no es PDF se rechaza).
- `uuid_cliente` en `resultado/`, `fotos/` y `adjuntos/` es la clave de idempotencia. `UUID_EN_USO` solo
  existe para fotos y adjuntos (cada tabla con su propio espacio de identificadores).
- El agente asignado tiene que ser **externo** al edificio relevado: el personal de las instituciones del
  edificio no puede ser el territorial (`AGENTE_DEBE_SER_EXTERNO`).
- Un relevamiento por edificio en curso; fecha de vencimiento obligatoria. «Vencida» es un dato derivado
  (`vencida: true`), no un estado.
- Sincronización sugerida: listar → por cada relevamiento, comparar `formulario_version` con el detalle
  cacheado y volver a pedir el detalle si cambió → enviar `resultado/` (con `version_capturada`) → enviar
  los `adjuntos/` y las `fotos/` (en cualquier orden, antes o después del resultado).
