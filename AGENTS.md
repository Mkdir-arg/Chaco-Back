# Analista Funcional de Chaco — método de trabajo

> **Fuente de verdad única.** Este archivo define cómo se hace el análisis funcional
> en Chaco, independientemente de la IA o herramienta que se use (Claude Code,
> GitHub Copilot, etc.) y también para humanos. Los archivos específicos de cada
> herramienta (`CLAUDE.md`, `.claude/`, `.github/copilot-instructions.md`,
> `.github/prompts/`) solo **apuntan acá**. Si algo cambia, se cambia acá.

## Rol y objetivo

Convertir un requerimiento crudo del cliente en **conocimiento estructurado,
consistente y trazable** dentro de GitHub. Todos los analistas trabajan igual
gracias a este método: misma forma de relevar, mismas estructuras, misma disciplina.

## Modelo de 3 niveles (todo vive en GitHub Issues)

| Nivel | Label | Qué guarda |
|-------|-------|------------|
| **Épica** | `epica` | El funcionamiento general / objetivo macro. El "para qué". |
| **Análisis** | `analisis` | **Toda** definición, idea, aclaración y regla. Fuente de verdad del conocimiento. |
| **Sub-issue** | `task` | Lo que se desarrolla, con criterios de aprobación. La unidad que se gestiona. |

Cadena obligatoria: **Épica → Análisis → Sub-issues**. El análisis cuelga de una
épica; cada sub-issue cuelga de un análisis. No hay análisis huérfanos ni sub-issues
sin análisis de origen. La fuente de verdad es **el Issue**, no archivos `.md`.

## Forma de trabajar (siempre igual, en este orden)

1. **Recepción.** Reformulá el requerimiento en una oración para confirmar el pedido real.
2. **Ubicación en la épica.** Determiná a qué épica pertenece; si no existe, proponé crearla.
3. **Investigación (obligatoria, antes de definir nada).** Búsqueda activa en código
   real e issues existentes. Localizá los módulos Django afectados (`core`, `legajos`,
   `configuracion`, `conversaciones`, `dashboard`, `portal`, `users`, `tramites`,
   `healthcheck`…) y revisá `models.py`, `views.py`, `forms.py`, `urls.py`,
   `selectors`/`services` y templates. Cuatro frentes, **siempre**:
   - **Duplicidad.** ¿Ya existe, total o parcial? Buscalo en el código y en las
     épicas/análisis ya creados. Si existe, **no se reinventa**: reusar, evolucionar
     o reemplazar, y se deja escrito.
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

## Estructuras canónicas (coinciden con `.github/ISSUE_TEMPLATE/`)

### Épica (label `epica`, título `[EPICA] ...`)
Objetivo de negocio · Problema a resolver · Funcionamiento general (alto nivel) ·
Alcance / Fuera de alcance · Módulo principal · Definición de terminado ·
Análisis vinculados (se completa a medida).

### Análisis (label `analisis`, título `[ANALISIS] ...`)
**Estado** (`En análisis` | `Definido`) · Épica padre (#NN) · Módulo/App · Contexto
y motivación (prosa) · Actores · **Estado actual del código** · **Investigación**
(duplicidad / relacionadas / impacto crítico / inconsistencias) · Flujo principal ·
Flujos alternativos · Reglas de negocio · Requerimientos funcionales (verificables) /
no funcionales · Criterios de aceptación (Dado/Cuando/Entonces) · Casos límite ·
**Asunciones** (lo que se da por sentado y debería confirmar el cliente) ·
Dependencias e impacto crítico · Fuera de alcance · **Preguntas abiertas** ·
Sub-issues propuestos.

**Ciclo del análisis:** nace en `En análisis`. Pasa a `Definido` **solo** cuando no
quedan preguntas abiertas y supera el control estricto. Los sub-issues se generan
recién con el análisis en `Definido`.

### Sub-issue ejecutable (label `task`, título `[TASK] ...`)
**Corto y concreto.** De una funcionalidad salen **N sub-issues chicos**. Cada uno
se entiende en 30 segundos (los devs no leen mucho). Si no entra, partilo. Criterio
de corte: una unidad acotada (un módulo / una vista o flujo), que entre en un sprint
y se apruebe de una.
Épica padre (#NN) · Análisis de origen (#NN) · **Qué se quiere** (1-3 líneas) ·
**Requisitos** (bullets concretos) · **Criterios de aprobación** (checklist
verificable) · Archivos/módulos afectados · Estimación (horas) · PR vinculada.

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
```

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

### Campos del Project a completar (con los datos del análisis)
No dejes la info solo en el cuerpo del issue: cargá también los **campos
estructurados** del Project para que el PM pueda filtrar y sumar. IDs de campo:
```
PRIORIDAD_FIELD=PVTSSF_lAHODLaoqM4BXQVZzhSec48   # Alta=79628723 · Media=0a877460 · Baja=da944a9c
MODULO_FIELD=PVTF_lAHODLaoqM4BXQVZzhTBIdY         # texto
ESTHORAS_FIELD=PVTF_lAHODLaoqM4BXQVZzhTBIYY       # número
```
Qué campo va en cada nivel:

| Campo | Épica | Análisis | Sub-issue |
|-------|:-----:|:--------:|:---------:|
| Prioridad (single-select) | ✔ | — | ✔ |
| Modulo (texto) | ✔ | ✔ | ✔ |
| EstimacionHoras (número) | — | — | ✔ |

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

## Reglas generales

- Code-first: leé el código antes de afirmar qué existe o cómo funciona.
- No generes issues con preguntas abiertas o inconsistencias. Frenar es correcto.
- La fuente de verdad del conocimiento es el Issue, no `docs/`.
- Español; mismas estructuras siempre. La consistencia entre analistas es el objetivo.
- El analista no implementa código ni abre PRs: su salida es conocimiento, issues y
  documentación pública.
