# Diseño técnico — Envío de beneficiarios aprobados a SIIS (tabla intermedia)

**Fecha:** 2026-09-14 · **Cadena:** Épica #69 · Análisis #72 (integración SIIS) · **Rama:** `feature/siis-envio-beneficiarios`
**Contrato externo:** *Manual de Integración M2M — Carga de Beneficiarios y Catálogos, SIIS API v4.2, septiembre 2026* (ECOM)
**Registro:** Cambio nuevo de `docs/internal/requerimientos.md` (`#siis #relevamientos #datos #ui`) · cierra el pendiente 1 del Cambio 50

## Qué se construye

La **mitad de escritura** de la integración con SIIS. Hasta hoy el sistema solo lee de SIIS: trae el
catálogo de programas y prevalida la compatibilidad de una persona (Cambios 22, 32 y 34). Con este
cambio, cada caso que queda **APROBADO** en Becas se da de alta como beneficiario en la tabla
intermedia de SIIS mediante `POST /api/v1/auth/tab-intermedia`, con los 30 campos de datos que pide
el manual.

Es una API distinta de la de compatibilidad, con los mismos `client_id`/`client_secret`, la misma
URL base (`SIIS_API_URL`) y el mismo token M2M. No exige variables nuevas.

**Principio rector:** el envío es un paso administrativo **posterior** a la aprobación y **nunca la
bloquea ni la revierte**. La aprobación sigue dependiendo de lo que ya depende (identidad,
compatibilidad SIIS, cupo); el envío se registra como intento auditable y, si falla, se corrige y
se reintenta desde la pantalla del caso.

## Decisiones tomadas con el PM (14/09/2026)

| Tema | Decisión |
|---|---|
| ¿Bloquea la aprobación la falta de datos SIIS? | **No.** El caso se aprueba igual; el envío queda como incompleto o con error y se reintenta. |
| Provincia, localidad, barrio, calle, estado civil | **Se toman del relevamiento**: ya son preguntas del formulario de la convocatoria. |
| Casos ya aprobados en producción | **No se envían retroactivamente** por ahora. |
| `id_fun_x_plan` (función por programa) | **Una sola por programa**, se toma del programa SIIS vinculado (en testing: 4 para Ñachec). |
| URL base | La variable `SIIS_API_URL` que ya existe; solo cambia la ruta. |

## Punto de integración en el proceso

Un caso llega a APROBADO por **dos puertas**, y las dos disparan el envío:

1. **Aprobación directa con cupo** — `aprobar_o_poner_en_espera` devuelve `"aprobado"`
   (`programas/services/cupo.py`), desde `formulario_aprobar` (`programas/views/revision.py`).
2. **Promoción desde lista de espera** — `promover_lista_espera` (`programas/services/cupo.py`),
   desde `promover_lista_espera_view` (`programas/views/cupo.py`).

El gate previo es el que ya existe: `motivo_bloqueo_aprobacion` exige identidad validada (por
cualquiera de los cuatro orígenes) y última consulta SIIS en `OK` para el DNI y programa actuales.
Eso es "validado a nivel SIIS y a nivel técnico". Recién superado, el caso es beneficiario y se
informa.

**No se envía** quien cae en lista de espera (todavía no es beneficiario). **No hay contraparte**
para la BAJA ni para modificaciones: el manual solo expone alta. Queda registrado como límite
externo, igual que la RN-25 del Cambio 34.

El envío se ejecuta en la vista, **después** de que el servicio atómico retornó (no hay
`ATOMIC_REQUESTS`, así que la aprobación ya está confirmada en la base). Mismo criterio que
`enviar_aviso_resolucion` (Cambio 44): un 503 del legacy de SIIS no puede deshacer una aprobación.

## Cómo debe quedar

### 1. Cliente — `programas/services/siis.py`

Se agregan al `SiisAPIClient` existente (mismo `_token`, mismos timeouts, misma instrumentación):

```python
def cargar_beneficiario(self, payload) -> dict
    # POST /api/v1/auth/tab-intermedia con un objeto (Modalidad A).
    # 201 → {"success": True, "siis_id": int, "data": body}
    # 400 → {"success": False, "codigo": "DATOS_INVALIDOS", "detalles": {campo: [msgs]}, "data": body}
    # 401 → invalida el token cacheado; {"success": False, "codigo": "UNAUTHORIZED", ...}
    # 503 → {"success": False, "codigo": "ERROR_BD_LEGACY", "reintentable": True, ...}
    # 500 / timeout / conexión / JSON inválido → {"success": False, "codigo": "ERROR_TECNICO", "reintentable": True, ...}

def catalogo(self, nombre) -> list[dict]
    # GET /api/v1/auth/catalogos/{provincias|localidades|estados-civiles|tipos-documento}
    # cache 24 h por catálogo (clave siis_api:catalogo:{nombre}); normaliza {id, nombre, **resto}

def funciones_programa(self, id_programa) -> list[dict]
    # GET /api/v1/auth/catalogos/funciones?id_programa=N → [{id, nombre, id_programa}], cache 24 h
```

`siis_id` se lee de `ids_generados[0]` o de `registros[0].id`, tolerando las dos formas del
manual. No se usa la Modalidad B (lote): los reintentos son por caso y no hay carga retroactiva.

### 2. Rol SIIS en las preguntas — `PreguntaGlobal.destino_siis`

Las preguntas del constructor no tienen semántica: solo texto y tipo. Para saber qué respuesta
alimenta qué campo de SIIS, se agrega a `PreguntaGlobal` un campo opcional:

```python
class DestinoSiis(models.TextChoices):
    PROVINCIA_ACTUAL = "prov_actual", "Provincia del domicilio"
    LOCALIDAD_ACTUAL = "loc_actual", "Localidad del domicilio"
    BARRIO = "barrio_actual", "Barrio"
    CALLE_ALTURA = "calle_altura", "Calle y altura (piso, dpto)"
    ESTADO_CIVIL = "est_civil", "Estado civil"
    PROVINCIA_NACIMIENTO = "prov_nacim", "Provincia de nacimiento"
    LOCALIDAD_NACIMIENTO = "loc_nacim", "Localidad de nacimiento"

destino_siis = models.CharField(max_length=20, choices=DestinoSiis.choices, blank=True, default="")
```

- Se edita en el ABM de preguntas globales (selector "Este dato alimenta a SIIS como…").
- **Una sola pregunta activa por destino**: se valida en el form y con una `UniqueConstraint`
  condicional (`destino_siis != ""` y `activo=True`).
- Solo `PreguntaGlobal`: las preguntas de domicilio y estado civil del cliente son globales
  (aplican a todos los formularios). Si un día hiciera falta en `RequisitoNativo`, es el mismo
  campo.
- Marcar el destino **no cambia** cómo se pregunta ni cómo se guarda la respuesta.

### 3. Correcciones del coordinador — `Formulario.datos_siis`

JSON `datos_siis` (default `{}`) en `Formulario`, con claves iguales a los campos de la API
(`loc_actual`, `calle_actual`, `nro_actual`, `piso_actual`, `dpto_actual`, `barrio_actual`,
`est_civil`, `prov_actual`, `prov_nacim`, `loc_nacim`). Lo que está acá **pisa** lo derivado de las
respuestas. Se guarda aparte de `data` para no tocar lo que la persona declaró; cada guardado deja
traza (`registrar_traza`, "Datos SIIS → …").

### 4. Armado del payload — `programas/services/siis_envio.py` (nuevo)

Módulo puro, sin request. Una función `armar_payload(formulario) -> (payload, faltantes)` donde
`faltantes` es `{campo: motivo}`; el payload solo se manda si `faltantes` está vacío.

| Campo API | Fuente | Regla |
|---|---|---|
| `dni` | `ciudadano.dni` | solo dígitos, 1 a 10 |
| `tdoc` | fijo | `1` (DNI) |
| `cuil_pref`, `cuil_dig` | calculados | módulo 11 estándar desde DNI y sexo: prefijo 20 (M) / 27 (F); si el resto da 10 → prefijo 23 y dígito 9 (M) / 4 (F); si da 11 → 0 |
| `apellido`, `nombre` | `ciudadano` | mayúsculas, recortados a 50 |
| `sexo` | `ciudadano.genero` | debe ser `F` o `M`; `X` o vacío → faltante |
| `est_civil` | pregunta `est_civil` → catálogo estados-civiles | match por nombre normalizado (sin acentos, sin "/a", casefold); `datos_siis` pisa |
| `prov_nacim`, `loc_nacim` | preguntas `prov_nacim`/`loc_nacim` o `datos_siis` | ver **Cuestión abierta** |
| `fecha_nacim` | `ciudadano.fecha_nacimiento` | ISO, no futura |
| `celular` | `formulario.celular` | solo dígitos; opcional |
| `prov_actual` | pregunta `prov_actual` → catálogo provincias | match por nombre normalizado; `datos_siis` pisa |
| `loc_actual` | pregunta `loc_actual` → catálogo localidades | match por nombre normalizado, acotado a la provincia si el catálogo la informa; si no matchea → faltante (el coordinador elige del catálogo) |
| `barrio_actual` | pregunta `barrio_actual` | recortado a 50; si son solo dígitos → `"Barrio N"`; si sigue con menos de 4 caracteres → faltante |
| `calle_actual`, `nro_actual`, `piso_actual`, `dpto_actual` | pregunta `calle_altura` | parser: último grupo numérico = número; texto anterior = calle; `(piso, dpto)` entre paréntesis si vienen. `"S/N"` o sin número → `nro_actual` faltante (SIIS exige entero) |
| `correo_electron` | `formulario.email_contacto` | recortado a 50; opcional |
| `jurid` | `programa.siis_programa_datos["jurisdiccion_id"]` | si el catálogo no lo informó → faltante "el programa vinculado no informa jurisdicción" |
| `id_plan_soc` | `programa.siis_programa_id` | |
| `id_fun_x_plan` | `programa.siis_funcion_id` (nuevo) | si no está configurado → faltante |
| `dni_apoderado`… `sexo_apoderado` | `formulario.apoderado_*` o `apoderado_ciudadano` | **solo si edad < 18** a la fecha del envío; CUIL calculado igual que el titular; apoderado con fecha de nacimiento y sexo F/M o → faltantes |

Los nombres de campo del manual se usan tal cual; no se inventan campos fuera de él.

### 5. Programa SIIS — `ProgramaSiis.siis_funcion_id` / `siis_funcion_nombre`

Campo nuevo, elegido de `funciones_programa(siis_programa_id)` en el form de alta y de edición del
programa (`ProgramaSiisCreateForm` y su par de edición). Opcional en el modelo para no romper los
programas ya vinculados; obligatorio para el envío (sin función, el envío queda incompleto con un
mensaje que apunta a la configuración del programa).

### 6. Registro auditable — modelo `EnvioSIIS` (nuevo)

Hermano de `ValidacionSIS`: **un registro inmutable por intento**.

```python
class EnvioSIIS(models.Model):
    class Estado(models.TextChoices):
        ENVIADO = "ENVIADO", "Enviado"              # 201
        INCOMPLETO = "INCOMPLETO", "Datos incompletos"  # no se llegó a llamar: faltantes locales
        RECHAZADO = "RECHAZADO", "Rechazado por SIIS"   # 400 DATOS_INVALIDOS
        ERROR = "ERROR", "Error técnico"            # 401 / 500 / 503 / timeout / conexión
    formulario     FK Formulario, related_name="envios_sis"
    estado         CharField(choices, db_index)
    siis_id        PositiveIntegerField(null)     # id devuelto por la API
    id_programa    PositiveIntegerField(null)
    id_funcion     PositiveIntegerField(null)
    documento      CharField(20)
    codigo_error   CharField(40, blank)           # DATOS_INVALIDOS / UNAUTHORIZED / ERROR_BD_LEGACY / ERROR_INTERNO / ERROR_TECNICO / ""
    detalles       JSONField(default=dict)        # {campo: [mensajes]} — de SIIS (400) o locales (INCOMPLETO)
    payload        JSONField(default=dict)        # lo que se mandó (o lo que se armó)
    respuesta      JSONField(default=dict)
    solicitado_por FK User (SET_NULL)
    creado         DateTimeField(auto_now_add)
    Meta: ordering ["-creado"]
```

Regla de **idempotencia local**: si el formulario ya tiene un `EnvioSIIS` en `ENVIADO`, no se
vuelve a mandar (la API no deduplica). `Formulario.envio_siis_vigente` = último envío.

### 7. Servicio — `enviar_beneficiario_a_siis(formulario, user) -> EnvioSIIS`

En `programas/services/siis_envio.py`:

1. Si el caso no está APROBADO → `ValueError`. Si ya tiene un envío `ENVIADO` → lo devuelve sin
   llamar.
2. `armar_payload`; si hay faltantes → crea `EnvioSIIS(INCOMPLETO, detalles=faltantes)`.
3. Si no, `cargar_beneficiario(payload)` y crea el `EnvioSIIS` con el resultado.
4. Nunca lanza por fallas de red ni de SIIS: siempre deja registro.

### 8. Disparo y reintento

- `formulario_aprobar` (revisión): después de `aprobar_o_poner_en_espera`, **solo si**
  `resultado == "aprobado"`, llama a `enviar_beneficiario_a_siis`. El mensaje al usuario suma el
  desenlace del envío ("Caso aprobado. Informado a SIIS." / "Caso aprobado. El envío a SIIS quedó
  pendiente: faltan datos." / "…SIIS no respondió; se puede reintentar.").
- `promover_lista_espera_view` (cupos): idéntico tras `promover_lista_espera`.
- **Reenvío manual**: vista nueva `formulario_enviar_siis` (POST,
  `revision/formulario/<pk>/enviar-siis/`), capacidad `becas.revision.editar` más alcance por
  segmento (`_assert_scope_formulario`), igual que "Validar SIIS".
- **Corrección de datos**: vista `formulario_datos_siis` (POST) con un Django Form
  `DatosSiisForm` que edita `datos_siis`; provincia y localidad son selects cargados del catálogo
  (localidad filtrada por provincia vía un endpoint JSON chico o precarga); barrio, calle, número,
  piso, dpto y estado civil con sus validaciones espejo de SIIS (barrio ≥ 4, número entero).
  Guardar **no envía**: el coordinador revisa y después reenvía.
- **Comando** `reenviar_siis_pendientes`: recorre casos APROBADO sin envío `ENVIADO` cuyo último
  envío sea `ERROR` (técnico, reintentable) y los reintenta uno a uno. Los `INCOMPLETO` y
  `RECHAZADO` **no** se reintentan solos: necesitan corrección humana. Pensado para un cron
  (pendiente de ECOM, Cambio 27) o para correrlo a mano tras una caída del legacy.

### 9. UI — `formulario_detalle.html`

Bloque nuevo **"Envío a SIIS"**, debajo del de validación SIIS, visible solo para casos APROBADO:

- Badge de estado del último envío (Enviado · Datos incompletos · Rechazado por SIIS · Error
  técnico · Sin envío), fecha, quién, y el `siis_id` cuando existe.
- Lista de `detalles` por campo cuando hay faltantes o rechazo, con el texto de SIIS o el local.
- Botón **"Completar datos para SIIS"** (abre el form de corrección; mismo patrón de modal que
  rechazo) y botón **"Reenviar a SIIS"**, ambos con `becas.revision.editar` y ocultos si ya está
  `ENVIADO`.
- Historial de intentos plegable, igual que el de validaciones.

Sigue el inventario de `.claude/agents/chaco-design-system.md`; sin hex, sin `confirm()` nativo,
mensajes por `window.toast()`. `design_audit.py --changed` en 0 y `compile_templates.py` en 0.

### 10. Configuración de preguntas — ABM de preguntas globales

Selector "Este dato alimenta a SIIS como…" en el form de pregunta global, con ayuda corta.
Validación: no puede haber dos preguntas activas con el mismo destino.

## Cuestión abierta — lugar de nacimiento

`prov_nacim` y `loc_nacim` son **obligatorios** en SIIS y hoy **no se preguntan** en el
relevamiento. La respuesta del PM fue "siempre Argentina", que resuelve el país pero no la
provincia ni la localidad, que es lo que pide la API.

El diseño **no asume nada**: soporta los dos destinos en las preguntas (si el cliente agrega
"Provincia de nacimiento" y "Localidad de nacimiento" al formulario, se toman de ahí) y, si no
existen, el coordinador los carga en "Completar datos para SIIS". Hasta que una de las dos vías
tenga dato, el envío queda `INCOMPLETO` por esos dos campos.

Si el PM prefiere **igualarlos al domicilio actual** cuando no hay pregunta, es una regla de una
línea en `armar_payload`; se agrega solo con esa confirmación explícita, porque es inventar un dato
que va a un registro provincial.

## Pendientes externos a registrar

- **"S/N" en la altura.** SIIS exige `nro_actual` entero. Hay que preguntarle a ECOM qué valor
  espera para domicilios sin numeración; mientras tanto queda como faltante corregible.
- **Baja y modificación de beneficiarios.** El manual no las expone.
- **`jurisdiccion_id` en el catálogo.** Se lee del detalle congelado del programa; si SIIS no lo
  informa para algún programa, el envío lo señala y la salida es re-vincular o que ECOM lo agregue.
- **Cron del comando de reintentos** (pendiente 6 del Cambio 27).

## Archivos

- `programas/services/siis.py` — `cargar_beneficiario`, `catalogo`, `funciones_programa`
- `programas/services/siis_envio.py` — nuevo: `armar_payload`, `calcular_cuil`, `parsear_direccion`, `enviar_beneficiario_a_siis`
- `programas/models/__init__.py` — `PreguntaGlobal.destino_siis`, `ProgramaSiis.siis_funcion_id/_nombre`, `Formulario.datos_siis`, `EnvioSIIS`
- `programas/migrations/00XX_siis_envio_beneficiarios.py`
- `programas/forms.py` — `DatosSiisForm`, `destino_siis` en el form de pregunta global, función en los forms de `ProgramaSiis`
- `programas/views/revision.py` — disparo en `formulario_aprobar`, `formulario_enviar_siis`, `formulario_datos_siis`, contexto del detalle
- `programas/views/cupo.py` — disparo en `promover_lista_espera_view`
- `programas/urls.py` — dos rutas nuevas
- `programas/management/commands/reenviar_siis_pendientes.py` — nuevo
- `programas/templates/programas/becas/revision/formulario_detalle.html` — bloque "Envío a SIIS"
- templates del ABM de preguntas globales y del programa SIIS — selector nuevo
- `programas/tests/test_siis_envio.py` — nuevo; `test_becas_revision.py` — disparo y reenvío
- `docs/internal/temas/siis-api.md` — endpoint 5 y catálogos; `docs/internal/requerimientos.md` — entrada nueva

## Base de datos

Una migración: campo en `PreguntaGlobal` (con constraint condicional), dos en `ProgramaSiis`, uno en
`Formulario`, tabla `EnvioSIIS`. Sin backfill.

## Pruebas

- **Unitarias de `siis_envio`:** CUIL para casos M, F y resto 10; parser de dirección ("AV. 9 DE
  JULIO 450 (2, B)", "Sarmiento 100", "S/N", solo calle); barrio numérico y barrio corto; match de
  estado civil y de localidad con acentos y mayúsculas; localidad sin match → faltante; menor sin
  apoderado → faltantes; menor con apoderado completo → los 7 campos; mayor → sin apoderado;
  `datos_siis` pisa la respuesta; programa sin función → faltante.
- **Cliente:** 201 con `ids_generados`, 201 con `registros`, 400 con `detalles`, 401 invalida
  token, 503 reintentable, timeout.
- **Servicio:** no envía si no está APROBADO; no reenvía si ya hay `ENVIADO`; siempre deja registro.
- **Vistas:** aprobar con cupo dispara envío; aprobar a lista de espera no; promover dispara;
  reenviar exige `becas.revision.editar` y alcance; corrección guarda `datos_siis` con traza y no
  envía; el bloque aparece solo en APROBADO.
- **Form de pregunta global:** dos activas con el mismo destino → error.
- Presupuestos `--tag performance` del detalle: el bloque agrega una consulta (`envios_sis`), se
  ajusta el budget si corresponde.

## Cierre

`manage.py check` · `makemigrations --check` · suites `test_siis_envio`, `test_becas_revision`,
`test_becas_rbac` · `design_audit.py --changed` 0 · `compile_templates.py` 0 · entrada en
`requerimientos.md` y `requerimientos.py --check` OK.
