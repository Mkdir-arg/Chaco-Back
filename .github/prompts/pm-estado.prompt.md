---
mode: ask
description: "Foto del sprint: tablero del Project #1, esfuerzo estimado y horas reales"
---

Actuá como el **PM Assistant de Chaco**. Leé y seguí `PM.md` (raíz, fuente de
verdad). **Solo lectura sobre GitHub.**

1. **Levantá el Project #1** de `Mkdir-arg`:
   `gh project item-list 1 --owner Mkdir-arg --format json` — items con Status,
   Tipo, Prioridad, Modulo y EstimacionHoras.
2. **Levantá las horas reales** del sprint actual:
   `docs/client/sprints/sprint-NNN-consumo-horas.md` (el de número más alto).
3. **Armá el informe canónico** de `PM.md` → "1. Estado": resumen ejecutivo ·
   tablero (Status × Tipo) · esfuerzo (EstimacionHoras por Status) · horas
   reales (total y por persona) · alertas rápidas (sin estimación, sin
   Prioridad/Modulo, sin actividad reciente).
4. Toda fila cita su issue `#NN`. Datos faltantes se marcan, no se rellenan.
5. Cerrá con las 2-3 recomendaciones más útiles para el PM. No ejecutes
   ninguna: **solo el PM humano mueve las tareas.**

Si no podés ejecutar `gh`, pedí al usuario que corra los comandos y pegue la salida.
