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
2. **Corré los 6 chequeos canónicos** de `PM.md` → "2. Salud":
   1. Cadena rota (tasks/análisis sin padre referenciado).
   2. Análisis con deuda (preguntas abiertas pero con sub-issues ya generados).
   3. Épicas sin `[REQUERIMIENTO]` teniendo todos sus análisis `Definido`.
   4. Cobertura QA (tasks sin `## Casos de prueba (QA)`; épicas cubiertas sin
      `[PLAN DE PRUEBAS]`).
   5. Campos del Project incompletos (Tipo, Prioridad, EstimacionHoras según nivel).
   6. Estancados (mismo Status sin actividad > 7 días).
3. Cada chequeo lista los issues concretos que fallan (`#NN`) o marca "✔ OK".
4. **Cerrá con el score** (chequeos OK / 6) y las 3 acciones más urgentes,
   indicando qué rol las ejecuta: PM humano (mover/priorizar), Analista
   (`/analisis`), o QA (`/qa:revision`, `/qa:plan`). No ejecutes ninguna vos.
