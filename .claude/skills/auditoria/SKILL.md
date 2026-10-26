---
name: auditoria
description: Auditoría de código de Chaco en dos modos: `pr <N>` revisa el diff de un PR antes de mergearlo a development (reemplaza al revisor independiente y deja el «Aprobado @ SHA» que exige el hook guardia_merge) y `completa [módulo]` audita development entera y entrega un informe con solución y regla para no repetir cada error. Usala antes de cualquier merge a development, cuando pidan auditar, revisar si el código es limpio y óptimo, o buscar errores, rendimiento y mejoras sin cambiar lógica ni estética.
---

# /auditoria

Auditoría de código de Chaco —errores, seguridad, rendimiento y código limpio— **sin cambiar
lógica ni estética**. Junta las rúbricas de Thermos con las piezas, los gates y las trampas
medidas del repo.

## Qué modo

| Argumentos | Modo | Procedimiento |
|---|---|---|
| `pr <N>` | B: antes de mergear el PR `N` a `development` | [`modo-pr.md`](modo-pr.md) |
| `completa` o `completa <módulo>` | A: toda `development`, o una app | [`modo-completa.md`](modo-completa.md) |
| sin argumentos | preguntá en texto cuál de los dos, nunca con `AskUserQuestion` | — |

Leé **entero** el procedimiento del modo antes de empezar. Lo ejecuta la sesión principal (el
juez); los auditores son subagentes `chaco-auditor`.

## Principios

- **Sin cambiar lógica ni estética.** Toda solución preserva el comportamiento y lo visual. Si no
  se puede, el hallazgo va como `DECISIÓN CLIENTE: <propuesta por defecto>` y no bloquea.
- **La auditoría no edita código del producto.** El modo B publica un comentario en el PR. El
  modo A escribe solo su informe en `docs/internal/auditoria-AAAA-MM/`. Los arreglos van después,
  en PRs propios y con aprobación.
- **No repite el CI.** La suite, ruff, mypy, `design_audit`, `compile_templates`, los motores
  reales, la ida y vuelta de migraciones y los presupuestos ya corren en cada PR (skill
  `gates-ci`). Un test se corre solo ante una duda concreta.
- **Severidad honesta.** Cada hallazgo lleva `archivo:línea`, un escenario concreto y evidencia.
  Ante la duda, menos severidad y qué falta para confirmarlo.
- **El modo B es la revisión independiente.** Reemplaza al revisor anterior, no se suma. El juez
  verifica cada `[BLOCKER]` y `[MAJOR]` antes de publicarlo.

## Piezas

| Pieza | Para qué |
|---|---|
| `.claude/agents/chaco-auditor.md` | el auditor (opus, solo lectura); cada lanzamiento recibe modo, alcance y rúbricas |
| `rubricas/correccion-seguridad.md` | errores, roturas, autorización, datos y migraciones, trampas de ECOM |
| `rubricas/codigo-limpio.md` | estructura, capas, helpers canónicos, archivos de más de 1000 líneas |
| `rubricas/rendimiento.md` | N+1, consultas que crecen, trampas medidas del ORM, cómo medir |
| `plantillas/ficha.md` | ficha de hallazgo del modo A, con «Regla para no repetirlo» |
| `plantillas/comentario-pr.md` | veredicto del modo B con el marcador del hook, y el re-sello |
| `.claude/hooks/guardia_merge.py` | hook `PreToolUse` que frena `gh pr merge` sin APPROVE para el head |

## El hook

`gh pr merge` de un PR de `Mkdir-arg/Chaco-Back` contra `development` pasa solo si el PR tiene un
comentario con `<!-- auditoria-chaco veredicto=APPROVE sha=<head> -->` y, si el comando trae
`--match-head-commit`, ese SHA coincide. Si `gh` no responde, también frena.

Es una guardia de proceso local, no un control de seguridad: no mira quién escribió el
comentario y no corre en el CI. No tiene bypass. Si frena, el head actual se audita o se re-sella.

## Costo de referencia

- Modo B: dos `chaco-auditor` (opus) por PR. El re-sello no lanza agentes.
- Modo A: hasta siete `chaco-auditor` en la pasada 1, más un agente sonnet por cada hallazgo
  CRÍTICO o ALTO que haya que reproducir.

## Origen

Las rúbricas de corrección y de código limpio están adaptadas de `thermo-nuclear-review` y
`thermo-nuclear-code-quality-review`, del plugin Thermos
([cursor/plugins](https://github.com/cursor/plugins), commit `8b3326d`, licencia MIT, © Cursor).
La de rendimiento sale de `chaco-dev-reviewer` §Método 5 y de las mediciones del banco MySQL.
