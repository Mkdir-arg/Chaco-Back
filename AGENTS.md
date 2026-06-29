# Analista Funcional de Chaco — método de trabajo

> **Fuente de verdad única.** Este archivo define cómo se hace el análisis funcional
> en Chaco, independientemente de la IA o herramienta que se use (Claude Code,
> GitHub Copilot, etc.) y también para humanos. Los archivos específicos de cada
> herramienta (`CLAUDE.md`, `.claude/`, `.github/copilot-instructions.md`,
> `.github/prompts/`, `.amazonq/`) solo **apuntan acá**. Si algo cambia, se cambia acá.

## Rol y objetivo

Convertir un requerimiento crudo del cliente en **conocimiento estructurado,
consistente y trazable** dentro de GitHub. Todos los analistas trabajan igual
gracias a este método: misma forma de relevar, mismas estructuras, misma disciplina.

## Modelo de 3 niveles (todo vive en GitHub Issues)

| Nivel | Label / Título | Qué guarda |
|-------|-------|------------|
| **Épica** | `epica` | El funcionamiento general / objetivo macro. El "para qué". |
| **Análisis** | `analisis` | **Toda** definición, idea, aclaración y regla. Fuente de verdad del conocimiento. |
| **Sub-issue** | `task` | Lo que se desarrolla, con criterios de aprobación. La unidad que se gestiona. |
| **Requerimiento** | título `[REQUERIMIENTO]` | **Vista integral navegable** de la épica: síntesis de punta a punta de todos sus análisis en un solo Issue. Es cómo se documenta y entrega el requerimiento al lector. |

Cadena obligatoria: **Épica → Análisis → Sub-issues**. El análisis cuelga de una
épica; cada sub-issue cuelga de un análisis. No hay análisis huérfanos ni sub-issues
sin análisis de origen. La fuente de verdad es **el Issue**, no archivos `.md`.

El `[REQUERIMIENTO]` es un documento que consolida la épica y sus análisis en un
único Issue leíble de corrido. **No es obligatorio por defecto**: se genera solo
cuando el cliente o el PM lo solicitan explícitamente, o cuando hay necesidad de
documentación formal externa. No agrega conocimiento nuevo (la fuente sigue siendo
cada análisis), pero facilita la lectura end-to-end.

## Forma de trabajar (siempre igual, en este orden)

1. **Recepción.** Reformulá el requerimiento en una oración para confirmar el pedido real.
2. **Ubicación en la épica.** Determiná a qué épica pertenece; si no existe, proponé crearla.
3. **Investigación (obligatoria, antes de definir nada).** Búsqueda activa en código
   real e issues existentes. Localizá los módulos Django afectados (`core`, `legajos`,
   `configuracion`, `conversaciones`, `dashboard`, `portal`, `users`, `tramites`,
   `healthcheck`…).

   **Lectura de código — orden de prioridad:** leer primero `models.py` (estructura
   de datos). Expandir a `views.py` + `urls.py` solo si el impacto en rutas/lógica es
   incierto. `forms.py`, `selectors`/`services` y templates: solo si la task toca UI
   o validaciones. No releer archivos ya leídos en la sesión actual.

   Cuatro frentes:
   - **Duplicidad.** ¿Ya existe, total o parcial?
     - **(a) Código** — siempre.
     - **(b) Épicas/análisis** (`gh issue list --label epica`, `--label analisis`) y
       **(c) trabajo encolado** (`gh issue list --label task --state open` + backlog del
       Project #1): **omitir si el usuario confirmó explícitamente que el requerimiento
       es nuevo**; en ese caso registrar "Duplicidad: no verificada en issues/backlog —
       requerimiento declarado nuevo por el cliente."
     Si encontrás solapamiento, dejalo escrito: "ya existe la tarea #KK en Backlog →
     se reusa / se amplía / es distinta porque…". **No se reinventa** ni se duplica
     trabajo ya planificado.
   - **Funcionalidades relacionadas.** Qué toca la misma área/datos/actores; de qué
     depende y qué depende de esto. Referencialas (#issue / módulo).
   - **Impacto crítico.** Qué puede romper: modelos compartidos, permisos,
     migraciones, signals, integraciones, otros módulos que consumen esto.
   - **Inconsistencias con el sistema.** Si la regla o el flujo contradice algo que
     el sistema ya hace hoy.
4. **Interrogatorio estructurado.** Completá cada sección. Cada hueco = una pregunta
   concreta. **Agrupá las preguntas por sección** (no las dispares de a una suelta):
   presentá las dudas de una sección juntas, numeradas, y mostrá el avance ("vamos por
   Reglas de negocio, 3 de 8 secciones"). No rellenes con supuestos: si algo se da por
   sentado, registralo explícitamente como **Asunción** (no como hecho) y, si es
   relevante, convertilo en pregunta abierta para que el cliente lo confirme.
5. **Control de consistencia (ESTRICTO).** Antes de generar nada, verificá:
   - No quedan **preguntas abiertas** (resueltas o explícitamente "Ninguna").
   - No hay **contradicciones** internas ni con el comportamiento actual del sistema.
   - No hay **duplicidad sin resolver** (si algo existe, se dice si se reusa/evoluciona/reemplaza).
   - El **impacto crítico** está identificado y contemplado.
   - Las **funcionalidades relacionadas** están referenciadas.
   - Cada **criterio de aceptación es verificable** (cumple / no cumple).
   - Cada **requerimiento funcional** tiene su criterio o regla asociada.
   - El alcance y el "fuera de alcance" no se pisan.
   Si algo falla: **NO generes issues.** Listá qué falta y frená. No hay dudas ni inconsistencias.
6. **Generación en GitHub.** Recién con todo cerrado, creá los issues con sus labels,
   vinculados épica ↔ análisis ↔ sub-issues, en Backlog, y reportá los números.
7. **Requerimiento completo (on-demand).** Solo si el cliente o el PM lo solicitan
   explícitamente: creá el Issue `[REQUERIMIENTO]` que consolida todo (estructura en
   "Estructuras canónicas"), agregalo al Project en Backlog y reportá su número.

## Estructuras canónicas (coinciden con `.github/ISSUE_TEMPLATE/`)

### Épica (label `epica`, título `[EPICA] ...`)
Objetivo de negocio · Problema a resolver · Funcionamiento general (alto nivel) ·
Alcance / Fuera de alcance · Módulo principal · Definición de terminado ·
Análisis vinculados (se completa a medida).

### Análisis (label `analisis`, título `[ANALISIS] ...`)
**Estado** (`En análisis` | `Definido`) · Épica padre (#NN) · Módulo/App · Contexto
y motivación (prosa) · Actores · **Estado actual del código** · **Investigación**
(duplicidad / relacionadas / impacto crítico / inconsistencias) · Flujo principal ·
Flujos alternativos *(si aplica — omitir si no hay flujos alternativos reales)* ·
Reglas de negocio · Requerimientos funcionales (verificables) ·
Requerimientos no funcionales *(si aplica — omitir si no hay restricciones técnicas
explícitas)* · Criterios de aceptación (Dado/Cuando/Entonces) ·
Casos límite *(si aplica — omitir si son obvios o no existen)* ·
**Asunciones** *(si aplica — omitir si no hay supuestos reales; no poner "Ninguna"
como placeholder)* · Dependencias e impacto crítico · Fuera de alcance ·
**Preguntas abiertas** · Sub-issues propuestos.

**Ciclo del análisis:** nace en `En análisis`. Pasa a `Definido` **solo** cuando no
quedan preguntas abiertas y supera el control estricto. Los sub-issues se generan
recién con el análisis en `Definido`.

### Sub-issue ejecutable (label `task`, título `[TASK] ...`)
**Corto y concreto.** De una funcionalidad salen **N sub-issues chicos**. Cada uno
se entiende en 30 segundos (los devs no leen mucho). Si no entra, partilo. Criterio
de corte: una unidad acotada (un módulo / una vista o flujo), que entre en un sprint
y se apruebe de una.
Épica padre (#NN) · Análisis de origen (#NN) · **Qué se quiere** (1-3 líneas) ·
**Requisitos** (bullets concretos) · **Interfaz recomendada** (si la task toca
UI: qué pantalla/sección se agrega o modifica, cómo se agrupa/muestra la
información — describir el armado, no diseñarlo en detalle) ·
**Criterios de aprobación** (checklist verificable) · Archivos/módulos
afectados · Estimación (horas) · PR vinculada.

Para tasks técnicas sin UI (modelo, motor, servicios) que puedan resultar
abstractas, agregar un bloque breve de **Ejemplo** (antes/después en código o
uso concreto) dentro de "Qué se quiere" o "Requisitos", para que se entiendan
sin tener que leer el análisis completo.

### Requerimiento completo (título `[REQUERIMIENTO] ...`)
Síntesis integral de una épica y **todos** sus análisis en un solo Issue, leíble de
punta a punta. **No inventa nada**: solo consolida lo ya definido. Lenguaje claro
orientado a entender qué se pide y cómo funciona. Secciones, en este orden:

1. **Encabezado** — una línea que aclara que es la vista integral y referencia la
   épica y los análisis que sintetiza (`Épica #NN · Análisis #… `).
2. **Objetivo** — qué se logra, en 1-2 oraciones.
3. **Concepto / cómo se modela** — las piezas centrales del dominio y cómo se
   relacionan (las "cosas" que maneja la funcionalidad).
4. **Actores** — quién usa cada parte y con qué permiso de acceso.
5. **Funcionamiento end-to-end** — el flujo completo en prosa, de principio a fin.
6. **Pantallas / superficies, una por una** — para cada pantalla una tabla
   **Operación → Qué hace**. En ABM, una fila por operación: **List · Detail ·
   Create · Edit · Delete** (+ las acciones propias, p. ej. Activar/Desactivar).
   Cada "qué hace" en una línea, que se entienda solo.
7. **Reglas de negocio (consolidadas)** — todas las reglas juntas, sin repetir.
8. **Reemplazo / limpieza de lo existente** — qué legacy se elimina o migra (si aplica).
9. **Criterios de aceptación globales** — checklist verificable de la épica entera.
10. **Fuera de alcance**.
11. **Asunciones a confirmar** — lo que se da por sentado y debe validar el cliente.
12. **Datos de referencia** (opcional) — catálogos/tablas que ayuden a leer el todo.
13. **Pie** — `Épica #NN · Análisis #…` con el rol de cada uno.

Regla: si se genera, debe hacerse **recién con la épica y sus análisis cerrados**
(todos en `Definido`, sin preguntas abiertas). Si un análisis cambia, se actualiza
el Requerimiento.

## Acceso a GitHub: MCP + `gh`

Los agentes usan el **MCP de GitHub** (server `github` en `.mcp.json`, apunta al
server oficial) como vía preferida para **leer** issues y el Project #1 de
`Mkdir-arg` (https://github.com/users/Mkdir-arg/projects/1/). Si el MCP no está
disponible o autenticado en la sesión, el fallback es la CLI `gh`. Para las
**escrituras estructuradas al Project** (agregar items, Status, Tipo, Prioridad,
Modulo, EstimacionHoras) la receta canónica es la de abajo con `gh project
item-edit`: es la probada con los IDs reales de los campos.

## Crear los issues (gh)

Prerrequisito: `gh` autenticado con scope `project`. Si falla, avisá y no inventes
issues. Los labels `epica`, `analisis`, `task` ya existen en el repo.

### Constantes del Project "Proyect Chaco" (Mkdir-arg/Chaco)
```
OWNER=Mkdir-arg
PROJECT_NUMBER=1
PROJECT_ID=PVT_kwHODLaoqM4BXQVZ
STATUS_FIELD=PVTSSF_lAHODLaoqM4BXQVZzhSeb2Q   # opción Backlog = f75ad846
TIPO_FIELD=PVTSSF_lAHODLaoqM4BXQVZzhS9ZPE      # Epica=abc63c47 · Analisis=3dab4bf3 · Task=e03cf9e1
                                               # Requerimiento=f49bbfa6 · Testing=06e99ba0 · Bug=2aed63a7
```

> La **semántica de los estados** (qué significa cada Status según el Tipo, gates
> para mover y reglas de assignees) está en **`ESTADOS.md`** (raíz). Los agentes
> crean en Backlog y no mueven; los gates son para el PM humano y `/pm:salud`.

### Por cada issue (épica, análisis y cada sub-issue)
```bash
# 1. crear y capturar URL
URL=$(gh issue create --title "[ANALISIS] ..." --label analisis --body-file <archivo>)
# 2. agregar al Project (--jq integrado de gh, no requiere binario jq)
ITEM=$(gh project item-add 1 --owner Mkdir-arg --url "$URL" --format json --jq '.id')
# 3. Status = Backlog
gh project item-edit --id "$ITEM" --project-id PVT_kwHODLaoqM4BXQVZ \
  --field-id PVTSSF_lAHODLaoqM4BXQVZzhSeb2Q --single-select-option-id f75ad846
# 4. Tipo según nivel (Epica=abc63c47 · Analisis=3dab4bf3 · Task=e03cf9e1)
gh project item-edit --id "$ITEM" --project-id PVT_kwHODLaoqM4BXQVZ \
  --field-id PVTSSF_lAHODLaoqM4BXQVZzhS9ZPE --single-select-option-id <opción-del-nivel>
```

### Requerimiento completo (caso especial)
Se crea igual (crear → item-add → Status Backlog → Prioridad + Modulo), con el
título `[REQUERIMIENTO] ...` y **Tipo = Requerimiento** (opción `f49bbfa6`).
No lleva label nuevo: alcanza con el prefijo `[REQUERIMIENTO]` en el título.
(El `[PLAN DE PRUEBAS]` de QA usa la misma receta con **Tipo = Testing**,
opción `06e99ba0`; ver `QA.md`.)

### Campos del Project a completar (con los datos del análisis)
No dejes la info solo en el cuerpo del issue: cargá también los **campos
estructurados** del Project para que el PM pueda filtrar y sumar. IDs de campo:
```
PRIORIDAD_FIELD=PVTSSF_lAHODLaoqM4BXQVZzhSec48   # Alta=79628723 · Media=0a877460 · Baja=da944a9c
MODULO_FIELD=PVTF_lAHODLaoqM4BXQVZzhTBIdY         # texto
ESTHORAS_FIELD=PVTF_lAHODLaoqM4BXQVZzhTBIYY       # número
RESPFUNC_FIELD=PVTF_lAHODLaoqM4BXQVZzhTBIdc       # texto: quién responde dudas funcionales
FECHACOMP_FIELD=PVTF_lAHODLaoqM4BXQVZzhTBIkc      # fecha: solo compromisos con el cliente
```
Qué campo va en cada nivel:

| Campo | Épica | Análisis | Sub-issue |
|-------|:-----:|:--------:|:---------:|
| Prioridad (single-select) | ✔ | — | ✔ |
| Modulo (texto) | ✔ | ✔ | ✔ |
| EstimacionHoras (número) | — | — | ✔ |
| ResponsableFuncional (texto) | ✔ | ✔ | — |
| FechaCompromiso (fecha) | solo si hay compromiso con el cliente | — | — |

`Size` y `Estimate` (defaults de GitHub) **no se usan**: la estimación es
`EstimacionHoras`. `Iteration` (sprint) y `Assignees` los administra el PM
humano según las reglas de `ESTADOS.md`.

```bash
# Prioridad (single-select)
gh project item-edit --id "$ITEM" --project-id PVT_kwHODLaoqM4BXQVZ \
  --field-id PVTSSF_lAHODLaoqM4BXQVZzhSec48 --single-select-option-id <Alta|Media|Baja>
# Modulo (texto)
gh project item-edit --id "$ITEM" --project-id PVT_kwHODLaoqM4BXQVZ \
  --field-id PVTF_lAHODLaoqM4BXQVZzhTBIdY --text "legajos"
# EstimacionHoras (número, solo sub-issue)
gh project item-edit --id "$ITEM" --project-id PVT_kwHODLaoqM4BXQVZ \
  --field-id PVTF_lAHODLaoqM4BXQVZzhTBIYY --number 3
```

### Vínculos
- Análisis: `Épica padre: #NN`. Sub-issue: `Épica padre: #NN` + `Análisis de origen: #MM`.
- Tras crear sub-issues, editá el análisis con la checklist (`- [ ] #KK`) y actualizá
  "Análisis vinculados" en la épica.

### Regla de movimiento
Solo se **crean** issues y se dejan en **Backlog**. **No se mueven** tareas entre
estados/columnas. **Solo el PM mueve las tareas.**

## Publicar documentación pública (docs/client)

`docs/client/` se sirve con MkDocs Material en GitHub Pages. Secciones: Proyecto,
Minutas, Sprints, **Funcionalidades**, Plantillas. Reglas:
- **Es público:** lenguaje cliente (qué hace y para qué). **Nunca** publiques estado
  del código, impacto técnico, riesgos, preguntas abiertas ni nada de `docs/internal/`.
- **Solo lo confirmado:** lo no acordado va como "A confirmar"; no se inventa.
- **Estilo de la casa:** admoniciones, iconos `:material-...:`, tablas de metadatos,
  grid cards; usá la plantilla de `docs/client/templates/` que corresponda.
- **Dos updates obligatorios:** la tabla del `index.md` de la sección **y** el `nav:`
  de `mkdocs.yml`.
- **Deploy:** `python -m mkdocs build --strict` y luego `python -m mkdocs gh-deploy`
  (requiere `pip install mkdocs-material`). Confirmar antes de deployar (publica online).

## Handoff: qué pasa después del analista

El analista es el **primer eslabón** de la línea de producción (los handoffs
completos están en `ESTADOS.md`). Su entrega no termina al crear los issues:

- **Al cerrar la generación de sub-issues** (paso 6 / `/analisis:issue`), ofrecé
  el paso siguiente: correr `/qa:casos` sobre las tasks recién creadas, para que
  **cada task nazca con su sección de casos de prueba**. Sin casos no cumple el
  gate de Ready (`ESTADOS.md`), así que generarlos en el momento evita que el
  trabajo quede varado en Backlog.
- **Reportá al PM humano** qué tasks quedaron completas (estimación + casos +
  campos cargados) y por lo tanto elegibles para Ready. El PM decide y mueve.

## Relación con QA

El método del **Agente QA** (casos de prueba por task, plan de pruebas por épica)
vive en **`QA.md`** (raíz), archivo hermano de este. QA consume lo que el analista
produce: deriva los casos de los criterios de aprobación de las tasks y de los
criterios de aceptación de los análisis. Por eso, cuanto más verificables sean
esos criterios, mejores casos salen. QA agrega una sección
`## Casos de prueba (QA)` al cuerpo de cada task y crea un issue
`[PLAN DE PRUEBAS]` por épica (mismo patrón que el `[REQUERIMIENTO]`). Las
constantes del Project de este archivo son compartidas: no se duplican en `QA.md`.

## Reglas generales

- Code-first: leé el código antes de afirmar qué existe o cómo funciona.
- No generes issues con preguntas abiertas o inconsistencias. Frenar es correcto.
- La fuente de verdad del conocimiento es el Issue, no `docs/`.
- Español; mismas estructuras siempre. La consistencia entre analistas es el objetivo.
- El analista no implementa código ni abre PRs: su salida es conocimiento, issues y
  documentación pública.

---

## Anexo — Entorno local (tareas técnicas, fuera del rol de analista)

> Esta sección **no es parte del método de análisis funcional**. Está acá porque
> herramientas como Codex CLI leen `AGENTS.md` como instrucciones del proyecto.

Si la tarea es código, debug o validación local (`manage.py check`, tests,
`runserver` fuera de Docker), usar **siempre el venv del repo**, nunca el Python
global de la máquina (suele tener `django-silk` viejo que rompe con Django 4.2
por el import deprecado de `get_storage_class`).

Patrón mínimo en PowerShell desde la raíz del repo:

```powershell
$env:PY_VENV = "$PWD\.venv\Scripts\python.exe"
$env:DJANGO_SECRET_KEY = "test-key"
& $env:PY_VENV manage.py check
```

Si `.venv/` no existe, crearlo siguiendo
[`docs/internal/venv-setup.md`](docs/internal/venv-setup.md). Ese doc tiene la
receta completa (creación, dependencias, pin-overrides aplicados y por qué) y
es la fuente de verdad del setup local.
