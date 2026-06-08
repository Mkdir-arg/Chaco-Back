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
4. Asegurá que exista `consumo_file`.
   - Si no existe, crealo con estas secciones:
     - Título del sprint de consumo
     - Tabla `Persona | Motivo | Qué hice | Consumo`
     - Sección "Total consumido"
5. Insertá una fila nueva en la tabla con:
   - Persona
   - Motivo
   - Qué hice
   - Consumo en formato `NN min`
6. Recalculá el total sumando todos los valores `NN min` de la tabla y actualizá la caja de "Contador total" mostrando:
   - Minutos totales
   - Equivalente en horas y minutos
7. Eliminá `.github/worklog/sesion-activa.json` para dejar la sesión cerrada.
8. Respondé un resumen con inicio, fin, minutos y archivo actualizado.
