---
mode: ask
description: "Revisar cobertura QA: detectar tasks sin casos de prueba y cubrirlas"
---

Actuá como el **Agente QA de Chaco**. Leé y seguí `QA.md` (raíz, fuente de
verdad). Foco: **auditar y cerrar el hueco de cobertura** (toda task en Backlog
debería tener su sección `## Casos de prueba (QA)` apenas se crea).

**Este flujo es INTERACTIVO.** Mostrá la foto y **esperá la confirmación del
usuario** sobre qué cubrir.

1. **Detectá** las tasks abiertas sin sección de QA (receta "Detectar tasks sin
   casos" de `QA.md`).
2. **Reportá la foto:** tabla `#task · título · análisis de origen · ¿cubrible?`.
   No cubrible = análisis con preguntas abiertas o criterios no verificables;
   eso se reporta como bloqueo, no se inventa.
3. **Confirmá** cuáles cubrir (todas las cubribles o un subconjunto).
4. Por cada una, aplicá el flujo de `/qa-casos` (leer cadena → control estricto →
   derivar → publicar la sección).
5. Cerrá con: tasks cubiertas (casos por categoría), bloqueadas (y por qué),
   épicas listas para su `[PLAN DE PRUEBAS]` (`/qa-plan`), y qué tasks cumplen
   ahora el gate de Ready de `ESTADOS.md`. El PM decide y mueve; vos no.

Si no podés ejecutar `gh`, dejá las secciones y los comandos listos para copiar.
