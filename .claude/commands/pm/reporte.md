---
description: Reporte de avance del período en lenguaje cliente (para enviar o publicar)
argument-hint: "[período o sprint, opcional]"
---

# Reporte de avance

Actuá como el **PM Assistant de Chaco** (estructura canónica y reglas en `PM.md`
(raíz, fuente de verdad) — leelo y seguilo).

Contexto del usuario: `$ARGUMENTS`

## Pasos
1. **Definí el período** (si no vino: el sprint actual) y levantá los datos:
   - Project #1 de `Mkdir-arg` e issues (GitHub MCP preferido; fallback `gh`):
     qué épicas/análisis/tasks se crearon, definieron o cerraron en el período.
   - Horas reales: `docs/client/financiero/` (`mes-AAAA-MM.md` del período +
     `detalle-tareas.md`).
   - Asunciones a confirmar pendientes en los análisis activos.
2. **Armá el reporte canónico** de `PM.md` → "4. Reporte", en **lenguaje
   cliente** (sin jerga técnica, sin estado del código, sin riesgos internos):
   período y resumen · funcionalidades trabajadas por épica · horas del período
   · próximos pasos · temas que necesitamos del cliente.
3. **Mostrá el reporte completo** al usuario y ajustá lo que pida.
4. Preguntá el destino: ¿queda en pantalla para enviar por otro canal, o se
   publica en `docs/client/`? Si se publica, seguí las reglas de publicación de
   `AGENTS.md` (plantilla, index, nav, build `--strict`) y **confirmá antes del
   deploy**.
