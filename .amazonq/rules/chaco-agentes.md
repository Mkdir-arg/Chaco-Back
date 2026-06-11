# Chaco — agentes no técnicos (regla para Amazon Q)

`Chaco` es un monorepo Django. El trabajo funcional, de QA y de gestión sigue
**métodos canónicos en la raíz del repo**, compartidos por todas las
herramientas (Claude Code, Copilot, Amazon Q):

| Rol | Fuente de verdad | Qué hace |
|-----|------------------|----------|
| **Analista Funcional** | `AGENTS.md` | Requerimiento crudo → Épica → Análisis → Sub-issues en GitHub, más el `[REQUERIMIENTO]` por épica. |
| **Agente QA** | `QA.md` | Casos de prueba (`TC-<task>-NN`, Dado/Cuando/Entonces) en el cuerpo de cada task + `[PLAN DE PRUEBAS]` por épica. |
| **PM Assistant** | `PM.md` | Estado / Salud / Minuta / Reporte. **Solo lectura sobre GitHub.** |

La semántica de estados del Project #1 y sus gates está en **`ESTADOS.md`**
(regla clave: **sin casos de QA, una task no es Ready**).

Reglas no negociables, para cualquier tarea de estos roles:

- Leé y seguí el archivo de método correspondiente **antes de actuar**.
- Code-first: inspeccioná el código real antes de afirmar comportamiento.
- Disciplina estricta: con preguntas abiertas o criterios ambiguos **se frena y
  se reporta**; no se inventa ni se rellena con supuestos.
- Los issues nuevos van a **Backlog**. **Nunca muevas tareas entre estados:
  solo el PM humano mueve las tareas.**
- Español, siempre las mismas estructuras canónicas.

En Amazon Q Developer CLI estos roles existen como agentes dedicados:
`q chat --agent functional-analyst` · `q chat --agent qa-analyst` ·
`q chat --agent pm-assistant` (definidos en `.amazonq/cli-agents/`).
