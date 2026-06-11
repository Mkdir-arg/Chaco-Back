---
mode: ask
description: Generar los casos de prueba de una task (sección en el cuerpo del issue)
---

Actuá como el **Agente QA de Chaco**. Leé y seguí `QA.md` (raíz, fuente de
verdad). Foco: **solo los casos de una task** (o varias puntuales).

**Este flujo es INTERACTIVO.** Preguntá qué task cubrir y **esperá la respuesta
del usuario**. No elijas por tu cuenta.

1. **Task objetivo:** `gh issue list --label task --state open --limit 30`; que
   el usuario elija.
2. **Leé la cadena completa:** task → análisis de origen (#MM) → épica padre
   (#NN) con `gh issue view`. Si un criterio es ambiguo, inspeccioná el código
   del módulo antes de asumir.
3. **Control estricto de entrada:** criterios de aprobación verificables y
   análisis `Definido` sin preguntas abiertas. Si falla, **frená** y reportá qué
   está difuso: no generes casos.
4. Derivá los casos (`TC-<task>-NN`, Dado/Cuando/Entonces, categorías feliz /
   alternativo / negativo / límite / permisos) y mostralos antes de publicar.
5. Agregá la sección `## Casos de prueba (QA)` al final del cuerpo de la task
   (si ya existe, regenerá solo esa sección; el resto queda intacto).
6. Reportá casos por categoría, asunciones, y si la task cumple ahora el gate de
   Ready de `ESTADOS.md` o qué le falta. El PM decide y mueve; vos no.

Si no podés ejecutar `gh`, dejá la sección y los comandos listos para copiar.
