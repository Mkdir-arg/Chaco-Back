# Chaco

## Identidad del repo

`Chaco` es un monorepo Django orientado a backoffice y portal ciudadano.

- Stack principal: Python 3.12, Django 4.2, MySQL 8, Tailwind CSS, Alpine.js, Docker Compose
- Apps que suelen concentrar trabajo: `core`, `legajos`, `configuracion`, `conversaciones`, `dashboard`, `portal`, `users`, `tramites`, `healthcheck`
- Superficies principales: backoffice y portal ciudadano
- La fuente de verdad es el código actual del repo, no documentación histórica

## Regla principal

Trabajar code-first.

1. Leer este archivo.
2. Entender el pedido actual del usuario.
3. Inspeccionar el código real afectado.
4. Diseñar o implementar con cambios mínimos y verificables.
5. Validar con `manage.py check`, tests o revisión de templates según corresponda.

## Convenciones de implementación

- Priorizar lectura de código antes de asumir comportamiento.
- No depender de `docs/`, `documentos/` ni `memory/` como prerequisito de trabajo.
- Si falta contexto funcional, derivarlo del código, rutas, templates y nombres del dominio.
- Usar Django Forms/ModelForms para formularios del backoffice.
- Crear migraciones inmediatamente después de cambiar modelos.
- Templates del backoffice: extender `includes/base.html`.
- Templates del portal: extender `portal/base.html`.
- Confirmaciones destructivas: SweetAlert2 o modal equivalente, nunca `confirm()` nativo.
- Mantener cambios pequeños, consistentes y fáciles de validar.

## Entorno local (fuera de Docker)

Para correr `manage.py check`, tests rápidos o cualquier `python` del repo sin
Docker, usar **siempre el venv del proyecto**, nunca el Python global de la
máquina (suele tener `django-silk` viejo incompatible con Django 4.2):

```powershell
# raíz del repo
$env:PY_VENV = "$PWD\.venv\Scripts\python.exe"
$env:DJANGO_SECRET_KEY = "test-key"
& $env:PY_VENV manage.py check
```

Si `.venv/` no existe todavía, crearlo siguiendo
[`docs/internal/venv-setup.md`](docs/internal/venv-setup.md). Ese doc también
lista los pin-overrides aplicados y por qué.

## Gestión en GitHub

- El trabajo se organiza en Issues con el modelo: **Épica → Análisis → Sub-issues**.
- Al crear issues, se dejan en **Backlog**.
- **Solo el PM mueve las tareas** entre estados/columnas del Project. Ningún agente
  ni asistente debe cambiar el estado de una tarea: como mucho crea issues en Backlog.

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
