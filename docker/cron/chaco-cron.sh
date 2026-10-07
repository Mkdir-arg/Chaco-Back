#!/bin/sh
# Envoltorio de las tareas programadas de DATAÑACH en icore-srv (G3-05).
# ---------------------------------------------------------------------------
# Las cuatro corridas periódicas eran `docker exec chaco-web-1 … >> ~/cron-chaco.log`
# a secas: sin candado (dos `generar_alertas` se solapaban si una tardaba más de una
# hora), sin límite de tiempo (un `docker exec` colgado quedaba corriendo para siempre y
# el log no decía nada), sin fecha en el log (no se podía saber cuándo corrió qué) y sin
# rotación. Este script pone las cuatro cosas en un solo lugar.
#
# INSTALACIÓN (una sola vez por servidor, como usuario `icore`):
#   cp docker/cron/chaco-cron.sh ~/chaco-cron.sh && chmod +x ~/chaco-cron.sh
# Y la rotación del log, como root:
#   cp docker/cron/logrotate-cron-chaco.conf /etc/logrotate.d/chaco-cron
#
# USO (lo invocan los .cron de esta carpeta):
#   ~/chaco-cron.sh <comando de manage.py> [límite de tiempo]
#
# Variables: CHACO_CONTENEDOR (default chaco-web-1), CHACO_CRON_LOG
# (default ~/cron-chaco.log).
#
# NO usar `sudo su`: la sesión de docker/git es del usuario icore.
set -u

COMANDO="${1:?uso: chaco-cron.sh <comando> [limite]}"
LIMITE="${2:-30m}"
CONTENEDOR="${CHACO_CONTENEDOR:-chaco-web-1}"
LOG="${CHACO_CRON_LOG:-${HOME}/cron-chaco.log}"
LOCK="/tmp/chaco-cron-${COMANDO}.lock"

# -E 99: `flock` devuelve 99 cuando NO consiguió el candado, para no confundirlo con un
# exit 1 del comando. Sin esto, «ya hay una corrida en curso» y «el comando falló» eran
# la misma línea en el log.
# `timeout` manda SIGTERM al vencer y devuelve 124.
inicio="$(date -Is)"
flock -n -E 99 "${LOCK}" timeout "${LIMITE}" \
  docker exec "${CONTENEDOR}" python manage.py "${COMANDO}" >>"${LOG}" 2>&1
codigo=$?

case "${codigo}" in
  0)
    echo "[${inicio} → $(date -Is)] ${COMANDO}: OK" >>"${LOG}"
    ;;
  99)
    echo "[${inicio}] ${COMANDO}: SALTEADA, la corrida anterior sigue en curso (${LOCK})" >>"${LOG}"
    ;;
  124)
    echo "[${inicio} → $(date -Is)] ${COMANDO}: CORTADA por timeout de ${LIMITE}" >>"${LOG}"
    ;;
  *)
    echo "[${inicio} → $(date -Is)] ${COMANDO}: FALLÓ con código ${codigo}" >>"${LOG}"
    ;;
esac

exit "${codigo}"
