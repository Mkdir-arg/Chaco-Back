# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Chaco

## Identidad del repo

`Chaco` es un monorepo Django orientado a backoffice y portal ciudadano.

- Stack: Python 3.12, **Django 5.2** (`requirements.txt` es el pin real), MySQL 8
  (local e icore-srv) / **MariaDB en ECOM, testing y PRD**,
  Redis 7, Channels, Tailwind CSS, Alpine.js, Docker Compose
- Apps que concentran trabajo: `programas` (la más grande, ~28k LOC), `core`,
  `users`, `legajos`, `portal`, `conversaciones`, `configuracion`, `dashboard`
- Superficies principales: backoffice y portal ciudadano
- La fuente de verdad es el código actual del repo, no documentación histórica

## Regla principal

Trabajar code-first.

1. Leer este archivo.
2. Entender el pedido actual del usuario.
3. **Consultar el archivo vivo de requerimientos** por etiqueta, para no rehacer ni
   contradecir una decisión ya tomada (ver más abajo). Se consulta por índice, nunca
   leyéndolo entero.
4. Inspeccionar el código real afectado.
5. Diseñar o implementar con cambios mínimos y verificables.
6. Validar con `manage.py check`, tests o revisión de templates según corresponda.
7. **Registrar el requerimiento en `docs/internal/requerimientos.md`** (ver más abajo). Sin ese paso el desarrollo no está terminado.

## Comandos

Todo `python` del repo va **siempre por el venv del proyecto**, nunca por el Python
global de la máquina (suele tener `django-silk` viejo incompatible). Si `.venv/` no
existe, crearlo siguiendo [`docs/internal/venv-setup.md`](docs/internal/venv-setup.md).

```powershell
# raíz del repo — prólogo de casi cualquier sesión
$env:PY_VENV = "$PWD\.venv\Scripts\python.exe"
$env:DJANGO_SECRET_KEY = "test-key"
```

Los comandos de acá son PowerShell y ahí andan tal cual. Si en cambio los corrés
por la herramienta Bash (Git Bash), la salida va en cp1252 y los scripts que
imprimen emoji —`requerimientos.py` y su semáforo de estado— mueren con
`UnicodeEncodeError`: exportá `PYTHONIOENCODING=utf-8` antes.

### Verificación y tests

```powershell
& $env:PY_VENV manage.py check                  # system check
& $env:PY_VENV manage.py check --deploy         # lo que corre el CI

# Tests: runner de Django (NO pytest). PYTEST_RUNNING=1 fuerza SQLite en memoria,
# así que no hace falta MySQL levantado; DJANGO_SYNCDB_PROJECT_APPS=True crea las
# tablas desde los modelos y saltea las migraciones.
$env:PYTEST_RUNNING = "1"; $env:DJANGO_SYNCDB_PROJECT_APPS = "True"
& $env:PY_VENV manage.py test                                   # suite completa
& $env:PY_VENV manage.py test programas                         # una app
& $env:PY_VENV manage.py test programas.tests.test_becas_rbac   # un módulo
& $env:PY_VENV manage.py test programas.tests.test_becas_rbac.NombreTest.test_caso
& $env:PY_VENV manage.py test --tag performance                 # presupuestos de queries

& $env:PY_VENV manage.py makemigrations --check --dry-run       # gate: no faltan migraciones
& $env:PY_VENV scripts\check_migraciones.py                     # gate: contrato de las migraciones nuevas
```

Las migraciones ida y vuelta contra el motor real (lo que corre el job `Migrate ida y
vuelta`) necesitan un contenedor y el árbol de la base del PR:

```powershell
docker run -d --name rt-db -e MARIADB_ROOT_PASSWORD=root -e MARIADB_DATABASE=chaco_perf_ci `
  -e MARIADB_INITDB_SKIP_TZINFO=1 -p 3331:3306 mariadb:10.11
docker run -d --name rt-redis -p 6382:6379 redis:7-alpine
git worktree add ..\base origin/development

$env:ENVIRONMENT = "ci"; $env:PERFORMANCE_CI = "1"          # los exige `seed_perf`
$env:DATABASE_NAME = "chaco_perf_ci"; $env:DATABASE_USER = "root"; $env:DATABASE_PASSWORD = "root"
$env:DATABASE_HOST = "127.0.0.1"; $env:DATABASE_PORT = "3331"
$env:REDIS_HOST = "127.0.0.1"; $env:REDIS_PORT = "6382"
$env:DJANGO_SETTINGS_MODULE = "settings_roundtrip"; $env:PYTHONPATH = "$PWD\.github\ci"
& $env:PY_VENV scripts\roundtrip_migraciones.py --arbol-base ..\base
& $env:PY_VENV scripts\check_sqlmigrate.py --arbol-base ..\base
```

Borrar los contenedores y el worktree al terminar (`docker rm -f rt-db rt-redis`,
`git worktree remove ..\base`). Nunca contra una base real.

### Lint y frontend

```powershell
& $env:PY_VENV -m ruff check .          # line-length 120, reglas E/F/W/I
& $env:PY_VENV -m ruff format .
npm run build:tailwind                  # el CSS compilado está COMMITTEADO: no se regenera solo
```

### Auditorías obligatorias al tocar UI

```powershell
& $env:PY_VENV scripts\design_audit.py --ratchet      # adherencia al sistema de diseño → 0 hallazgos NUEVOS
& $env:PY_VENV scripts\design_audit.py --arquetipo <listado|detalle|formulario|modal> <archivo>  # pantalla nueva
& .\.venv312\Scripts\python.exe scripts\compile_templates.py --bloques  # sintaxis de TODOS los templates → 0, + ningún {% block %} sin destino (con .venv da 1 falso por {% querystring %})
& $env:PY_VENV scripts\check_design_agent.py --changed
```

`design_audit.py` y `check_design_agent.py` también corren como hook `PostToolUse`
sobre `Edit|Write` (ver `.claude/settings.json`). El hook compara contra `HEAD` y avisa
solo lo que agregó la edición; la deuda previa del archivo no se reporta.

### Requerimientos

```powershell
& $env:PY_VENV scripts\requerimientos.py --tag rbac      # qué se decidió sobre el tema
& $env:PY_VENV scripts\requerimientos.py --buscar "cupo" # dónde se habló de algo
& $env:PY_VENV scripts\requerimientos.py --ver 24        # una entrada completa
& $env:PY_VENV scripts\requerimientos.py --check         # coherencia índice <-> entradas
```

### Docker

```bash
docker compose up -d --build                                # dev: app en :8000, MySQL en :3307
docker compose -f docker-compose.prod.yml up -d --build     # prod (ver README.md)
```

El entrypoint corre migraciones, `collectstatic` y el bootstrap
(`seed_datos_base crear_programas`) según variables de entorno.

## Arquitectura

### Mapa de URLs a apps (`config/urls.py`)

| Ruta | App | Qué vive ahí |
|---|---|---|
| `/becas/` | `programas` | Becas: programas SIIS, segmentos/subsegmentos, cupos, convocatorias, relevamientos, formularios, padrón, revisión, dashboard y reportes |
| `/dispositivos/` | `programas` | Dispositivos: alta y validación, camas, admisiones, registro diario, espera |
| `/merenderos/` | `programas` | Merenderos: solicitudes, entregas de mercadería, prestaciones |
| `/legajos/` | `legajos` | Ciudadanos, legajos de atención, derivaciones, alertas, adjuntos, RENAPER |
| `/portal/` | `portal` | Portal ciudadano (registro, perfil, consultas) e inscripción pública por token |
| `/conversaciones/` | `conversaciones` | Chat backoffice ↔ ciudadano, colas, presencia |
| `/configuracion/` | `configuracion` | Geografía, secretarías y subsecretarías, wizard de programas |
| `/` (raíz) | `users`, `core`, `dashboard`, `healthcheck` | Login y ABM de usuarios/roles, inicio, métricas, `/health/` |
| `/api/...` | varias | DRF; esquema en `/api/schema/`, docs en `/api/docs/` — **todas detrás de login** |

`tramites/` está declarada en `INSTALLED_APPS` pero es un stub sin urls ni modelos.

### Patrón de capas

Cada app de dominio sigue el mismo corte, y conviene respetarlo al agregar código:

```
models/      datos
selectors/   consultas de lectura, sin lógica de negocio
services/    lógica de negocio y escritura  <- acá va el peso del dominio
views/       orquestación HTTP, sin lógica de dominio
forms/       validación de entrada (Django Forms/ModelForms)
templates/   presentación
```

En `programas` el dominio está partido por producto dentro de `services/` y
`views/` (`becas.py`, `dispositivos.py`, `merenderos.py`, `cupo.py`, `siis.py`…).
Los modelos de los tres productos conviven en `programas/models/__init__.py`.

### Autorización: capacidades, no grupos

[`core/rbac.py`](core/rbac.py) es la **pieza única** de autorización del backoffice.
Una capacidad (`modulo.accion`, p. ej. `ciudadano.ver`) es un `Permission` real de
Django anclado al modelo `users.Capacidad`, tildado sobre cada Rol (`Group`) vía
`group.permissions`.

- Se autoriza **solo por capacidad**, nunca por nombre de grupo.
- Un Rol = `Group` + `users.RolMeta` (descripción, categoría, protegido, activo, y
  `programa` cuando la categoría es `Programa`).
- API de uso: `puede(user, codigo, programa=None)`, `puede_alguna(...)` y el
  decorador `@requiere("codigo.capacidad")`.
- El `CATALOGO` de `core/rbac.py` es la fuente única: alimenta el seed, el árbol del
  ABM de Roles y el modelo ancla. Agregar una capacidad implica tocar ese catálogo,
  no inventar un permiso suelto.
- Los módulos con `"alcance": "programa"` se evalúan **acotados a un programa**; el
  alcance de admin de programa se mueve en varios lugares a la vez (`CAPS_ADMIN_*`).
- `is_superuser` tiene bypass total. El grupo `Ciudadanos` es un marcador de
  identidad del portal, no una capacidad de backoffice (`es_ciudadano_portal`).

### Separación backoffice / portal

`core.middleware.PortalCiudadanoMiddleware` redirige a `portal:ciudadano_mi_perfil`
a cualquier usuario ciudadano que pise una URL fuera de `/portal/`. Es la barrera
real entre las dos superficies: no alcanza con esconder el link.

Otros middlewares propios que condicionan el comportamiento:
`users.middleware.BackofficeSingleSessionMiddleware` (una sola sesión de backoffice
por usuario), `CambioContrasenaObligatorioMiddleware` (bloquea hasta cambiar la clave
provisoria) y `config.middlewares.security_headers.SecurityHeadersMiddleware` (CSP y
`frame-ancestors`, porque el ingress pisa `X-Frame-Options`).

### Tiempo real e integraciones

- WebSockets por Channels (`conversaciones/consumers.py`, `config/asgi.py`), solo con
  `APP_RUNTIME=daphne`; con `runserver` las rutas `ws/` responden `426`.
- Integraciones externas, todas con credenciales por entorno: **RENAPER** (padrón de
  personas, con `RENAPER_TEST_MODE`), **Personas API** y **SIIS**
  (`programas/services/siis.py`, `siis_sync.py`, `validacion_siis.py`).
- `media/` se sirve detrás de login: ahí viven documentos del ciudadano y padrones.

### Entornos y settings

`config/settings.py` es único y se ramifica por variables de entorno: `ENVIRONMENT`
(`dev|qa|prd`), `DJANGO_DEBUG`, `PYTEST_RUNNING` (→ SQLite en memoria + `zeal`),
`DJANGO_SYNCDB_PROJECT_APPS` (→ sin migraciones), `PERFORMANCE_*`. Redis solo se usa
como cache/sessions en `prd` o en el CI de performance; en dev es LocMem.
`config/settings_production.py` fuerza `DEBUG=False`.

## Convenciones de implementación

- Priorizar lectura de código antes de asumir comportamiento.
- No depender de `docs/`, `documentos/` ni `memory/` como prerequisito de trabajo.
- Si falta contexto funcional, derivarlo del código, rutas, templates y nombres del dominio.
- Usar Django Forms/ModelForms para formularios del backoffice.
- Crear migraciones inmediatamente después de cambiar modelos (el CI falla si faltan).
- **Contrato de las migraciones nuevas** (`scripts/check_migraciones.py`, gate del job
  `Migration Check`): una columna nueva nace `null=True`, o `NOT NULL` con `DEFAULT` real
  en la base (`RunSQL(… SET DEFAULT …, state_operations=[])`), o lleva
  `# ROLLBACK-OK: <motivo>` —si no, el código viejo deja de poder dar de alta apenas se
  baja la release—; un `RemoveField`/`DeleteModel`/`RenameField`/`RenameModel` lleva
  `# CONTRACT: <dejó de leerse en la release X>` y va dos releases después de que nadie
  lo lea; y todo `RunPython`/`RunSQL` declara su reversa, con `# REVERSA-NOOP: <qué dato
  queda inconsistente>` si no deshace nada. Las ocho migraciones por las que no se vuelve
  están en el paso D.4 de [`processes.md`](docs/internal/processes.md).
- **Expand/contract** (job `Migrate ida y vuelta`, que ejecuta las migraciones del PR
  contra MariaDB y MySQL y después las desaplica, sobre datos sembrados): durante el
  rolling conviven la release vieja y la nueva contra el mismo esquema, así que *expand*
  (agregar) va sola en la release N y *contract* (borrar, renombrar, **o un `AlterField`
  que pone `NOT NULL` o le saca el `DEFAULT` a una columna**) va recién en N+2. Eso
  último no lo ve `check_migraciones.py` —necesita el estado anterior— y lo mide el job
  comparando el esquema real antes y después. Y una migración **ya aplicada** se puede
  editar (marcas, comentarios, reversa) pero su **SQL de ida no puede cambiar**: lo
  compara `scripts/check_sqlmigrate.py` en el mismo job.
- Modelos nuevos: heredar de `core.models.TimeStamped` como hace el resto.
- Templates del backoffice: extender `includes/base.html`.
- Templates del portal: extender `portal/base.html`.
- Confirmaciones destructivas: SweetAlert2 o modal equivalente, nunca `confirm()` nativo.
- Notificaciones: `window.toast()` (`nodo-toast.js/css`); los templates hijos no llevan
  su propio bloque `{% for message in messages %}`.
- Mantener cambios pequeños, consistentes y fáciles de validar.

## Regla de oro: el archivo vivo de requerimientos

[`docs/internal/requerimientos.md`](docs/internal/requerimientos.md) **se consulta al
iniciar un requerimiento y se escribe al terminarlo.** Las dos mitades son obligatorias.

**Al iniciar** — el archivo crece sin parar, así que no se lee entero: se consulta con
[`scripts/requerimientos.py`](scripts/requerimientos.py) (comandos arriba), que lo
indexa por etiquetas y devuelve solo lo pedido. Se leen las entradas del tema —sobre
todo **Decisiones tomadas**, **Pendientes** e **Historial**— antes de diseñar. Si lo
que se va a hacer contradice algo registrado, se dice antes de implementar.

**Al terminar** — se agrega la entrada nueva y su fila en el índice. Es condición de
cierre junto con `manage.py check` y la auditoría de diseño, y se verifica con
`scripts\requerimientos.py --check` (tiene que dar OK).

La regla completa, la plantilla obligatoria, el vocabulario de etiquetas y el índice
viven **en ese archivo**; no se duplica su contenido acá.

## Diseño / UI (nuevo sistema de diseño)

El frontend productivo es la evidencia que prevalece para toda decisión de UI.
`docs/design-kb/` conserva assets, prototipos y antecedentes; no autoriza a cambiar
el producto para calcarlo. Los tokens y componentes cargados se relevan desde el
código y se inventarían en el agente canónico.

Para cualquier trabajo de UI usá los agentes de `.claude/agents/` (de `AGENTS.md`
no hace falta leer nada para UI):

- **`.claude/agents/chaco-design-system.md`** — fuente operativa única de diseño e
  inventario (núcleo corto; fichas de arquetipos y componentes en `.claude/design/`).
  Se contrasta contra el código antes de cada cambio.
- **`chaco-frontend`** — **desarrollo y migración** (con `Write`): construir una pantalla
  nueva o ajustar una existente, preservando contratos Django.
- **`chaco-design-reviewer`** — revisión de UI contra el código y el agente canónico.

Al tocar UI, no repitas reglas visuales ni adoptes valores desde materiales históricos:
seguí el inventario y la reconciliación de `.claude/agents/chaco-design-system.md`.

**Pantalla nueva = clonar la golden de su arquetipo.** La tabla *Arquetipos* del agente
canónico nombra una sola pantalla de referencia por arquetipo; se copia su esqueleto (ficha
en `.claude/design/arquetipos/`) y se cambia solo el dominio. Una pantalla hermana del
mismo módulo **nunca** es molde. Antes de escribir se declara el *Plan de pantalla*; si
trae novedades (clase, include, variante o valor nuevo) no se escribe y se devuelve al
llamador.

**Auditoría mecánica compartida:** `scripts/design_audit.py` es la fuente única de los
chequeos de adherencia (hex, fuentes legacy, `confirm()`, paleta cruda, `style=`,
`<style>`, encabezado, tabla, íconos, clases inexistentes…). Funciona como *ratchet*: la
corrida completa tiene deuda preexistente, pero **0 hallazgos nuevos respecto de la base es
condición de cierre** (hook local y CI). Las goldens se mantienen en 0 (`--goldens`, en CI),
y `scripts/compile_templates.py` también en 0 (caza tags rotos que `manage.py check`
no ve). Los comandos están arriba, en *Comandos → Auditorías*.

Si cambiás una pieza de UI clasificada como **canónica** o una golden, el mismo diff
tiene que actualizar su fila en `.claude/agents/chaco-design-system.md` o su ficha en
`.claude/design/`, o `check_design_agent.py` falla (hook y CI). La historia de los
cambios va a `docs/internal/requerimientos.md`, nunca al agente.

## Gates de CI

Los PRs van contra `development`. Estos checks **tienen que estar en verde** —y salen
rojos si no lo están—, pero hoy el merge no los exige todavía: el repo no tiene
protección de rama. Los dos rulesets que la encienden están versionados en
[`docs/internal/rulesets/`](docs/internal/rulesets.md) y **los aplica el dueño del
repo**; hasta entonces, no mergear en rojo es una regla del proceso, no un mecanismo.

- **Backend CI** — `manage.py check --deploy` (`Django System Check`),
  `makemigrations --check --dry-run` + `scripts/check_migraciones.py` sobre las
  migraciones nuevas del PR (`Migration Check`) y `coverage run manage.py test`
  (`Tests & Coverage`, `fail_under = 48` en `pyproject.toml`).
- **Performance Guard** — tests `--tag performance` (presupuestos de queries en
  `scripts/perf_budgets.json`), comparación de duración y contrato MySQL/Redis efímero.
  Ahí viven también los dos jobs que corren contra el motor de verdad, **todavía no
  obligatorios**: `Motor real (<motor>)` (los tests `@tag("mysql")` contra
  `mariadb:10.11`, `mariadb:11` y `mysql:8.0`) y `Migrate ida y vuelta (<motor>)` (las
  migraciones del PR aplicadas, desaplicadas y vueltas a aplicar sobre datos sembrados,
  contra `mariadb:10.11` sin tablas de zona horaria y `mysql:8.0`). Los dos entran al
  ruleset cuando acumulen corridas.
- **Security** — `pip-audit` (`Pip Audit`), con las excepciones de
  `security/excepciones.toml`, que vencen.
- **Datos** — `Sin datos personales`: ningún volcado de personas entra al repo.
- **Code Quality** — `Ruff errores` (`ruff check . --select F`) y `Contratos del repo`: las condiciones de cierre de
  este archivo, corridas en el CI (sintaxis de todos los templates, `requerimientos.py --check`, `collectstatic` con el
  almacenamiento con manifest y el ratchet de `design_audit` contra `.design-audit-ratchet`).
- **Design Agent Contract** — `Validate inventory and authority`: contrato y límites del
  agente (`check_design_agent.py --limites`), `design_audit.py --ratchet` (0 hallazgos
  nuevos), `--goldens` (las pantallas de referencia en 0) y build de Tailwind sin diff.

Los dos últimos corren en **todos** los PRs: el filtro por rutas está adentro del job,
así que cuando el PR no toca Python o UI el check termina en verde sin hacer nada. Un
check con `paths:` en el trigger no puede ser obligatorio, porque no reporta nunca.

No bloquean (`continue-on-error`): `Ruff estilo` (E, W, I y formato), Bandit y
dependency-review. Igual se dejan en verde salvo que el rojo sea preexistente y ajeno
al cambio.

`Backend CI`, `Performance Guard` y `Datos` corren además en `push` a `development`,
para que un push directo deje un check rojo visible mientras no haya ruleset.

`Release gate` (`release-gate.yml`) no corre en los PRs: se dispara a mano con el SHA de
`main` que se va a espejar y verifica **ese release** —CI verde del PR que lo originó,
suite completa, migraciones sobre MariaDB, la imagen construida con su manifest de
estáticos y un smoke HTTP—. Es lo que `/pushGitLabecomTEST` corre antes de espejar y lo
que `/pushGitLabecomPRD` exige en verde. Y `publish-main.yml` no publica un release de un
commit que no venga de un PR con el CI en verde.

## Gotchas

- **Django local ≠ Django del CI.** `requirements.txt` y el CI usan Django 5.2.17
  sobre Python 3.12; el `.venv/` de esta máquina puede estar en Django 4.2 y Python
  3.14. De ahí salen diferencias de errores de test y de presupuestos de queries.
  Receta para alinearlo: [`docs/internal/venv-setup.md`](docs/internal/venv-setup.md).
- **ECOM corre MariaDB, en testing y en PRD** (no MySQL). El código tiene que andar en
  los dos motores: MySQL 8 local e icore-srv, MariaDB en ECOM. Lo más visible:
  con MariaDB 10.7+ Django 5 manda el `UUIDField` **con guiones** (36 caracteres), así
  que una columna `char(32)` da *"Data too long"* y un lookup `campo=uuid` no encuentra
  filas en hex (las trae un restore). Todo `UUIDField` nuevo necesita su migración a
  `char(36)` (patrón de `programas.0073`) y búsqueda con `q_uuid_en_texto`
  (`programas/services/becas.py`). Cambio 99.
- **La base de ECOM no tiene tablas de timezone.** No usar `TruncWeek`/`TruncDate` sobre un
  `DateTimeField` con `USE_TZ` en código que corre en ECOM: Django lo traduce a
  `CONVERT_TZ`, que devuelve `NULL` y rompe **solo en producción**. Agrupar en Python
  (ver `programas/services/dashboard_becas.py`).
- **El CSS de Tailwind está committeado** y no se regenera solo: correr
  `npm run build:tailwind` y commitear la salida.
- **`nginx` cachea la IP del upstream**: tras recrear `web`/`websocket` hay que
  reiniciarlo, o aparecen 500 por *"Missing staticfiles manifest entry"* (README.md).
- **MySQL pineado en 8.0.32** en icore-srv: versiones más nuevas mueren en CPUs sin
  `x86-64-v2`.

## Gestión en GitHub

- El repo en GitHub es **`Mkdir-arg/Chaco-Back`**: usar `--repo Mkdir-arg/Chaco-Back`
  en todo comando `gh` (el nombre viejo devuelve vacío en silencio).
- El trabajo se organiza en Issues con el modelo: **Épica → Análisis → Sub-issues**.
- Al crear issues, se dejan en **Backlog**. El Project #1 los auto-mueve a "Ready" al
  crearlos o asignarlos: re-setear `Status=Backlog` como último paso y verificar.
- **Solo el PM mueve las tareas** entre estados/columnas del Project. Ningún agente
  ni asistente debe cambiar el estado de una tarea: como mucho crea issues en Backlog.
- La **semántica de los estados** (qué significa cada Status según el Tipo, gates
  para mover, reglas de assignees y handoffs entre agentes) está en **`ESTADOS.md`**
  (raíz). Regla clave: **sin casos de QA, una task no es Ready**.

## Análisis funcional

El método completo del analista funcional (cómo relevar, estructuras de issues,
receta `gh`, publicación) vive en **`AGENTS.md`** (raíz), fuente de verdad única
compartida con todas las herramientas. Para tareas de análisis, seguí ese archivo.

## QA

El método del Agente QA (casos de prueba en el cuerpo de cada task, plan de
pruebas `[PLAN DE PRUEBAS]` por épica, revisión de cobertura) vive en **`QA.md`**
(raíz), hermano de `AGENTS.md`. Para tareas de QA, seguí ese archivo.

## Gestión (PM Assistant)

El método del PM Assistant (estado del sprint, auditoría de salud/trazabilidad,
minutas y reportes en lenguaje cliente — **solo lectura** sobre el Project) vive
en **`PM.md`** (raíz), hermano de `AGENTS.md` y `QA.md`.

## Acceso a GitHub

Todos los agentes (Analista, QA, PM Assistant) usan el **MCP de GitHub**
(server `github` en `.mcp.json`) como vía preferida para leer issues y el
Project #1 de `Mkdir-arg` (https://github.com/users/Mkdir-arg/projects/1/),
con fallback a la CLI `gh`. Las escrituras estructuradas al Project usan la
receta `gh` de `AGENTS.md`.

## Ramas y releases

`development` es la rama de trabajo y la rama por defecto. `main` es una release
generada automáticamente por `.github/workflows/publish-main.yml` y **no se toca a
mano**. El snapshot excluye los archivos de desarrollo (`.claude/`, `docs/`,
`AGENTS.md`, `CLAUDE.md`, los scripts de auditoría…) vía `export-ignore` en
`.gitattributes`, y un guard del workflow rechaza el release si alguno se cuela o si
falta un archivo de runtime. El detalle operativo vive en
[`docs/internal/branching.md`](docs/internal/branching.md).

`main` se espeja después al GitLab de ECOM, que tiene CI/CD propio (`test` → testing,
`main` → **producción**, deploy automático). Ese espejo va en **dos pasos separados, con
una verificación humana en el medio**: `/pushGitLabecomTEST` (corre el `release-gate` y
espeja `test`) y, después de que alguien pruebe testing, `/pushGitLabecomPRD` (exige el
mismo árbol en `ecom/test`, el gate en verde y una segunda confirmación escribiendo
`PRODUCCION`). El procedimiento normativo está en
[`docs/internal/espejo-ecom.md`](docs/internal/espejo-ecom.md). La app móvil va aparte
con `/pushGitLabecomMOBILE`.
