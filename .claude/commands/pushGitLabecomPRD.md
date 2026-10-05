---
description: Espejar a `main` del GitLab de ECOM — DESPLIEGA PRODUCCIÓN automáticamente. Exige el SHA ya verificado en testing, el release-gate en verde y una segunda confirmación escrita.
allowed-tools: Bash(git push:*), Bash(git ls-remote:*), Bash(git fetch:*), Bash(git log:*), Bash(git rev-parse:*), Bash(git remote:*), Bash(git clone:*), Bash(git commit-tree:*), Bash(git write-tree:*), Bash(git show:*), Bash(git diff:*), Bash(git merge-base:*), Bash(git rev-list:*), Bash(gh workflow run:*), Bash(gh run list:*), Bash(gh run view:*)
---

Sos el operador de la **segunda mitad** del espejo a ECOM. **Pushear `main` es desplegar en
producción**: el pipeline construye la imagen y ArgoCD la despliega **sin pase, sin
aprobación y sin ventana**, visible en 5 a 7 minutos. No hay QA intermedio.

Este comando **no se corre a continuación de `/pushGitLabecomTEST`**. Se corre cuando
alguien verificó testing. Si quien te lo pide acaba de espejar `test` en esta misma sesión,
decí que no y explicá por qué.

El procedimiento normativo es `docs/internal/espejo-ecom.md`; el mecanismo de ramas está en
`docs/internal/branching.md`.

## Entrada obligatoria

El **SHA verificado en testing** (el que informó `/pushGitLabecomTEST`). Si el usuario no te
lo da, pedíselo. No lo deduzcas de `git rev-parse main`: el release pudo avanzar desde
entonces, y lo que se lleva a producción es lo que se probó.

## Comprobaciones previas (todas, antes de tocar nada)

1. **Que sea lo que se probó.**
   - `git ls-remote --heads ecom` → SHA de `test` y de `main`.
   - Clon superficial de `ecom/test` y `git -C $tmp rev-parse HEAD^{tree}`.
   - `git rev-parse <sha>^{tree}`.
   - **Los dos árboles tienen que ser idénticos.** Si no, se probó otra cosa: PARÁ.
2. **Que el `release-gate` de ese SHA esté en verde.**
   `gh run list --repo Mkdir-arg/Chaco-Back --workflow=release-gate.yml --limit 10`: el
   título de cada corrida lleva el SHA (`Release gate <sha>`), así que confirmá que la
   verde es **la de este release** y no la de otro. Sin corrida para ese SHA, corré el gate
   (`gh workflow run release-gate.yml --repo Mkdir-arg/Chaco-Back --ref development -f sha=<sha>`)
   y esperá a que termine.
3. **Que alguien haya verificado testing.** Preguntá **qué** se probó, **quién** y **cuándo**.
   Si la respuesta es «no lo miró nadie», el procedimiento termina acá.
4. **Si el release trae migraciones:** decilo explícitamente, con cuáles, y recordá el
   runbook de rollback (Anexo D de `docs/internal/processes.md`) y el dump previo de ECOM.
5. `git ls-remote ecom main` vs. el SHA: si `ecom/main` está divergida (pasó con un hotfix
   aislado), se alinea con un commit de merge cuyo árbol es el nuestro
   (`git commit-tree <tree> -p <ecom/main> -p <sha>`), **nunca forzando**. Receta completa
   en `branching.md`.

## Confirmación (dos, no una)

Mostrá, en este orden:

- **«Vas a desplegar PRODUCCIÓN.** El push a `ecom/main` dispara el build y ArgoCD lo
  despliega automáticamente en 5 a 7 minutos. No hay vuelta atrás sin un rollback manual.»
- El SHA, el asunto del commit de release y los commits pendientes
  (`git log --oneline <sha-remoto-main>..<sha>`).
- El resultado de las cinco comprobaciones de arriba, una por una.
- Si hay migraciones, cuáles y si alguna no se puede revertir.

Después pedí la **segunda confirmación**: el usuario tiene que escribir exactamente
`PRODUCCION`. «sí», «dale» o «ok» **no alcanzan**: volvé a pedirlo.

## Push

`git push ecom <sha>:refs/heads/main` (normalmente avance directo; si está divergida, el
commit de alineación). Nunca `--force`.

Después:

- `git ls-remote ecom main` para verificar.
- Avisá que hay que mirar **Pipelines** del lado de ECOM y, pasados 5 a 7 minutos, que la
  pantalla de login de producción abra.
- Recordá que el rollback es apuntar a la imagen anterior (hoy solo hay `:latest`: ver la
  propuesta de tag inmutable en `docs/internal/propuesta-ecom-verify.md`) y que el runbook
  está en `processes.md`.

## Reglas

- Sin las cinco comprobaciones y sin la palabra `PRODUCCION`, no pushees.
- Nunca forzar, nunca tocar `origin`, nunca otra rama que `main` de ECOM.
- Si el push falla por red o timeout, avisá y **no reintentes a ciegas**: puede haber
  entrado igual. Verificá con `git ls-remote` antes de cualquier reintento.
- Si algo no cierra —un árbol que no coincide, un gate que no está, nadie que haya
  probado—, **frená y contalo**. Producción no se corrige con un segundo intento.
