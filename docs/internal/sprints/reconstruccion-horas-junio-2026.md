# Reconstrucción de horas — Junio 2026 (trabajo hecho y no registrado)

**Documento interno.** No se publica. Sirve para completar el detalle de consumo de
`docs/client/versiones/version-001-consumo-horas.md` con sesiones de junio que se
trabajaron pero no se cargaron en su momento.

## Reglas (para que el registro sea defendible)

1. **Cada uno completa lo suyo** (o Matías con el registro de cada uno adelante). No se
   estiman horas de terceros.
2. **Solo trabajo real de junio.** Si no te acordás de la duración exacta, usá una
   estimación honesta redondeada a 15 min y marcala con `~`.
3. **Evidencia siempre que exista:** commit, PR, issue, archivo, mensaje, minuta. Da
   respaldo si el cliente pregunta.
4. Cuando esté completa, Matías consolida en el detalle público y se actualiza el
   financiero de junio. **Nada entra al reporte cliente sin pasar por acá.**

Estado actual del registro público (ya cargado, no repetir):
**Junio = 499 h 12 min** — Juani 113:25 · Matías 112:31 · Agostina 112:17 · Pablo 95:59 · Equipo UX 65:00.

> **Actualización 02/07/2026:** se consolidaron en el registro público **300 h** de regularización
> (23/06–30/06): front de la app de campo (Pablo, 55 h), backend de Becas (Juani, 56:40),
> análisis del programa Dispositivos (Matías 63:20 + Agostina 60:00) y mockups del equipo UX (65 h).
> Las grillas por persona de abajo quedan como respaldo histórico del relevamiento.

---

## Pablo Cao — App de relevamiento territorial (Becas)

Ya registrado: 16, 18, 19, 22, 23, 24, 26 y 28 de junio (40 h 59 min).
**Días de junio sin ninguna entrada tuya:** 3–13, 17 (solo reunión), 20–21, 25, 27, 29–30.

| Fecha | Tarea (qué hiciste) | Duración | Evidencia (commit/PR/issue/archivo) |
|---|---|---|---|
| | | | |
| | | | |
| | | | |

Anclas de memoria (para ubicar sesiones no cargadas, completar solo si fueron reales):
- ¿Hubo trabajo previo al 16/06 en el setup de Expo / maqueta inicial de la app?
- ¿Sesiones del 25/06 o 27/06 entre las entregas del 24 y del 26?
- ¿Trabajo del 29–30/06 previo a la sesión del 01/07 (issue #83)?

---

## Juan Portilla Kitroser — Backend de Becas

✅ **Identidad resuelta por git:** "Juan Kitro" = **Juani Portilla** (`juanikitro` /
`Juan Ignacio Portilla Kitroser`). Ya tiene 56 h 45 min registradas en junio (hasta el
24/06). **El historial de git muestra 3 días de trabajo fuerte SIN registrar** —
completar solo la duración real:

| Fecha | Tarea (evidencia de commits) | Duración | Evidencia |
|---|---|---|---|
| 2026-06-26 | Becas: convocatorias (listado + detalle 4 tabs), infraestructura AJAX para modales, requisitos por segmento + cuestionario social, segmentos con modales AJAX, campo observaciones | | 6 commits `feat(becas)` del 26/06 + PR #96 |
| 2026-06-29 | Becas: filtrado dinámico de subsegmento (#75) · Roles: tabs de capacidades + buscador + ÑACHEC/Becas | | commits 29/06 + PRs #105/#106/#107 |
| 2026-06-30 | CI de GitHub Actions para PRs (setup + fixes Ruff/Bandit/coverage) · Becas: cupo/lista de espera UI + solapa Becas en legajo ciudadano | | commits 30/06 + PRs #110/#111/#113 |
| 2026-06-03 | Design KB inicial (NODO design-kb + resolución conflictos NODO vs CHACO) — verificar si quedó dentro de los 480 min registrados el 08/06 | | 2 commits del 03/06 |
| | | | |

---

## Matías Fariña — Análisis funcional del Programa Dispositivos

Ya registrado en junio: análisis Becas, legajo ciudadano, estimación y gestión
(49 h 11 min). **No hay ninguna entrada tuya por el análisis de Dispositivos**, que sí
ocurrió en junio. Anclas verificables en el repo:

- **25/06** — Versión inicial de la propuesta (`docs/internal/analisis/005-…`,
  historial de cambios §19: Miro + especificación NODO + mapeo del código).
- **26/06** — Integración campo a campo de los formularios F-00/F-01/F-02 (mismo
  historial; se cerró Q-9 y se abrieron C-6/C-7/C-8).
- **26/06** — Reunión con el Ministerio sobre dispositivos y merenderos (minuta
  `seguimiento-dispositivos-merenderos-2026-06-26.md`).
- ¿Sesiones de lectura del Miro / especificación NODO previas al 25/06?

| Fecha | Tarea | Duración | Evidencia |
|---|---|---|---|
| 2026-06-25 | Análisis Dispositivos — versión inicial de la propuesta | | historial doc 005 |
| 2026-06-26 | Análisis Dispositivos — formularios F-00/F-01/F-02 campo a campo | | historial doc 005 |
| 2026-06-26 | Reunión Ministerio — dispositivos y merenderos | | minuta 2026-06-26 |
| | | | |

---

## Florencia — Mockups del front de Becas

**No hay ninguna entrada tuya en junio.** Todo tu trabajo del mes va acá. Anclas
verificables:

- El kit de referencia del Design System registra **diseños de referencia de la
  diseñadora** y una ronda de **10 respuestas de coordinación** (entrada de Juani del
  08/06). ¿Qué sesiones tuyas hay detrás de ese material?
- Mockups de pantallas del front de Becas: ¿cuáles, en qué fechas, con qué entregable
  (Figma/archivo/link)?

| Fecha | Tarea | Duración | Evidencia (link a Figma/archivo) |
|---|---|---|---|
| | | | |
| | | | |
| | | | |

---

## Verificaciones pendientes del registro existente

- [ ] **Posible duplicado:** 2026-06-18 · Agostina Coppola · "Testing requerimientos y
  análisis de legajos dispositivos/merenderos" aparece **dos veces** (222 min y
  370 min). Confirmar si fueron dos sesiones reales el mismo día o una carga doble;
  si es doble, corregir el detalle público y el total (−222 o −370 min).
- [ ] Confirmar identidad "Juan Kitro" vs "Juani Portilla" (ver arriba).
