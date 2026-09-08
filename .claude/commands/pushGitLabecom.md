---
description: Espejar el release al GitLab de ECOM — primero test (despliega testing), después main (DESPLIEGA PRODUCCIÓN, automático). Muestra qué se envía y pide confirmación.
allowed-tools: Bash(git push:*), Bash(git ls-remote:*), Bash(git fetch:*), Bash(git log:*), Bash(git rev-parse:*), Bash(git remote:*), Bash(git clone:*), Bash(git commit-tree:*), Bash(git show:*), Bash(git diff:*), Bash(git merge-base:*), Bash(git rev-list:*)
---

Sos el operador del **espejo del código al GitLab de ECOM**. Enviás el release a **dos
ramas, en este orden**: primero `test` —que despliega el entorno de testing— y después
`main`, que **despliega producción**. **Mostrás qué se va a enviar y pedís confirmación
explícita** antes de pushear.

> **Pushear `main` es desplegar en producción.** Confirmado por DevOps de ECOM el
> 26/08/2026: los dos entornos tienen el mismo CI/CD y la imagen nueva de `main`
> impacta **automáticamente**, sin pase ni aprobación, y se ve en 5 a 7 minutos. No
> hay QA intermedio. Por eso el orden importa: `test` primero, se verifica ahí, y
> recién después `main`.

## Contexto fijo (no negociable)

- **Remoto destino:** `ecom` →
  `https://git.ecom.com.ar/externos/relevamiento-becas-des-hum/datanach.git`
- **Vía HTTPS, NO SSH.** El SSH interno no es alcanzable desde afuera y la VPN de icore
  no enruta la red de ECOM; el HTTPS (443) sí está expuesto, así que se pushea sin VPN.
- **Solo `test` y `main`.** Nunca otras ramas ni tags.
- **NUNCA tocar `origin`** (GitHub, `Mkdir-arg/Chaco-Back`). Solo `ecom`.
- **NUNCA forzar.** Ni `--force` ni `--force-with-lease` ni borrar y recrear una rama.
  Hay una técnica sin reescritura para el caso de ramas divergidas (paso 4).
- **Auth:** HTTPS con PAT (scope `write_repository`) vía Git Credential Manager. Nunca
  embebas el token en el comando ni en la URL.

## Qué pasa del otro lado

Cada push dispara el pipeline de ECOM, que construye la imagen del `Dockerfile` de la
raíz y la publica como `…/datanach/<rama>:latest`. **ArgoCD** despliega esas imágenes:
`test` → `https://datanach.ecomdev.ar/` (testing), `main` → **producción**, ambos
automáticos y con 5 a 7 minutos de demora. El pipeline vive en
`.gitlab-ci.yml`, que **viaja en nuestro release**: sin ese archivo GitLab no crea
pipeline y la rama se actualiza sin construir nada, en silencio.

## Pasos

1. **Remoto y release local al día.**
   - `git remote get-url ecom` (si no existe, agregalo con la URL de arriba).
   - `git fetch origin main:main` — el `main` local suele estar atrasado respecto del
     release publicado, y espejar un snapshot viejo es el error más fácil de cometer.
   - `git rev-parse main` es lo que va a quedar en las dos ramas.

2. **Estado remoto de las dos ramas.**
   `git ls-remote --heads ecom` → SHAs de `test` y `main`.
   Si las dos ya están en el SHA local, informá que está todo al día y terminá.

3. **ANTES DE PISAR `test`: revisá si tiene cambios de ellos.**
   Es el chequeo más importante del comando. ECOM edita `.gitlab-ci.yml` en esa rama
   —ya lo hicieron para arreglar el build— y su automatización (`argocd`) también
   commitea ahí. Si espejás sin mirar, **les revertís el arreglo**.

   Su commit no se puede traer con `git fetch ecom test`: el servidor corta con
   **HTTP 500**. Se usa un clon superficial:

   ```powershell
   $tmp = "<scratchpad>\ecom-test"
   git clone --depth=5 --branch test --quiet <url-ecom> $tmp
   git -C $tmp log --format='%h %an | %s'      # ¿hay commits que no sean nuestros?
   git -C $tmp diff HEAD~1 HEAD                # qué cambiaron
   ```

   - Si hay commits de ellos con cambios que **no tenemos**, PARÁ. Hay que traerlos a
     `development` primero (commit propio), publicar release y recién entonces espejar.
     Si tocaron `.gitlab-ci.yml`, nuestra copia tiene que quedar **byte a byte igual**:
     compará blobs con `git rev-parse HEAD:.gitlab-ci.yml` en los dos lados.
   - Si lo único que difiere es código nuestro más viejo, seguí.

4. **Actualizá `test` sin forzar.**
   `test` está divergida (tiene commits de ellos), así que un push normal se rechaza.
   En vez de forzar, se crea un commit de merge cuyo **árbol es idéntico al de nuestro
   `main`** y que tiene su commit como segundo padre: eso lo vuelve un avance directo.
   Se opera en el clon superficial para no ensuciar el repo del proyecto:

   ```powershell
   git -C $tmp fetch <ruta-del-repo> main            # por filesystem, sin red
   $tree  = git -C $tmp rev-parse FETCH_HEAD^{tree}
   $merge = git -C $tmp commit-tree $tree -p FETCH_HEAD -p HEAD -m "merge: alinear test con el release <sha>"
   git -C $tmp push origin ${merge}:refs/heads/test
   ```

   Verificá que el árbol del commit nuevo sea igual al de `main` antes de pushear, y
   después que `git ls-remote ecom test` devuelva ese commit.

   > Si `test` **no** estuviera divergida, alcanza `git push ecom main:test`.

5. **Actualizá `main`.**
   `git push ecom main` — normalmente es avance directo.

6. **Verificá las dos** con `git ls-remote --heads ecom` y avisale al usuario que mire
   **Pipelines** en el GitLab de ECOM: el push solo deja el código, el despliegue
   depende de que el build termine bien.

## Confirmación

Antes de cualquier push, mostrale al usuario:

- **"Vas a espejar el release al GitLab de ECOM: primero `test` (despliega testing) y
  después `main` (PRODUCCIÓN — el deploy es automático y tarda 5 a 7 minutos)."**
- Los **commits pendientes** de cada rama (`git log --oneline <sha-remoto>..main`).
- El SHA local de `main` que va a quedar en las dos.
- Si el paso 3 encontró cambios de ellos, **decilo antes que nada** y esperá la
  decisión: sin resolver eso, el espejo les revierte trabajo.

No pushees sin un "sí" explícito.

## Fallas conocidas

- **HTTP 500 en el push** (`RPC failed; send-pack: unexpected disconnect`): es el
  tamaño del paquete, no la red ni el PAT. Cada commit de `main` es un snapshot
  completo generado con `rsync --delete`, así que si se acumularon varias releases el
  pack se va de rango. Se resuelve **en tandas**, de lo más viejo a lo más nuevo:
  `git push ecom <sha-intermedio>:refs/heads/main`, verificando después de cada una.
  Todas son avances directos y el resultado final es idéntico. Espejar seguido lo evita.
- **HTTP 500 en `git fetch ecom test`**: mismo origen. Usá el clon superficial.
- **Push bloqueado por el clasificador**: pasa con `--force`, que acá no se usa. Si
  bloquea un push normal, el usuario tiene que habilitarlo con `/permissions`.
- **La rama se actualiza y no se construye nada**: falta `.gitlab-ci.yml` en el árbol
  publicado. El guard de `publish-main.yml` ya lo exige, pero si aparece, revisá eso.

## Reglas

- Si el usuario **no confirma**, no hacés nada.
- Nunca forzar, nunca tocar `origin`, nunca otra rama que `test` o `main`.
- Nunca embebas el PAT; dejá que GCM maneje la credencial.
- Si el push falla por red o timeout, avisá y **no reintentes a ciegas**.
- Recordale rotar el PAT si en algún momento lo compartió en texto.
- El detalle del mecanismo del otro lado está en `docs/internal/branching.md`.
