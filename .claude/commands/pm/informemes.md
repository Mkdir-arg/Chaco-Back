---
description: Informe de cierre de mes en lenguaje cliente (texto de correo listo para enviar)
argument-hint: "[mes AAAA-MM, opcional — por defecto el último mes cerrado]"
---

# Informe de mes

Actuá como el **PM Assistant de Chaco** (estructura canónica y reglas en `PM.md`
(raíz, fuente de verdad) — leelo y seguilo, sección "6. Informe de mes").

Contexto del usuario: `$ARGUMENTS`

## Pasos

1. **Definí el mes**: el que pidió el usuario o, por defecto, el último mes
   **cerrado** según `docs/client/financiero/index.md` (sección "Meses
   cerrados"). Si piden un mes todavía en curso, avisalo y confirmá antes de
   seguir.
2. **Levantá los datos del mes** (recolectá todo antes de escribir):
   - `docs/client/financiero/mes-AAAA-MM.md` + `detalle-tareas.md` → números
     finales del cierre, consumo por programa y por persona/foco, notas de
     regularización y de traslado.
   - `docs/client/minutas/` → reuniones del mes: fecha, temas y acuerdos. Si el
     mes no tuvo minutas publicadas, **no se inventa la sección**: se reemplaza
     por la coordinación real que sí hubo (dependencias resueltas con el
     organismo, definiciones acordadas, entornos) o se fusiona con otra.
   - `docs/client/funcionalidades/` → definiciones y estimaciones presentadas o
     aprobadas en el período (con su estado de aprobación).
   - Desarrollo del período: releases a `main` del mes (`git log --oneline
     --since/--until`) e issues cerrados (GitHub MCP preferido, fallback `gh`)
     — se cuentan por el **valor** que aportan, nunca por la técnica. La lista
     "Qué se está trabajando en el mes" del `mes-AAAA-MM.md` ya está en lenguaje
     cliente: es la mejor materia prima para la sección de desarrollo.
3. **Redactá el informe** con la estructura canónica de `PM.md` → "6. Informe de
   mes". La **referencia de tono y formato** son los informes ya enviados, en
   `docs/internal/informes-mes/` (el más reciente manda; `2026-06.md` es el que
   fijó la estructura). Adaptá las secciones al contenido real del mes.
4. **Mostralo completo** al usuario y ajustá lo que pida.
5. **Guardá el informe** en `docs/internal/informes-mes/AAAA-MM.md` (registro
   interno, no se publica: `docs_dir` del sitio es `docs/client`). Es lo que
   hace reproducible el formato del mes siguiente.
6. **No publiques ni envíes nada** en `docs/client/` salvo pedido explícito — si
   lo piden, reglas de `AGENTS.md` (plantilla, index, nav, build `--strict`) y
   confirmación antes del deploy.

## Cierre del mes con traslado de excedente

Regla vigente desde el **02/09/2026** (decisión del PM). Cuando el esfuerzo real
del mes **supera** el presupuesto mensual:

- El mes se **imputa al presupuesto** (100%, nunca más) y el excedente se
  **traslada al mes siguiente** como consumo inicial. Al cliente no se le pasa
  de más y el esfuerzo real sigue visible y trazable.
- El informe y las páginas del mes declaran **las dos cifras**: *esfuerzo real
  del mes* y *horas imputadas al presupuesto*, con el traslado explícito.
- El detalle día por día **no se toca**: sigue reflejando el esfuerzo real. El
  traslado es de imputación, no de registro.

Si el usuario pide **cerrar** el mes (esto sí escribe, y va a `development`):

1. `mes-AAAA-MM.md` → pasa a "Resumen de cierre": tarjetas con presupuesto,
   horas imputadas (100%) y saldo 0, más la nota del traslado. Las tablas por
   programa y por persona conservan el **esfuerzo real** (etiquetado como tal).
2. `mes-AAAA-MM+1.md` → se crea como "Mes en curso" con el excedente ya
   consumido y el saldo disponible resultante.
3. `index.md` → el mes cerrado baja a "Meses cerrados" (con su % y la nota del
   traslado) y la tarjeta de "Mes en curso" pasa al mes nuevo.
4. `mkdocs.yml` → sumar la página del mes nuevo al nav (`nav:` → financiero).
5. `detalle-tareas.md` → nota de cierre al pie de la sección del mes y
   aclaración en el contador total (esfuerzo real vs imputación).
6. Commit a `development` (worktree desde `origin/development` si la sesión está
   en otra rama; **verificar la rama en el mismo comando que el commit**) y
   verificar que **Docs Auto Deploy** termine en verde.
