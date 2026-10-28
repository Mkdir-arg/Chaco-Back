---
description: Derivar y crear los sub-issues ejecutables desde un análisis cerrado
argument-hint: "[número del análisis, opcional]"
---

# Crear los sub-issues de un análisis

Actuá como el **Analista Funcional de Chaco** (metodología, estructura canónica y
receta `gh` en `AGENTS.md` (raíz, fuente de verdad) — leelo y seguilo).

Foco de este comando: **solo los sub-issues**, a partir de un análisis ya cerrado.

Contexto del usuario: `$ARGUMENTS`

## Pasos
1. **Análisis de origen.** Identificá el análisis:
   `gh issue list --label analisis --state open --limit 30`. Que el usuario elija;
   leé su contenido (`gh issue view <n>`).
2. **Control estricto previo:** verificá que el análisis **no tenga preguntas
   abiertas** ni inconsistencias y que sus criterios sean verificables. Si todavía
   tiene huecos, **frená**: hay que cerrarlo (volver a `/analisis:analisis`) antes
   de generar sub-issues.
3. Tomá los "Sub-issues propuestos" y derivá **N sub-issues cortos y concretos**.
   Cada uno entendible en 30 segundos (los devs no leen mucho):
   - **Qué se quiere** (1-3 líneas)
   - **Requisitos** (bullets concretos)
   - **Criterios de aprobación** (checklist verificable)
   - Archivos/módulos afectados + estimación en horas
   Si una tarea es grande, partila.
4. Creá cada sub-issue (label `task`) con `Épica padre: #NN` + `Análisis de
   origen: #MM`, agregalo al Project en **Backlog** y seteá **Tipo = Task** y
   **Iteration = la activa**, con Status=Backlog como último paso y verificado (ver
   receta `gh` de `AGENTS.md`). No muevas las tareas de Backlog.
5. Editá el análisis para listar los sub-issues como checklist (`- [ ] #KK`).
6. Reportá la cadena creada: **Épica #NN → Análisis #MM → Sub-issues #…**.
7. **Handoff a QA (no lo saltees):** ofrecé generar **ahora** los casos de prueba
   de las tasks recién creadas (`/qa:casos`), para que cada task nazca con su
   sección `## Casos de prueba (QA)`. Sin casos, la task no cumple el gate de
   Ready (`ESTADOS.md`). Cerrá indicando al PM qué tasks quedaron completas
   (estimación + casos + campos) y por lo tanto elegibles para Ready.
