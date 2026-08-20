---
description: Espejar la rama main de la app móvil (Chaco-mobile, GitHub) al GitLab de ECOM (repo relevamiento-becas-admin-app) — clona/actualiza el repo móvil, muestra los commits pendientes, pide confirmación y hace git push ecom main
allowed-tools: Bash(git clone:*), Bash(git push:*), Bash(git ls-remote:*), Bash(git fetch:*), Bash(git log:*), Bash(git rev-parse:*), Bash(git remote:*)
---

Sos el operador del **espejo de la app móvil al GitLab de ECOM**. La app de territoriales
vive en **su propio repo de GitHub** (`Mkdir-arg/Chaco-mobile`), separado de este repo.
Tu tarea es espejar la rama `main` de ese repo móvil hacia el remoto `ecom`, **mostrando
primero qué se va a enviar y pidiendo confirmación explícita** antes de pushear.

## Contexto fijo (no negociable)

- **Repo fuente (`origin`):** `https://github.com/Mkdir-arg/Chaco-mobile.git` (GitHub, la
  app de territoriales extraída a su propio repositorio). La **fuente de verdad es
  `origin/main`** de ese repo, no un checkout local editado.
- **Remoto destino (`ecom`):**
  `https://git.ecom.com.ar/externos/relevamiento-becas-des-hum/relevamiento-becas-admin-app.git`
- **Vía HTTPS, NO SSH.** El snippet que muestra GitLab usa `git@git.ecom.com.ar:...` (SSH,
  puerto 22): **eso NO es alcanzable desde afuera** y la VPN de icore no enruta la red de
  ECOM. El **HTTPS (443) está expuesto a internet**, así que se clona/pushea **sin VPN**.
- **Clon de trabajo local:** `../Chaco-mobile` (hermano de este repo `Chaco`). Se opera
  siempre con `git -C ../Chaco-mobile ...` para no tocar el repo actual.
- **Solo se envía `main`.** Nunca otras ramas ni tags.
- **NUNCA tocar el `origin` del repo móvil** (es su GitHub). Solo se le agrega el remoto
  `ecom` y se pushea a él.
- **Auth:** HTTPS con Personal Access Token (scope `write_repository`) vía Git Credential
  Manager. Puede abrir una ventana de login la primera vez; el usuario ingresa su usuario
  de GitLab ECOM + el PAT como contraseña.

## Pasos

1. **Asegurá el clon local del repo móvil (`../Chaco-mobile`):**
   - Si **no existe** (no hay `../Chaco-mobile/.git`):
     `git clone https://github.com/Mkdir-arg/Chaco-mobile.git ../Chaco-mobile`
   - Si **ya existe**, traé lo último de GitHub:
     `git -C ../Chaco-mobile fetch origin`
   - En ambos casos la referencia de verdad es **`origin/main`** (recién fetcheada).

2. **Verificá el remoto `ecom` dentro del clon móvil:**
   `git -C ../Chaco-mobile remote get-url ecom`
   - Si no existe, agregalo:
     `git -C ../Chaco-mobile remote add ecom https://git.ecom.com.ar/externos/relevamiento-becas-des-hum/relevamiento-becas-admin-app.git`

3. **Averiguá el estado remoto de `main` en ecom:**
   `git -C ../Chaco-mobile ls-remote ecom main`
   (obtené el SHA remoto; puede pedir login por GCM la primera vez)

4. **Calculá los commits pendientes** (lo que falta en `ecom` respecto de `origin/main`):
   - SHA fuente: `git -C ../Chaco-mobile rev-parse origin/main`
   - Con SHA remoto existente:
     `git -C ../Chaco-mobile log --oneline <SHA_remoto>..origin/main`
   - Si el `main` remoto está **vacío** (repo nuevo, sin salida en el paso 3): mostrá
     `git -C ../Chaco-mobile log --oneline -20 origin/main` y aclará que se sube **todo el
     historial** de `main`.
   - Si el SHA remoto **es igual** al de `origin/main`: informá *"ecom/main (app) ya está
     al día, no hay nada para enviar"* y **terminá sin pushear**.

5. **Mostrale al usuario y PEDÍ CONFIRMACIÓN** (no pushees sin un "sí" explícito):
   - Mensaje: **"Vas a espejar la app móvil (rama `main` de Chaco-mobile) al GitLab de ECOM (repo `relevamiento-becas-admin-app`, remoto `ecom`)."**
   - La **lista de commits pendientes** del paso 4.
   - El SHA fuente (`origin/main`) que va a quedar en el remoto.

6. **Si el usuario confirma, pusheá `origin/main` a `ecom/main`:**
   - Comando **LIMPIO**, sin token embebido en la URL (el clasificador bloquea comandos
     con secretos adentro): `git -C ../Chaco-mobile push ecom origin/main:refs/heads/main`
   - El destino va **completamente calificado** (`refs/heads/main`): si el repo remoto está
     vacío, `origin/main:main` a secas falla ("not a full refname") porque git no puede
     adivinar la rama nueva.
   - Requiere la regla de permiso `Bash(git push:*)` (ya declarada en el frontmatter de
     este comando). Si el push queda bloqueado por el clasificador, avisale al usuario que
     agregue la regla con `/permissions`.

7. **Verificá:** `git -C ../Chaco-mobile ls-remote ecom main` debe coincidir con
   `git -C ../Chaco-mobile rev-parse origin/main`. Reportá el resultado (SHA fuente == SHA
   remoto).

## Reglas

- Si el usuario **no confirma**, no hacés nada.
- **Nunca** pushees una rama distinta de `main`, ni tags, ni toques el `origin` del repo
  móvil ni el remoto `ecom` de **este** repo (Chaco).
- **Nunca** embebas el PAT en el comando ni en la URL del remoto (queda registrado y el
  clasificador lo bloquea). Dejá que GCM maneje la credencial.
- Si el push falla por **red/timeout**, avisá que puede ser conectividad y **no reintentes
  a ciegas**.
- Recordale al usuario **rotar/revocar el PAT** si en algún momento lo compartió en texto.
