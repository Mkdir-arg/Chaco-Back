---
description: Consolidar el plan de pruebas de una épica ([PLAN DE PRUEBAS])
argument-hint: "[número de épica, opcional]"
---

# Plan de pruebas de una épica

Actuá como el **Agente QA de Chaco** (metodología, estructura canónica del plan y
receta `gh` en `QA.md` (raíz, fuente de verdad) — leelo y seguilo).

Foco de este comando: **solo el `[PLAN DE PRUEBAS]`** de una épica.

Contexto del usuario: `$ARGUMENTS`

## Pasos
1. **Épica objetivo.** Si no vino por argumento, listá:
   `gh issue list --label epica --state open --limit 30` y que el usuario elija.
   Leé la épica, sus análisis y sus tasks.
2. **Prerrequisito estricto:** **todas** las tasks de la épica deben tener su
   sección `## Casos de prueba (QA)`. Si falta alguna, **frená** y listá cuáles:
   hay que cubrirlas primero (`/qa:casos`).
3. **Consolidá** con la estructura canónica de `QA.md`: alcance, actores y
   accesos, cobertura por task (tabla), **casos end-to-end** (`TC-E2E-NN`) que
   crucen tasks, datos de prueba, criterios de salida, fuera de alcance.
   El plan **no inventa casos por task nuevos**: consolida los existentes y solo
   agrega los end-to-end.
4. Mostrá el plan al usuario antes de publicar.
5. **Creá el issue** `[PLAN DE PRUEBAS] ...`, agregalo al Project en **Backlog**,
   sin Tipo, con el campo Modulo (receta del `[REQUERIMIENTO]` en `AGENTS.md`).
   No muevas tareas.
6. Reportá el número del plan y la cadena: **Épica #NN → Plan #PP**.
