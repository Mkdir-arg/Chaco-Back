# SIIS — API del Sistema Integrado de Información Social (ECOM)

API REST del SIIS según el **convenio contractual v1 con DATAÑACH**. Es la
integración central de Becas: catálogo de programas sociales (nivel Programa
del Cambio 32) y validación de compatibilidad de personas (doble-OKA, análisis
#72).

## Responsable y origen de la documentación

| | |
|---|---|
| **Responsable (ECOM)** | Federico Daniel Aguirre |
| **Recibido** | Hilo *"Re: Requerimientos"* del **27/07/2026**, de F. Aguirre a Matías Fariña, con **Guido Cortiglia en copia** |
| **Adjuntos del correo** | Colección Postman ([copia saneada acá](siis-api.postman_collection.json)) + instructivo de uso |
| **Entorno entregado** | `https://siisapi.ecomdev.ar` (**test** — datos desactualizados: sirve para integración y algo de validación, no para validar negocio) |

## Credenciales

Llegaron **en el cuerpo del correo** (`CLIENTE_API_NOMBRE=DATAÑACH`,
`client_id=datanach_test` + secret) y venían **embebidas dentro de la colección
Postman**: en la copia versionada acá el `client_secret` fue **vaciado a
propósito** — no se versionan secretos. Van al gestor de claves y al servidor
como `SIIS_API_CLIENT_ID` / `SIIS_API_CLIENT_SECRET`. Como viajaron por mail en
texto plano, ante sospecha de exposición pedir a ECOM la regeneración.

## Endpoints (convenio v1)

| # | Endpoint | Qué hace |
|---|----------|----------|
| 1 | `POST /api/v1/auth/token` — body `{client_id, client_secret}` | Token JWT máquina-a-máquina, vigencia **1 hora** |
| 2 | `GET /api/v1/programas?estado=ACTIVO\|INACTIVO\|TODOS` | Catálogo maestro de programas sociales |
| 3 | `GET /api/v1/programas/{id}/segmentos` | Segmentos (funciones) de un programa |
| 4 | `POST /api/v1/validaciones/compatibilidad` | Elegibilidad e incompatibilidades de una persona |
| 5 | `POST /api/v1/auth/tab-intermedia` — objeto o arreglo de 30 campos | Alta de beneficiarios en la tabla intermedia (manual v4.2, sep-2026). 201 con `ids_generados` o `registros`; 400 `DATOS_INVALIDOS` con `detalles` por campo; 401 `UNAUTHORIZED`; 503 `ERROR_BD_LEGACY` reintentable; 500 `ERROR_INTERNO`. **Lo que el manual no cubre y de este lado se trata como incierto: ver abajo** |
| 6 | `GET /api/v1/auth/catalogos/{provincias\|localidades\|estados-civiles\|tipos-documento\|jurisdicciones}` | Catálogos maestros para normalizar los ids del alta |
| 7 | `GET /api/v1/auth/catalogos/funciones?id_programa=` | Funciones por programa; el `id` va en `id_fun_x_plan` |

Todos los llamados 2-7 con `Authorization: Bearer <token>`.

### Qué pasa cuando la respuesta no es ninguna de esas (D-S02)

**El alta no tiene baja.** La API no deduplica, no deja preguntar si un
beneficiario ya existe y no permite borrar lo que se mandó, así que reintentar un
POST que **pudo haber llegado** es la peor decisión posible: deja dos altas
irreversibles de la misma persona. Por eso el cliente clasifica cada desenlace por
una sola pregunta —*¿puede haber quedado un alta del otro lado?*— y no por el
código HTTP (Cambio 127):

| Qué contestó SIIS | De este lado | Se reintenta solo |
|---|---|---|
| 200 / 201 | `ENVIADO` | — |
| 401 | se pide token nuevo y se reintenta **una vez adentro**; si vuelve a fallar, `ERROR` | sí |
| 400 `DATOS_INVALIDOS`, y el resto de los 4xx salvo 401/408/429 | `RECHAZADO` (los que no traen código, con `CONFIGURACION`) | no: pide corregir datos |
| 503 **con `ERROR_BD_LEGACY` en el cuerpo** | `ERROR` | sí |
| `ConnectTimeout`, DNS que no resuelve, conexión rechazada | `ERROR` | sí |
| `ReadTimeout`, conexión cortada a mitad, respuesta truncada, 408, 429, 500, 502, 504 | **`INCIERTO`** | **no** |
| **503 SIN `ERROR_BD_LEGACY` en el cuerpo** (el que devuelve el balanceador antes de llegar a la aplicación) | **`INCIERTO`** | **no** |
| **500 con el cuerpo que no es JSON válido** | **`INCIERTO`** | **no** |

Las dos últimas filas son **decisión nuestra, no contrato**: el manual promete
`ERROR_BD_LEGACY` en el cuerpo del 503, pero un 503 del balanceador llega sin
cuerpo y un 500 puede llegar con el HTML de una página de error. Mientras no haya
contrato se tratan como inciertos, que es el lado conservador. **Lo que cuesta:**
un `INCIERTO` deja el caso **tomado** y ningún camino lo reenvía; sale a mano con
`manage.py conciliar_envios_siis`, después de preguntarle a ECOM si esa alta
quedó registrada.

**Pedidos abiertos a ECOM (D-S02):**

1. **Una clave de idempotencia** (`id_externo` = pk del formulario) en el alta.
   Es la solución de fondo: con ella el reintento deja de ser peligroso y las dos
   filas de arriba pueden volver a ser reintentables.
2. **Confirmar qué significa su 503 sin cuerpo.** Si siempre quiere decir «no se
   escribió nada», pasa a reintentable y nos ahorra una conciliación por cada uno.

## Alta de beneficiarios (manual M2M v4.2, septiembre 2026)

Segunda mitad de la integración: hasta el Cambio 50 solo **leíamos** de SIIS
(catálogo de programas y compatibilidad). Desde el alta de beneficiarios
también **escribimos**: cada caso que queda **APROBADO** en Becas se informa a
la tabla intermedia.

- **Qué lo dispara.** Las dos puertas a APROBADO: aprobación con cupo desde
  revisión y promoción desde lista de espera. El envío corre **después** de que
  la aprobación quedó confirmada y **nunca la bloquea ni la revierte**: un 503
  del legacy no puede deshacer una aprobación. Quien cae en lista de espera no
  se envía (todavía no es beneficiario).
- **Registro.** `EnvioSIIS`, hermano inmutable de `ValidacionSIS`: un registro
  por intento con estado `ENVIADO` (201), `INCOMPLETO` (faltan datos locales,
  no se llegó a llamar), `RECHAZADO` (400) o `ERROR` (401/5xx/red). La API no
  deduplica, así que la idempotencia es nuestra: con un `ENVIADO` vigente no se
  vuelve a mandar.
- **De dónde salen los 30 campos.** Del ciudadano (DNI, nombre, sexo, fecha de
  nacimiento; CUIL calculado por módulo 11), del programa SIIS vinculado
  (`id_plan_soc`, `jurid`, `id_fun_x_plan`) y de las **respuestas del
  relevamiento** marcadas con un *destino SIIS* en el ABM de preguntas globales
  (`PreguntaGlobal.destino_siis`: provincia, localidad, barrio, calle y altura,
  estado civil, lugar de nacimiento). Lo que el coordinador corrige a mano vive
  en `Formulario.datos_siis` y **pisa** lo derivado de las respuestas, sin tocar
  lo que la persona declaró.
- **Apoderado.** Los 7 campos son obligatorios solo si la persona es menor de
  18 años a la fecha del envío, y el apoderado debe ser mayor de edad.
- **Reintento.** Manual desde la pantalla del caso, o por lote con
  `manage.py reenviar_siis_pendientes` (solo los `ERROR`: los `INCOMPLETO` y
  `RECHAZADO` necesitan corrección humana).

### Límites del contrato (del lado de ECOM)

- **No hay baja ni modificación** de beneficiarios: el manual solo expone el
  alta. Una corrección posterior a un `ENVIADO` no tiene contraparte.
- **`nro_actual` es un entero obligatorio**: falta saber qué espera SIIS para
  domicilios sin numeración (`S/N`). Mientras tanto queda como dato faltante
  corregible.
- **`jurisdiccion_id`** se lee del detalle congelado del programa; si SIIS no lo
  informa para algún programa, el envío lo señala y hay que re-vincular.
- **No se usa la Modalidad B (lote)**: los reintentos son por caso y no hay
  carga retroactiva de los casos ya aprobados en producción.

### Diferencia entre el convenio v1 y el servicio vigente (importante)

La colección refleja el **convenio v1**; el contrato **evolucionó** y nuestro
código ya consume la versión vigente:

- **Validar compatibilidad** — v1 pedía `{documento, sexo, id_segmento}`; el
  servicio vigente recibe **`{dni, id_programa, fecha_nacimiento?}`** (SIIS
  dejó de exponer el nivel "segmento" y de pedir el sexo; ver Cambios 22 y 32
  del archivo vivo). El veredicto llega **siempre con HTTP 200**:
  `resultado: OK|RECHAZADO` + `apto`; un 4xx es error de integración, no un
  rechazo de negocio.
- **Segmentos por programa** (endpoint 3) — nuestro código **no lo consume**:
  desde el Cambio 32 el segmento es local y solo el Programa espeja a SIIS.

## Estado en nuestro código

- Cliente: [`programas/services/siis.py`](../../../programas/services/siis.py) —
  token cacheado, catálogo de programas cacheado, `validar_compatibilidad()`.
- Sincronización de vigencia: `programas/services/siis_sync.py` + comando
  `sincronizar_programas_siis` (cron en `docker/cron/`), una fila por
  `ProgramaSiis`.
- Registro inmutable de validaciones: modelo `ValidacionSIS` (motivos:
  persona inexistente, beneficio existente, empleo público docente).
- Alta de beneficiarios: `programas/services/siis_envio.py` (armado del payload,
  CUIL, parser de dirección y servicio de envío), modelo `EnvioSIIS` y comando
  `reenviar_siis_pendientes`. Usa el mismo token, la misma `SIIS_API_URL` y las
  mismas credenciales: no agrega variables de entorno.
- Configuración por env: `SIIS_API_URL` (**sin default desde el Cambio 123**: si
  falta, no se manda nada en vez de mandarlo al SIIS de desarrollo),
  `SIIS_API_CLIENT_ID`, `SIIS_API_CLIENT_SECRET`, `SIIS_API_CONNECT_TIMEOUT`,
  `SIIS_API_TIMEOUT`. En PRD, además, `DATANACH_ES_PRODUCCION=1`, que es lo que
  hace que `manage.py check --deploy` rechace apuntar al ambiente de test.

## Acotaciones del correo (27/07/2026)

- El entorno de test tiene **datos desactualizados**.
- ECOM quedó en ajustar la **seguridad** del servicio en los días siguientes.
- **Accesos a la BD de producción en trámite**; de su lado queda el deploy en
  producción del servicio y ajustes.
- **Gran Base**: la arma ECOM internamente (otro equipo); los accesos y la
  documentación llegaron después, el 31/07/2026 → ver
  [gran-base-personas.md](gran-base-personas.md).
- **Geolocalización**: ECOM **no tiene** APIs de geo ni las va a tener para
  esta temática — recomendación explícita de F. Aguirre: queda fuera de sus
  servicios; seguimos con nuestro propio plan (GPS capturado por la app).

## Pendientes

- [ ] Preguntarle a ECOM qué valor espera `nro_actual` para domicilios **sin numeración** (`S/N`).
- [ ] Baja y modificación de beneficiarios: pedir el contrato si el negocio lo necesita.
- [ ] Credenciales de **producción** (dependen del deploy prod de ECOM y sus accesos a BD).
- [ ] Cargar las credenciales de test en el gestor de claves y en el entorno.
- [ ] Cuando ECOM confirme el contrato definitivo, cerrar el análisis #72 (hoy bloqueado por eso).
