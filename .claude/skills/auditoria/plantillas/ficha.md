# Plantilla: ficha de hallazgo (modo `completa`)

Mismo formato que la auditoría de octubre (`docs/internal/auditoria-2026-10/README.md` §0.3), más
el campo **Regla para no repetirlo**. Una ficha por problema: si dos ejes encuentran lo mismo,
queda una sola y la otra figura en «Origen».

```markdown
### <ID> · <título corto: qué falla, no dónde>
**Severidad:** CRÍTICA|ALTA|MEDIA|BAJA|INFO · **Estado:** CONFIRMADO con test (`poc/<archivo>::<Clase>.<test>`) | CONFIRMADO (lectura) | PLAUSIBLE | REFUTADO
· **Eje:** SEG|ERR|PERF|LIM|DAT|FE|TST · **Origen:** <IDs absorbidos, o de la auditoría previa> · **Ola:** <n> · **Esfuerzo:** S|S-M|M|L
- **Ubicación:** `path:línea` (líneas del SHA auditado; si se movieron, buscar por nombre de función)
- **Escenario:** datos o estado concretos → resultado incorrecto (lo reproducido, si hay PoC)
- **Causa raíz:** por qué pasa, no qué se ve
- **Solución:** archivos, funciones, pseudocódigo o migración. Preserva lógica y estética; si no
  puede, `DECISIÓN CLIENTE: <propuesta por defecto>`
- **Lo que NO hay que hacer:** el arreglo tentador que rompe otra cosa (si aplica)
- **Tests a agregar:** nombres (`<app>/tests/test_<x>.py::<Clase>.<test>`)
- **Verificación:** cómo se comprueba que quedó resuelto (test, `perf_budgets.json`, banco MySQL)
- **Regla para no repetirlo:** **control mecánico | skill | agente | CLAUDE.md** · **destino** · texto o chequeo propuesto
```

## IDs

Prefijo del eje + número de dos dígitos (`SEG-01`, `PERF-02`…):

| Eje | Prefijo |
|---|---|
| Seguridad y RBAC | `SEG` |
| Errores y corrección | `ERR` |
| Rendimiento y base | `PERF` |
| Código limpio y arquitectura | `LIM` |
| Datos, migraciones y operación | `DAT` |
| Front (calidad, sin estética) | `FE` |
| Tests y red de seguridad | `TST` |

## Estados

En la pasada 1 el auditor solo usa `CONFIRMADO (lectura)` o `PLAUSIBLE`; `CONFIRMADO con test` y
`REFUTADO` los asigna la pasada 2, que escribe y corre la PoC.

- **CONFIRMADO con test:** hay una PoC en `poc/` que lo reproduce.
- **CONFIRMADO (lectura):** verificado leyendo el código citado.
- **PLAUSIBLE:** el mecanismo es real pero depende de datos o configuración de producción, o no se
  reprodujo.
- **REFUTADO:** la verificación mostró que no pasa. Va a «Descartados» del README con el motivo,
  para que nadie lo reintroduzca.

## Esfuerzo

`S` = 2 h · `S-M` = 4 h · `M` = 8 h · `L` = 20 h.

## «Regla para no repetirlo»: cómo elegir el tipo

Elegí el primero que aplique:

1. **Control mecánico** — si una herramienta lo puede detectar, la regla es el control, no un
   párrafo. Destinos posibles: un chequeo nuevo en `scripts/design_audit.py`, una regla de ruff en
   `pyproject.toml`, un test que falle si reaparece (ratchet), una entrada en
   `scripts/perf_budgets.json`, una regla de `scripts/check_migraciones.py`. Escribí el chequeo
   propuesto (patrón, condición, mensaje).
2. **Skill** o **agente** del tema — lo que ninguna herramienta ve, escrito donde se lee en el
   momento justo. Skill: `.claude/skills/mysql-mariadb/` (base), `.claude/skills/seguridad-django/`
   (seguridad), `.claude/skills/auditoria/rubricas/*.md` (lo que la próxima auditoría tiene que
   mirar). Agente: `.claude/agents/chaco-frontend.md` (front), `.claude/agents/chaco-auditor.md`.
   Escribí el texto tal como quedaría.
3. **`CLAUDE.md`** — solo si aplica a **toda** sesión de trabajo en el repo. Se carga entero en
   cada sesión: cada línea ahí cuesta en todas.
