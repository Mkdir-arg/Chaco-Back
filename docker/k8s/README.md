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
  websockets en el mismo proceso).
- **Estáticos**: los sirve la propia app (whitenoise). No hace falta sidecar.
- **Archivos subidos**: con `SERVE_MEDIA=True` la app también sirve `/media/`.
  `MEDIA_ROOT` (`/app/media`) **tiene que ser un volumen persistente**: ahí viven
  los adjuntos que cargan los territoriales.
- **Probes**: `/health/` responde 200.

## Las dos formas de correr el bootstrap

1. **Sin `command`/`args` en el pod** (recomendado): el entrypoint hace todo.
2. **Con comando propio**: el entrypoint ejecuta ese comando y **se saltea
   migraciones y sembrado**. En ese caso el bootstrap va aparte, como
   initContainer o Job con `args: ["bootstrap"]` (modo one-shot: corre todo y
   termina). Ver `bootstrap-initcontainer.yaml`.

## Variables

Van como **env del contenedor** (Secret/ConfigMap): las del arranque
(`RUN_*`, `LOCAL_BOOTSTRAP_COMMANDS`, `APP_RUNTIME`) y `DJANGO_SETTINGS_MODULE`
las lee el script de inicio, no Django — un archivo montado no les llega. La lista
completa y quién provee cada valor: `.env.qa.example` en la raíz del repo.

Con `DJANGO_SETTINGS_MODULE=config.settings_production` la app redirige a HTTPS:
el ingress **debe** enviar `X-Forwarded-Proto: https` o las peticiones entran en
bucle de redirección.

## Tareas programadas

Un CronJob por comando (ver `cronjobs.yaml`). `sincronizar_programas_siis` **nunca
va en el arranque del pod**: depende de un servicio externo y una caída de ese
servicio dejaría el pod sin levantar.
