---
description: "Panorama por programa: horas estimadas vs horas registradas (Becas / Dispositivos)"
argument-hint: "[programa o foco, opcional]"
---

# Panorama por programa

Actuá como el **PM Assistant de Chaco** (metodología y estructura canónica del
informe en `PM.md` (raíz, fuente de verdad) — leelo y seguilo, sección
"5. Programas"). **Solo lectura.**

Contexto del usuario: `$ARGUMENTS`

## Pasos
1. **Levantá las estimaciones**: todos los
   `docs/client/funcionalidades/estimacion-programa-*.md`. De cada uno tomá el
   total y el desglose por concepto del "Resumen ejecutivo", más fecha, versión
   y estado de aprobación.
2. **Levantá el consumo por programa**: tablas mensuales con columna `Programa`
   de `docs/client/versiones/version-NNN-consumo-horas.md` (el de número más
   alto). Sumá por programa desde julio 2026. Los meses sin columna `Programa`
   (junio 2026) y las horas `Transversal` van aparte, no contra los programas.
3. **Cruzá con el Project #1** de `Mkdir-arg` (GitHub MCP preferido; fallback
   `gh project item-list 1 --owner Mkdir-arg --format json`): suma de
   `EstimacionHoras` de las tasks de la épica de cada programa vs. el total del
   documento. Si el MCP/`gh` no está disponible, marcá la sección como
   "sin verificar" y seguí.
4. **Armá el informe canónico** de `PM.md` → "5. Programas": resumen ejecutivo ·
   panorama (Estimado | Consumido | % avance | Restante | Estado) · detalle del
   estimado · horas fuera de programas · cruce con el Project · alertas.
5. Datos faltantes se marcan, no se rellenan. Todo número cita su fuente
   (documento de estimación o registro de consumo).
6. Cerrá con las 2-3 lecturas más útiles para el PM (dónde hay riesgo de
   desvío, qué conviene mirar primero).