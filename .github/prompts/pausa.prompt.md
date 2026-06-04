---
mode: agent
description: Pausar o reanudar una sesión activa para descontar tiempos muertos
---

Actuá como asistente operativo de seguimiento de horas del proyecto.

Objetivo: permitir pausar/reanudar una sesión iniciada con `/inicio-de-trabajo` para no imputar tiempos muertos en `/fin-de-trabajo`.

Reglas:
- No hagas deploy ni commits.
- Si no existe `.github/worklog/sesion-activa.json`, frená y pedí iniciar con `/inicio-de-trabajo`.
- Trabajá con cambios mínimos y respetá el JSON existente.

Comportamiento del comando `/pausa` (toggle):
1. Leé `.github/worklog/sesion-activa.json`.
2. Si `pausada_desde_iso` **no** existe o está en `null`:
   - Registrá hora actual en formato ISO local (`YYYY-MM-DDTHH:mm:ss`) en `pausada_desde_iso`.
   - Guardá el archivo.
   - Respondé: sesión pausada + hora de pausa.
3. Si `pausada_desde_iso` **sí** tiene valor:
   - Registrá hora actual (`reanuda_iso`).
   - Calculá minutos pausados de este tramo (redondeo al minuto más cercano).
   - Agregá una entrada al arreglo `pausas` con este esquema:

```json
{
  "inicio_iso": "YYYY-MM-DDTHH:mm:ss",
  "fin_iso": "YYYY-MM-DDTHH:mm:ss",
  "minutos": 0
}
```

   - Poné `pausada_desde_iso` en `null`.
   - Guardá el archivo.
   - Respondé: sesión reanudada + minutos pausados del tramo + pausas acumuladas.

Formato recomendado del archivo de sesión activa:

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
