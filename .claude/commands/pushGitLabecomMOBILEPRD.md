---
description: Espejar la app móvil/PWA a la rama `main` del GitLab de ECOM (repo datanach-app) — PRODUCCIÓN. Exige que el árbol sea idéntico al ya probado en `ecom/test` y una segunda confirmación escrita.
allowed-tools: Bash(git push:*), Bash(git ls-remote:*), Bash(git fetch:*), Bash(git log:*), Bash(git rev-parse:*), Bash(git remote:*), Bash(git clone:*), Bash(git commit-tree:*), Bash(git show:*), Bash(git diff:*), Bash(git merge-base:*), Bash(git rev-list:*), Bash(git cat-file:*)
---

Sos el operador de la **segunda mitad** del espejo de la **app móvil/PWA** a ECOM. La rama
`main` de ECOM se trata como **PRODUCCIÓN**: el pipeline construye la imagen
`<rama>:latest` para `main` igual que para `test`, y no hay QA intermedio. Qué la despliega
y cuándo **no consta en el repo (no verificado)**; por prudencia se asume que llega a
producción sola, sin pase ni ventana.

Es el gemelo de `/pushGitLabecomPRD` (el del back). **No se corre a continuación de
`/pushGitLabecomMOBILETEST`**: se corre cuando alguien probó la PWA de testing
(`https://datanach-app.ecomdev.ar`). Si quien te lo pide acaba de espejar `test` en esta
misma sesión, decí que no y explicá por qué.

Procedimiento general: `docs/internal/espejo-ecom.md`; ramas: `docs/internal/branching.md`.

## Contexto fijo (no negociable)

- **Fuente:** `origin/main` de `Mkdir-arg/Chaco-mobile` (GitHub), en el clon `../Chaco-mobile`
  (se opera con `git -C ../Chaco-mobile ...`). `main` de GitHub recibe lo de `test` por PR.
- **Remoto destino (`ecom`):**
  `https://git.ecom.com.ar/externos/relevamiento-becas-des-hum/datanach-app.git`
  (si el remoto tiene la URL vieja `relevamiento-becas-admin-app.git`:
  `git -C ../Chaco-mobile remote set-url ecom <url-nueva>`).
- **Vía HTTPS**, PAT por Git Credential Manager; nunca embeber el token.
- **Solo `main` de ECOM.** Ni `test`, ni otras ramas, ni tags. Nunca tocar `origin`.
- **NUNCA forzar** (ni `--force`, ni `--force-with-lease`, ni borrar y recrear).

## Comprobaciones previas (todas, antes de tocar nada)

1. `git -C ../Chaco-mobile fetch origin` y `git -C ../Chaco-mobile ls-remote --heads ecom`
   (SHAs de `test` y `main` de ECOM).
2. **Que sea lo que se probó.** Árbol de `ecom/test` (con clon superficial si el objeto no
   está en el clon: `git clone --depth=5 --branch test <url-ecom> $tmp` y
   `git -C $tmp rev-parse HEAD^{tree}`) contra `git -C ../Chaco-mobile rev-parse origin/main^{tree}`.
   **Tienen que ser idénticos.**
   - Si **no** lo son: **FRENÁ**. Explicá que primero hay que pasar `test` → `main` en
     GitHub (PR) y que testing tenga ese mismo árbol (`/pushGitLabecomMOBILETEST`, y que
     alguien lo pruebe). No se lleva a producción algo distinto de lo probado.
3. **Que alguien haya verificado la PWA de testing.** Preguntá **qué** se probó, **quién** y
   **cuándo**. Si la respuesta es «no lo miró nadie», el procedimiento termina acá.
4. **Commits de ECOM en `ecom/main` que no tenemos** (ellos editan `.gitlab-ci.yml` y
   `argocd` commitea ahí). Con `merge-base --is-ancestor <ecom/main> origin/main`:
   - OK → avance directo.
   - No → clon superficial (`git clone --depth=5 --branch main`), `log` y `diff` de lo suyo.
     Si hay cambios de ellos que no tenemos, **PARÁ** (traerlos primero a GitHub). Si
     tocaron `.gitlab-ci.yml`, nuestra copia queda byte a byte igual.
     Si solo diverge por código nuestro, commit de alineación (ver Push).
5. **Estado de partida:** SHA de `origin/main`, SHA de `ecom/main`, y si son iguales
   («al día», terminá sin pushear).

## Confirmación (dos, no una)

Mostrá, en este orden:

- **«Vas a desplegar PRODUCCIÓN de la app.** El push a `ecom/main` dispara el build de la
  imagen de `main`, que se trata como producción. No hay vuelta atrás sin un rollback
  manual.»
- El SHA de `origin/main`, su árbol, el árbol de `ecom/test` y su coincidencia, y los
  commits pendientes (`git -C ../Chaco-mobile log --oneline <sha-ecom-main>..origin/main`).
- El resultado de las cinco comprobaciones, una por una.
- Si hay cambios de contrato con el back (tests de contrato de `programas/tests/`), decilo:
  la app y el back no se despliegan juntos.

Después pedí la **segunda confirmación**: el usuario tiene que escribir exactamente
`PRODUCCION`. «sí», «dale» o «ok» **no alcanzan**: volvé a pedirlo.

## Push

Sin forzar, comando limpio:

- **Avance directo:** `git -C ../Chaco-mobile push ecom origin/main:refs/heads/main`
- **Alineación** (si `ecom/main` diverge por código nuestro):
  `$merge = git -C ../Chaco-mobile commit-tree <tree-de-origin/main> -p origin/main -p <sha-ecom-main> -m "merge: alinear main con origin/main <sha>"`,
  verificar que `${merge}^{tree}` sea el árbol de `origin/main` **antes** de pushear y
  después `git -C ../Chaco-mobile push ecom ${merge}:refs/heads/main`.

Si el clasificador bloquea el push en Bash, por PowerShell o que lo corra el PM.

Después:

- `git -C ../Chaco-mobile ls-remote ecom refs/heads/main` para verificar.
- Avisá que hay que mirar **Pipelines** del lado de ECOM y, cuando termine, que la app de
  producción abra y el login funcione.
- El rollback es apuntar a la imagen anterior; hoy solo existe `:latest` por rama.

## Reglas

- Sin las comprobaciones y sin la palabra `PRODUCCION`, no pushees.
- **No se encadena con `/pushGitLabecomMOBILETEST` en la misma corrida**, aunque lo pidan.
- Nunca forzar (ni `--force-with-lease`), nunca tocar `origin`, nunca otra rama que `main`
  de ECOM, sin tags, nunca embeber el PAT.
- Si el push falla por red o timeout, avisá y **no reintentes a ciegas**: puede haber
  entrado igual. Verificá con `ls-remote` antes de cualquier reintento.
- Si algo no cierra —un árbol que no coincide, nadie que haya probado—, **frená y contalo**.
