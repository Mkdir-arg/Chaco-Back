# Procesos internos

## Entornos

| Entorno | URL | Quién despliega | Cómo |
|---|---|---|---|
| Local | `localhost:8000` | Cada desarrollador | `docker compose up` con `.env.local` |
| Nuestro productivo | `relevamiento-deshum.ecomdev.ar` (`icore-srv`) | Nosotros, **a mano** | Ver *Deploy a producción* |
| Testing de ECOM | `datanach.ecomdev.ar` | **Solo** con el push a `test` | CI/CD de ECOM, ver [branching.md](branching.md) |
| QA de ECOM | a definir | **Solo** con el push a `main` | Ídem |

Los dos entornos de ECOM corren en Kubernetes y los despliega ArgoCD a partir de la
imagen que construye su pipeline. Un cambio de **código** llega solo con el push; un
cambio de **configuración** —una variable nueva, un secreto, una tarea programada—
lo tiene que aplicar su equipo de infraestructura.

!!! warning "El entrypoint es el que migra y siembra — y se puede saltear sin querer"
    Si el manifiesto del pod define `command`/`args`, el entrypoint de la imagen
    ejecuta eso directamente y **se saltea migraciones, estáticos y sembrado**
    (`docker-entrypoint.sh` hace `exec "$@"` ante cualquier argumento). El síntoma
    es silencioso: la app levanta con esquema atrasado y roles faltantes — es la
    hipótesis más probable de por qué el testing de ECOM quedó con 3 de 5 roles de
    Becas. Diagnóstico: en los logs del arranque del pod tienen que verse
    `Aplicando migraciones...` y `Seed de datos base`; si aparece
    `Comando personalizado detectado`, el bootstrap no corrió. La salida para ese
    caso es un initContainer o Job con la misma imagen y `args: ["bootstrap"]`
    (modo one-shot del entrypoint). Plantillas en [`docker/k8s/`](../../docker/k8s/)
    y el checklist completo en la guía pública (versión 001, sección
    *Si el despliegue es en Kubernetes*).

## Variables de entorno

La plantilla comentada es [`.env.qa.example`](../../.env.qa.example): lista cada
variable con si es obligatoria y **quién provee el valor**. Viaja en el release, así
que ECOM la tiene en el repositorio espejado. `.env.local.example` es la equivalente
para desarrollo.

`settings.py` lee del entorno primero, así que da igual montar un `.env.production`
en el servidor o inyectar las variables en el contenedor. El archivo
`.env.production` **solo se carga automáticamente cuando `ENVIRONMENT=prd`**.

**Cada entorno tiene sus propios valores.** No se copian los de otro, y menos los de
producción: una `DJANGO_SECRET_KEY` compartida hace que una sesión firmada en un
entorno valga en el otro, y unas credenciales de base compartidas ponen los datos
reales al alcance de una prueba. Cuando hay que entregar un secreto, no va por chat
ni por mail.

Quién pone qué:

| Grupo | Lo provee |
|---|---|
| `DJANGO_SECRET_KEY`, `DATABASE_*`, `REDIS_*`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `DOMINIO` | Quien monta el entorno, con valores nuevos |
| `SIIS_API_*`, `PERSONAS_API_*` | **ECOM**: son sus servicios y ellos emiten las credenciales |
| `RENAPER_*` | El organismo, vía ECOM. Con `RENAPER_TEST_MODE=True` el entorno levanta sin credenciales |
| `EMAIL_*` | Infraestructura de ECOM (pendiente al 11/08/2026: sin esto la invitación por correo no sale) |

!!! warning "Los valores de ejemplo están en `.env.qa.example`"
    Ese archivo es la **plantilla completa y comentada**: trae cada variable con un
    valor de ejemplo, las que son obligatorias y quién provee el secreto. Viaja en el
    release, así que está en el repositorio espejado a ECOM. Para desarrollo, el
    equivalente es `.env.local.example`. Las tablas de abajo son la referencia; la
    plantilla es lo que se copia y se completa.

### Todas las variables

#### Obligatorias: sin estas el entorno no levanta o responde 400

| Variable | Valor | Si falta |
|---|---|---|
| `DJANGO_SECRET_KEY` | secreto propio de **cada** entorno | el proceso no arranca (`ValueError`) |
| `DJANGO_SETTINGS_MODULE` | `config.settings_production` en servidores | quedan los defaults de desarrollo (Silk activo, sin refuerzos de seguridad) |
| `DJANGO_ALLOWED_HOSTS` | dominios separados por coma | con `settings_production` el proceso no arranca; sin él, 400 a toda petición |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | orígenes con esquema (`https://dominio`) | los formularios fallan por CSRF |
| `DOMINIO` | dominio público del entorno | los links de los correos apuntan a `localhost:8000` |
| `ENVIRONMENT` | `dev` \| `qa` \| `prd` | asume `dev`: caché en memoria del proceso en lugar de Redis |
| `DATABASE_NAME` · `DATABASE_USER` · `DATABASE_PASSWORD` · `DATABASE_HOST` · `DATABASE_PORT` | conexión MySQL propia del entorno | no hay base: el arranque falla |
| `REDIS_HOST` · `REDIS_PORT` · `REDIS_SSL` · `REDIS_DB` (o `REDIS_URL`) | `redis` / `6379` / `False` / `1` | con `ENVIRONMENT=prd` la caché y las sesiones son Redis: sin él, error en cada request |

#### Integraciones: si faltan, la aplicación **levanta igual** y falla en silencio

Este es el grupo que más veces quedó sin cargar, justamente porque no rompe el
arranque. Ninguna de estas fallas se ve en pantalla ni deja traza en el log.

| Grupo | Variables | Lo provee | Qué se degrada si falta |
|---|---|---|---|
| **Base de Personas (Gran Base)** | `PERSONAS_API_CLIENT_ID`, `PERSONAS_API_CLIENT_SECRET`, `PERSONAS_API_ENTIDAD_UUID` · `PERSONAS_API_ACTIVA` (default `True`; en `False` no se consulta y la identidad sale del padrón de la convocatoria — Cambio 57) · opcionales con default: `PERSONAS_API_URL`, `PERSONAS_API_FUENTE_ID` (13), `PERSONAS_API_CONNECT_TIMEOUT`, `PERSONAS_API_TIMEOUT` | **ECOM** | el **formulario público** y la app de campo **nunca validan identidad**: el paso 1 no precarga nada y toda inscripción queda `origen=manual`. La consulta corta antes de salir a la red, así que no hay error ni log |
| **SIIS** | `SIIS_API_URL` (**sin default desde el Cambio 123**: vacía, no se manda nada), `SIIS_API_CLIENT_ID`, `SIIS_API_CLIENT_SECRET` · en PRD además `DATANACH_ES_PRODUCCION=1` · con default: timeouts | **ECOM** | el select de «Programa SIIS» queda vacío y no se pueden crear ni vincular segmentos. `manage.py check --deploy` falla con `core.E001` si falta la URL y con `core.E002` si apunta al SIIS de desarrollo en producción |
| **RENAPER** | `RENAPER_TEST_MODE` · si es `False`: `RENAPER_API_URL` (o `RENAPER_LOGIN_URL` + `RENAPER_CONSULTA_URL`) y `RENAPER_API_USERNAME` + `RENAPER_API_PASSWORD` **o** `RENAPER_API_KEY` (+ `RENAPER_API_KEY_HEADER`, `RENAPER_API_KEY_PREFIX`) · ajustes: `RENAPER_AUTH_MODE`, `RENAPER_HTTP_METHOD`, `RENAPER_RETRIES`, timeouts, `RENAPER_TEST_LATENCY_SECONDS` | El organismo, vía ECOM | el backoffice no puede validar ni revalidar identidad en legajos. Con `RENAPER_TEST_MODE=True` el entorno levanta sin credenciales y devuelve datos de prueba |
| **Correo** | `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL` · opcionales: `EMAIL_TIMEOUT`, `EMAIL_SOPORTE`, `EMAIL_PIE_DIRECCION` | Infraestructura de ECOM | no salen la confirmación de la inscripción pública ni las credenciales de alta ni el recupero de contraseña. La inscripción **no** se rompe: el fallo de correo se traga a propósito |

!!! warning "El remitente tiene que ser del dominio del servidor SMTP"
    Si `DEFAULT_FROM_EMAIL` no pertenece al dominio de `EMAIL_HOST`, el servidor puede
    rechazar el relay y los correos rebotan sin aviso en la aplicación.

#### Arranque del contenedor

| Variable | Valor | Para qué |
|---|---|---|
| `APP_RUNTIME` | `daphne` \| `gunicorn` \| `runserver` | `daphne`: HTTP y WebSockets en un solo proceso (un núcleo). `gunicorn`: HTTP en varios procesos; los WebSockets van en otro contenedor con `daphne` y hay que declarar `WEBSOCKETS_ENABLED=True`. `runserver`: solo desarrollo |
| `GUNICORN_WORKERS` · `GUNICORN_THREADS` · `GUNICORN_TIMEOUT` | `3` / `2` / `120` | tamaño del pool HTTP con `APP_RUNTIME=gunicorn` (~150–200 MB por worker) |
| `APP_BIND` · `APP_PORT` | `0.0.0.0` / `8000` | interfaz y puerto donde escucha |
| `RUN_MIGRATIONS` | `true` | aplica `migrate` en cada arranque |
| `RUN_COLLECTSTATIC` | `true` | recolecta estáticos en cada arranque |
| `LOCAL_BOOTSTRAP_COMMANDS` | `seed_datos_base crear_programas` | sembrado obligatorio (ver la advertencia de abajo) |
| `LOCAL_OPTIONAL_BOOTSTRAP_COMMANDS` | vacío | comandos extra que pueden fallar sin abortar el arranque |
| `DJANGO_ENV_FILE` | p. ej. `.env.local` | archivo de entorno a cargar. Se carga **sin sobreescribir** lo que ya viene en el entorno |
| `SERVE_MEDIA` | `True` siempre (desde SEC-09 nginx ya no sirve `/media/`) | archivos adjuntos accesibles, detrás de login |
| `WEBSOCKETS_ENABLED` | se deduce de `APP_RUNTIME` (`True` solo con `daphne`) | con `gunicorn` hay que ponerla en `True` si otro contenedor daphne atiende `/ws/` |
| `DJANGO_SYNCDB_PROJECT_APPS` | `False` | solo para CI |

#### Opcionales con default sano (se toca solo si hace falta)

`DJANGO_DEBUG` (ignorada: `settings_production` fuerza `DEBUG = False`) ·
`SESSION_IDLE_TIMEOUT_MINUTES` (15) · `SESSION_IDLE_WARNING_SECONDS` (60) ·
`PASSWORD_RESET_TIMEOUT` (86400) · `SECURE_SSL_REDIRECT` · `SESSION_COOKIE_SECURE` ·
`CSRF_COOKIE_SECURE` · `SECURE_HSTS_SECONDS` · `SECURE_HSTS_INCLUDE_SUBDOMAINS` ·
`SECURE_HSTS_PRELOAD` (todas seguras por defecto en `settings_production`) ·
`SLOW_REQUEST_MS` (3000) · `PERFORMANCE_QUERY_MONITORING_ENABLED` y el resto de
`PERFORMANCE_*` (instrumentación de consultas).

!!! warning "Tres variables que no hacen nada"
    Aparecieron en configuraciones reales y conviene saber que son inertes:
    `RUN_CREAR_PROGRAMAS` y `RUN_CREAR_SUPERADMIN` **no las lee nadie** —el bootstrap
    no crea usuarios, el primer superusuario se crea a mano (ver abajo)— y
    `OPENAI_API_KEY` quedó residual en `settings.py` sin ningún consumidor.

#### Cómo verificar que están todas

Después de montar o actualizar un entorno, dentro del contenedor:

```bash
python manage.py diagnosticar_integraciones --dni <un DNI real> --sexo F
```

Audita las variables de todas las integraciones, prueba Base de Personas de verdad
—diciendo si el formulario público precargaría los datos— y devuelve código de salida
distinto de 0 si algo falta, así sirve de gate de despliegue. Nunca imprime secretos.
Para SIIS y correo existen además `diagnosticar_siis` y `diagnosticar_correo`.

### Dos cosas que rompen un entorno nuevo

1. **El dominio tiene que estar en `DJANGO_ALLOWED_HOSTS` y
   `DJANGO_CSRF_TRUSTED_ORIGINS`.** Si no, la aplicación responde 400 a toda
   petición y los formularios fallan por CSRF. Es la causa más común de
   «desplegué y no anda».
2. **Una base vacía necesita el sembrado inicial y un superusuario.** El bootstrap
   —`seed_datos_base crear_programas`— crea roles, capacidades y programas, pero
   **a propósito no crea ningún usuario**. El primer superusuario se crea una vez,
   a mano, con las credenciales que defina el ambiente:

   ```bash
   docker exec -it chaco-web-1 python manage.py createsuperuser
   ```

   En nuestro servidor el sembrado lo hace el entrypoint con
   `LOCAL_BOOTSTRAP_COMMANDS`; en Kubernetes hay que decidir si va en el arranque o
   se corre una vez a mano — teniendo en cuenta la advertencia de *Cron del host*
   sobre los comandos de bootstrap que pueden fallar.

   !!! warning "No recortar la lista del bootstrap"
       `seed_datos_base` es un paraguas: corre `seed_rbac` y `seed_becas`, crea los
       roles de menú y carga los catálogos base —incluidas las **localidades**, que
       necesita el selector de zona de los relevamientos— si están vacíos. Como
       `seed_becas` reemplaza el conjunto de capacidades de cada rol, correrlo en
       cada arranque es lo que mantiene los roles alineados con el código.

       Un bootstrap que lo omita deja los roles **congelados en el estado en que se
       sembró la base**: es lo que le pasó al entorno de testing de ECOM, que al
       11/08/2026 mostraba 3 de los 5 roles de Becas porque le faltaban Coordinador
       Regional y Referente. Se arregla corriendo `seed_datos_base` (o `seed_becas`)
       una vez; se evita no recortando la lista.

   !!! danger "Por qué no hay un comando que lo cree solo"
       Existía `crear_superadmin`, con usuario y contraseña **escritos en el
       código** (`admin` / una contraseña conocida), y corría en el bootstrap de
       **cualquier** ambiente. Se retiró el 11/08/2026: dejaba un superusuario con
       credencial pública en todo entorno servido, incluido uno expuesto a
       internet. Si algún ambiente lo tuvo, **hay que cambiarle la contraseña a ese
       usuario**: borrar el comando no cambia lo ya creado.

## Deploy a producción

Esto es **icore-srv**, que se despliega a mano. Los entornos de ECOM (testing y
producción) se despliegan solos desde su GitLab: ver [`espejo-ecom.md`](espejo-ecom.md).

```bash
# 1. Asegurarse de estar en main actualizado (icore trabaja sobre `main`)
git checkout main
git pull origin main

# 2. Ejecutar script de deploy
./scripts/deploy_prod.sh
```

El script `deploy_prod.sh` **no** construye ni publica imágenes en ningún registry: hace
el build local de compose y recrea los servicios en la misma máquina. Lo que hace, en
orden:

1. Verifica que el árbol esté limpio y guarda un respaldo en `deploy_backups/<ts>/`
   (compose resuelto, `.env.production`, `nginx.conf`, settings y el commit anterior).
2. Anota cuántas migraciones figuran aplicadas **antes** de tocar nada, con el contenedor
   viejo todavía arriba.
3. `docker compose up -d --build --force-recreate`.
4. Espera a que `GET /health/ready/` conteste (readiness: toca la base y, en `prd`, el
   cache de sesiones). **No** es `/health/`, que devuelve 200 con la base caída.
5. Corre los *post-deploy checks*: `migrate --check`, el manifest de estáticos con más de
   50 entradas y `GET /login/` = 200.
6. Si algo de 4 o 5 falla, imprime los logs y **vuelve el código** al commit anterior,
   creando la rama `rollback/<ts>` (nunca detached HEAD).

**El rollback automático se aborta solo** si el deploy alcanzó a aplicar migraciones:
volver el código deja el esquema adelantado y las filas a medias, y de ahí se sale con el
runbook de abajo, que empieza por el dump. El script lo dice y sale con error en vez de
improvisar.

Variables útiles: `ROLLBACK_ON_FAIL=0` (no vuelve solo), `PULL_BEFORE_DEPLOY=1`,
`HEALTH_URL`, `LOGIN_URL`, `APP_SERVICE`, `MANIFEST_MINIMO`.

Después de recrear `web` o `websocket` hay que **reiniciar nginx**: cachea la IP del
upstream al arrancar y, si no, aparecen 500 por *«Missing staticfiles manifest entry»*.

### Checklist pre-deploy

- [ ] Tests pasando en CI
- [ ] Migraciones revisadas (sin operaciones destructivas sin respaldo)
- [ ] **Dump de la base** si el deploy trae migraciones (paso D.0 del runbook)
- [ ] Variables de entorno de producción actualizadas si hubo cambios
- [ ] Anotado de qué release se viene: el **tag `release-AAAA.MM.DD-<short>`** de `main`
      que corresponde a lo que está corriendo hoy (`git describe --tags --abbrev=0
      --match 'release-*'`). Es a lo que se vuelve si hay que volver
- [ ] Notificar al equipo en el canal correspondiente

### Si el arranque se frena con «django_migrations y el esquema no se corresponden»

El entrypoint corre `manage.py verificar_esquema_migraciones` antes del `migrate`
(OPS-01). Si aborta, **no** se saltea con `SKIP_SCHEMA_GUARD=true` y **nunca** se usa
`--fake`: el mensaje dice cuál de los tres casos es.

- *Filas sin archivo*: el registro tiene migraciones que el código desplegado no tiene.
  Pasa cuando una rama renumeró migraciones. Es el estado conocido de icore-srv, y su
  reparación está escrita en [`core/sql/2026-10-06_renombrar_migraciones_icore.sql`](../../core/sql/2026-10-06_renombrar_migraciones_icore.sql).
- *Tablas que ya existen*: viene de un restore encima de una base que tenía más tablas.
  Se borran esas tablas antes de desplegar (nunca `--fake`).
- *Tablas huérfanas* (solo aviso): restos de una reversa que se cortó. No frena el
  arranque; se limpian con el runbook en la mano.

## Cron del host (icore-srv)

Hay trabajo periódico que **no** corre dentro de la app: lo dispara el cron del
usuario `icore` en el host, siempre con el mismo patrón —
`docker exec chaco-web-1 python manage.py <comando>` y log en `~/cron-chaco.log`.

Los snippets están versionados en [`docker/cron/`](../../docker/cron/), con la
explicación de cada uno en su cabecera. Se instalan **una sola vez** por servidor:
no viajan con el deploy, así que un servidor nuevo (o un `crontab` que se pierda)
los necesita de nuevo a mano.

| Comando | Horario | Qué pasa si no corre |
|---|---|---|
| `generar_alertas` | horario | No se generan las alertas de legajos |
| `procesar_vencimientos` | 03:10 | Convocatorias vencidas quedan abiertas y sus relevamientos no pasan a revisión |
| `limpiar_alertas_conversaciones` | 03:30 | Se acumulan alertas de conversaciones ya resueltas |
| `sincronizar_programas_siis` | 04:00 | **Una baja de programa en SIIS no se detecta**: el segmento sigue operando como si el programa estuviera vigente |

Instalación:

```bash
# En el host, como usuario icore (NUNCA con sudo su: la sesión de docker/git es de icore)
crontab -e
# pegar las líneas de los .cron de docker/cron/, y verificar:
crontab -l
```

### Al agregar un comando periódico nuevo

1. Versionar el snippet en `docker/cron/<comando>.cron` con su cabecera explicativa.
2. Sumarlo a la tabla de arriba.
3. Instalarlo en el host (paso manual, no lo hace el deploy).

**No** lo agregues a `LOCAL_OPTIONAL_BOOTSTRAP_COMMANDS` de `docker-compose.prod.yml`
salvo que el comando no pueda fallar. El `docker-entrypoint.sh` corre con `set -eu`
y sin tolerancia a fallos, así que un comando de bootstrap que termine con error
**deja el contenedor sin arrancar**. Ese es el motivo por el que
`procesar_vencimientos` (puro trabajo local sobre la base) sí está en el bootstrap
y `sincronizar_programas_siis` (depende de un servicio externo) no: una caída de
ECOM tiraría abajo el arranque de `web`.

## Rollback

Runbook completo. Se sigue en orden: **D.0** se hace antes del deploy, y si después hay
que volver atrás, **D.1** dice cuál de los tres caminos corresponde. El que no está en
la tabla —«revertir migraciones con `migrate <app> <anterior>`»— no es un camino: en
MariaDB deja el esquema a mitad y la base sin corresponder a ninguna release.

**D.0 · Antes de cada deploy con migración (obligatorio).**

En icore-srv, como usuario `icore` (nunca con `sudo su`):

```bash
mkdir -p ~/backups
# Las comillas simples son a propósito: MYSQL_ROOT_PASSWORD y DATABASE_NAME los resuelve
# el contenedor (los trae de .env.production), no la shell del host, que no los tiene.
docker compose -f docker-compose.prod.yml exec -T mysql \
  sh -c 'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction --routines --triggers "$DATABASE_NAME"' \
  | gzip > ~/backups/chaco-$(date +%Y%m%d_%H%M%S)-pre-deploy.sql.gz
ls -lh ~/backups/ | tail -3          # verificar que el archivo existe y no pesa 0
```

En ECOM el dump lo hacen ellos: se pide **por escrito** y se espera la confirmación
**antes** de espejar a `main` (que despliega producción automáticamente).

En los dos casos se anota, antes de empezar: de qué release se viene (tag o SHA de
`main`) y cuál es la última migración aplicada.

```bash
docker exec chaco-web-1 python manage.py showmigrations --plan | grep '\[X\]' | tail -1
```

**D.1 · Qué rollback corresponde.**

| Situación | Qué hacer |
|---|---|
| El deploy no traía migraciones | D.2 (solo código) |
| Traía solo migraciones *expand* (columna nueva, tabla nueva, índice nuevo), aplicadas OK | D.2, previa verificación D.2.0 |
| Traía *contract* (borrar o renombrar), datos destructivos o una **barrera de reversa** | D.4 (restore). **No** intentar `migrate <app> <anterior>` |
| El `migrate` falló a mitad **hacia adelante**, dentro de una sola migración | D.3 primero, y recién después decidir |
| El `migrate` falló durante una **reversa** | D.4 directo: la base ya quedó a mitad |

**D.2 · Rollback de código.**

**D.2.0 ·** Antes de bajar la release, listar las columnas `NOT NULL` sin default que la
release nueva agregó: el código viejo no las manda en el `INSERT` y, con
`STRICT_TRANS_TABLES`, MariaDB rechaza **toda alta** con
*«Field … doesn't have a default value»* (el backoffice de lectura sigue andando, así
que el síntoma llega por el territorial y no por el monitoreo).

```sql
SELECT TABLE_NAME, COLUMN_NAME FROM information_schema.COLUMNS
 WHERE TABLE_SCHEMA = DATABASE() AND IS_NULLABLE = 'NO'
   AND COLUMN_DEFAULT IS NULL AND EXTRA NOT LIKE '%auto_increment%'
   AND TABLE_NAME IN ('programas_formulario', 'legajos_ciudadano', 'programas_padronhabilitado');
```

A cada columna que **no existía** en la release de destino:
`ALTER TABLE <tabla> ALTER COLUMN <columna> SET DEFAULT '<valor>';` — es solo metadata,
es instantáneo y se revierte con `DROP DEFAULT`.

**D.2.1 · ECOM (Kubernetes).** Con tag inmutable de imagen,
`kubectl set image deploy/<web> web=…:<sha anterior>` (segundos). Sin tag —hoy el
pipeline publica siempre `:latest`— hay que hacer `git revert` del commit de alineación
en `ecom/main`, esperar el build (5-7 min) y `kubectl rollout restart`.
**`kubectl rollout undo` no sirve:** las dos revisiones apuntan a la misma `:latest`.
Se verifica con un alta de caso de prueba, no con `/health/` —que da 200 con la base
caída— sino con `/health/ready/` y una pantalla real.

El tag de imagen por commit es **D-RED-02**, lo tiene que aplicar ECOM en su
`.gitlab-ci.yml` y está redactado en
[`propuesta-ecom-verify.md`](propuesta-ecom-verify.md) §2, pendiente de que lo mande el
PM. Mientras tanto, el SHA a pedirles es el del tag `release-*` de nuestro `main`.

**D.2.2 · icore-srv.** El checkout de `/home/icore/chaco` está en **`main`** —la rama de
release— y se adelanta con `git pull --ff-only origin main`; `development` no se
despliega en ningún servidor. Se trabaja como usuario `icore`, nunca con `sudo su`.

```bash
cd /home/icore/chaco
git fetch origin main --tags
# «La release anterior» tiene nombre desde el Cambio 153 (RED-16): cada publicación
# deja un tag `release-AAAA.MM.DD-<short>` sobre el commit de `main`.
git tag --list 'release-*' --sort=-creatordate | head -5
# NO: git reset --hard sobre main. El próximo `git pull --ff-only origin main` lo
# devuelve a la release rota sin que nadie se entere. Una rama propia deja el
# rollback visible en `git status` y no pisa main.
git switch --force-create "rollback/$(date +%Y%m%d_%H%M%S)" <TAG_O_SHA_ANTERIOR>
docker compose -f docker-compose.prod.yml up -d --build --force-recreate web
docker compose -f docker-compose.prod.yml restart nginx   # cachea la IP del upstream
```

Es lo mismo que hace el rollback automático de `deploy_prod.sh`, que además **se aborta
solo** si el deploy ya había aplicado migraciones: en ese caso el camino es D.4, no este.

Para volver al flujo normal una vez publicada la release corregida:
`git switch main && git pull --ff-only origin main` y el deploy de siempre.

**D.3 · `migrate` cortado hacia adelante.** No reintentar el deploy y **nunca** usar
`--fake`: marcar como aplicada una migración que no corrió deja el esquema y
`django_migrations` discrepando para siempre, y el próximo deploy falla en otro lado.
Se diagnostica con `showmigrations --plan` y comparando `sqlmigrate <app> <NNNN>` contra
`SHOW CREATE TABLE`; se completan a mano **solo** las operaciones que falten de *esa*
migración y recién entonces se inserta su fila en `django_migrations`. Si falta más de
una operación, o hay dudas: D.4.

**D.4 · Restore.** Es el camino obligatorio para *contract*, datos borrados y barreras de
reversa. Son barreras de reversa, por pérdida de datos, `programas.0032`,
`programas.0056` y `programas.0069`; y por los UUID de MariaDB, `programas.0047`,
`programas.0048`, `programas.0073`, `legajos.0007` y `users.0023`. Las ocho abortan solas
con un mensaje que apunta acá si alguien intenta revertirlas: las cinco de UUID solo en
MySQL/MariaDB (fuera de ahí su ida ya era un no-op) y las tres de datos en cualquier
motor.

1. Bajar la app (`kubectl scale --replicas=0`, o `docker compose -f docker-compose.prod.yml stop web websocket`).
2. `DROP DATABASE` + `CREATE DATABASE` + restore del dump de D.0. **Nunca restaurar
   encima:** deja tablas huérfanas de la release nueva y el deploy siguiente muere con
   *«Table already exists»*.
3. Si el dump viene de otro motor, re-normalizar los UUID antes de levantar.
4. Desplegar la release anterior y verificar que la última migración `[X]` sea la de esa
   release.
5. Levantar y verificar con un alta real.
6. Registrar qué datos se perdieron entre el dump y el rollback.

**D.5 · Después, siempre.** Issue en GitHub con label `incident`, y una línea en la
sección `## Reversión` de la entrada de [`requerimientos.md`](requerimientos.md)
correspondiente con lo que pasó de verdad al revertir.

## Gestión de incidentes

### Severidades

| Nivel | Descripción | Tiempo de respuesta |
|---|---|---|
| P1 | Sistema caído o datos comprometidos | Inmediato |
| P2 | Funcionalidad crítica degradada | < 2 horas |
| P3 | Bug con workaround disponible | Próximo sprint |

### Pasos ante un incidente P1/P2

1. Notificar en el canal del equipo con descripción del problema
2. Revisar logs: `docker compose -f docker-compose.prod.yml logs -f web` (el servicio se
   llama `web`; `django` no existe en el compose)
3. Evaluar rollback si el problema es post-deploy
4. Abrir issue en GitHub con label `incident` documentando causa y resolución

## Gestión de migraciones en producción

- **El dump de D.0 es obligatorio** antes de cualquier deploy con migración, con el
  comando escrito arriba y el archivo verificado. «Hacer backup» sin comando no es un
  procedimiento: no hay ningún `mysqldump` automático en el repo.
- Un `ALTER TABLE` sobre una tabla grande (`programas_formulario` ronda los 283 MB,
  `legajos_ciudadano`, `programas_adjuntoformulario`) se ensaya antes en el banco de
  [`scripts/perf_mysql/`](../../scripts/perf_mysql/) y se planifica en horario de bajo
  tráfico.
- **`--fake` no se usa.** Ni para destrabar un deploy ni para «ponerse al día»: deja el
  esquema y `django_migrations` discrepando, y el próximo deploy falla en otro lado. Si
  el `migrate` quedó cortado, el camino es D.3; si fue durante una reversa, D.4.
- **Las migraciones no se revierten en producción.** El camino de vuelta es el restore de
  D.4, y ahí está la lista completa de las que directamente no tienen reversa segura. Las
  ocho llevan la marca `# BARRERA-DE-REVERSA:` en su archivo y abortan con un mensaje
  explícito **antes** de tocar la base si alguien lo intenta.
- **Toda migración de datos declara qué se pierde al revertirla.** Si su reversa no
  deshace nada, arriba va `# REVERSA-NOOP: <qué dato queda inconsistente>`; un
  `RemoveField`/`DeleteModel`/`RenameField`/`RenameModel` lleva `# CONTRACT: <dejó de
  leerse en la release X>`, y una columna nueva `NOT NULL` nace con `DEFAULT` en la base o
  con `# ROLLBACK-OK: <motivo>`. Lo verifica `scripts/check_migraciones.py`, que corre en
  el job `Migration Check` del CI sobre las migraciones nuevas del PR.
- Si la migración que se va a desplegar es barrera de reversa, **se dice en el aviso de
  deploy**: a partir de ahí solo se vuelve con restore.
- El esquema se mueve siempre primero y nunca hacia atrás dentro de la misma release
  (*expand* en la release N, *contract* recién en N+2, cuando ninguna release viva lee la
  columna).
