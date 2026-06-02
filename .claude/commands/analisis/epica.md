---
description: Crear o completar una Épica (funcionamiento general / objetivo macro)
argument-hint: "[tema u objetivo de la épica, opcional]"
---

# Crear / completar una Épica

Actuá como el **Analista Funcional de Chaco** (metodología, estructura canónica y
receta `gh` en `.claude/agents/functional-analyst.md` — leelo y seguilo).

Foco de este comando: **solo la épica**. No crees análisis ni sub-issues acá.

Contexto del usuario: `$ARGUMENTS`

## Pasos
1. Si no hay tema claro, preguntá el objetivo macro.
2. Ubicá el/los módulos Django involucrados (lectura rápida del repo) para no
   definir a ciegas el funcionamiento general.
3. Interrogá sección por sección hasta completar la épica:
   - Objetivo de negocio
   - Problema a resolver
   - Funcionamiento general (alto nivel, sin implementación)
   - Alcance / Fuera de alcance
   - Módulo principal
   - Definición de terminado
4. **Estricto:** no crees la épica si quedan huecos o contradicciones. Listá lo
   que falta y frená.
5. Creá el issue (label `epica`), agregalo al Project en **Backlog** y seteá
   **Tipo = Epica** (ver receta `gh` del agente). No muevas la tarea de Backlog.
6. Reportá el número de la épica creada.
