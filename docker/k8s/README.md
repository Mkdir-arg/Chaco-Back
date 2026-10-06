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
- **Archivos subidos**: con `SERVE_MEDIA=True` la app también sirve `/media/`.
  `MEDIA_ROOT` (`/app/media`) **tiene que ser un volumen persistente**: ahí viven
  los adjuntos que cargan los territoriales.
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
| Job `args: ["bootstrap"]` (`bootstrap-job.yaml`), y `RUN_MIGRATIONS=false` en todos los Deployments | **Siempre**. Es la única forma con `replicas > 1` |

Con el Job, el orden del deploy es: aplicar el Job con la imagen nueva, esperar a
que termine (`kubectl wait --for=condition=complete`) y recién entonces
`kubectl set image` del Deployment. Si el Job falla, el rollout **no** se hace: el
runbook es el Anexo D de `docs/internal/processes.md`.

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
