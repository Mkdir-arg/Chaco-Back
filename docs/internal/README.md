# Documentación interna — Chaco

Índice de toda la documentación interna del equipo.
Esta carpeta **no se publica** en GitHub Pages.

## Contenido

| Archivo | Descripción |
|---|---|
| [requerimientos.md](requerimientos.md) y [requerimientos/](requerimientos/) | **Registro vivo de requerimientos.** Todo desarrollo se registra al cerrarse: pedido, solicitante, decisiones, historial y reversión. El archivo guarda la regla y el historial 1–548; cada Cambio desde el 549 es un archivo `requerimientos/N.md` |
| [architecture.md](architecture.md) | Diagrama de componentes y decisiones de diseño |
| [setup.md](setup.md) | Cómo levantar el proyecto localmente |
| [onboarding.md](onboarding.md) | Guía para desarrolladores nuevos |
| [workflow.md](workflow.md) | Branching, commits y proceso de PR |
| [roadmap.md](roadmap.md) | Objetivos por trimestre |
| [processes.md](processes.md) | Deploy, rollback e incidentes |
| [despliegue-constructor.md](despliegue-constructor.md) | **Manual de la puesta en marcha del constructor de formularios** (Cambios 58/73/74/76): espejo, migraciones, tablas huérfanas tras restaurar producción, verificación, reversión y carga de `ciudadanos_renaper` |
| [decisions/](decisions/README.md) | Registro de decisiones técnicas (ADRs) |

## Regla de uso

Si algo va a quedar obsoleto en menos de 2 semanas → va en un issue, no acá.
