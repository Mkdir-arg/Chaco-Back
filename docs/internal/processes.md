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
| **SIIS** | `SIIS_API_CLIENT_ID`, `SIIS_API_CLIENT_SECRET` · con default: `SIIS_API_URL`, timeouts | **ECOM** | el select de «Programa SIIS» queda vacío y no se pueden crear ni vincular segmentos |
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
| `SERVE_MEDIA` | `True` cuando no hay un nginx sirviendo `/media/` | archivos adjuntos accesibles |
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

```bash
# 1. Asegurarse de estar en main actualizado
git checkout main
git pull origin main

# 2. Ejecutar script de deploy
./scripts/deploy_prod.sh
```

El script `deploy_prod.sh` realiza:
1. Build de la imagen Docker
2. Push al registry
3. Restart del servicio en el servidor

### Checklist pre-deploy

- [ ] Tests pasando en CI
- [ ] Migraciones revisadas (sin operaciones destructivas sin respaldo)
- [ ] Variables de entorno de producción actualizadas si hubo cambios
- [ ] Notificar al equipo en el canal correspondiente

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

Si el deploy falla o hay un error crítico en producción:

```bash
# Volver a la imagen anterior
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d --no-build
# (ajustar tag de imagen según el caso)
```

Para rollback de migraciones:
```bash
docker compose exec django python manage.py migrate <app> <migration_anterior>
```

## Gestión de incidentes

### Severidades

| Nivel | Descripción | Tiempo de respuesta |
|---|---|---|
| P1 | Sistema caído o datos comprometidos | Inmediato |
| P2 | Funcionalidad crítica degradada | < 2 horas |
| P3 | Bug con workaround disponible | Próximo sprint |

### Pasos ante un incidente P1/P2

1. Notificar en el canal del equipo con descripción del problema
2. Revisar logs: `docker compose logs -f django`
3. Evaluar rollback si el problema es post-deploy
4. Abrir issue en GitHub con label `incident` documentando causa y resolución

## Gestión de migraciones en producción

- Siempre hacer backup de la base antes de migraciones que alteran tablas grandes
- Migraciones con `ALTER TABLE` en tablas > 100k filas deben planificarse en horario de bajo tráfico
- Usar `--fake` solo si se está seguro de que el esquema ya está aplicado manualmente
