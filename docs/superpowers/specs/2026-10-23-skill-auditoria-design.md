# Skill `/auditoria`: auditoría completa y control antes de mergear

**Fecha:** 23/10/2026
**Estado:** diseño aprobado, sin implementar

## Problema

Hoy la calidad del código se controla en dos momentos sin un método común:

- **En cada PR**, un revisor independiente (el «revisor liviano» del 08-oct) da APPROVE o
  CHANGES NEEDED y el juez publica «Aprobado @ SHA». El prompt de ese revisor vivía en un
  scratchpad; no está en el repo ni es repetible por otra sesión.
- **De vez en cuando**, una auditoría de todo el código (la integral de oct-2026, 206
  hallazgos). Su método está descripto en `docs/internal/auditoria-2026-10/README.md`, pero
  armarla de nuevo es trabajo manual.

El PM quiere las dos cosas como un proceso: auditar `development` entera cuando lo pida, y
auditar cada PR antes de mergearlo para saber si el código es limpio y óptimo. En los dos
casos, **sin cambiar lógica ni estética**: se mejora cómo funciona el código, no qué hace ni
cómo se ve.

Se suman las rúbricas de Thermos (`github.com/cursor/plugins`, MIT): una de corrección y
seguridad, otra de calidad de código, más exigente que lo que el repo usa hoy.

## Alcance

**Adentro:**

- Una skill de proyecto, `.claude/skills/auditoria/`, con dos modos:
  - **A — `/auditoria completa [módulo]`**: audita `origin/development` entera (o un
    módulo) y entrega **solo un informe**.
  - **B — `/auditoria pr <N>`**: audita el diff de un PR contra `development` y **reemplaza
    al revisor independiente**.
- Un agente auditor de solo lectura, `.claude/agents/chaco-auditor.md`.
- Un hook `PreToolUse` que frena `gh pr merge` sin una auditoría aprobada para el SHA actual.

**Afuera:**

- Implementar los hallazgos. El modo A no toca código; las olas se implementan después,
  por el flujo normal, cada PR pasando por el modo B.
- Auditar diseño visual. La UI la gobierna el agente canónico de diseño y su reviewer; esta
  skill solo mira la calidad del JS y de los templates como código.
- Un check en el CI. Se descartó (ver Decisiones).
- Tocar `chaco-dev-reviewer`: lo siguen usando `/dev:cierre` y el PM Assistant.

## Decisiones tomadas

### Una skill, dos modos

El alcance de la auditoría completa es todo `development`; el del control antes de mergear,
solo lo que el PR agrega o modifica. Comparten rúbricas, agente y plantillas, así que van en
una sola skill con dos puntos de entrada.

### El modo B reemplaza al revisor, no se suma

Sumar un segundo paso por PR vuelve al ciclo lento que el 08-oct se decidió dejar atrás.
El modo B **es** la revisión independiente: absorbe el checklist del revisor liviano (lo que
ningún gate mide: datos sin vuelta, acceso ganado o perdido, contratos externos y app móvil,
rolling, consultas lentas en MariaDB) y le suma las rúbricas de Thermos. El veredicto sigue
siendo «Aprobado @ SHA» y sigue valiendo el ciclo acelerado: APPROVE con solo MINOR se
mergea y los MINOR pasan al PR siguiente del carril.

### Adaptar las rúbricas, no copiarlas

Mismo criterio que el Cambio 340 con ECC. La rúbrica de calidad de Thermos pide
reestructurar «con ambición»; aplicada tal cual a cada PR, frenaría merges por deuda que el
PR no creó y empujaría contra la regla de cambios mínimos de `CLAUDE.md`. Se calibra:

- En el **modo B** bloquea solo lo que el PR **empeora**: un archivo que cruza las 1000
  líneas, condiciones especiales metidas en un flujo ajeno, un helper duplicado cuando hay
  uno canónico, lógica en la capa equivocada (models / selectors / services / views).
- Las reestructuraciones grandes sobre código existente quedan como MINOR o como propuesta
  para el modo A.

Cada rúbrica cita su origen y la licencia MIT. La skill no depende de que Thermos esté
instalado en `~/.claude`.

### «Sin cambiar lógica ni estética» como regla de cada propuesta

La auditoría nunca edita código. Toda solución propuesta preserva el comportamiento y lo
visual. Un error se corrige para que el sistema haga lo que ya debía hacer; si la única
solución cambia una regla de negocio o el diseño, el hallazgo queda como
`DECISIÓN CLIENTE: <propuesta por defecto>` y no bloquea.

### El modo A entrega solo el informe, con la regla para no repetir el error

Una auditoría completa trae decenas de hallazgos y en la de octubre hubo que refutar o
ajustar varios antes de tocar código. Cada hallazgo trae **la solución** y **la regla que
evita repetirlo**, con destino concreto. Si el error se puede detectar mecánicamente, la
regla propuesta es un control (chequeo de `design_audit`, regla de ruff, test, presupuesto de
consultas), no un párrafo: así se aprendió en la red de seguridad. La prosa va donde se lee
en el momento justo (la skill o el agente del tema), no por defecto a `CLAUDE.md`, que se
carga entero en cada sesión.

### Obligatoriedad: hook local, no CI

| Opción | Por qué no / por qué sí |
|---|---|
| Convención | Nada lo frena si se olvida. |
| Check en el CI con Claude | API key como secret, costo en cada push, y un check rojo más frena `Publish main`. |
| **Hook local** | **Elegida.** Hoy mergea el juez por `gh pr merge --match-head-commit`: el hook cubre ese camino exacto, exige que el SHA auditado sea el que se mergea y no cuesta nada. |

No cubre un merge desde la web de GitHub ni `gh api …/merge`: es una guarda del proceso, no
de seguridad.

## Componentes

```
.claude/skills/auditoria/
  SKILL.md                      principios + ruteo a un modo
  modo-pr.md                    procedimiento del modo B
  modo-completa.md              procedimiento del modo A
  rubricas/
    correccion-seguridad.md     ← thermo-nuclear-review + seguridad-django + migraciones/contratos
    codigo-limpio.md            ← thermo-nuclear-code-quality-review, calibrada a Chaco
    rendimiento.md              ← N+1, trampas de MariaDB, presupuestos, perf_audit.py
  plantillas/
    ficha.md                    ficha del modo A (formato oct-2026 + «Regla para no repetirlo»)
    comentario-pr.md            veredicto del modo B + marcador del hook
.claude/agents/chaco-auditor.md agente auditor: model opus, tools Read/Grep/Glob/Bash
.claude/hooks/guardia_merge.py  hook PreToolUse, solo stdlib
```

Un solo agente auditor: cada lanzamiento recibe en el prompt qué rúbrica leer y cuál es el
alcance. Lee la rúbrica como archivo (no la invoca como skill). Todo `.claude/` es
`export-ignore`: nada de esto viaja al release ni a ECOM.

## Modo B — `/auditoria pr <N>`

1. Resolver el PR (`gh pr view N --repo Mkdir-arg/Chaco-Back`): base, `headRefOid`, archivos.
   La base tiene que ser `development`.
2. Diff contra el merge-base con `origin/development`. Si hace falta correr algo, worktree
   del head en el scratchpad.
3. Lanzar **dos `chaco-auditor` en paralelo** con el mismo diff:
   - **corrección, seguridad, datos y contratos** (`rubricas/correccion-seguridad.md`);
   - **código limpio y rendimiento** (`rubricas/codigo-limpio.md` + `rubricas/rendimiento.md`).
4. No repetir lo que corre el CI (suite, ruff, mypy, `design_audit`, `compile_templates`,
   motores reales, ida y vuelta de migraciones, presupuestos): la skill `gates-ci` dice qué
   cubre cada check. Correr un test solo ante una duda concreta.
5. Consolidar: deduplicar, pesar más lo que encontraron los dos, severidad
   `[BLOCKER]` / `[MAJOR]` / `[MINOR]` con `archivo:línea` y evidencia.
6. Veredicto: **APPROVE** sin BLOCKER ni MAJOR; si no, **CHANGES NEEDED**.
7. Publicar un comentario en el PR con `plantillas/comentario-pr.md`. Lleva el marcador
   `<!-- auditoria-chaco veredicto=APPROVE|CHANGES_NEEDED sha=<40 hex> -->`. Si un hallazgo
   repite un patrón ya registrado (requerimientos, auditoría previa), suma «Regla propuesta».

### Re-sello sin agentes

Antes de mergear, el juez suele traer `development` al PR (update-branch) o renumerar el
Cambio: el SHA cambia y el hook volvería a frenar. Si el PR ya tiene un APPROVE para un SHA
anterior, el modo B compara **el diff propio del PR** (contra su merge-base) en los dos SHAs
con `git patch-id --stable`:

- **Iguales** → el cambio vino solo de la base: publica un comentario de re-sello con el
  marcador para el SHA nuevo, sin lanzar agentes.
- **Distintos** → auditoría completa del modo B. Excepción: si lo único que cambió del diff
  propio es `docs/internal/requerimientos.md` (renumeración del Cambio), re-sella y lo dice
  en el comentario.

## Hook — `guardia_merge.py`

- Lee el JSON de `PreToolUse` por stdin. Si `tool_input.command` no contiene `gh pr merge`,
  sale con 0 sin consultar nada.
- Resuelve el número de PR (argumento o rama actual) y el repo (`--repo` o el del checkout).
  Si no es `Mkdir-arg/Chaco-Back` o la base no es `development`, deja pasar.
- Exige un comentario con el marcador `veredicto=APPROVE` cuyo `sha` sea el `headRefOid`
  actual. Si el comando trae `--match-head-commit X`, X tiene que coincidir.
- Si falta, sale con 2 y el mensaje `Falta /auditoria pr N sobre <sha>`.
- Si `gh` falla, también frena: el merge necesita `gh` igual.
- Se registra en `.claude/settings.json` con matcher `Bash|PowerShell`.
- Test con casos: comando sin merge, sin comentario, SHA viejo, CHANGES_NEEDED,
  `--match-head-commit` distinto, todo en orden, `gh` caído. Vive en
  `core/tests/test_guardia_merge.py` con `skipUnless` sobre la existencia del hook (mismo
  patrón que `test_gates_ci` con `design_audit.py`): `.claude/` no viaja al release, y así el
  test corre en el CI de `development` y se saltea en el snapshot de `main`. `gh` se simula;
  el test no toca la red.

## Modo A — `/auditoria completa [módulo]`

1. Worktree de `origin/development` en el scratchpad; anotar el SHA auditado.
2. Línea de base mecánica con scripts del repo: ruff, archivos de más de 1000 líneas,
   `perf_audit.py` (SQLite, sin base), `check_migraciones.py --todas`, deuda de
   `design_audit.py`. Se le pasa a los auditores.
3. **Pasada 1** — hasta 7 `chaco-auditor` en paralelo, uno por eje (acotados al módulo si se
   indicó): seguridad y RBAC · errores y corrección · rendimiento y base · código limpio y
   arquitectura · datos, migraciones y operación · front (calidad de JS y templates, sin
   estética) · tests y red de seguridad.
4. **Pasada 2** — cada hallazgo CRÍTICO o ALTO sin prueba se reproduce con un test en el
   worktree (agente sonnet) → CONFIRMADO o REFUTADO. Los refutados van a «Descartados».
5. Cruzar contra la auditoría previa: no reintroducir lo refutado allá (§8 de oct-2026);
   referenciar lo que sigue abierto.
6. Entregar en `docs/internal/auditoria-AAAA-MM/`: `README.md` (resumen, índice, plan por olas
   con horas S/M/L → 2/4/8/20 h, **tabla de reglas propuestas**, descartados),
   `hallazgos/<eje>.md` y `poc/`. Entra por un PR solo de documentación, que también pasa
   por el modo B.

### Formato de ficha

El de oct-2026 (§0.3 de su README) más un campo:

```
### <ID> · <título>
**Severidad** CRÍTICA|ALTA|MEDIA|BAJA|INFO · **Estado** CONFIRMADO con test|CONFIRMADO|PLAUSIBLE · **Eje** · **Ola** · **Esfuerzo** S|M|L
- Ubicación: path:línea
- Escenario: datos/estado → resultado incorrecto
- Causa raíz
- Solución (preserva lógica y estética; si no puede, DECISIÓN CLIENTE)
- Lo que NO hacer
- Tests a agregar
- Verificación
- Regla para no repetirlo: tipo (control mecánico | skill | agente | CLAUDE.md) · destino · texto o chequeo
```

## Costo de referencia

- Modo B: dos agentes opus por PR (el revisor anterior era uno).
- Modo A: hasta 7 opus en la pasada 1, más un sonnet por hallazgo a verificar.

## Validación

- Test del hook (casos de arriba) y verificación por mutación: quitar la comparación de SHA
  tiene que poner el test en rojo.
- Los tests que leen `CLAUDE.md` (`core.tests.test_gates_ci` y vecinos) siguen en verde tras
  sumar la línea.
- `check_design_agent.py`, `requerimientos.py --check`.
- Prueba de punta a punta: el PR que agrega la skill es el primero auditado con el modo B y el
  primero que el hook deja (o no) mergear.

## Reversión

Borrar `.claude/skills/auditoria/`, `.claude/agents/chaco-auditor.md`,
`.claude/hooks/guardia_merge.py`, el bloque `PreToolUse` de `.claude/settings.json` y la línea
de `CLAUDE.md`. No toca datos ni producto.
