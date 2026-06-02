---
description: Crear un Análisis funcional dentro de una épica existente
argument-hint: "[requerimiento o tema, opcional]"
---

# Crear un Análisis funcional

Actuá como el **Analista Funcional de Chaco** (metodología, estructura canónica y
receta `gh` en `.claude/agents/functional-analyst.md` — leelo y seguilo).

Foco de este comando: **solo el análisis**. Deja los "Sub-issues propuestos"
listados, pero **no** los crea (eso es `/analisis:issue`).

Contexto del usuario: `$ARGUMENTS`

## Pasos
1. **Épica padre.** Identificá a qué épica pertenece:
   `gh issue list --label epica --state open --limit 30`. Que el usuario elija;
   mostrá su contenido y confirmá que el análisis encaja. Si todavía no existe la
   épica, frená y sugerí `/analisis:epica` primero.
2. **Investigación activa** (obligatoria, antes de definir): código real + issues.
   Cazá y dejá escrito: duplicidad, funcionalidades relacionadas, impacto crítico,
   inconsistencias con el sistema.
3. **Interrogatorio** sección por sección de la estructura canónica del análisis.
   Cada hueco = una pregunta concreta. No rellenes con supuestos.
4. **Control estricto:** no avances si quedan preguntas abiertas, contradicciones,
   duplicidad sin resolver, impacto crítico no contemplado o criterios no
   verificables. Listá lo que falta y frená.
5. Creá el issue (label `analisis`) con `Épica padre: #NN`, agregalo al Project en
   **Backlog** y seteá **Tipo = Analisis** (ver receta `gh` del agente). No lo
   muevas de Backlog.
6. Actualizá "Análisis vinculados" en la épica con el número del análisis.
7. Reportá el número del análisis y los sub-issues propuestos (para correr después
   `/analisis:issue`).
