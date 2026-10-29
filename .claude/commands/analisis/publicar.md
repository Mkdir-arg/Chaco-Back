---
description: Publicar un documento público en docs/client (minuta, versión o funcionalidad) y deploy a GitHub Pages
argument-hint: "[qué publicar / nro de issue / tema, opcional]"
---

# Publicar en la biblioteca pública (docs/client)

Actuá como el **Analista Funcional de Chaco** (método completo y reglas de
publicación en `AGENTS.md`, raíz — fuente de verdad). Este comando publica
documentación **de cara al cliente** en `docs/client/`, que se sirve con MkDocs
Material en GitHub Pages. Es público: **curá el contenido** y respetá el estilo de
la casa.

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
- **Nombres** en `kebab-case.md`. Minutas con fecha `YYYY-MM-DD` cuando aplique.
- **Dos actualizaciones obligatorias** por cada documento (si falta una, no se ve):
  1. La tabla de registro del `index.md` de la sección.
  2. El bloque `nav:` de `mkdocs.yml`.

## Paso 1 — Qué publicar

Preguntá (numerado, en texto, si no quedó claro en `$ARGUMENTS`):

> ¿Qué publicamos?
> 1. **Funcionalidad** — versión pública de una épica/definición (desde un Issue de GitHub).
> 2. **Minuta** — minuta de reunión.
> 3. **Versión** — definición o cierre de una versión (`docs/client/versiones/`).

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

### Versión → `docs/client/versiones/`
(`docs/client/sprints/` ya no existe: las entregas se publican como versiones.)
1. Molde: `docs/client/versiones/version-001.md` (cerrada) o `version-002.md` (en curso).
2. Creá/actualizá `docs/client/versiones/version-NNN.md` con objetivo, período,
   alcance comprometido y estado de cada ítem.
3. Actualizá la tabla de `versiones/index.md` y el `nav:` bajo "Versiones".

## Paso 3 — Validar y deployar

Seguí el **flujo vigente de `AGENTS.md` → «Publicar documentación pública»** (venv del
proyecto, dependencias de `requirements-ci.txt`, `mkdocs build --strict`,
`check_docs_client.py` en 0, deploy por `docs-auto-deploy.yml`, sin `gh-deploy` manual).
Es la fuente única: no se repiten acá los comandos. Corregí lo que marque el build o el gate.
4. Reportá: archivo creado, fila agregada al índice, entrada en `nav:` y si se
   deployó o quedó pendiente.
