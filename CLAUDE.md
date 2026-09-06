# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Chaco

## Identidad del repo

`Chaco` es un monorepo Django orientado a backoffice y portal ciudadano.

- Stack: Python 3.12, **Django 5.2** (`requirements.txt` es el pin real), MySQL 8,
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
```

### Lint y frontend

```powershell
& $env:PY_VENV -m ruff check .          # line-length 120, reglas E/F/W/I
& $env:PY_VENV -m ruff format .
npm run build:tailwind                  # el CSS compilado está COMMITTEADO: no se regenera solo
```

### Auditorías obligatorias al tocar UI

```powershell
& $env:PY_VENV scripts\design_audit.py --changed      # adherencia al sistema de diseño → 0 errores
& $env:PY_VENV scripts\compile_templates.py           # sintaxis de TODOS los templates → 0
& $env:PY_VENV scripts\check_design_agent.py --changed
```

`design_audit.py` y `check_design_agent.py` también corren como hook `PostToolUse`
sobre `Edit|Write` (ver `.claude/settings.json`), así que un edit de UI que viole
una regla se avisa en el momento.

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

Para cualquier trabajo de UI, leé `AGENTS.md` y usá los agentes de
`.claude/agents/`:

- **`.claude/agents/chaco-design-system.md`** — fuente operativa única de diseño e
  inventario. Se contrasta contra el código antes de cada cambio.
- **`chaco-frontend`** — **desarrollo y migración** (con `Write`): construir una pantalla
  nueva o ajustar una existente, preservando contratos Django.
- **`chaco-design-reviewer`** — revisión de UI contra el código y el agente canónico.

Al tocar UI, no repitas reglas visuales ni adoptes valores desde materiales históricos:
seguí el inventario y la reconciliación de `.claude/agents/chaco-design-system.md`.

**Auditoría mecánica compartida:** `scripts/design_audit.py` es la fuente única de los
chequeos de adherencia (hex, fuentes legacy, `confirm()`, gradientes legacy, etc.).
Tras tocar UI: **0 errores es condición de cierre** (los WARN se evalúan con criterio),
y `scripts/compile_templates.py` también en 0 (caza tags rotos que `manage.py check`
no ve). Los comandos están arriba, en *Comandos → Auditorías*.

Si cambiás una pieza de UI clasificada como **canónica** en el inventario, el mismo
diff tiene que actualizar `.claude/agents/chaco-design-system.md`, o
`check_design_agent.py` falla (en el hook y en el CI).

## Gates de CI

Los PRs van contra `development`. Bloquean el merge:

- **Backend CI** — `manage.py check --deploy`, `makemigrations --check --dry-run` y
  `coverage run manage.py test` (`fail_under = 48` en `pyproject.toml`).
- **Performance Guard** — tests `--tag performance` (presupuestos de queries en
  `scripts/perf_budgets.json`), comparación de duración y contrato MySQL/Redis efímero.
- **Security** — `pip-audit`.
- **Design Agent Contract** — solo si el PR toca UI, agentes o los `.md` de contrato.

No bloquean (`continue-on-error`): Ruff lint, Ruff format, Bandit, dependency-review.
Igual se dejan en verde salvo que el rojo sea preexistente y ajeno al cambio.

## Gotchas

- **Django local ≠ Django del CI.** `requirements.txt` y el CI usan Django 5.2.17
  sobre Python 3.12; el `.venv/` de esta máquina puede estar en Django 4.2 y Python
  3.14. De ahí salen diferencias de errores de test y de presupuestos de queries.
  Receta para alinearlo: [`docs/internal/venv-setup.md`](docs/internal/venv-setup.md).
- **MySQL de ECOM sin tablas de timezone.** No usar `TruncWeek`/`TruncDate` sobre un
  `DateTimeField` con `USE_TZ` en código que corre en ECOM: Django lo traduce a
  `CONVERT_TZ`, que devuelve `NULL` y rompe **solo en producción**. Agrupar en Python
  (ver `programas/services/dashboard_becas.py`).
- **El CSS de Tailwind está committeado** y no se regenera solo: correr
  `npm run build:tailwind` y commitear la salida.
- **`nginx` cachea la IP del upstream**: tras recrear `web`/`websocket` hay que
  reiniciarlo, o aparecen 500 por *"Missing staticfiles manifest entry"* (README.md).
- **MySQL pineado en 8.0.32** en producción: versiones más nuevas mueren en CPUs sin
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
`main` → **producción**, deploy automático). Ese espejo se hace con `/pushGitLabecom`;
la app móvil va aparte con `/pushGitLabecomMOBILE`.
