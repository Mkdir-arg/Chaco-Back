# Gran Base — API de Base de Personas (ECOM)

Integración con el padrón unificado de personas de la provincia ("Gran Base" /
proyecto **personas-dev** de ECOM). Consumida por Becas para validar personas por
DNI; el pedido vigente del cliente es **ampliar qué datos se toman de acá**
(task #243).

## Responsable y origen de la documentación

| | |
|---|---|
| **Responsable técnico (ECOM)** | Lucas Sebastián Ibañez |
| **Vía / intermediario** | Federico Daniel Aguirre (aclaró el 27/07/2026 que la Gran Base la arma ECOM internamente, con otro equipo — ver [siis-api.md](siis-api.md)) |
| **Recibido** | Correo del **31/07/2026 10:36**, asunto *"Documentacion API BD Personas"* |
| **Adjuntos del correo** | Colección Postman parametrizada ([copia acá](gran-base-personas.postman_collection.json)) + captura de respuesta de ejemplo |
| **Entorno entregado** | `https://personas.ecomdev.ar/api/v1` (desarrollo) |

## Credenciales

Las credenciales de desarrollo (`client_id`, `client_secret`, `entidad_uuid`)
llegaron **en el cuerpo de ese correo** — no se copian acá ni a ningún archivo
del repo. Guardarlas en el gestor de claves del equipo y cargarlas en el
servidor como variables de entorno (`PERSONAS_API_*`, ver abajo). Como viajaron
por mail en texto plano, ante cualquier sospecha de exposición se puede pedir a
ECOM **"Regenerar client secret"** desde la web de Aplicaciones.

Alta de credenciales del lado ECOM (referencia de su doc): se crea una
**Aplicación** OAuth2 (grant `client_credentials`) y en **Permisos apps** se
asocia entidad + aplicación + permiso `personas` + habilitado. El secret se
copia en texto plano (si el detalle muestra `pbkdf2_…`, es el hash: regenerar).

## Autenticación

`POST {base_url}/aplicaciones/token/` — sin header de autorización.

| Campo del body | Valor |
|----------------|-------|
| `grant_type` | `client_credentials` (fijo) |
| `client_id` | de la aplicación |
| `client_secret` | en texto plano |
| `entidad` | UUID de la entidad habilitada |

- El token dura **24 horas** y se usa como `Authorization: Bearer <token>`.
- Respuesta estilo SID: `{codigo_http, mensaje_http, data: {codigo, mensaje, token, token_type, scope, expiration}}`.
- Health check: `GET {base_url}/health/` — sin autenticación.
- Ojo con la colección Postman: sus URLs asumen `base_url` **sin** `/api/v1`
  (default local `http://127.0.0.1:8002`); el `base_url` de dev que entregó ECOM
  **ya incluye** `/api/v1`.

## Consulta de personas

`GET {base_url}/personas/consulta/` con Bearer token.

| Query param | Requerido | Descripción |
|-------------|-----------|-------------|
| `dni` | **Sí** | Numérico, solo dígitos |
| `sexo` | No | `M`, `F` o `ND` |
| `fuente_id` | No | Fuente de datos; si no se manda, usa la predeterminada del servicio |

> La consulta web de ECOM admite más filtros (`cuit`, `nombre`, `q`); la **API**
> por ahora solo expone `dni` y `sexo` (+ `fuente_id`).

### Fuentes de datos — pendiente clave

La forma de `data` **cambia según la fuente**:

- **Fuente "ATP"** (ejemplo de la doc oficial): `data.personas[]` con
  `id, apellido, nombre, dni, tipo_documento, cuit, sexo, fecha_nacimiento,
  fecha_fallecimiento, domicilio, fuente, tipo_persona`.
- **`fuente_id=12`** (captura adjunta al correo, 200 OK): `data` con campos de
  tipo RENAPER — `id_tramite_principal, id_tramite_tarjeta_reimpresa, ejemplar,
  vencimiento, …` (captura parcial; relevar la respuesta completa contra el
  servicio es parte de la task #243).
- El correo indica usar **`fuente_id=13` por el momento**; la colección
  ejemplifica con `12`. **La fuente predeterminada definitiva quedó pendiente de
  definición por ECOM.**

### Errores

| HTTP | Causa |
|------|-------|
| 400 | DNI inválido/faltante; body inválido; secret que parece hash (`pbkdf2_`) |
| 401 | Token inválido o vencido; `client_id` incorrecto; secret con espacios |
| 403 | App sin permiso `personas.view_persona` o entidad no habilitada |
| 404 | No hay personas para ese DNI |

## Estado en nuestro código

- Cliente: [`programas/services/personas.py`](../../../programas/services/personas.py)
  (`PersonasAPIClient`) — mismo endpoint de token, cachea el token
  (`personas_api:token`), consulta por DNI.
- Configuración por settings/env: `PERSONAS_API_URL`, `PERSONAS_API_CLIENT_ID`,
  `PERSONAS_API_CLIENT_SECRET`, `PERSONAS_API_ENTIDAD_UUID`,
  `PERSONAS_API_FUENTE_ID`, timeouts.
- **`PERSONAS_API_ACTIVA` (Cambio 57, 28/08/2026):** la Gran Base ya no es la
  única fuente de identidad. `programas/services/identidad.py::identificar`
  hace la cascada **padrón de la convocatoria → Gran Base (si está activa) →
  manual**, para el link y para la app. Con la variable en `False` no se la
  consulta en ningún lugar (paso 1, `consultar_persona_becas`, «Revalidar»,
  diagnóstico); las personas del padrón con nombre y apellido se validan
  igual. Cuando el servicio vuelve, se prende y manda sobre el padrón si
  difieren. No es un plan B: el padrón se consulta primero siempre.
- `normalizar_persona()` hoy solo toma `dni, apellido, nombre, fecha_nacimiento,
  sexo` y tolera variantes de nombres "hasta que se cierre el contrato
  definitivo" — ampliar qué campos se consumen es exactamente el pedido de la
  task #243.

## Pendientes

- [ ] Relevar la respuesta completa por fuente (13 y 12) contra el servicio real y volcarla en la task #243.
- [ ] Avisar a Guido y definir qué datos se suman al sistema (#243).
- [ ] Que ECOM defina la fuente de datos predeterminada definitiva.
- [ ] Cargar las credenciales en el gestor de claves y en el entorno del servidor.
