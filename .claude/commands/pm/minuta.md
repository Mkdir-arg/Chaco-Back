---
description: Registrar la minuta de una reunión y publicarla en docs/client
argument-hint: "[notas de la reunión, opcional]"
---

# Minuta de reunión

Actuá como el **PM Assistant de Chaco** (estructura canónica y reglas de
publicación en `PM.md` (raíz, fuente de verdad) — leelo y seguilo).

Contexto del usuario: `$ARGUMENTS`

## Pasos
1. **Recolectá lo conversado.** Si no vino por argumento, pedile al usuario las
   notas crudas. Preguntá (numerado, en texto) solo lo que falte para completar:
   fecha, asistentes, temas, decisiones, compromisos (quién/qué/cuándo).
2. **Estructurá la minuta canónica** de `PM.md` → "3. Minuta", en **lenguaje
   cliente**: solo lo confirmado; lo no acordado va como "A confirmar". Nada de
   estado del código ni temas internos (regla de `docs/client/`).
3. **Mostrá la minuta completa** al usuario y ajustá lo que pida.
4. **Publicá en `docs/client/`** siguiendo las reglas de `AGENTS.md` →
   "Publicar documentación pública" (plantilla de `docs/client/templates/`, `index.md`
   de Minutas **y** `nav:` de `mkdocs.yml`; build y gate `check_docs_client.py` en 0
   están ahí, no se repiten).
5. **Deploy:** lo hace `docs-auto-deploy.yml` al llegar a `development` (flujo en la misma
   sección de `AGENTS.md`); no corras `gh-deploy` a mano. Confirmá con el usuario antes
   de pushear, porque publica online.
6. Si en la reunión surgieron requerimientos nuevos, **no los analices**:
   listalos al final y recomendá pasarlos por `/analisis`.
