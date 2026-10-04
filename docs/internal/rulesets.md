# Protección de `development` y `main` (rulesets)

Hasta el 04-oct-2026 `CLAUDE.md` decía «Gates de CI… Bloquean el merge» y no era
cierto: `gh api repos/Mkdir-arg/Chaco-Back/rulesets` devolvía `[]` y
`branches/development/protection` devolvía `404`. Un PR en rojo se mergeaba con el
botón normal, y un `git push origin development` entraba sin disparar ningún
workflow de verificación —todos son `on: pull_request`— pero **sí** disparaba
`publish-main.yml`, que regenera `main` y es lo que después se espeja al GitLab de
ECOM. Medido sobre 90 días: **23 commits de código entraron sin PR** (RED-20).

Los dos rulesets que lo cierran están versionados acá:

- [`rulesets/ruleset-development.json`](rulesets/ruleset-development.json)
- [`rulesets/ruleset-main.json`](rulesets/ruleset-main.json)

**Los aplica el dueño del repo**, a mano, una sola vez. No hay workflow que los
cree: un automatismo con permiso para escribir rulesets puede borrarlos.

---

## 1. Aplicarlos

Desde la raíz del repo, con una cuenta con permiso de administración:

```bash
gh api repos/Mkdir-arg/Chaco-Back/rulesets -X POST \
  --input docs/internal/rulesets/ruleset-development.json

gh api repos/Mkdir-arg/Chaco-Back/rulesets -X POST \
  --input docs/internal/rulesets/ruleset-main.json
```

Verificación (tiene que listar los dos, en `active`):

```bash
gh api repos/Mkdir-arg/Chaco-Back/rulesets --jq '.[] | "\(.id)\t\(.name)\t\(.enforcement)"'
```

Y la prueba de que de verdad frenan:

1. `git push origin development` desde local → **rechazado** (`protected branch hook declined`).
2. Un PR con un test roto → el botón de merge queda deshabilitado hasta que los
   checks obligatorios estén en verde.
3. Un PR cuya rama quedó atrás de `development` → GitHub pide «Update branch»
   antes de habilitar el merge (es `strict_required_status_checks_policy`).

## 2. Modificarlos o darlos de baja

Un ruleset ya creado se actualiza por `id` (no se borra y se recrea: perdería el
historial de bypass):

```bash
ID=$(gh api repos/Mkdir-arg/Chaco-Back/rulesets --jq '.[] | select(.name=="development protegida") | .id')

gh api repos/Mkdir-arg/Chaco-Back/rulesets/$ID -X PUT \
  --input docs/internal/rulesets/ruleset-development.json
```

Para aflojarlo en una emergencia **sin borrarlo**, pasarlo a `evaluate` (registra
pero no bloquea) y volverlo a `active` apenas se resuelve:

```bash
gh api repos/Mkdir-arg/Chaco-Back/rulesets/$ID -X PUT -f enforcement=evaluate
gh api repos/Mkdir-arg/Chaco-Back/rulesets/$ID -X PUT -f enforcement=active
```

## 3. Qué dice cada uno y por qué

### `development protegida`

| Regla | Qué hace | Por qué |
|---|---|---|
| `deletion`, `non_fast_forward` | No se borra ni se reescribe la historia | `development` es la rama de trabajo y la base de todo PR |
| `pull_request` con `required_approving_review_count: 0` | Todo cambio entra por PR | **A propósito en 0:** todo el equipo y los agentes publican con la misma cuenta y GitHub no deja aprobar el propio PR; exigir 1 aprobación bloquearía todos los merges. La revisión independiente sigue siendo el «Aprobado @ SHA» del proceso, no el botón |
| `required_status_checks` con `strict` | Los nueve checks de abajo tienen que estar verdes y la rama al día | Sin `strict`, un PR verde contra una base vieja mergea igual |
| `bypass_actors: []` | Nadie pasa por arriba | Si hiciera falta, se hace explícito y se revisa |

Checks obligatorios y de dónde salen:

| Check | Workflow |
|---|---|
| `Django System Check`, `Migration Check`, `Tests & Coverage` | `pr-backend.yml` |
| `Query Budgets & Smoke Time`, `Ephemeral MySQL Redis Contract` | `pr-performance.yml` |
| `Pip Audit` | `pr-security.yml` |
| `Sin datos personales` | `pr-datos.yml` |
| `Ruff errores` | `pr-quality.yml` |
| `Validate inventory and authority` | `design-agent-contract.yml` |

No están `Ruff estilo`, `Bandit Security Scan` ni `Dependency Review`: los tres son
`continue-on-error` y un check no bloqueante en la lista de obligatorios siempre
reporta verde, o sea que no agrega nada.

**Regla para agregar un check a la lista:** un `context` solo puede ser obligatorio
si su job **siempre termina** en todo PR a `development`. Un workflow con `paths:`
en el trigger no corre cuando el PR no toca esas rutas, el check nunca reporta y el
PR queda esperando para siempre. Por eso `pr-quality.yml` y
`design-agent-contract.yml` no filtran por `paths` en el trigger: el filtro va
adentro del job (`dorny/paths-filter`), el job termina en `success` cuando no hay
nada que revisar, y recién ahí puede ser obligatorio. El test
`core/tests/test_gates_ci.py::RulesetsPropuestosTests` verifica las dos cosas sobre
el JSON de acá: que cada `context` exista como job y que su workflow no filtre.

### `main generada`

`main` no es una rama de trabajo: la escribe `publish-main.yml` en cada push a
`development` y de ahí sale el espejo al GitLab de ECOM y la imagen de PRD
(ver [`branching.md`](branching.md)). El ruleset prohíbe `deletion`,
`non_fast_forward` y `update` —o sea, **nadie la empuja**— con un único bypass: la
app de GitHub Actions (`actor_id: 15368`, el id de `/apps/github-actions`), que es
quien publica. Si alguna vez hay que tocar `main` a mano, el procedimiento es
corregir `development` y dejar que el workflow republique.

## 4. Mientras tanto

Hasta que los rulesets estén aplicados, `pr-backend.yml`, `pr-performance.yml` y
`pr-datos.yml` corren **también** en `push` a `development`, para que un push
directo deje al menos un check rojo visible antes del espejo a ECOM. Es una
barrera que avisa, no una que frena. Una vez aplicados los rulesets el push
directo ya no entra y esos disparadores quedan como defensa en profundidad.
