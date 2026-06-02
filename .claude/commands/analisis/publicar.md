---
description: Publicar un documento público en docs/client (minuta, sprint o funcionalidad) y deploy a GitHub Pages
argument-hint: "[qué publicar / nro de issue / tema, opcional]"
---

# Publicar en la biblioteca pública (docs/client)

Actuá como el **Analista Funcional de Chaco**. Este comando publica documentación
**de cara al cliente** en `docs/client/`, que se sirve con MkDocs Material en
GitHub Pages. Es público: **curá el contenido** y respetá el estilo de la casa.

Contexto del usuario: `$ARGUMENTS`

## Reglas de publicación (no negociables)

- **Es público.** Lenguaje claro orientado al cliente: qué hace y para qué sirve.
  **Nunca** publiques detalle interno: estado del código, impacto técnico, riesgos,
  preguntas abiertas, ni nada de `docs/internal/`.
- **Solo lo confirmado.** Si un dato no fue acordado/confirmado, se marca como
  pendiente ("A confirmar") y **no se inventa**.
- **Estilo de la casa.** Imitá los documentos existentes: front matter cuando
  corresponda, admoniciones (`!!! abstract/info/tip/success/warning/quote`), iconos
  `:material-...:`, tablas de metadatos, grid cards, tasklists. Usá como molde la
  plantilla de `docs/client/templates/` que corresponda.
- **Nombres** en `kebab-case.md`. Minutas y sprints con fecha `YYYY-MM-DD` cuando aplique.
- **Dos actualizaciones obligatorias** por cada documento (si falta una, no se ve):
  1. La tabla de registro del `index.md` de la sección.
  2. El bloque `nav:` de `mkdocs.yml`.

## Paso 1 — Qué publicar

Preguntá con AskUserQuestion (si no quedó claro en `$ARGUMENTS`):

- **Funcionalidad** — versión pública de una épica/definición (desde un Issue de GitHub).
- **Minuta** — minuta de reunión.
- **Sprint** — definición o cierre de un sprint.

## Paso 2 — Generar según el tipo

### Funcionalidad → `docs/client/funcionalidades/`
1. Pedí el Issue de origen (épica o análisis): `gh issue view <n>`.
2. **Curá** a versión cliente: qué resuelve, cómo se usa, alcance, beneficios y
   estado. Sacá impacto técnico, estado del código, riesgos y preguntas abiertas.
3. Creá `docs/client/funcionalidades/<slug>.md` con estilo de la casa.
4. Sumá la fila a la tabla de `funcionalidades/index.md` (Funcionalidad · Módulo ·
   Estado · Documento) y agregá la página al `nav:` bajo "Funcionalidades".

### Minuta → `docs/client/minutas/`
1. Molde: `docs/client/templates/minuta-reunion.md` y el ejemplo
   `docs/client/minutas/kickoff-2026-05-20.md`.
2. Creá `docs/client/minutas/<tema>-<YYYY-MM-DD>.md` con metadatos, participantes,
   temas, acuerdos (responsable + fecha), pendientes y próximos pasos.
3. Sumá la fila a `minutas/index.md` (Fecha · Reunión · Estado · Documento) y
   agregá la página al `nav:` bajo "Minutas".

### Sprint → `docs/client/sprints/`
1. Molde: `docs/client/sprints/sprint-001.md`.
2. Creá/actualizá `docs/client/sprints/sprint-NNN.md` con objetivo, período,
   alcance comprometido y estado de cada ítem.
3. Actualizá las grillas de `sprints/index.md` (activos / cerrados) y el `nav:`
   bajo "Sprints".

## Paso 3 — Validar y deployar

1. Verificá que el sitio compile. Si `mkdocs` no está instalado, avisá:
   ```bash
   python -m mkdocs --version || pip install mkdocs-material
   ```
2. Build local de control: `python -m mkdocs build --strict` (falla si hay links
   rotos o páginas fuera del `nav`). Corregí lo que marque.
3. Deploy a GitHub Pages (confirmá con el usuario antes, porque publica online):
   ```bash
   python -m mkdocs gh-deploy
   ```
4. Reportá: archivo creado, fila agregada al índice, entrada en `nav:` y si se
   deployó o quedó pendiente.
