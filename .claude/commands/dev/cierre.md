---
description: Cierre tecnico de desarrollo antes de merge/QA: revisa cambios, performance, diseno, seguridad y validaciones focalizadas.
allowed-tools: Read, Grep, Glob, Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git branch:*), Bash(rg:*), Bash(python:*), Bash(./.venv/Scripts/python.exe:*), Bash(.\\.venv\\Scripts\\python.exe:*), Bash(git show:*), Bash(git rev-parse:*)
---

Actua como operador de cierre tecnico de desarrollo de Chaco. Tu objetivo es decidir
si los cambios actuales estan listos para QA/merge, usando al agente
`chaco-dev-reviewer` como criterio de revision.

## Reglas

- No hagas commits, merges, pushes, deploys ni espejos a ECOM.
- No reviertas cambios del usuario.
- Si el working tree esta sucio, revisa exactamente ese estado.
- Si no hay cambios, informa que no hay nada para cerrar y termina.
- Si hay cambios de UI, lee obligatoriamente `.claude/agents/chaco-design-system.md`.
- Si un comando no puede correr por entorno, registralo como bloqueo o riesgo residual;
  no lo tapes con un "OK".

## Paso 1 — Inventario del cambio

Ejecuta:

```powershell
git status --short --branch
git diff --name-status
git diff --stat
```

Clasifica archivos modificados:

- Backend / services / selectors
- Views / URLs / forms / serializers
- Templates / CSS / JS
- Models / migrations / seeds
- Tests
- Docs / infra

## Paso 2 — Lectura obligatoria

Lee:

```powershell
AGENTS.md
.claude/agents/chaco-dev-reviewer.md
```

Si toca UI, lee tambien:

```powershell
.claude/agents/chaco-design-system.md
```

Despues lee los archivos modificados y consumidores directos necesarios. Para Django,
prioriza modelos, views, urls, forms, services/selectors, serializers, templates y
tests relacionados.

## Paso 3 — Revision de riesgos

Revisa y reporta hallazgos concretos sobre:

- Regresiones funcionales o cambios de contrato.
- Permisos/RBAC, auth, CSRF y rutas publicas.
- Seguridad publica: enumeracion, rate limit, archivos, headers, tokens y mensajes.
- Performance:
  - querysets materializados con `list(...)` en vistas o reportes;
  - `.count()` repetido o dentro de loops;
  - loops sobre querysets con acceso a relaciones sin `select_related`/`prefetch_related`;
  - `prefetch_related` masivo donde conviene `values().annotate()`;
  - filtros `__date` en campos datetime calientes;
  - templates con `|length` sobre querysets grandes;
  - listados sin paginacion ni limite explicito.
- Migraciones, compatibilidad de datos y comandos de bootstrap.
- UI: coherencia con el agente canonico, accesibilidad y responsive.
- Frontend Django: arquetipo visual aplicado, datos/permisos preparados fuera del
  template, paginacion/límites en listados y ausencia de rediseño lateral.

## Paso 4 — Validaciones

Corre siempre que aplique:

```powershell
$env:DJANGO_SECRET_KEY = "test-key"
& .\.venv\Scripts\python.exe manage.py check
& .\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
git diff --check
```

Si hubo templates:

```powershell
& .\.venv\Scripts\python.exe scripts\compile_templates.py
```

Si hubo UI:

```powershell
& .\.venv\Scripts\python.exe scripts\check_design_agent.py --changed
& .\.venv\Scripts\python.exe scripts\design_audit.py --changed
```

Selecciona tests focalizados por modulo. Para tests que crean base:

```powershell
$env:PYTEST_RUNNING = "1"
$env:DJANGO_SECRET_KEY = "test-key"
& .\.venv\Scripts\python.exe manage.py test <tests-focalizados> --verbosity 1
```

Si los tests de render fallan por la deuda conocida de Python 3.14 + Django 4.2
(`AttributeError: 'super' object has no attribute 'dicts'`), separa esa falla de
fallas reales y corre pruebas directas de servicios/modelos cuando sea posible.

## Paso 5 — Informe final

Responde en este formato:

```markdown
## Cierre tecnico — <rama>

### Hallazgos
- Sin hallazgos bloqueantes.
- [Alta|Media|Baja] archivo:linea — problema, impacto y arreglo minimo.

### Performance
- Que se reviso.
- Riesgos corregidos o pendientes.

### Diseno/UI
- Aplica/no aplica.
- Arquetipo usado y referencia productiva.
- Resultado de validaciones.

### Validacion
- `comando`: OK/fallo y detalle util.

### Veredicto
Listo para QA | Listo con riesgo menor | No listo
```

El veredicto debe ser estricto: si hay una falla real sin resolver, es "No listo".
Si solo quedan warnings conocidos o limitaciones de entorno documentadas, puede ser
"Listo con riesgo menor".
