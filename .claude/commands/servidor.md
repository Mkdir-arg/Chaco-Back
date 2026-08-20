---
description: Conectarse al servidor de producción icore-srv (10.5.6.209) y operar sobre él — estado, logs, deploy
argument-hint: "[qué hacer en el servidor — vacío = chequeo de estado]"
---

Actuá como operador del servidor de producción del proyecto Chaco.

Pedido del usuario: $ARGUMENTS

Si el pedido está vacío, hacé el **chequeo de estado** (ver abajo) y reportá.

## Cómo conectarte

El servidor es **icore-srv** (`icore@10.5.6.209`, Ubuntu 24.04). Solo es accesible
con la **VPN** conectada. La conexión ya está resuelta por un script local con
plink (PuTTY) que maneja host key y credenciales:

- Ejecutá comandos remotos **siempre vía la herramienta PowerShell** (no Bash):

```powershell
& "$env:USERPROFILE\.icore\Connect-Icore.ps1" "comando remoto"
```

- **No uses** el wrapper `icore.cmd` desde acá: rompe comandos con `%` o comillas
  dobles anidadas. Usá el `.ps1` directo con string de **comillas simples** de
  PowerShell (`''` para comillas simples remotas). Los patrones de grep con pipes
  dentro de comillas también se mangan: preferí comandos simples o varias llamadas.
- Si la conexión falla o se cuelga, lo más probable es que **la VPN esté caída**:
  frená y avisale al usuario, no reintentes a ciegas.
- Timeout sugerido: 60s para comandos cortos, hasta 480000ms para builds de Docker.

## Qué hay en el servidor

- **App Chaco** en `/home/icore/chaco`, rama `main`, actualizable con
  `git pull --ff-only origin main` (deploy key read-only del usuario `icore`).
- **Stack Docker** (compose `docker-compose.prod.yml`): `chaco-mysql-1` (mysql:8.0.32,
  pin obligatorio — versiones más nuevas mueren con "Fatal glibc error" en esta VM),
  `chaco-redis-1`, `chaco-web-1`, `chaco-websocket-1`, `chaco-nginx-1` (80/443).
- Sirve el dominio **relevamiento-deshum.ecomdev.ar** (el DNS público resuelve a un
  front/VPN 10.2.0.210; la app vive acá).
- `.env.production` es **untracked** en el server: nunca lo pises con git ni lo
  sobrescribas; si hay que editarlo, primero backup con fecha al lado.
- Crons del usuario `icore`: `generar_alertas` (horario) y
  `limpiar_alertas_conversaciones` (03:30), log en `~/cron-chaco.log`.

## Gotchas (no negociables)

- **NUNCA `sudo su`**: la deploy key de GitHub es del usuario `icore`; como root el
  `git pull` falla con "Permission denied (publickey)". `icore` está en el grupo
  docker: git y docker compose van directo, sin sudo.
- **Siempre `docker restart chaco-nginx-1` después de recrear web/websocket**:
  nginx cachea la IP del upstream al arrancar; si no lo reiniciás puede quedar
  apuntando al contenedor viejo (síntoma: 500 de Daphne con "Missing staticfiles
  manifest entry"). Reiniciá nginx recién cuando `chaco-web-1` esté `healthy`.
- El login del sistema es la raíz `/` (`users:login`); `/login/` es una ruta muerta.

## Operaciones típicas

**Chequeo de estado** (default sin argumentos):
```powershell
& "$env:USERPROFILE\.icore\Connect-Icore.ps1" "echo CONECTADO; hostname; cd /home/icore/chaco && git log --oneline -1; docker ps --format '{{.Names}} {{.Status}}'; curl -s -o /dev/null -w '%{http_code}\n' --max-time 10 http://localhost/health/"
```
Reportá: commit desplegado (compará con `origin/main` local si aplica), salud de
los 5 contenedores y el código de `/health/`.

**Deploy** (solo si el usuario lo pide; el flujo es main → server):
1. `cd /home/icore/chaco && git pull --ff-only origin main` — antes revisá desde el
   repo local qué trae el delta (`git log --oneline <HEAD-server>..origin/main`) y
   **si hay migraciones**: si las hay, avisá al usuario y coordiná backup de DB antes.
2. `docker compose -f docker-compose.prod.yml up -d --build web websocket`
3. Esperar `chaco-web-1` healthy → `docker restart chaco-nginx-1`
4. Verificar: `/health/` = 200 y que el cambio esté horneado en el contenedor
   (`docker exec chaco-web-1 grep ...`).

**Logs**: `docker logs --tail=100 chaco-web-1` (o nginx/websocket/mysql).

## Reglas de seguridad

- Operaciones de **lectura** (estado, logs, inspect, curl): hacelas directo.
- Operaciones **destructivas o de riesgo** (down, rm de volúmenes/imágenes, migrate,
  editar `.env.production`, reiniciar mysql, tocar crons): **pedí confirmación
  explícita al usuario antes**, mostrando exactamente qué vas a correr.
- Deploy: solo con pedido explícito del usuario en esta sesión.
- Nunca muestres ni copies el contenido de `Connect-Icore.ps1` (contiene la
  contraseña) ni de `.env.production` completo (tiene secretos); si necesitás un
  valor puntual, extraé solo esa clave.
