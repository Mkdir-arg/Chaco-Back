---
description: Revisar cobertura QA: detectar tasks sin casos de prueba y cubrirlas
---

# Revisión de cobertura QA

Actuá como el **Agente QA de Chaco** (metodología y receta `gh` en `QA.md`
(raíz, fuente de verdad) — leelo y seguilo).

Foco de este comando: **auditar y cerrar el hueco de cobertura**. Toda task en
Backlog debería tener su sección `## Casos de prueba (QA)` apenas se crea.

Contexto del usuario: `$ARGUMENTS`

## Pasos
1. **Detectá** las tasks abiertas sin sección de QA (receta "Detectar tasks sin
   casos" de `QA.md`).
2. **Reportá la foto:** tabla con `#task · título · análisis de origen · ¿cubrible?`.
   Una task es "no cubrible" si su análisis tiene preguntas abiertas o sus
   criterios no son verificables — eso se reporta como bloqueo, no se inventa.
3. **Confirmá con el usuario** cuáles cubrir (todas las cubribles o un subconjunto).
4. Por cada una, aplicá el flujo de `/qa:casos` (leer cadena → control estricto →
   derivar → publicar la sección en el cuerpo de la task).
5. **Cierre:** reportá tasks cubiertas (casos por categoría), tasks bloqueadas y
   por qué, y si alguna épica quedó lista para su `[PLAN DE PRUEBAS]` (`/qa:plan`).
