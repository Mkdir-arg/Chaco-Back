# Referencia para desplegar la imagen en Kubernetes

Plantillas mínimas para correr DATAÑACH en Kubernetes. **No son manifiestos
listos**: cada plataforma les pone su imagen, sus secrets y su ingress. Existen
para que las decisiones que la imagen ya tomó no haya que redescubrirlas.

La guía completa (variables, sembrado, superusuario, verificación) está publicada
en la documentación del proyecto, sección *Si el despliegue es en Kubernetes*.

## Lo que la imagen resuelve sola

- **Entrypoint**: al arrancar sin argumentos corre migraciones, recolecta estáticos
  (por defecto en `ENVIRONMENT=prd|qa`) y siembra roles/programas/catálogos, y
  recién después levanta el server (daphne con `APP_RUNTIME=daphne`: HTTP y
  websockets en el mismo proceso; ver *HTTP en varios procesos* para la
  alternativa con gunicorn). Con más de una réplica eso hay que apagarlo
  (`RUN_MIGRATIONS=false`): ver *Quién corre `migrate`*.
- **Estáticos**: los sirve la propia app (whitenoise). No hace falta sidecar.
- **Archivos subidos**: `/media/` lo sirve siempre la app, detrás de sesión y
  verificando de quién es cada archivo (SEC-09); no hay flag que lo apague.
  `MEDIA_ROOT` (`/app/media`) **tiene que ser un volumen persistente**: ahí viven
  los adjuntos que cargan los territoriales. Si el ingress soporta
  `X-Accel-Redirect` y expone `/protected-media/` como `internal`, con
  `MEDIA_X_ACCEL=True` la app autoriza y los bytes los manda el ingress.
  **Antes de prenderla, verificar el `location`.** Prendida contra un front que no
  lo tenga, toda descarga responde **200 con 0 bytes** —no un error—: el usuario baja
  archivos vacíos y nadie se entera. Django no puede comprobarlo (el ingress es de
  otro equipo), así que `manage.py check --deploy` solo avisa (`core.W004`) cuando la
  variable está prendida. La comprobación es manual: bajar un archivo conocido desde
  `/media/<ruta>` y confirmar que llega con contenido. El bloque es
  `location /protected-media/ { internal; alias <MEDIA_ROOT>; add_header Content-Disposition attachment; add_header X-Content-Type-Options nosniff always; }`
  (el `nginx.conf` del repo ya lo tiene). Sin confirmación, dejar la variable sin
  definir: el default entrega los bytes desde Django y es lo que corre hoy.
- **Probes**: `/health/` responde 200. Usar **startupProbe** además de
  liveness/readiness: el primer arranque tarda minutos y sin él el liveness mata
  el bootstrap (loop de reinicios con exit 137 y sin error en el log).

## Lo que pone la plataforma

- **Base de datos** (MySQL 8 recomendado; MariaDB funciona, mismo warning `W036`
  en ambos motores) y **Redis** — la app lo usa para caché y websockets, un
  `redis:7-alpine` alcanza; se apunta con `REDIS_HOST`.
- **Puertos consistentes**: `APP_PORT` (env) = `containerPort` = `targetPort`
  del Service = puerto de las probes. Se cambia uno, se cambian los cuatro.
- **PVC para `/app/media`** y el ingress con `X-Forwarded-Proto: https` y
  `Upgrade`/`Connection` en `/ws/`.

## Quién corre `migrate`: uno solo

Django **no** toma ningún candado para `migrate` en MySQL/MariaDB. Dos procesos
migrando a la vez se pisan y, si se cruzan dentro de una migración de varias
operaciones, el esquema queda a medias y **sin** fila en `django_migrations`:
medido contra MariaDB 11.8, uno de los dos muere con 1050 desde base vacía y con
1060 desde base al día. Eso no se arregla reintentando el deploy.

| Forma | Cuándo es válida |
|---|---|
| Sin `command`/`args` en el pod: el entrypoint migra en cada arranque | Solo con **`replicas: 1`** y sin rolling. Con más réplicas son N migradores |
| initContainer `args: ["bootstrap"]` (`bootstrap-initcontainer.yaml`) | Solo con **`replicas: 1`**: el initContainer corre en **cada** pod |
| Job `args: ["bootstrap"]` (`bootstrap-job.yaml`), y `RUN_MIGRATIONS=false` + `LOCAL_BOOTSTRAP_COMMANDS=false` en todos los Deployments | **Siempre**. Es la única forma con `replicas > 1` |

Con el Job, el orden del deploy es: aplicar el Job con la imagen nueva, esperar a
que termine (`kubectl wait --for=condition=complete`) y recién entonces
`kubectl set image` del Deployment. Si el Job falla, el rollout **no** se hace: el
runbook es el Anexo D de `docs/internal/processes.md`.

**La red debajo de la regla.** El entrypoint corre las migraciones y el sembrado con un
candado de base tomado (`manage.py bootstrap_lock`, un `GET_LOCK('datanach_bootstrap',
900)`), así que si la regla no se aplica —un ambiente con `replicas > 1` que todavía
arranca con el entrypoint— los pods se **esperan** en vez de pisarse. No reemplaza al Job:
el candado serializa, pero N pods migrando de a uno siguen siendo N arranques lentos, y el
Job es además lo que frena el rollout si la migración falla. `GET_LOCK` es de la conexión,
así que un pod matado a mitad del bootstrap lo suelta solo — y por eso el candado va en una
conexión **dedicada**: `loaddata` (dentro de `seed_datos_base`) cierra la conexión por
defecto al terminar, y con el candado ahí se soltaba a mitad del sembrado.

Lo que el candado **no** cubre: los comandos de `LOCAL_OPTIONAL_BOOTSTRAP_COMMANDS`, que
corren fuera y después (son idempotentes y no pueden abortar el arranque), y el rolling en
sí —dos releases distintas migrando contra el mismo esquema sigue siendo expand/contract—.

Ese mismo bloque corre con el `read_timeout` levantado a 1200 s
(`MIGRATE_DB_READ_TIMEOUT`), sin exportarlo al proceso del server: con los 10 s del
tráfico, un `ALTER` que espera el metadata lock de una tabla en uso devuelve un 2013 al
cliente y **se aplica igual** en el servidor, dejando el esquema adelantado y la migración
sin fila en `django_migrations` (OPS-05).

El Job **no monta `/app/media`**, a propósito: corre mientras los pods viejos siguen
atendiendo y tienen el PVC tomado, así que con un PVC `ReadWriteOnce` —lo normal—
quedaría en `Pending` hasta el timeout y el deploy se frenaría sin un error claro. El
bootstrap no escribe ahí (`migrate`, `collectstatic` a `/app/staticfiles` y los seeds no
tocan adjuntos). Si alguna vez hiciera falta montarlo, el PVC tiene que ser
`ReadWriteMany`. Por el mismo motivo, los Deployments llevan además
`LOCAL_BOOTSTRAP_COMMANDS=false`: el `migrate` no es lo único que repetiría cada pod.

**Expand/contract.** Durante el rolling conviven la release vieja y la nueva contra
el mismo esquema (~60 s), así que una release nunca borra ni renombra una columna
que la anterior todavía lee: eso se hace dos releases después. El gate
`# CONTRACT:` de `scripts/check_migraciones.py` lo exige en cada migración nueva, y
el job `Migrate ida y vuelta` prueba la ida y la vuelta sobre datos.

Cuando el contenedor principal define su propio `command`, el entrypoint ejecuta ese
comando y **se saltea migraciones, estáticos y sembrado**: ahí el initContainer o el
Job no son opcionales.

## Variables

Van como **env del contenedor** (Secret/ConfigMap): las del arranque
(`RUN_*`, `LOCAL_BOOTSTRAP_COMMANDS`, `APP_RUNTIME`) y `DJANGO_SETTINGS_MODULE`
las lee el script de inicio, no Django — un archivo montado no les llega. La lista
completa y quién provee cada valor: `.env.qa.example` en la raíz del repo.

Con `DJANGO_SETTINGS_MODULE=config.settings_production` la app redirige a HTTPS:
el ingress **debe** enviar `X-Forwarded-Proto: https` o las peticiones entran en
bucle de redirección.

## HTTP en varios procesos (opcional)

Daphne es **un solo proceso**: por el GIL, todo el HTTP de un pod usa un núcleo
aunque el nodo tenga más, y la latencia de una pantalla depende de lo que estén
haciendo los demás usuarios en ese momento. Dos formas de repartir la carga:

1. **Más réplicas** del Deployment actual. No cambia nada de la imagen.
2. **`APP_RUNTIME=gunicorn`** en el Deployment web: la imagen levanta gunicorn con
   `GUNICORN_WORKERS` procesos × `GUNICORN_THREADS` hilos (default 3 × 2; unos
   150–200 MB por worker, ajustar `resources.limits.memory`). Gunicorn **no sirve
   websockets**: hace falta un **segundo Deployment** con `APP_RUNTIME=daphne` y
   el ingress enrutando `/ws/` hacia su Service, más `WEBSOCKETS_ENABLED=True` en
   el Deployment web (con gunicorn no se deduce). Los dos Deployments llevan
   `RUN_MIGRATIONS=false` y el `migrate` va en el Job de `bootstrap-job.yaml`: dos
   Deployments arrancando a la vez son dos migradores (*Quién corre `migrate`*).

Un límite de CPU bajo en el pod (`resources.limits.cpu`) también alarga el login:
la verificación de la contraseña es CPU puro y se estrangula.

## Tareas programadas

Un CronJob por comando (ver `cronjobs.yaml`). `sincronizar_programas_siis` **nunca
va en el arranque del pod**: depende de un servicio externo y una caída de ese
servicio dejaría el pod sin levantar.

Los cuatro declaran `timeZone: America/Argentina/Buenos_Aires` (sin ella el `schedule`
corre en UTC y las 03:10 caen a las 00:10 ART), `activeDeadlineSeconds` y `backoffLimit:
1`. El deadline no es cosmético: con `concurrencyPolicy: Forbid` y sin él, **una corrida
colgada bloquea en silencio todas las siguientes** y el síntoma aparece una semana
después. Si el cluster es anterior a Kubernetes 1.27 no entiende `timeZone`: sacarla y
correr los horarios tres horas.
