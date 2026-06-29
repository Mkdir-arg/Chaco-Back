# Onboarding — Desarrolladores nuevos

## Semana 1: orientación

### Día 1
- [ ] Leer `CLAUDE.md` en la raíz del repo
- [ ] Leer `docs/internal/architecture.md`
- [ ] Seguir `docs/internal/setup.md` y levantar el entorno local
- [ ] Pedir acceso al repositorio, GitHub Projects y canales del equipo

### Días 2-3
- [ ] Explorar las apps principales: `legajos`, `configuracion`, `portal`
- [ ] Navegar el backoffice en local para entender las superficies
- [ ] Leer `docs/internal/workflow.md` para entender el proceso de trabajo

### Días 4-5
- [ ] Revisar los ADRs en `docs/internal/decisions/`
- [ ] Hacer una tarea pequeña del board de GitHub Projects
- [ ] Hacer tu primer PR siguiendo el workflow del equipo

## Accesos que necesitás pedir

- [ ] Repositorio en GitHub (rol: Developer)
- [ ] GitHub Projects del equipo
- [ ] Variables de entorno locales (`.env`)

## Contexto del dominio

El sistema gestiona:

- **Legajos de ciudadanos**: registro, programas sociales, derivaciones
- **NACHEC**: módulo de seguimiento de casos con flujo de estados
- **Portal ciudadano**: acceso self-service para ciudadanos
- **Conversaciones**: chat en tiempo real entre staff y ciudadanos
- **Configuración institucional**: secretarías, subsecretarías, dispositivos, programas

## Convenciones que debés conocer

- Patrón `selectors → services → views` en cada app
- Templates del backoffice extienden `includes/base.html`
- Templates del portal extienden `portal/base.html`
- Confirmaciones destructivas: SweetAlert2, nunca `confirm()` nativo
- Migraciones: siempre crear inmediatamente después de cambiar modelos

## Preguntas frecuentes de nuevos devs

**¿Dónde está la lógica de negocio?**
En `services/` de cada app. Las views solo orquestan.

**¿Cómo sé qué permisos tiene cada rol?**
Ver `users/` y los grupos definidos en `legajos/management/commands/setup_groups.py`.

**¿Cómo funciona el multi-institución?**
El middleware `config/middlewares/institucion_redirect.py` maneja el contexto por institución.
