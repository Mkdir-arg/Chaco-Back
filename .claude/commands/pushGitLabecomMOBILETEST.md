---
description: Espejar la app móvil/PWA (Chaco-mobile, rama `test` de GitHub) a la rama `test` del GitLab de ECOM (repo datanach-app) — despliega la PWA de testing. NO toca producción.
allowed-tools: Bash(git push:*), Bash(git ls-remote:*), Bash(git fetch:*), Bash(git log:*), Bash(git rev-parse:*), Bash(git remote:*), Bash(git clone:*), Bash(git commit-tree:*), Bash(git show:*), Bash(git diff:*), Bash(git merge-base:*), Bash(git rev-list:*), Bash(git cat-file:*)
---

Sos el operador de la **primera mitad** del espejo de la **app móvil/PWA** a ECOM: llevás la
rama `test` de Chaco-mobile (GitHub) a la rama `test` del GitLab de ECOM, que construye la
imagen de **testing** (PWA en `https://datanach-app.ecomdev.ar`). **Nunca tocás `main`.**
Producción es la segunda mitad y es otro comando, `/pushGitLabecomMOBILEPRD`, que se corre
en otra sesión después de que alguien haya probado la PWA de testing.

Es el gemelo de `/pushGitLabecomTEST` (el del back, RED-23). El procedimiento general y el
mecanismo de ramas están en `docs/internal/espejo-ecom.md` y `docs/internal/branching.md`;
si este archivo los contradice, mandan ellos.

## Contexto fijo (no negociable)

- **Repo fuente (`origin` del clon móvil):** `https://github.com/Mkdir-arg/Chaco-mobile.git`.
  La fuente es **`origin/test`** recién fetcheada, no un checkout local editado. Desde el
  22/10/2026 el flujo es PR → `test` de GitHub → `ecom/test`.
- **Remoto destino (`ecom`):**
  `https://git.ecom.com.ar/externos/relevamiento-becas-des-hum/datanach-app.git`
  (el nombre viejo, `relevamiento-becas-admin-app.git`, redirige con aviso: no se usa).
- **Clon de trabajo:** `../Chaco-mobile` (hermano de este repo). Se opera siempre con
  `git -C ../Chaco-mobile ...`.
- **Qué hace el pipeline de ECOM** (`.gitlab-ci.yml` de la app, idéntico en `test` y `main`
  al 22/10/2026): un job `build` que, para `test` **o** `main`, construye el `Dockerfile` y
  hace push de `<registry>/<namespace>/<proyecto>/<rama>:latest`. Cómo se despliega esa
  imagen (ArgoCD u otro) **no consta en el repo: no verificado**. Se asume que `test`
  despliega testing y `main` producción.
- **Vía HTTPS, NO SSH**, con PAT por Git Credential Manager. Nunca embebas el token.
- **Solo la rama `test`.** Ni `main`, ni otras ramas, ni tags.
- **NUNCA tocar `origin`** (GitHub). Solo se pushea al remoto `ecom` del clon móvil.
- **NUNCA forzar.** Ni `--force`, ni `--force-with-lease`, ni borrar y recrear.

## Pasos

1. **Clon y remotos.**
   - Si no existe `../Chaco-mobile/.git`: `git clone https://github.com/Mkdir-arg/Chaco-mobile.git ../Chaco-mobile`.
   - `git -C ../Chaco-mobile fetch origin`.
   - `git -C ../Chaco-mobile remote get-url ecom`: si no existe, agregarlo con la URL de
     arriba; si existe con otra (la vieja), `git -C ../Chaco-mobile remote set-url ecom <url-nueva>`.

2. **Fuente y destino.**
   - **Fijá los SHAs** (después del único `fetch` de la corrida; no se vuelve a hacer otro
     hasta el push): `$src = git -C ../Chaco-mobile rev-parse origin/test` y `$ecomTest` =
     SHA de `git -C ../Chaco-mobile ls-remote ecom refs/heads/test`. Mostralos. De acá en
     adelante todo (comprobación, confirmación, push) usa **estos SHAs, no las refs**.
   - Si son **iguales**: informá «`ecom/test` ya está al día» y **terminá sin pushear**.

3. **ANTES DE PISAR `test`: revisá si tiene cambios de ellos.** ECOM edita `.gitlab-ci.yml`
   en esa rama y su automatización (`argocd`) también commitea ahí. Si espejás sin mirar,
   les revertís el arreglo. El commit remoto puede no estar en nuestro clon: probá
   `git -C ../Chaco-mobile merge-base --is-ancestor <sha-remoto> origin/test`.
   - **Da OK (exit 0):** el remoto es ancestro de la fuente → **avance directo**, nada de
     ellos que perder. Seguí al paso 4.
   - **No da OK o el objeto no existe localmente:** clon superficial para ver sus commits
     (el `fetch` desde ECOM puede cortar con HTTP 500):

     ```powershell
     $tmp = "<scratchpad>\ecom-app-test"
     git clone --depth=5 --branch test --quiet https://git.ecom.com.ar/externos/relevamiento-becas-des-hum/datanach-app.git $tmp
     git -C $tmp log --format='%h %an | %s'
     git -C $tmp diff HEAD~1 HEAD
     ```

     - Si hay commits de ellos con cambios que **no tenemos**, **PARÁ**: hay que traerlos
       primero a la rama `test` de GitHub (PR), y recién entonces espejar. Si tocaron
       `.gitlab-ci.yml`, nuestra copia tiene que quedar byte a byte igual (comparar
       `git rev-parse <commit>:.gitlab-ci.yml` en los dos lados).
     - Si solo difiere por código nuestro más viejo, seguí con el commit de alineación
       (paso 5b).

4. **Confirmación.** Mostrale al usuario, antes de pushear:
   - «Vas a espejar la app (`Chaco-mobile` `test` `<sha>`) a `ecom/test`: construye la
     imagen de **testing**, no producción.»
   - Los commits pendientes: `git -C ../Chaco-mobile log --oneline <sha-remoto>..origin/test`.
   - Si el paso 3 encontró cambios de ellos, **decilo antes que nada**.

   Sin un «sí» explícito no hacés nada.

5. **Push sin forzar.** Comando limpio, sin token en la URL.
   - **Antes de cualquier push (5a o 5b)**, releé
     `git -C ../Chaco-mobile ls-remote ecom refs/heads/test`. Si el SHA **no coincide** con
     `$ecomTest`, **PARÁ y no pushees** (alguien pusheó en el medio) y volvé al paso 2.
   - **5a. Avance directo** (el remoto es ancestro de la fuente):
     `git -C ../Chaco-mobile push ecom ${src}:refs/heads/test`
   - **5b. Commit de alineación** (el remoto tiene commits solo nuestros que divergen):

     ```powershell
     $tree  = git -C ../Chaco-mobile rev-parse ${src}^{tree}
     $merge = git -C ../Chaco-mobile commit-tree $tree -p $src -p $ecomTest -m "merge: alinear test con origin/test $src"
     git -C ../Chaco-mobile rev-parse "${merge}^{tree}"   # igual a $tree ANTES de pushear
     git -C ../Chaco-mobile push ecom ${merge}:refs/heads/test
     ```

     Si `$ecomTest` no está en el clon, hacer lo mismo en el clon superficial del paso 3
     (`$tmp`), trayendo la fuente por ruta absoluta, sin red:

     ```powershell
     git -C $tmp fetch <ruta absoluta de ../Chaco-mobile> $src
     $tree  = git -C $tmp rev-parse ${src}^{tree}
     $merge = git -C $tmp commit-tree $tree -p $src -p $ecomTest -m "merge: alinear test con origin/test $src"
     git -C $tmp rev-parse "${merge}^{tree}"   # igual a $tree ANTES de pushear
     git -C $tmp push origin ${merge}:refs/heads/test   # en $tmp, `origin` ES ECOM
     ```

   - Si el clasificador bloquea el push en Bash, correlo por PowerShell o que lo corra el PM.

6. **Verificá e informá.**
   - `git -C ../Chaco-mobile ls-remote ecom refs/heads/test` debe coincidir con la fuente
     (o con el commit de alineación, cuyo árbol es el de la fuente).
   - El deploy no es instantáneo: hay que mirar **Pipelines** en el GitLab de ECOM; el push
     solo deja el código.
   - **Decí textual el SHA espejado y su árbol (`^{tree}`)**: son el insumo de
     `/pushGitLabecomMOBILEPRD`.
   - Qué conviene probar en `https://datanach-app.ecomdev.ar` antes de pensar en producción.

## Reglas

- Si el usuario no confirma, no hacés nada.
- Nunca `main`, nunca `origin`, nunca forzar (ni `--force-with-lease`), nunca embeber el PAT.
- Sin tags; solo la rama `test`.
- Si el push falla por red o timeout, avisá y **no reintentes a ciegas**: puede haber
  entrado igual; verificá con `ls-remote` antes de cualquier reintento.
- **No encadenes con producción.** Terminás acá, aunque te lo pidan en la misma sesión.
