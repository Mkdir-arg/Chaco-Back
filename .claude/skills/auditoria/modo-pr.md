# Modo B — `/auditoria pr <N>`

Corre antes de mergear **cualquier** PR a `development` y reemplaza al revisor independiente.
Los comandos son de Git Bash, desde cualquier checkout del repo. `<scratchpad>` es el directorio
temporal de la sesión, escrito con barras `/`.

## 1. Resolver el PR

```bash
gh pr view <N> --repo Mkdir-arg/Chaco-Back --json number,state,baseRefName,headRefOid,headRefName,files
git fetch origin development "+pull/<N>/head:refs/remotes/origin/pr/<N>"
HEAD_SHA=<headRefOid>
MB=$(git merge-base origin/development "$HEAD_SHA")
RAIZ=$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")  # checkout principal: venv y worktrees
```

`state` tiene que ser `OPEN` y `baseRefName`, `development`. Si no, no se audita: decilo y
terminá.

## 2. ¿Ya hay un veredicto?

Último marcador de la discusión:

```bash
gh pr view <N> --repo Mkdir-arg/Chaco-Back --json comments --jq '.comments[].body' \
  | grep -oE 'auditoria-chaco veredicto=(APPROVE|CHANGES_NEEDED) sha=[0-9a-f]{40}' | tail -1
```

| Último marcador | Qué hacer |
|---|---|
| ninguno | auditar (paso 4) |
| cualquiera, con `sha` = `HEAD_SHA` | este head ya está auditado: informalo y terminá. Se vuelve a auditar solo si lo piden |
| `APPROVE` con otro `sha` (`OLD`) | intentar el re-sello (paso 3) |
| `CHANGES_NEEDED` con otro `sha` | auditar (paso 4); el prompt lleva los hallazgos de ese comentario para verificar primero si se resolvieron |

## 3. Re-sello, sin agentes

El juez suele traer `development` al PR o renumerar el Cambio antes de mergear: el SHA cambia,
pero el código propio del PR no. Se compara el diff propio (contra su merge-base) en los dos SHAs:

```bash
git cat-file -e "$OLD^{commit}" 2>/dev/null || git fetch origin "$OLD"
MB_OLD=$(git merge-base origin/development "$OLD")
EXCL=':(exclude)docs/internal/requerimientos.md'
P_OLD=$(git diff "$MB_OLD" "$OLD" -- . "$EXCL" | git patch-id --stable | cut -d' ' -f1)
P_NEW=$(git diff "$MB" "$HEAD_SHA" -- . "$EXCL" | git patch-id --stable | cut -d' ' -f1)
R_OLD=$(git diff "$MB_OLD" "$OLD" -- docs/internal/requerimientos.md | git patch-id --stable | cut -d' ' -f1)
R_NEW=$(git diff "$MB" "$HEAD_SHA" -- docs/internal/requerimientos.md | git patch-id --stable | cut -d' ' -f1)
echo "P_OLD=$P_OLD P_NEW=$P_NEW R_OLD=$R_OLD R_NEW=$R_NEW"
```

- `P_OLD` y `P_NEW` **no vacíos e iguales**: el cambio vino solo de la base. Publicá la variante
  «Re-sello» de `plantillas/comentario-pr.md` (paso 7) y terminá. Si además `R_OLD` ≠ `R_NEW`, usá
  la línea «salvo `docs/internal/requerimientos.md`».
- Distintos, alguno vacío, u `OLD` imposible de traer: auditar (paso 4).

## 4. Preparar el material

```bash
git diff --stat "$MB" "$HEAD_SHA"
git diff "$MB" "$HEAD_SHA" > <scratchpad>/pr-<N>.diff
git diff --name-only "$MB" "$HEAD_SHA" > <scratchpad>/pr-<N>-archivos.txt
WT="$RAIZ/.claude/worktrees/pr-<N>"
git worktree add --detach "$WT" "$HEAD_SHA"
```

En el worktree del head los auditores leen los archivos enteros con las líneas del PR y, ante una
duda concreta, corren un test focalizado con `"$RAIZ/.venv312/Scripts/python.exe"` (Python 3.12 +
Django 5.2, igual al CI). Va en `.claude/worktrees/` (ignorado por git) y no en el scratchpad: en
Windows la ruta del scratchpad es tan larga que el checkout falla con `Filename too long`.

## 5. Lanzar los dos auditores, en un solo mensaje

Dos `Agent(subagent_type="chaco-auditor")` en **el mismo mensaje**, para que corran en paralelo.
El modelo lo fija el agente. Las rúbricas se leen del checkout del juez (`<checkout>` =
`git rev-parse --show-toplevel`), no del PR: un PR que toca las rúbricas no se audita con su
propia versión. Prompt:

```
Modo: pr. PR #<N> de Mkdir-arg/Chaco-Back, head <HEAD_SHA>, base development (merge-base <MB>).
Diff: <scratchpad>/pr-<N>.diff · Archivos: <scratchpad>/pr-<N>-archivos.txt
Código del head: worktree <WT> (citá las líneas de ahí).
Rúbricas, leelas enteras con Read: <ver abajo>.
No repitas lo que corre el CI: leé .claude/skills/gates-ci/SKILL.md.
[Solo si hubo CHANGES_NEEDED: Hallazgos de la ronda anterior, verificá primero si quedaron resueltos: …]
Devolvé los hallazgos con el formato de tu agente; si no hay, «Sin hallazgos» y qué revisaste.
```

| Auditor | Rúbricas |
|---|---|
| 1 · corrección, seguridad, datos y contratos | `<checkout>/.claude/skills/auditoria/rubricas/correccion-seguridad.md` |
| 2 · código limpio y rendimiento | `<checkout>/.claude/skills/auditoria/rubricas/codigo-limpio.md` y `<checkout>/.claude/skills/auditoria/rubricas/rendimiento.md` |

## 6. Consolidar y decidir

- **Deduplicar.** El mismo problema visto por los dos cuenta una vez y pesa más.
- **Verificar.** Abrí la línea citada de cada `[BLOCKER]` y `[MAJOR]`. Lo que no se sostiene se
  descarta, y el motivo va en tu respuesta al usuario, no en el comentario.
- **Desacuerdos.** Si los dos difieren en la severidad, decidís vos con la tabla «Severidad» de la
  rúbrica.
- **Veredicto.** APPROVE si no hay `[BLOCKER]` ni `[MAJOR]`. Si hay, CHANGES NEEDED.
- **Ciclo acelerado.** Un APPROVE con solo `[MINOR]` se mergea, y los MINOR van al próximo PR del
  carril. Excepción: un MINOR que sea riesgo latente de datos, de seguridad o de arranque en PRD
  sube a `[MAJOR]` y abre una ronda.
- **Regla propuesta.** Va solo si un hallazgo repite un patrón ya registrado. Buscalo con
  `scripts/requerimientos.py --buscar` y en la auditoría anterior.

## 7. Publicar

Volvé a leer `headRefOid`: si cambió mientras auditabas, volvé al paso 2. Escribí el comentario en
`<scratchpad>/auditoria-pr-<N>.md` con `plantillas/comentario-pr.md` y publicalo:

```bash
gh pr comment <N> --repo Mkdir-arg/Chaco-Back --body-file <scratchpad>/auditoria-pr-<N>.md
gh pr view <N> --repo Mkdir-arg/Chaco-Back --json comments --jq '.comments[-1].body' | tail -1
```

La segunda línea confirma que el marcador quedó publicado.

## 8. Merge, si corresponde

Solo si lo decide el juez o el usuario, y con el CI del head en verde
(`gh pr checks <N> --repo Mkdir-arg/Chaco-Back`). La skill `gates-ci` dice qué no bloquea el merge
pero igual frena `Publish main`.

```bash
gh pr merge <N> --repo Mkdir-arg/Chaco-Back --merge --match-head-commit "$HEAD_SHA"
```

El hook `guardia_merge` lo verifica. Si frena, leé el motivo: falta auditar o re-sellar el head
actual. No hay bypass.

## 9. Limpiar

```bash
git worktree remove --force "$WT"
git update-ref -d refs/remotes/origin/pr/<N>
```
