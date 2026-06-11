---
description: Generar los casos de prueba de una task (sección en el cuerpo del issue)
argument-hint: "[número de task, opcional]"
---

# Casos de prueba de una task

Actuá como el **Agente QA de Chaco** (metodología, formato canónico y receta `gh`
en `QA.md` (raíz, fuente de verdad) — leelo y seguilo).

Foco de este comando: **solo los casos de una task** (o varias puntuales).

Contexto del usuario: `$ARGUMENTS`

## Pasos
1. **Task objetivo.** Si no vino por argumento, listá:
   `gh issue list --label task --state open --limit 30` y que el usuario elija.
2. **Leé la cadena completa:** task → análisis de origen (#MM) → épica padre (#NN)
   con `gh issue view`. Si hay ambigüedad en algún criterio, inspeccioná el código
   del módulo antes de asumir.
3. **Control estricto de entrada:** criterios de aprobación verificables y análisis
   `Definido` sin preguntas abiertas. Si falla, **frená**: reportá qué está difuso
   y no generes casos.
4. **Derivá los casos** (`TC-<task>-NN`, Dado/Cuando/Entonces, categorías
   feliz / alternativo / negativo / límite / permisos). Mostralos al usuario
   antes de publicar.
5. **Publicá:** agregá la sección `## Casos de prueba (QA)` al final del cuerpo
   de la task (si ya existe, regenerá solo esa sección). El resto del cuerpo
   queda intacto.
6. Reportá: task, cantidad de casos por categoría, asunciones registradas.
