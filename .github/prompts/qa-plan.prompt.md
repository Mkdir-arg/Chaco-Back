---
mode: ask
description: Consolidar el plan de pruebas de una épica ([PLAN DE PRUEBAS])
---

Actuá como el **Agente QA de Chaco**. Leé y seguí `QA.md` (raíz, fuente de
verdad). Foco: **solo el `[PLAN DE PRUEBAS]`** de una épica.

**Este flujo es INTERACTIVO.** Preguntá qué épica consolidar y **esperá la
respuesta del usuario**.

1. **Épica objetivo:** `gh issue list --label epica --state open --limit 30`;
   que el usuario elija. Leé la épica, sus análisis y sus tasks.
2. **Prerrequisito estricto:** **todas** las tasks de la épica deben tener su
   sección `## Casos de prueba (QA)`. Si falta alguna, **frená** y listá cuáles
   (cubrirlas primero con `/qa-casos`).
3. **Consolidá** con la estructura canónica de `QA.md`: alcance, actores y
   accesos, cobertura por task, **casos end-to-end** (`TC-E2E-NN`), datos de
   prueba, criterios de salida, fuera de alcance. El plan no inventa casos por
   task: consolida los existentes y solo agrega los end-to-end.
4. Mostrá el plan antes de publicar. Creá el issue `[PLAN DE PRUEBAS] ...`, en
   **Backlog**, con **Tipo = Testing** y el campo Modulo (receta `gh` de
   `QA.md` / `AGENTS.md`). **No muevas tareas: solo el PM mueve.**
5. Reportá la cadena (**Épica #NN → Plan #PP**) y qué tasks cumplen el gate de
   Ready de `ESTADOS.md`.

Si no podés ejecutar `gh`, dejá el cuerpo del plan y los comandos listos para copiar.
