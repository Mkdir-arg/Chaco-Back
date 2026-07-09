---
description: "Horas por programa: estimado, consumido y disponible (tabla concisa)"
argument-hint: "[programa o foco, opcional]"
---

# Horas por programa

Actuá como el **PM Assistant de Chaco** (metodología y estructura canónica del
informe en `PM.md` (raíz, fuente de verdad) — leelo y seguilo, sección
"5. Horas"). **Solo lectura.**

Contexto del usuario: `$ARGUMENTS`

## Pasos
1. **Levantá las estimaciones**: todos los
   `docs/client/funcionalidades/estimacion-programa-*.md` → total del
   "Resumen ejecutivo" de cada programa. Marcá las pendientes de aprobación.
2. **Levantá el consumo por programa**: `docs/client/financiero/`
   (`mes-AAAA-MM.md` de cada mes + `detalle-tareas.md` día por día).
   **Junio 2026 se imputa íntegramente a Becas y cuenta como consumo real
   contra su estimación** (decisión del PM, 08/07/2026); desde julio sumá por
   programa con la columna `Programa`. Las horas `Transversal` van aparte, no
   descuentan disponible de ningún programa.
3. **Armá la tabla concisa** de `PM.md` → "5. Horas":
   Programa | Estimado | Consumido | **Disponible** (Estimado − Consumido),
   más fila Transversal (solo consumido) y fila Total. Debajo, una línea con
   el mes en curso: presupuesto mensual, consumido al día de la fecha y saldo.
4. **Nada más.** Sin cruce con el Project, sin secciones extra. Datos
   faltantes se marcan, no se rellenan; si hay algo grave (p. ej. consumo sin
   estimación aprobada), una línea al pie alcanza.