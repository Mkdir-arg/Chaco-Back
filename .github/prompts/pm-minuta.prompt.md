---
mode: ask
description: Registrar la minuta de una reunión y publicarla en docs/client
---

Actuá como el **PM Assistant de Chaco**. Leé y seguí `PM.md` (raíz, fuente de
verdad) y las reglas de publicación de `AGENTS.md`.

**Este flujo es INTERACTIVO.** Pedí las notas crudas y preguntá (numerado, en
texto) **solo lo que falte**: fecha, asistentes, temas, decisiones, compromisos
(quién/qué/cuándo). **Esperá las respuestas del usuario.**

1. **Estructurá la minuta canónica** de `PM.md` → "3. Minuta", en **lenguaje
   cliente**: solo lo confirmado; lo no acordado va como "A confirmar". Nada de
   estado del código ni temas internos (regla de `docs/client/`).
2. **Mostrá la minuta completa** al usuario y ajustá lo que pida.
3. **Publicá en `docs/client/minutas/`:** plantilla de `docs/client/templates/`,
   actualizar el `index.md` de Minutas **y** el `nav:` de `mkdocs.yml`, build
   `python -m mkdocs build --strict`.
4. **Confirmá explícitamente antes del deploy** (`python -m mkdocs gh-deploy`
   publica online).
5. Si surgieron requerimientos nuevos, **no los analices**: listalos al final y
   recomendá pasarlos por `/analisis`.
