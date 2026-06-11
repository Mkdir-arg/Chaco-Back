---
description: Auditoría de salud del Project: trazabilidad, campos, cobertura QA, estancados
---

# Salud del proyecto

Actuá como el **PM Assistant de Chaco** (metodología y estructura canónica del
informe en `PM.md` (raíz, fuente de verdad) — leelo y seguilo). **Solo lectura.**

Contexto del usuario: `$ARGUMENTS`

## Pasos
1. **Levantá todo:** items del Project #1 de `Mkdir-arg` (GitHub MCP preferido;
   fallback `gh`) + issues abiertos con sus cuerpos (`epica`, `analisis`, `task`,
   `[REQUERIMIENTO]`, `[PLAN DE PRUEBAS]`).
2. **Corré los 7 chequeos canónicos** de `PM.md` → "2. Salud":
   1. Cadena rota (tasks/análisis sin padre referenciado).
   2. Análisis con deuda (preguntas abiertas pero con sub-issues ya generados).
   3. Épicas sin `[REQUERIMIENTO]` teniendo todos sus análisis `Definido`.
   4. Cobertura QA (tasks sin `## Casos de prueba (QA)`; épicas cubiertas sin
      `[PLAN DE PRUEBAS]`).
   5. Campos del Project incompletos (Tipo, Prioridad, EstimacionHoras según nivel).
   6. Estancados (mismo Status sin actividad > 7 días).
   7. Violaciones de la máquina de estados (`ESTADOS.md`): tasks en Ready+ sin
      casos/estimación/assignee único/iteración; análisis Done con preguntas
      abiertas; épicas fuera de Backlog/Done (son agrupadores);
      `[REQUERIMIENTO]` desincronizado de sus tasks (tracker macro:
      Backlog → In progress → In QA → Done); `[PLAN DE PRUEBAS]` fuera de
      Backlog/Done; Blocked sin causa o > 7 días; In QA sin avance de
      `- [ ] Pasa` > 5 días.
3. Cada chequeo lista los issues concretos que fallan (`#NN`) o marca "✔ OK".
4. **Cerrá con el score** (chequeos OK / 7) y las 3 acciones más urgentes,
   indicando qué rol las ejecuta: PM humano (mover/priorizar), Analista
   (`/analisis`), o QA (`/qa:revision`, `/qa:plan`). No ejecutes ninguna vos.
5. **Plan de remediación** (sección final obligatoria): una lista numerada con
   **un renglón por error encontrado**, cada uno con el comando exacto a correr
   para solucionarlo, listo para copiar y pegar. Mapeo:
   - Cadena rota / análisis con deuda (preguntas abiertas) →
     `/analisis:analisis #NN` (Analista: completar/cerrar el análisis).
   - Épica con todos sus análisis `Definido` pero sin `[REQUERIMIENTO]` →
     `/analisis:issue #NN` (Analista: derivar y consolidar).
   - Task sin `## Casos de prueba (QA)` (incluye tasks Ready+ sin casos) →
     `/qa:casos #NN`. Si son 3 o más tasks sin cubrir → un solo `/qa:revision`.
   - Épica cubierta sin `[PLAN DE PRUEBAS]` → `/qa:plan #NN`.
   - Campos del Project incompletos, estancados, épicas/`[REQUERIMIENTO]`/
     `[PLAN DE PRUEBAS]` en estado incorrecto, Blocked sin causa, assignees o
     iteración → **PM humano, manual en el Project** (no hay comando; decir
     exactamente qué campo/estado tocar en qué issue).
   Ordená la lista para resolver de a uno: primero Analista, después QA,
   al final lo manual del PM. No ejecutes ningún comando vos.
