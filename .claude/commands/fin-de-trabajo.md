---
description: Cerrar sesión de trabajo, calcular tiempo consumido y actualizar el detalle de horas del sprint actual
---

Actuá como asistente operativo de seguimiento de horas del proyecto.

Objetivo: cerrar una sesión iniciada con `/inicio-de-trabajo`, registrar lo realizado y actualizar el documento de consumo de horas del sprint actual con contador total.

Reglas:
- No hagas deploy ni commits.
- Si no existe `.github/worklog/sesion-activa.json`, frená y pedí iniciar con `/inicio-de-trabajo`.
- Trabajá con cambios mínimos y respetá el estilo del markdown existente.

Pasos:
1. Leé `.github/worklog/sesion-activa.json` y tomá:
   - persona
   - programa (si falta, preguntá: **Becas**, **Dispositivos** o **Transversal**)
   - motivo
   - que_hare
   - inicio_iso
   - pausada_desde_iso (si existe)
   - pausas (si existe)
   - consumo_file
2. Pedí al usuario una breve descripción de "qué hiciste" (1 a 3 frases). Si no responde, usá `que_hare` como fallback.
3. Registrá hora de fin en ISO local y calculá minutos consumidos (redondeo al minuto más cercano):
   - `minutos_brutos = fin - inicio`
   - `minutos_pausa = suma de pausas cerradas`.
   - Si `pausada_desde_iso` está informado al cerrar, sumá además la pausa abierta `fin - pausada_desde_iso`.
   - `minutos_consumidos = max(0, minutos_brutos - minutos_pausa)`.
4. Asegurá que en `consumo_file` exista la sección del mes en curso
   (`## ... Consumo de <mes> <año> — detalle día por día`).
   - Si no existe, creala con una tabla `Día | Persona | Programa | Motivo | Qué hice | Consumo`
     y una subsección `### Consumo de <mes> por programa` con filas Becas / Dispositivos / Transversal.
   - Desde julio 2026 todo registro lleva programa; no toques las tablas de meses anteriores.
5. Insertá una fila nueva en la tabla del mes en curso con:
   - Día (`YYYY-MM-DD`)
   - Persona
   - Programa (Becas / Dispositivos / Transversal)
   - Motivo
   - Qué hice
   - Consumo en formato `NN min`
6. Recalculá y actualizá:
   - La tabla `Consumo de <mes> por programa` (suma de `NN min` por programa, en formato `N h MM min`).
   - La caja de "Contador total": minutos totales, equivalente en horas y minutos, y el desglose por mes.
7. Eliminá `.github/worklog/sesion-activa.json` para dejar la sesión cerrada.
8. Avisá que la página financiera del mes (`docs/client/financiero/mes-<año>-<mes>.md`) queda desactualizada y ofrecé actualizar sus números (consumo, saldo, por programa y por persona).
9. Respondé un resumen con inicio, fin, minutos, programa y archivo actualizado.
