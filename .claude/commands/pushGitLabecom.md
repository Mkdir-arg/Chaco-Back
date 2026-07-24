---
description: Enviar la rama main al GitLab de ECOM (remoto ecom) — muestra los commits pendientes, pide confirmación y hace git push ecom main
allowed-tools: Bash(git push:*), Bash(git ls-remote:*), Bash(git fetch:*), Bash(git log:*), Bash(git rev-parse:*), Bash(git remote:*)
---

Sos el operador del **espejo del código al GitLab de ECOM**. Tu tarea es enviar la
rama `main` al remoto `ecom`, pero **mostrando primero qué se va a enviar y pidiendo
confirmación explícita** antes de pushear.

## Contexto fijo (no negociable)

- **Remoto destino:** `ecom` →
  `https://git.ecom.com.ar/externos/relevamiento-becas-des-hum/datanach.git`
  (renombrado desde `relevamiento-becas-admin` en jul-2026, por el rename del sistema a
  DATAÑACH; la URL vieja aún redirige, pero usá la nueva)
- **Vía HTTPS, NO SSH.** El SSH interno (puerto 22) no es alcanzable desde afuera y la
  VPN de icore no enruta la red de ECOM (`10.2.0.x`); pero el **HTTPS (443) está expuesto
  a internet**, así que se pushea sin VPN.
- **Solo se envía `main`.** Nunca otras ramas ni tags.
- **NUNCA tocar el remoto `origin`** (es GitHub, `Mkdir-arg/Chaco`). Solo `ecom`.
- **Auth:** HTTPS con Personal Access Token (scope `write_repository`) vía Git Credential
  Manager. Puede abrir una ventana de login la primera vez; el usuario ingresa su usuario
  de GitLab ECOM + el PAT como contraseña.

## Pasos

1. **Verificá el remoto `ecom`:**
   `git remote get-url ecom`
   - Si no existe, agregalo:
     `git remote add ecom https://git.ecom.com.ar/externos/relevamiento-becas-des-hum/datanach.git`

2. **Averiguá el estado remoto de `main`:**
   `git ls-remote ecom main`
   (obtené el SHA remoto; puede pedir login por GCM la primera vez)

3. **Calculá los commits pendientes (lo que falta en `ecom`):**
   - Con SHA remoto existente: `git log --oneline <SHA_remoto>..main`
   - Si el `main` remoto está vacío (repo nuevo): mostrá `git log --oneline -20 main` y
     aclará que se sube **todo el historial** de `main`.
   - Si el SHA remoto **es igual** a `git rev-parse main`: informá *"ecom/main ya está al
     día, no hay nada para enviar"* y **terminá sin pushear**.

4. **Mostrale al usuario y PEDÍ CONFIRMACIÓN** (no pushees sin un "sí" explícito):
   - Mensaje: **"Vas a enviar el repo productivo (rama `main`) al GitLab de ECOM (remoto `ecom`)."**
   - La **lista de commits pendientes** del paso 3.
   - El SHA local de `main` (`git rev-parse main`) que va a quedar en el remoto.

5. **Si el usuario confirma, pusheá:**
   - Comando **LIMPIO**, sin token embebido en la URL (el clasificador bloquea comandos
     con secretos adentro): `git push ecom main`
   - Requiere que exista la regla de permiso `Bash(git push:*)` en
     `.claude/settings.local.json`. Si el push queda bloqueado por el clasificador, avisale
     al usuario que agregue esa regla con `/permissions` (Claude no puede autoautorizársela).

6. **Verificá:** `git ls-remote ecom main` debe coincidir con `git rev-parse main`.
   Reportá el resultado (SHA local == SHA remoto).

## Reglas

- Si el usuario **no confirma**, no hacés nada.
- **Nunca** pushees una rama distinta de `main`, ni tags, ni toques `origin`.
- **Nunca** embebas el PAT en el comando ni en la URL del remoto (queda registrado y el
  clasificador lo bloquea). Dejá que GCM maneje la credencial.
- Si el push falla por **red/timeout**, avisá que puede ser conectividad y **no reintentes
  a ciegas**.
- Recordale al usuario **rotar/revocar el PAT** si en algún momento lo compartió en texto.
