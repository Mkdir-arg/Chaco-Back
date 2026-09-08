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

Todos los llamados 2-4 con `Authorization: Bearer <token>`.

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
- Configuración por env: `SIIS_API_URL` (default ya apunta al entorno de test),
  `SIIS_API_CLIENT_ID`, `SIIS_API_CLIENT_SECRET`, `SIIS_API_CONNECT_TIMEOUT`,
  `SIIS_API_TIMEOUT`.

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

- [ ] Credenciales de **producción** (dependen del deploy prod de ECOM y sus accesos a BD).
- [ ] Cargar las credenciales de test en el gestor de claves y en el entorno.
- [ ] Cuando ECOM confirme el contrato definitivo, cerrar el análisis #72 (hoy bloqueado por eso).
