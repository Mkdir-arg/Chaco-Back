# Programa Becas — Implementación

Documento técnico del Programa Becas (épica #69 / análisis #70). Cubre las 6
tasks: #73 (modelos), #79 (roles RBAC), #74 (configuración), #76 (relevamientos),
#77 (revisión) y #82 (API de campo). La fuente de verdad es el código en la app
`programas`; este doc orienta sobre dónde está cada pieza y cómo levantarlo.

## Alcance y decisiones

- Los modelos de Becas viven en `programas/models.py` pero son **independientes**
  del modelo genérico `Programa`/`InscripcionPrograma`. La instancia
  `Programa(codigo="BECAS")` solo **ancla el alcance del RBAC** (roles de
  categoría "Programa") y la futura solapa del legajo.
- **Fuera de alcance de esta versión** (placeholders deliberados): validación
  socioeconómica/asignación de cupo del **SIS**, validación **RENAPER** en línea,
  y la ocupación efectiva de cupo (`CupoSegmento`/`ListaEspera` quedan como
  estructura base). La UI de revisión muestra "Resultado SIS: pendiente".

## Mapa de archivos

| Pieza | Archivo |
|---|---|
| Modelos | `programas/models.py` (sección "Programa Becas") |
| Migración de esquema | `programas/migrations/0002_*` |
| Seed (programa + adjuntos + roles) | `programas/management/commands/seed_becas.py` |
| Capacidades RBAC | `core/rbac.py` (módulo `becas`, alcance programa) |
| Autorización por segmento | `programas/services/autorizacion.py` |
| Helpers de dominio | `programas/services/becas.py` |
| Forms backoffice | `programas/forms.py` |
| Vistas backoffice | `programas/views/{configuracion,relevamientos,revision}.py` |
| URLs backoffice | `programas/urls.py` (namespace `becas`, prefijo `/becas/`) |
| API de campo | `programas/api/{serializers,views}.py`, `programas/api_urls.py` (`/api/becas/`) |
| Templates | `programas/templates/programas/becas/**` |
| Sidebar | `templates/includes/sidebar/opciones.html` (sección "Programa Becas") |
| Tests | `programas/tests/test_becas_*.py` |

## Modelos (#73)

`Segmento` (cupo + `requiere_gps`), `Subsegmento` (RN-40: la suma de cupos de
subsegmentos no supera el del segmento, validado en `clean()`), `CupoSegmento`,
`Convocatoria` (segmento requerido + subsegmento opcional del mismo segmento),
`Relevamiento` (nombre autogenerado "Relevamiento NNN"; estados ASIGNADO →
EN_CURSO → FINALIZANDO → FINALIZADO → EN_REVISION → TERMINADO), `PreguntaGlobal`
y `RequisitoNativo` (con `TipoCampo`; requisito de segmento aplica también a sus
subsegmentos — herencia), `AsignacionCoordinador`, `Formulario` (bloques de
contacto/apoderado + `data` JSON dinámico + `datos_identificacion` para sync
offline), `TracaFormulario` (auditoría inmutable de ediciones) y `ListaEspera`.

## RBAC y roles (#79)

Capacidades granulares por entidad (10 grupos, todos **alcance de programa**):
Segmento/Subsegmento/Requisito/Pregunta global/Coordinador (ver/crear/editar
cada uno), Convocatoria/Relevamiento (ver/crear/editar), Revisión (ver/editar),
Cupo (ver), Beneficiario (ver/editar), más `becas.programa.administrar`
(capacidad paraguas: bypass de scoping por segmento) y `becas.campo` (app de
campo del territorial, sin cambios). Catálogo completo en `core/rbac.py`.

Roles sembrados por `seed_becas` (Group + `RolMeta` categoría "Programa",
acotados al Programa Becas):

| Rol | Capacidades |
|---|---|
| Becas — Administrador | `becas.programa.administrar` + todas las capacidades finas (menos `becas.campo`) |
| Becas — Coordinador | ver estructural (segmento/subsegmento/requisito) + ver/crear/editar de convocatoria/relevamiento/revisión/beneficiario + cupo.ver (acotado a sus segmentos) |
| Becas — Territorial | `becas.campo` (solo app móvil) |

El RBAC tiene alcance de *programa*; el alcance fino por **segmento** del
coordinador lo aporta `AsignacionCoordinador` combinado con la capacidad en
`programas/services/autorizacion.py` (`puede_gestionar_segmento`,
`segmentos_visibles`). Admin del programa ve todo; coordinador solo sus segmentos
asignados; el resto, nada.

## Backoffice

- **Configuración (#74)** — capacidades finas por entidad (`becas.segmento.*`,
  `becas.subsegmento.*`, `becas.requisito.*`, `becas.pregunta.*`,
  `becas.coordinador.*`; ver es de solo lectura, scoped a los segmentos
  asignados del Coordinador): ABM de segmentos, subsegmentos (con cupo RN-40),
  asignación de coordinadores (solo usuarios con rol Coordinador), requisitos
  nativos (de segmento o subsegmento) y preguntas globales del cuestionario
  social (sin scoping, config global del programa).
- **Relevamientos (#76)** — `becas.convocatoria.*` / `becas.relevamiento.*`: ABM
  con alta (nombre auto), reasignación de territorial y reprogramación;
  convocatorias; filtros por estado; scoping por segmento (detalle ajeno → 403).
- **Revisión (#77)** — `becas.revision.ver` / `becas.revision.editar`: listado
  por relevamiento, edición de contacto/apoderado con **traza por cambio**,
  aprobar / rechazar (motivo obligatorio, SweetAlert2), transiciones FINALIZADO
  → EN_REVISION → TERMINADO. Placeholder de Resultado SIS.
- **Cupo y beneficiarios (#78)** — `becas.cupo.ver` (stats de ocupación) y
  `becas.beneficiario.ver`/`becas.beneficiario.editar` (listado, dar de baja,
  promover y agregar a lista de espera; scoped por segmento, ya no admin-only).

## API de campo (#82)

Prefijo `/api/becas/`, auth por **token** (`rest_framework.authtoken`),
capacidad `becas.campo`. El territorial solo ve/gestiona SUS relevamientos.

| Método | Endpoint | Acción |
|---|---|---|
| POST | `/api/becas/auth/token/` | Login (devuelve token; exige `becas.campo`) |
| GET | `/api/becas/relevamientos/` | Relevamientos asignados |
| GET | `/api/becas/relevamientos/{id}/` | Detalle + `definicion_formulario` |
| POST | `/api/becas/relevamientos/{id}/iniciar/` | ASIGNADO → EN_CURSO |
| POST | `/api/becas/relevamientos/{id}/finalizar/` | EN_CURSO → FINALIZADO |
| POST | `/api/becas/relevamientos/{id}/reabrir/` | FINALIZADO → EN_CURSO |
| GET/POST | `/api/becas/relevamientos/{id}/formularios/` | Listar / crear (sync) |
| GET/PUT/PATCH | `/api/becas/formularios/{id}/` | Ver / actualizar |

**Sync offline**: al crear un formulario con `datos_identificacion` (dni, nombre,
apellido, ...) y sin ciudadano, se resuelve por DNI con `get_or_create`
(`programas/services/becas.resolver_ciudadano_offline`): linkea el ciudadano
existente o lo crea, y limpia `datos_identificacion`.

## Cierre por vencimiento

Cuando la `fecha_fin` de una convocatoria pasa, se cierra sola (`activo=False`,
`cerrada_automaticamente=True`, `cerrada_el`), y sus relevamientos todavía
abiertos (`ASIGNADO/EN_CURSO/FINALIZANDO/FINALIZADO`) pasan a `EN_REVISION`. El
corte usa `timezone.localdate()`: con `fecha_fin = 31/07` sigue vigente el 31 y
vence el 01/08.

- **Mecanismo reusable**: registro de reglas en `core/services/vencimientos.py`;
  las reglas de Becas viven en `programas/services/vencimientos.py` (se registran
  en `ProgramasConfig.ready()`). Para sumar otra entidad, agregá una regla.
- **Runner**: `python manage.py procesar_vencimientos` (idempotente).
  Flags: `--dry-run` (no toca, solo informa) y `--solo <slug>`
  (`becas.convocatoria` / `becas.relevamiento`).
- **Cuándo corre**: en el arranque del contenedor `web`
  (`LOCAL_OPTIONAL_BOOTSTRAP_COMMANDS`) y a diario por cron del host — snippet
  versionado en [`docker/cron/procesar_vencimientos.cron`](../../docker/cron/procesar_vencimientos.cron).
- **Reactivar una vencida** ("fecha manda"): hay que extender la `fecha_fin`.
  Desde la tabla, el botón abre un pop-up (SweetAlert2) que pide la nueva fecha
  (`convocatoria_reactivar`); desde el detalle, el form valida que no se active
  con fecha pasada.

## Puesta en marcha

```powershell
# 1) Migrar (crea tablas de Becas y de authtoken)
python manage.py migrate

# 2) Sembrar el RBAC base y luego el Programa Becas (idempotentes)
python manage.py seed_rbac
python manage.py seed_becas
```

`seed_becas` deja: el `Programa(codigo="BECAS")`, los adjuntos obligatorios fijos
(`PreguntaGlobal` tipo ARCHIVO) y los 3 roles con sus capacidades. Reejecutable
sin duplicar.

## Tests

```powershell
$env:PY_VENV = "$PWD\.venv\Scripts\python.exe"
$env:DJANGO_SECRET_KEY = "test-key"
$env:PYTEST_RUNNING = "1"            # fuerza SQLite en memoria
$env:DJANGO_SYNCDB_PROJECT_APPS = "True"  # arma el esquema desde modelos
& $env:PY_VENV manage.py test programas
```

84 tests propios de Becas (`programas/tests/test_becas_*.py`). En la suite global
(`manage.py test`) quedan 3 fallos **pre-existentes** no relacionados con Becas:
2 errores de `seed_rbac` por el carácter `✓` en consola cp1252 de Windows y
`test_admin_ve_menu_completo` (espera un link `ciudadano_nuevo` que el sidebar ya
no tiene en `main`).

## Notas de entorno (Windows, sin Docker)

El venv documentado en [`venv-setup.md`](venv-setup.md) requiere Python 3.12
(usar `py install 3.12`). En Windows, `mysqlclient` no compila sin las libs de
MySQL: para correr `check`/tests basta instalar `requirements.txt` **sin**
`mysqlclient` y usar `PYTEST_RUNNING=1` (SQLite). `django-silk` necesita
`pkg_resources`: instalar `setuptools<81` en el venv.
