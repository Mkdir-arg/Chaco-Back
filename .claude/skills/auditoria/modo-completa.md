# Modo A — `/auditoria completa [módulo]`

Audita `origin/development` entera, o una app si se pasa `<módulo>` (`programas`, `core`,
`legajos`…). Entrega **solo un informe**: cada hallazgo con su solución y su «Regla para no
repetirlo». No implementa nada; los arreglos salen después, por olas, con aprobación del PM.

Comandos de Git Bash. `<scratchpad>` es el directorio temporal de la sesión, escrito con barras
`/`. `AAAA-MM` es el año y mes de la auditoría.

## 1. Worktree del SHA auditado

```bash
git fetch origin development
SHA=$(git rev-parse origin/development)
RAIZ=$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")  # checkout principal: venv y worktrees
W="$RAIZ/.claude/worktrees/auditoria-${SHA:0:8}"
git worktree add --detach "$W" "$SHA"
PY="$RAIZ/.venv312/Scripts/python.exe"                                     # Python 3.12 + Django 5.2, igual al CI
RUFF="$RAIZ/.venv/Scripts/python.exe"                                      # el que tiene ruff
export PYTHONIOENCODING=utf-8
```

Anotá `SHA`: todas las líneas que se citen son de ese commit. El worktree va en
`.claude/worktrees/` (ignorado por git) y no en el scratchpad: en Windows la ruta del scratchpad es
tan larga que el checkout falla con `Filename too long`.

## 2. Línea de base mecánica

A `<scratchpad>/linea-base/`, no al repo. Se le pasa a los auditores.

```bash
L=<scratchpad>/linea-base; mkdir -p "$L"
"$RUFF" -m ruff check "$W" --statistics > "$L/ruff.txt"
git -C "$W" ls-files -z '*.py' '*.html' '*.js' | sed -z "s|^|$W/|" | xargs -0 wc -l | grep -v ' total$' \
  | awk '$1>1000' | sort -rn > "$L/archivos-grandes.txt"   # -z: hay nombres con espacios
"$PY" "$W/scripts/perf_audit.py" --output "$L/perf.json" > "$L/perf.txt"
"$PY" "$W/scripts/check_migraciones.py" --todas > "$L/migraciones.txt"
"$PY" "$W/scripts/design_audit.py" > "$L/design.txt"
```

- `ruff`, `check_migraciones.py` y `design_audit.py` salen con 1 por la deuda que ya existe: es
  la línea de base, no un rojo.
- `perf_audit.py` arma su propia SQLite en memoria y siembra con `seed_perf`; no necesita base.
- `design_audit.py` sin argumentos da la deuda total. `--ratchet` acá no sirve: compara contra
  `HEAD`, que en el worktree es el mismo SHA.
- En `archivos-grandes.txt`, ignorá lo vendorizado y lo compilado.

## 3. Pasada 1 — un auditor por eje

Hasta siete `Agent(subagent_type="chaco-auditor")` en **un solo mensaje**. Con `<módulo>`, cada
uno queda acotado a esa app y a lo que la consume.

| Eje | Prefijo | Rúbricas | Qué mira además |
|---|---|---|---|
| Seguridad y RBAC | `SEG` | `correccion-seguridad.md` §3 y §5 + skill `seguridad-django` | vistas, `/api/`, link público, archivos de `media/`, datos personales |
| Errores y corrección | `ERR` | `correccion-seguridad.md` §1, §2 y §6 | services, crons, integraciones (RENAPER, SIIS), transiciones de estado |
| Rendimiento y base | `PERF` | `rendimiento.md` | `perf.json`; listados, dashboards, exports, link público |
| Código limpio y arquitectura | `LIM` | `codigo-limpio.md` | `archivos-grandes.txt`, `ruff.txt`, capas, helpers duplicados |
| Datos, migraciones y operación | `DAT` | `correccion-seguridad.md` §4 y §5 + skill `mysql-mariadb` | `migraciones.txt`, comandos de gestión, entrypoint, settings |
| Front (calidad, sin estética) | `FE` | `codigo-limpio.md` (Front) + skill `seguridad-django` §4 XSS | JS de `static/custom/`, lógica en templates; `design.txt` solo como señal |
| Tests y red de seguridad | `TST` | `codigo-limpio.md` | caminos críticos sin test; tests que pasan por el motivo equivocado (si rompés la guarda, ¿se pone rojo?) |

Prompt de cada uno (rutas de las rúbricas: `<checkout>/.claude/skills/auditoria/rubricas/`, con
`<checkout>` = `git rev-parse --show-toplevel` del juez):

```
Modo: completa. Eje: <eje> (prefijo <PREFIJO>). Alcance: <todo el repo | la app <módulo> y sus consumidores>.
Worktree: <W> (SHA <SHA>; citá líneas de ese commit). Nada se escribe en el worktree.
Línea de base: <scratchpad>/linea-base/ (<los archivos que sirven a este eje>).
Rúbricas, leelas enteras con Read: <…>. Ficha: <checkout>/.claude/skills/auditoria/plantillas/ficha.md
No repitas lo que corre el CI: leé .claude/skills/gates-ci/SKILL.md.
No reportes lo que la auditoría anterior ya descartó: docs/internal/auditoria-2026-10/README.md, sección «0.4 Qué NO hacer».
Devolvé fichas completas. En esta pasada, el estado es CONFIRMADO (lectura) o PLAUSIBLE.
```

## 4. Pasada 2 — reproducir lo grave

Por cada ficha CRÍTICA o ALTA, un `Agent(subagent_type="general-purpose", model="sonnet")`,
de a cuatro en paralelo como mucho. Cada uno recibe la ficha y:

- escribe la PoC en `$W/docs/internal/auditoria-AAAA-MM/poc/test_repro_<id>.py`. Como en
  octubre (`docs/internal/auditoria-2026-10/poc/README.md`), el test **afirma el defecto
  actual**: verde quiere decir que el bug existe;
- la copia a `$W/<app>/tests/`, la corre y borra la copia:
  `PYTEST_RUNNING=1 DJANGO_SYNCDB_PROJECT_APPS=True DJANGO_SECRET_KEY=test-key "$PY" "$W/manage.py" test <app>.tests.test_repro_<id>`;
- no toca código del producto;
- devuelve `CONFIRMADO con test (poc/<archivo>::<Clase>.<test>)` o `REFUTADO: <por qué>`.
  Lo que depende de MariaDB o del volumen queda `PLAUSIBLE`, con la medición que haría falta en
  el banco `scripts/perf_mysql/`.

## 5. Cruzar con la auditoría anterior

La sección «8. Refutado y descartado» de `docs/internal/auditoria-2026-10/README.md` se lee por
offset, porque el archivo es grande (`grep -n "^## 8" …`).

- Una ficha que reintroduce algo refutado ahí se descarta, citando la entrada.
- Una ficha que coincide con un hallazgo de octubre que sigue abierto lleva su ID en «Origen» y
  no se duplica.

## 6. Informe

En el mismo worktree, con rama nueva: `git -C "$W" switch -c docs/auditoria-AAAA-MM`.

```
docs/internal/auditoria-AAAA-MM/
  README.md
  hallazgos/   un archivo por eje: seguridad.md, errores.md, rendimiento.md, codigo-limpio.md, datos.md, front.md, tests.md
  poc/         las PoC de la pasada 2 + README.md con cómo correrlas (formato del de octubre)
```

`README.md`, con estas secciones en este orden:

1. **Resumen.** SHA auditado, alcance, fichas por severidad y por eje, y las tres a cinco que
   importan.
2. **Índice.** Tabla ID · título · severidad · estado · esfuerzo · ola · archivo.
3. **Plan por olas.** Lo CRÍTICO primero, agrupado por archivo para no pisarse. Horas por ola con
   S = 2, S-M = 4, M = 8, L = 20.
4. **Reglas propuestas.** Tabla tipo · destino · texto o chequeo · fichas que la originan.
   Agrupadas: una regla que evita cinco fichas vale más que cinco reglas.
5. **Descartados.** Lo refutado en la pasada 2 y lo que reintroducía §8 de octubre, con el motivo.
6. **Línea de base.** Resumen de `<scratchpad>/linea-base/`.

En `.gitattributes`, debajo de la línea de `auditoria-2026-10`, agregá
`docs/internal/auditoria-AAAA-MM/**/*.md text eol=lf`. Con finales de línea mezclados, un
resolvedor por unión duplicó el README entero de octubre (07-oct).

Entrega: un PR solo de documentación contra `development` (`--repo Mkdir-arg/Chaco-Back`), con su
entrada en `docs/internal/requerimientos.md`. Pasa por `/auditoria pr <N>` como cualquier PR.
**Nada se implementa sin aprobación.** Después del merge, `git worktree remove "$W"`.
