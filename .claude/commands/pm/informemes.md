---
description: Informe de cierre de mes en lenguaje cliente (texto de correo listo para enviar)
argument-hint: "[mes AAAA-MM, opcional — por defecto el último mes cerrado]"
---

# Informe de mes

Actuá como el **PM Assistant de Chaco** (estructura canónica y reglas en `PM.md`
(raíz, fuente de verdad) — leelo y seguilo, sección "6. Informe de mes").
**Solo lectura.**

Contexto del usuario: `$ARGUMENTS`

## Pasos
1. **Definí el mes**: el que pidió el usuario o, por defecto, el último mes
   **cerrado** según `docs/client/financiero/index.md` (sección "Meses
   cerrados"). Si piden un mes todavía en curso, avisalo y confirmá antes de
   seguir.
2. **Levantá los datos del mes** (recolectá todo antes de escribir):
   - `docs/client/financiero/mes-AAAA-MM.md` + `detalle-tareas.md` → números
     finales del cierre, consumo por programa y por persona/foco, notas de
     regularización.
   - `docs/client/minutas/` → reuniones del mes: fecha, temas y acuerdos.
   - `docs/client/funcionalidades/` → definiciones y estimaciones presentadas
     o aprobadas en el período (con su estado de aprobación).
   - Desarrollo del período: releases a `main` del mes (`git log --oneline
     --since/--until`) e issues cerrados (GitHub MCP preferido, fallback
     `gh`) — se cuentan por el **valor** que aportan, nunca por la técnica.
3. **Redactá el informe** con la estructura canónica de `PM.md` → "6. Informe
   de mes", imitando el tono y el nivel de detalle del informe de junio 2026:
   formato correo ("Estimados, …"), prosa clara, secciones numeradas y la
   tabla `Frente | Horas | Participación` al final. Adaptá las secciones al
   contenido real del mes (si no hubo estimaciones nuevas o reuniones, esa
   sección se acorta o se fusiona; no se inventa).
4. **Mostralo completo** al usuario y ajustá lo que pida. El texto queda en
   pantalla listo para copiar y enviar; **no publiques ni envíes nada** salvo
   pedido explícito — si piden publicarlo en `docs/client/`, seguí las reglas
   de `AGENTS.md` (plantilla, index, nav, build `--strict`) y confirmá antes
   del deploy.
