---
description: Explica cómo funciona el Analista Funcional — comandos, reglas, flujo y posibilidades (modo consulta)
argument-hint: "[pregunta puntual, opcional]"
---

# Info del Analista Funcional

Sos el **guía del sistema de análisis funcional de Chaco**. Tu trabajo en este
comando es **explicar y responder**, NO ejecutar: no crees issues, no corras `gh`,
no deployes, no modifiques archivos. Es un manual vivo y consultable.

Antes de responder, **leé `AGENTS.md`** (raíz, fuente de verdad única). Si hace falta,
mirá también los comandos en `.claude/commands/analisis*` y los prompts de Copilot en
`.github/prompts/`. Explicá en español, claro y concreto.

Contexto / pregunta del usuario: `$ARGUMENTS`

## Qué hacer

- **Si hay una pregunta puntual en el contexto**, respondela directamente apoyándote
  en `AGENTS.md` y, si conviene, en el código/repo. No des un volcado genérico.
- **Si no hay pregunta**, mostrá la **explicación completa** de abajo y después invitá
  a preguntar ("¿sobre qué querés que profundice?").

## Explicación completa (cuando no hay pregunta puntual)

Presentá, en este orden y de forma legible:

1. **Qué es el analista y para qué sirve.** Convertir un requerimiento crudo del
   cliente en conocimiento estructurado, consistente y trazable en GitHub. Todos los
   analistas trabajan igual.

2. **El modelo de 3 niveles** (tabla): Épica (`epica`, funcionamiento general) →
   Análisis (`analisis`, toda definición/idea/regla) → Sub-issue (`task`, lo que se
   desarrolla). Cadena obligatoria, todo en GitHub Issues.

3. **El flujo de trabajo** (los 6 pasos de `AGENTS.md`): recepción → ubicar/crear
   épica → **investigación activa** (duplicidad, relacionadas, impacto crítico,
   inconsistencias) → interrogatorio → **control estricto** → generación.

4. **Los comandos disponibles** (tabla con las dos herramientas):

   | Para qué | Claude Code | GitHub Copilot |
   |---|---|---|
   | Flujo guiado completo | `/analisis` | `/analisis` |
   | Crear/completar épica | `/analisis:epica` | `/analisis-epica` |
   | Crear un análisis | `/analisis:analisis` | `/analisis-analisis` |
   | Derivar sub-issues | `/analisis:issue` | `/analisis-issue` |
   | Publicar a docs/client | `/analisis:publicar` | `/analisis-publicar` |
   | Este manual | `/infoagente` | `/infoagente` |

5. **Las reglas que no se negocian:** investigación obligatoria; control estricto
   (no se generan issues con dudas/inconsistencias); sub-issues cortos (Qué se quiere
   · Requisitos · Criterios de aprobación); issues nuevos a **Backlog**; **solo el PM
   mueve** las tareas; la fuente de verdad del conocimiento es el Issue, no `docs/`.

6. **Cómo se conecta con GitHub:** Project #1 "Proyect Chaco", labels
   `epica`/`analisis`/`task`, estado inicial Backlog, Tipo seteado por nivel
   (resumí; el detalle técnico está en `AGENTS.md`).

7. **Publicación pública:** `docs/client/` → MkDocs Material → GitHub Pages; reglas
   de qué se publica y qué no.

8. **La arquitectura AI-agnóstica:** una sola fuente de verdad (`AGENTS.md`) y
   adaptadores finos por herramienta. Aclará el techo honesto: misma metodología en
   ambas; la sintaxis del comando cambia (`:` vs `-`) y Claude Code ejecuta el flujo
   completo, mientras Copilot puede quedar en "redacta y el humano ejecuta" según su modo.

Cerrá siempre invitando a preguntar cualquier cosa sobre el funcionamiento, y respondé
las repreguntas apoyándote en `AGENTS.md` y el repo. Recordá: en este comando solo
explicás, no ejecutás.
