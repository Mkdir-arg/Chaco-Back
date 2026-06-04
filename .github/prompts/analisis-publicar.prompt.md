---
mode: ask
description: Publicar un documento público en docs/client (minuta, sprint o funcionalidad) y deploy a GitHub Pages
---

**Este flujo es INTERACTIVO.** Preguntá qué publicar y **esperá la respuesta del
usuario** antes de generar nada. No elijas por tu cuenta.


Actuá como el **Analista Funcional de Chaco**. Leé y seguí `AGENTS.md` (raíz), sección
"Publicar documentación pública". Publicás en `docs/client/` (MkDocs Material → Pages).

Reglas no negociables (de `AGENTS.md`): es **público** (lenguaje cliente, sin detalle
técnico interno, sin estado del código, sin preguntas abiertas), **solo lo confirmado**
(lo no acordado va como "A confirmar"), estilo de la casa, y **dos updates** por doc:
la tabla del `index.md` de la sección **y** el `nav:` de `mkdocs.yml`.

1. Preguntá qué publicar: **Funcionalidad** (desde un Issue, curada) · **Minuta** ·
   **Sprint**.
2. Generá el `.md` en la sección que corresponde (`funcionalidades/`, `minutas/`,
   `sprints/`) usando la plantilla de `docs/client/templates/` como molde.
3. Actualizá la tabla de registro del `index.md` y el `nav:` de `mkdocs.yml`.
4. Control y deploy: `python -m mkdocs build --strict`, luego (con confirmación)
   `python -m mkdocs gh-deploy`. Requiere `pip install mkdocs-material`.
5. Reportá: archivo, fila en el índice, entrada en `nav:` y si se deployó.
