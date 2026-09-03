# :material-package-variant-closed: Versión 001

<div class="grid cards" markdown>

-   :material-circle:{ style="color: #f59e0b" } **Estado**

    En progreso

-   :material-calendar-range: **Período**

    3 jun 2026 → en curso

-   :material-counter: **Avance**

    —

-   :material-clock-outline: **Horas consumidas**

    556h 20min (al 10/07/2026)

</div>

!!! abstract "Objetivo"
    Definir el funcionamiento de los programas **Becas** y **Dispositivos**, y desarrollar el **motor RBAC base** para dejar el sistema de permisos operativo.

---

## :material-clipboard-list-outline: Alcance de la versión

| # | Funcionalidad | Prioridad | Estado | Hs est. | Hs reales |
|:-:|---|:-:|:-:|:-:|:-:|
| 1 | [Programa Becas — análisis funcional y estimación](../funcionalidades/programa-becas.md) | Alta | Completado | — | 46h |
| 2 | Motor RBAC base | Alta | Completado | — | 22h |
| 3 | [Programa Dispositivos y Merenderos — análisis y estimación](../funcionalidades/programa-dispositivos.md) | Alta | Estimación presentada | — | 154h |
| 4 | Programa Becas — backend del backoffice | Alta | En pruebas | — | 83h |
| 5 | Programa Becas — pruebas funcionales del backend | Alta | En progreso | — | 32h |
| 6 | App de campo (React Native) | Alta | En desarrollo | — | 101h |
| 7 | Mockups y diseño UX (Becas) | Alta | En progreso | — | 65h |
| 8 | Análisis Legajo Ciudadano | Media | Completado | — | 30h |
| 9 | Design System del proyecto | Media | Completado | — | 8h |
| 10 | Reuniones y coordinación | — | — | — | 15h |
| | **Total** | | | | **556h** |

!!! note "Criterio de las horas reales"
    Las horas por funcionalidad suman el consumo registrado por frente de trabajo según el campo *Motivo* del [detalle de consumo](../financiero/detalle-tareas.md) (556 h 20 min al 10/07/2026). La estimación comprometida del desarrollo de Becas (654 h) se ejecuta en los meses siguientes — ver [estimación](../funcionalidades/estimacion-programa-becas.md).

---

## :material-server-network: Despliegue de la versión

Stack: **Docker Compose**, cinco contenedores — MySQL, Redis, app web, websockets y nginx. El código de release vive en la rama **`main`** del repositorio (sin herramientas internas ni documentación).

Los ambientes de **testing y QA de ECOM no usan esta guía**: se despliegan solos con un push a `test`/`main` vía su CI/CD. Sus diferencias están en [Si el despliegue es en Kubernetes](#si-el-despliegue-es-en-kubernetes); la configuración de variables (paso 3) es la misma.

!!! warning "Reglas fijas"
    - Esta página es pública: donde aparece `<...>` va un valor real. **Cada ambiente usa valores propios** — nunca los de otro ambiente.
    - Se opera con un usuario del grupo `docker`. **Nunca `sudo su`**: la deploy key y Docker son del usuario de despliegue.
    - `.env.production` no se versiona ni se sube al repositorio.

### :material-numeric-1-circle: Requisitos del servidor

| Requisito | Detalle |
|---|---|
| Docker Engine + Compose | Verificar: `docker --version` y `docker compose version` |
| Usuario de despliegue | En el grupo `docker`, con **deploy key de solo lectura** del repositorio |
| MySQL `8.0.32` | Pin obligatorio: builds más nuevas no arrancan en CPUs sin `x86-64-v2` (caso de la VM actual) |
| Disco | Holgura para `mysql_data` y las capas de imagen |

### :material-numeric-2-circle: Traer la versión

```bash
git clone -b main git@github.com:Mkdir-arg/Chaco-Back.git ~/chaco
cd ~/chaco
```

Si el servidor ya tiene una versión, no se re-clona: ver [Actualizar a una versión nueva](#actualizar-a-una-version-nueva).

### :material-numeric-3-circle: Configurar el ambiente

Crear `~/chaco/.env.production` con permisos restringidos:

```bash
nano .env.production
chmod 600 .env.production
```

La referencia completa de variables es **`.env.qa.example`** (raíz del repositorio, viaja en el release): cada variable indica si es obligatoria y quién provee el valor. Mínimo para levantar:

```ini
# ─── Django ───────────────────────────────────────────────
DJANGO_SECRET_KEY=<cadena-larga-y-aleatoria-nueva-para-este-ambiente>
DJANGO_DEBUG=False
ENVIRONMENT=prd

# ─── URL del ambiente ─────────────────────────────────────
# Varias direcciones van separadas por coma.
DJANGO_ALLOWED_HOSTS=<dominio-o-ip-del-servidor>
DJANGO_CSRF_TRUSTED_ORIGINS=https://<dominio-o-ip-del-servidor>
DOMINIO=<dominio-o-ip-del-servidor>

# ─── Base de datos: las lee la APLICACIÓN ─────────────────
DATABASE_NAME=chaco
DATABASE_USER=chaco
DATABASE_PASSWORD=<password-db>
DATABASE_HOST=mysql
DATABASE_PORT=3306

# ─── Base de datos: las lee el CONTENEDOR MySQL ───────────
# Deben coincidir con las de arriba.
MYSQL_DATABASE=chaco
MYSQL_USER=chaco
MYSQL_PASSWORD=<password-db>
MYSQL_ROOT_PASSWORD=<password-root-db>

# ─── Redis ────────────────────────────────────────────────
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=1

# ─── Arranque del contenedor ──────────────────────────────
# Este bloque lo lee el proceso de arranque, no Django: en Kubernetes va como
# variables de entorno del pod, no en un archivo montado.
DJANGO_SETTINGS_MODULE=config.settings_production
APP_RUNTIME=daphne
RUN_MIGRATIONS=true
# Con ENVIRONMENT=prd|qa ya es el default; se deja explícito.
RUN_COLLECTSTATIC=true
# True solo sin nginx adelante (Kubernetes). Requiere volumen persistente en /app/media.
SERVE_MEDIA=False
# No recortar: siembra RBAC, roles de Becas, roles de menú y catálogos base.
LOCAL_BOOTSTRAP_COMMANDS=seed_datos_base crear_programas
LOCAL_OPTIONAL_BOOTSTRAP_COMMANDS=procesar_vencimientos

# ─── SIIS: catálogo de programas (Becas) ──────────────────
SIIS_API_URL=https://siisapi.ecomdev.ar
SIIS_API_CLIENT_ID=<lo-provee-ECOM>
SIIS_API_CLIENT_SECRET=<lo-provee-ECOM>

# ─── Personas / Gran Base: prevalidación de ciudadanos ────
PERSONAS_API_URL=https://personas.ecomdev.ar/api/v1
PERSONAS_API_CLIENT_ID=<lo-provee-ECOM>
PERSONAS_API_CLIENT_SECRET=<lo-provee-ECOM>
PERSONAS_API_ENTIDAD_UUID=<lo-provee-ECOM>
PERSONAS_API_FUENTE_ID=13

# ─── RENAPER ──────────────────────────────────────────────
# TEST_MODE=True devuelve datos ficticios y levanta sin credenciales.
RENAPER_TEST_MODE=False
RENAPER_API_URL=<url>
RENAPER_API_USERNAME=<usuario>
RENAPER_API_PASSWORD=<password>
RENAPER_AUTH_MODE=credentials
RENAPER_HTTP_METHOD=get

# ─── Correo saliente ──────────────────────────────────────
# El envío real ocurre solo con ENVIRONMENT=prd; con qa el correo va a la
# consola del contenedor aunque el SMTP esté configurado.
EMAIL_HOST=<servidor-smtp>
EMAIL_PORT=587
EMAIL_HOST_USER=<usuario>
EMAIL_HOST_PASSWORD=<password>
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=DATAÑACH <no-responder@chaco.gob.ar>

# ─── Sesión ───────────────────────────────────────────────
SESSION_IDLE_TIMEOUT_MINUTES=15
SESSION_IDLE_WARNING_SECONDS=60
```

Quién provee cada valor:

| Grupo | Lo define |
|---|---|
| Clave secreta, base de datos, Redis, dominio | Quien monta el ambiente, con **valores nuevos** |
| `SIIS_API_*` y `PERSONAS_API_*` | **ECOM** (son sus servicios) |
| `RENAPER_*` | El organismo, vía ECOM |
| `EMAIL_*` | Infraestructura del correo institucional |

!!! danger "Errores de configuración que impiden operar"
    1. **Dominio ausente** de `DJANGO_ALLOWED_HOSTS` o `DJANGO_CSRF_TRUSTED_ORIGINS` → 400 en toda petición y errores CSRF en los formularios.
    2. **`DATABASE_*` y `MYSQL_*` sin coincidir** → los contenedores quedan *healthy* pero la app no conecta a la base.
    3. **`LOCAL_BOOTSTRAP_COMMANDS` recortado** → roles congelados (un rol nuevo del sistema no aparece nunca) y catálogos sin cargar, incluidas las localidades del selector de zona.

**Certificado TLS** — con dominio real, usar el emitido. Por IP o red privada, autofirmado:

```bash
openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
  -keyout nginx-selfsigned.key -out nginx-selfsigned.crt \
  -subj "/CN=<dominio-o-ip-del-servidor>"
```

### :material-numeric-4-circle: Levantar todo

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

El entrypoint, en cada arranque y sin intervención: espera la base → aplica migraciones → recolecta estáticos → siembra roles, programas y catálogos → cierra lo vencido en Becas.

nginx cachea la IP interna de la app al arrancar. Tras cada `up --build`, reiniciarlo (síntoma si se omite: error 500 de archivos estáticos):

```bash
docker compose -f docker-compose.prod.yml ps   # esperar chaco-web-1 healthy
docker restart chaco-nginx-1
```

### :material-numeric-5-circle: Crear el primer superusuario

El sembrado **no crea usuarios**. El primer superusuario se crea una vez, con credenciales que define quien monta el ambiente:

```bash
docker exec -it chaco-web-1 python manage.py createsuperuser
```

Variante sin interacción (deja la contraseña en el historial del shell — evitarla en servidores):

```bash
docker exec \
  -e DJANGO_SUPERUSER_USERNAME=<usuario> \
  -e DJANGO_SUPERUSER_EMAIL=<correo> \
  -e DJANGO_SUPERUSER_PASSWORD=<contraseña> \
  chaco-web-1 python manage.py createsuperuser --noinput
```

Este usuario es solo la puerta de entrada: los usuarios de trabajo se dan de alta desde **Administración → Usuarios**, con su rol.

### :material-numeric-6-circle: Verificar que quedó sano

```bash
curl -f http://localhost/health/               # 200
curl -sI http://localhost/ | head -1           # 200 — el ingreso es la raíz /, no existe /login/
docker compose -f docker-compose.prod.yml ps   # cinco contenedores healthy
docker exec chaco-web-1 python manage.py showmigrations | tail -20
```

### :material-numeric-7-circle: Tareas programadas

Se instalan **una sola vez por servidor** (no viajan con el deploy). Snippets en `docker/cron/`:

| Tarea | Horario | Si no corre |
|---|:-:|---|
| `generar_alertas` | cada hora | No se generan las alertas de legajos |
| `procesar_vencimientos` | 03:10 | Convocatorias vencidas quedan abiertas; sus relevamientos no pasan a revisión |
| `limpiar_alertas_conversaciones` | 03:30 | Se acumulan alertas ya resueltas |
| `sincronizar_programas_siis` | 04:00 | **Una baja de programa en SIIS no se detecta** |

```bash
crontab -e
# patrón: <horario> docker exec chaco-web-1 python manage.py <comando> >> ~/cron-chaco.log 2>&1
crontab -l
```

`sincronizar_programas_siis` va **solo por cron**, nunca en el arranque: depende de un servicio externo y una caída dejaría el contenedor sin levantar.

### :material-kubernetes: Si el despliegue es en Kubernetes

Misma imagen; el compose de la VM resuelve cosas que en Kubernetes se replican explícitamente. Todo lo demás de la guía aplica igual.

**1. El pod arranca con el entrypoint de la imagen.** Con `command`/`args` en el manifiesto, el entrypoint ejecuta eso y **saltea migraciones, estáticos y sembrado** — síntoma silencioso: esquema atrasado y roles faltantes. Logs esperados al arrancar:

```
Aplicando migraciones...
Ejecutando python manage.py seed_datos_base
```

Si aparece `Comando personalizado detectado`, el bootstrap no corrió. Salidas: quitar `command`/`args`, o un initContainer/Job con la misma imagen y `args: ["bootstrap"]` (one-shot: migra, recolecta, siembra y termina). Ejemplo: `docker/k8s/bootstrap-initcontainer.yaml`.

**2. Las variables van como env del pod.** Las del bloque *Arranque del contenedor* y `DJANGO_SETTINGS_MODULE` las lee el script de inicio, no Django: un archivo montado no alcanza. Síntoma típico de que no llegaron: líneas de `django.utils.autoreload` en el log del pod — significa que el contenedor está corriendo el servidor de desarrollo porque le falta `APP_RUNTIME=daphne`.

**3. HTTPS.** Con `settings_production` la app exige `DJANGO_ALLOWED_HOSTS` (falla al arrancar si falta) y redirige a HTTPS: el ingress **debe enviar `X-Forwarded-Proto: https`**, o toda petición entra en bucle de redirección.

**4. Estáticos y media.** `/static/` lo sirve la app (whitenoise; `collectstatic` es default en `prd|qa`) — sin nginx ni sidecar. `/media/`: `SERVE_MEDIA=True` para que la app lo sirva, y **PVC en `/app/media`** — sin volumen, los adjuntos se pierden al reiniciar el pod.

**5. Websockets.** Con `APP_RUNTIME=daphne` un solo proceso atiende HTTP y `/ws/`; el ingress debe pasar los encabezados `Upgrade` y `Connection`. Para repartir el HTTP en varios procesos, `APP_RUNTIME=gunicorn` en el Deployment web, un segundo Deployment con daphne para `/ws/` y `WEBSOCKETS_ENABLED=True` en el web (detalle en `docker/k8s/README.md`, sección *HTTP en varios procesos*).

**6. Probes.** `/health/` sirve como liveness y readiness — y hace falta además un **startupProbe** holgado (`periodSeconds: 10`, `failureThreshold: 60`): el primer arranque tarda minutos y sin él el liveness mata el bootstrap a mitad de camino, dejando el pod en loop de reinicios (exit 137, sin error en el log). Los puertos tienen que ser consistentes: `APP_PORT` = `containerPort` = `targetPort` del Service = puerto de las probes.

**7. Tareas programadas = CronJob**, uno por comando de la tabla anterior. Plantillas: `docker/k8s/cronjobs.yaml`. `sincronizar_programas_siis` jamás en el arranque del pod.

**8. Base de datos y Redis propios.** El pin `mysql:8.0.32` es una limitación de la VM, no del sistema: en Kubernetes se usa su MySQL 8 vía `DATABASE_*` (MariaDB funciona; el warning `W036` de las constraints condicionales aparece igual con ambos motores y esas reglas las valida la aplicación). Y hace falta un **Redis** provisto por la plataforma —la app lo usa para caché y websockets, un `redis:7-alpine` alcanza—, apuntado con `REDIS_*`.

### :material-update: Actualizar a una versión nueva

```bash
cd ~/chaco
git pull --ff-only origin main
docker compose -f docker-compose.prod.yml up -d --build web websocket
docker compose -f docker-compose.prod.yml ps    # esperar chaco-web-1 healthy
docker restart chaco-nginx-1
curl -f http://localhost/health/
```

Las migraciones se aplican solas en el arranque. `.env.production` no se toca (no está versionado), pero conviene **compararlo contra `.env.qa.example`** después de actualizar: una variable nueva faltante no rompe el arranque — deja la funcionalidad que depende de ella apagada, en silencio.

!!! danger "Al actualizar a esta versión: el arranque ya no crea usuarios"
    Antes el arranque creaba un superusuario con credenciales fijas; se retiró. Un ambiente en funcionamiento no se ve afectado. Si la base se recrea, el superusuario se crea a mano (paso 5). Y **si la base se sembró con una versión anterior, existe el usuario `admin` con la contraseña conocida** — cambiarla o eliminarlo:

    ```bash
    docker exec -it chaco-web-1 python manage.py changepassword admin
    ```

!!! danger "No hacer"
    - `sudo su` — como root fallan `git pull` y el deploy.
    - Editar la base a mano — el esquema lo manejan las migraciones.
    - Subir `.env.production` al repositorio.
    - Reutilizar valores de otro ambiente (clave secreta y base, sobre todo).
    - Cambiar el pin de MySQL `8.0.32` sin verificar que la VM lo soporte.
