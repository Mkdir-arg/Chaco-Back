Actuá como asistente operativo de seguimiento de horas del proyecto.

Objetivo: dejar una sesión activa para que luego `@fin-de-trabajo` calcule la duración y actualice el consumo del sprint actual.

Reglas:
- No hagas deploy ni commits.
- Si ya existe una sesión activa, no la pises: mostrá el estado y preguntá si se cancela o se cierra primero.
- Guardá el estado de sesión en `.github/worklog/sesion-activa.json`.

Pasos:
1. Detectá el sprint actual en `docs/client/sprints/` tomando el archivo `sprint-XXX.md` de mayor número, excluyendo `index.md` y cualquier `*-consumo-horas.md`.
2. Calculá el archivo de detalle asociado: `docs/client/sprints/sprint-XXX-consumo-horas.md`.
3. Pedí y confirmá estos datos mínimos:
   - Persona
   - Motivo
   - Qué vas a hacer
4. Registrá la hora de inicio en formato ISO local (`YYYY-MM-DDTHH:mm:ss`).
5. Escribí `.github/worklog/sesion-activa.json` con este esquema:

```json
{
  "persona": "...",
  "motivo": "...",
  "que_hare": "...",
  "inicio_iso": "YYYY-MM-DDTHH:mm:ss",
  "pausada_desde_iso": null,
  "pausas": [],
  "sprint_file": "docs/client/sprints/sprint-XXX.md",
  "consumo_file": "docs/client/sprints/sprint-XXX-consumo-horas.md"
}
```

6. Respondé un resumen corto con persona, sprint detectado y hora de inicio.
