---
description: Espejar el release al GitLab de ECOM, solo la rama `test` (despliega testing). Corre el release-gate antes y NO toca producción.
allowed-tools: Bash(git push:*), Bash(git ls-remote:*), Bash(git fetch:*), Bash(git log:*), Bash(git rev-parse:*), Bash(git remote:*), Bash(git clone:*), Bash(git commit-tree:*), Bash(git show:*), Bash(git diff:*), Bash(git merge-base:*), Bash(git rev-list:*), Bash(gh workflow run:*), Bash(gh run list:*), Bash(gh run view:*)
---

Sos el operador de la **primera mitad** del espejo a ECOM: llevás el release a la rama
`test`, que despliega **testing** (`https://datanach.ecomdev.ar/`). **Nunca tocás `main`.**
Producción es la segunda mitad y es otro comando, `/pushGitLabecomPRD`, que se corre en
otra sesión después de que alguien haya probado testing.

El procedimiento normativo es `docs/internal/espejo-ecom.md`; el mecanismo de ramas y las
fallas conocidas del push están en `docs/internal/branching.md`. Si este archivo y esos
documentos se contradicen, mandan ellos.

## Contexto fijo (no negociable)

- **Remoto destino:** `ecom` → `https://git.ecom.com.ar/externos/relevamiento-becas-des-hum/datanach.git`
- **Vía HTTPS, NO SSH**, con PAT por Git Credential Manager. Nunca embebas el token.
- **Solo la rama `test`.** Ni `main`, ni otras ramas, ni tags.
- **NUNCA tocar `origin`** (GitHub, `Mkdir-arg/Chaco-Back`).
- **NUNCA forzar.** Ni `--force`, ni `--force-with-lease`, ni borrar y recrear.

## Pasos

1. **Release local al día.**
   - `git remote get-url ecom` (si no existe, agregalo con la URL de arriba).
   - `git fetch origin main:main` — el `main` local suele estar atrasado respecto del
     release publicado, y espejar un snapshot viejo es el error más fácil de cometer.
   - `git rev-parse main` → **ese SHA es el release**. Mostralo.

2. **Correr el `release-gate` para ese SHA y esperar a que termine.**

   ```powershell
   gh workflow run release-gate.yml --repo Mkdir-arg/Chaco-Back --ref development -f sha=<sha>
   gh run list --repo Mkdir-arg/Chaco-Back --workflow=release-gate.yml --limit 5
   ```

   El título de la corrida lleva el SHA (`Release gate <sha>`): verificá que estás mirando
   **la de este release** y no otra. Verifica: CI verde del PR que lo originó —con todos
   los checks obligatorios presentes, no solo «ninguno rojo»—, suite completa, migraciones
   sobre MariaDB, la imagen construida con su manifest de estáticos y un smoke HTTP.
   **Si da rojo, no se espeja.** Mostrá qué job falló (`gh run view --log-failed`).

3. **ANTES DE PISAR `test`: revisá si tiene cambios de ellos.**
   ECOM edita `.gitlab-ci.yml` en esa rama y su automatización (`argocd`) también commitea
   ahí. Si espejás sin mirar, les revertís el arreglo. Su commit no se puede traer con
   `git fetch ecom test` (el servidor corta con HTTP 500): se usa un clon superficial.

   ```powershell
   $tmp = "<scratchpad>\ecom-test"
   git clone --depth=5 --branch test --quiet <url-ecom> $tmp
   git -C $tmp log --format='%h %an | %s'
   git -C $tmp diff HEAD~1 HEAD
   ```

   - Si hay commits de ellos con cambios que **no tenemos**, PARÁ: hay que traerlos a
     `development` primero, publicar release y recién entonces espejar. Si tocaron
     `.gitlab-ci.yml`, nuestra copia tiene que quedar **byte a byte igual**: compará blobs
     con `git rev-parse HEAD:.gitlab-ci.yml` en los dos lados.
   - Si lo único que difiere es código nuestro más viejo, seguí.

4. **Confirmación.** Mostrale al usuario, antes de pushear:
   - «Vas a espejar el release `<sha>` a `ecom/test`: despliega **testing**, no producción.»
   - El resultado del `release-gate` y el link de la corrida.
   - Los commits pendientes (`git log --oneline <sha-remoto>..main`).
   - Si el paso 3 encontró cambios de ellos, **decilo antes que nada**.

   Sin un «sí» explícito no hacés nada.

5. **Actualizá `test` sin forzar.** `test` suele estar divergida, así que se crea un commit
   de merge cuyo árbol es idéntico al de `main` y que tiene su commit como segundo padre:

   ```powershell
   git -C $tmp fetch <ruta-del-repo> main            # por filesystem, sin red
   $tree  = git -C $tmp rev-parse FETCH_HEAD^{tree}
   $merge = git -C $tmp commit-tree $tree -p FETCH_HEAD -p HEAD -m "merge: alinear test con el release <sha>"
   git -C $tmp push origin ${merge}:refs/heads/test
   ```

   Verificá que el árbol del commit nuevo sea igual al de `main` **antes** de pushear.
   Si `test` no estuviera divergida, alcanza `git push ecom main:test`.

6. **Cerrá informando:**
   - `git ls-remote ecom test` con el SHA que quedó.
   - Que el deploy de testing tarda 5 a 7 minutos y que hay que mirar **Pipelines** en el
     GitLab de ECOM: el push solo deja el código.
   - **El SHA del release espejado**, textual: es el insumo de `/pushGitLabecomPRD`.
   - Qué conviene probar en testing antes de pensar en producción.

## Reglas

- Si el usuario no confirma, no hacés nada.
- Nunca `main`, nunca `origin`, nunca forzar, nunca embeber el PAT.
- Si el push falla por red o timeout, avisá y **no reintentes a ciegas**. El HTTP 500 en el
  push es tamaño de paquete, no red: se resuelve en tandas (`branching.md`).
- **No encadenes con producción.** Terminás acá, aunque te lo pidan en la misma sesión: la
  verificación en testing es de una persona y lleva su tiempo.
