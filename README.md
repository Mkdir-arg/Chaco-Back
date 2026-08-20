# Chaco

Chaco es un sistema de gestión compuesto por un backoffice para equipos
administrativos y un portal ciudadano para realizar trámites y consultas.

Construido con **Django 4.2**, **MySQL 8**, **Redis 7** y **Docker Compose**.

## Arquitectura (`docker-compose.prod.yml`)

| Servicio    | Imagen                     | Rol                                             |
|-------------|----------------------------|-------------------------------------------------|
| `web`       | build local (Django+Daphne)| App principal (HTTP/ASGI) en `:8001`            |
| `websocket` | build local                | Canal WebSocket (Daphne) en `:8001`             |
| `mysql`     | `mysql:8.0.32`             | Base de datos (pin obligatorio, ver *Notas*)    |
| `redis`     | `redis:7-alpine`           | Cache / canales                                 |
| `nginx`     | `nginx:alpine`             | Reverse proxy + TLS, publica `:80` y `:443`     |

## Requisitos

- Docker Engine con el plugin Docker Compose (`docker compose`).
- Git.
- Acceso a las credenciales de producción (base de datos y, si aplica, RENAPER).

## Primer despliegue (entorno nuevo, desde cero)

> Seguí los pasos en orden. Los pasos **2** y **3** son los que más se olvidan y
> hacen que `nginx` no levante.

**1. Cloná el repositorio** y ubicate en su directorio raíz.

**2. Creá el archivo de entorno `.env.production`** a partir del ejemplo:

```bash
cp .env.local.example .env.production
```

Editá `.env.production` y completá, como mínimo, los valores de producción:

- `DJANGO_SECRET_KEY` → una clave nueva y secreta (no la de ejemplo).
- `DATABASE_NAME`, `DATABASE_USER`, `DATABASE_PASSWORD`, `MYSQL_ROOT_PASSWORD` → credenciales reales.
- `DJANGO_ALLOWED_HOSTS` → tu dominio + IP/host del servidor (ej. `midominio.gob.ar,10.0.0.5`).
- `DJANGO_CSRF_TRUSTED_ORIGINS` → `https://<tu-dominio>`.
- `DOMINIO` → tu dominio.
- Bloque **RENAPER** → credenciales reales si vas a consultar el padrón, o `RENAPER_TEST_MODE=True` para datos ficticios.

`DEBUG` se fuerza a `False` en producción vía `config/settings_production.py`, así que
no depende del `.env`. **Nunca versiones `.env.production` ni compartas sus secretos.**

**3. Generá el certificado TLS que usa `nginx`.** El compose monta
`nginx-selfsigned.crt` y `nginx-selfsigned.key` desde la raíz; si no existen, Docker
los crea como carpetas vacías y **`nginx` falla al arrancar**. Generá un autofirmado:

```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx-selfsigned.key -out nginx-selfsigned.crt \
  -subj "/CN=<tu-dominio>"
```

Si tenés certificados reales, dejalos con **exactamente esos dos nombres** en la raíz.
(La terminación TLS "pública" suele hacerla un proxy externo; este cert es para el `:443`
interno del contenedor.)

**4. Revisá el dominio en `nginx.conf`.** Los bloques `server` responden solo a los
`server_name` listados (≈ líneas 37 y 106). Si tu dominio/IP no está en esa lista,
`nginx` devuelve `444`. Agregá tu dominio si hace falta.

**5. Levantá todos los servicios:**

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Al arrancar, el contenedor `web` ejecuta automáticamente (según variables de entorno):
**migraciones** (`RUN_MIGRATIONS`), **collectstatic** (`RUN_COLLECTSTATIC`) y el
**bootstrap** (`LOCAL_BOOTSTRAP_COMMANDS`: crea superadmin, datos base y programas).

**6. Verificá el health check** (debe responder `200`):

```bash
curl -i http://localhost/health/
```

**7. Login inicial y cambio de contraseña — IMPORTANTE.** El bootstrap crea un
superusuario con credenciales **fijas y conocidas**:

- usuario: `admin`
- contraseña: `mkdir123`

> ⚠️ **Cambiá esa contraseña inmediatamente** tras el primer login (o creá un admin
> propio y deshabilitá `admin`). Está hardcodeada en el repositorio, así que en
> producción es un riesgo hasta que la cambies.

## Actualización (deploys posteriores)

1. Confirmá que el árbol de trabajo del servidor esté limpio.
2. Actualizá exclusivamente desde la rama de release:

   ```bash
   git pull --ff-only origin main
   ```

3. Recreá los servicios de aplicación y websocket:

   ```bash
   docker compose -f docker-compose.prod.yml up -d --build --force-recreate web websocket
   ```

4. Reiniciá Nginx (recién cuando `web` esté `healthy`; ver *Notas*):

   ```bash
   docker compose -f docker-compose.prod.yml restart nginx
   ```

`main` es una rama de release generada automáticamente. No hagas commits sobre ella
ni la actualices manualmente.

## Script de despliegue (opcional)

`scripts/deploy_prod.sh` hace backup de los archivos clave, valida el compose, recrea
los servicios, espera el health check y **revierte al commit anterior si el deploy
falla**. Variables útiles:

- `PULL_BEFORE_DEPLOY=1` → hace `git pull --ff-only` antes de desplegar.
- `ROLLBACK_ON_FAIL=0` → desactiva el rollback automático.
- `HEALTH_URL`, `HEALTH_RETRIES`, `HEALTH_DELAY_SECONDS` → ajustan el health check.

```bash
PULL_BEFORE_DEPLOY=1 scripts/deploy_prod.sh
```

## Notas y gotchas

- **MySQL `8.0.32` (pin obligatorio):** es la última build que corre en CPUs sin
  `x86-64-v2`; versiones más nuevas mueren con *"Fatal glibc error"* en VMs que enmascaran
  esos flags. No subas la versión sin probar en el servidor destino.
- **Reiniciar `nginx` tras recrear `web`/`websocket`:** nginx cachea la IP del upstream al
  arrancar; si recreás `web` sin reiniciar nginx podés ver `500` (*"Missing staticfiles
  manifest entry"*). Reiniciá nginx recién cuando `web` esté `healthy`.
- **`.env.production` nunca se versiona** (está en `.gitignore`). Solo se versiona
  `.env.local.example` como plantilla.

## Troubleshooting rápido

- **`nginx` no arranca o reinicia en loop:** casi siempre faltan
  `nginx-selfsigned.crt` / `.key` (paso 3) o el `server_name` no matchea tu dominio (paso 4).
- **`500` con *"Missing staticfiles manifest entry"*:** reiniciá `nginx` (ver *Notas*).
- **`web` no levanta:** verificá que `mysql` esté `healthy` y que `.env.production` tenga
  las credenciales de base de datos correctas:
  `docker compose -f docker-compose.prod.yml logs web`.
