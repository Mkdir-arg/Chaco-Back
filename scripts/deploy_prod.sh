#!/usr/bin/env bash
set -Eeuo pipefail

# Deploy script for production (icore-srv)
# - Optional git pull
# - Backup of key files + resolved compose
# - Recreate/build services
# - Readiness check with retries + post-deploy checks
# - Rollback of the CODE to the previous commit on failure, aborted if the deploy
#   already applied migrations (volver la base es decision humana: runbook D de
#   docs/internal/processes.md)
#
# RED-59 / OPS-04. Lo que cambio el Cambio 153 y por que:
#   * HEALTH_URL apuntaba a /health/, que responde 200 con la base caida: el criterio
#     de exito --y el del rollback automatico-- no distinguia «vivo» de «sirve», asi que
#     el rollback no se disparaba nunca por un esquema roto o un collectstatic fallido.
#     Ahora es /health/ready/, que toca la base y el cache de sesiones.
#   * `git checkout --force <sha>` dejaba detached HEAD y el `git pull --ff-only` del
#     deploy siguiente fallaba. Ahora el rollback crea la rama `rollback/<timestamp>`.
#   * El rollback volvia el codigo y nunca la base. Si el deploy aplico migraciones,
#     el contenedor viejo arranca contra un esquema adelantado (RED-14): eso se aborta
#     y se manda al runbook, que empieza por el dump.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env.production}"
HEALTH_URL="${HEALTH_URL:-http://localhost/health/ready/}"
LOGIN_URL="${LOGIN_URL:-http://localhost/login/}"
HEALTH_RETRIES="${HEALTH_RETRIES:-30}"
HEALTH_DELAY_SECONDS="${HEALTH_DELAY_SECONDS:-5}"
ROLLBACK_ON_FAIL="${ROLLBACK_ON_FAIL:-1}"
PULL_BEFORE_DEPLOY="${PULL_BEFORE_DEPLOY:-0}"
APP_SERVICE="${APP_SERVICE:-web}"
# Hoy el manifest tiene ~1.400 entradas. 50 es el piso que separa «collectstatic
# corrio» de «el archivo existe pero esta vacio», que es el caso que deja cada
# template con {% static %} en 500 (Missing staticfiles manifest entry).
MANIFEST_MINIMO="${MANIFEST_MINIMO:-50}"

cd "$APP_DIR"

log() { printf '[deploy] %s\n' "$*"; }
err() { printf '[deploy][error] %s\n' "$*" >&2; }

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    err "Missing required command: $1"
    exit 1
  fi
}

require_cmd docker
require_cmd git
require_cmd curl

if ! docker compose version >/dev/null 2>&1; then
  err "Docker Compose plugin is required (docker compose ...)"
  exit 1
fi

if [ ! -f "$COMPOSE_FILE" ]; then
  err "Compose file not found: $COMPOSE_FILE"
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  err "Env file not found: $ENV_FILE"
  exit 1
fi

if [ "$PULL_BEFORE_DEPLOY" = "1" ]; then
  log "Pulling latest changes from git..."
  git pull --ff-only
fi

if [ -n "$(git status --porcelain)" ]; then
  err "Working tree is not clean. Commit/stash changes before deploy."
  exit 1
fi

PREV_COMMIT="$(git rev-parse HEAD)"
log "Current commit: $PREV_COMMIT"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$APP_DIR/deploy_backups/$TIMESTAMP"
mkdir -p "$BACKUP_DIR"

log "Saving deployment backup to $BACKUP_DIR"
cp "$COMPOSE_FILE" "$BACKUP_DIR/"
cp "$ENV_FILE" "$BACKUP_DIR/"
[ -f "nginx.conf" ] && cp "nginx.conf" "$BACKUP_DIR/"
[ -f "config/settings.py" ] && cp "config/settings.py" "$BACKUP_DIR/settings.py"
[ -f "config/settings_production.py" ] && cp "config/settings_production.py" "$BACKUP_DIR/settings_production.py"
docker compose -f "$COMPOSE_FILE" config > "$BACKUP_DIR/compose.resolved.yml"
printf '%s\n' "$PREV_COMMIT" > "$BACKUP_DIR/previous_commit.txt"

en_la_app() {
  docker compose -f "$COMPOSE_FILE" exec -T "$APP_SERVICE" "$@"
}

health_check() {
  local i=1
  while [ "$i" -le "$HEALTH_RETRIES" ]; do
    if curl -fsS "$HEALTH_URL" >/dev/null; then
      log "Health check OK: $HEALTH_URL"
      return 0
    fi
    log "Health check failed ($i/$HEALTH_RETRIES), retrying in ${HEALTH_DELAY_SECONDS}s..."
    sleep "$HEALTH_DELAY_SECONDS"
    i=$((i + 1))
  done
  return 1
}

# RED-59: un 200 en /health/ready/ dice que la base contesta; no dice que el esquema
# este al dia ni que los estaticos esten. Estas tres son las que fallaron de verdad en
# este sistema: migracion a medias, collectstatic sin manifest (nginx cacheando la IP
# vieja del upstream) y la pantalla de login en 500 por lo anterior.
post_deploy_checks() {
  local pendientes manifest codigo

  log "Post-deploy: migraciones al dia..."
  if ! en_la_app python manage.py migrate --check >/dev/null 2>&1; then
    pendientes="$(en_la_app python manage.py showmigrations --plan 2>/dev/null | grep -c '^\[ \]' || true)"
    err "Quedan migraciones sin aplicar (${pendientes:-?}): el esquema no es el de esta release."
    return 1
  fi

  log "Post-deploy: manifest de estaticos..."
  manifest="$(en_la_app python -c \
    "import json;d=json.load(open('/app/staticfiles/staticfiles.json'));print(len(d.get('paths',d)))" \
    2>/dev/null || true)"
  if [ -z "$manifest" ] || [ "$manifest" -lt "$MANIFEST_MINIMO" ] 2>/dev/null; then
    err "staticfiles.json con ${manifest:-0} entradas (minimo $MANIFEST_MINIMO): cada {% static %} va a dar 500."
    return 1
  fi
  log "Post-deploy: manifest OK ($manifest entradas)."

  log "Post-deploy: pantalla de login..."
  codigo="$(curl -fsS -o /dev/null -w '%{http_code}' "$LOGIN_URL" || true)"
  if [ "$codigo" != "200" ]; then
    err "GET $LOGIN_URL devolvio ${codigo:-sin respuesta}, no 200."
    return 1
  fi

  log "Post-deploy checks OK."
  return 0
}

# Cuantas migraciones figuran aplicadas ahora mismo. Vacio = no se pudo averiguar
# (el contenedor no esta levantado todavia, o ya no responde).
migraciones_aplicadas() {
  en_la_app python manage.py showmigrations --plan 2>/dev/null | grep -c '^\[X\]' || true
}

rollback() {
  local ahora
  if [ "$ROLLBACK_ON_FAIL" != "1" ]; then
    err "Rollback disabled (ROLLBACK_ON_FAIL=$ROLLBACK_ON_FAIL)."
    return 1
  fi

  # RED-59: el rollback de este script vuelve el CODIGO y nunca la base. Si el deploy
  # alcanzo a aplicar migraciones, el contenedor viejo arranca contra un esquema
  # adelantado: columnas NOT NULL que su codigo no escribe, filas a medias. Volver de
  # ahi necesita el dump de D.0 y una persona decidiendo que se pierde.
  ahora="$(migraciones_aplicadas)"
  if [ -n "$MIGRACIONES_ANTES" ] && [ -n "$ahora" ] && [ "$ahora" -gt "$MIGRACIONES_ANTES" ]; then
    err "ABORTADO: el deploy aplico $((ahora - MIGRACIONES_ANTES)) migracion(es)."
    err "Volver solo el codigo dejaria el esquema adelantado (RED-14)."
    err "Seguir el runbook de rollback: docs/internal/processes.md, Anexo D (empieza por el dump)."
    err "Commit anterior: $PREV_COMMIT"
    return 1
  fi
  if [ -z "$ahora" ] || [ -z "$MIGRACIONES_ANTES" ]; then
    err "AVISO: no se pudo comparar el estado de las migraciones; revisar el runbook (processes.md, Anexo D)."
  fi

  err "Starting rollback to commit $PREV_COMMIT ..."
  # `git checkout --force` dejaba detached HEAD y el `git pull --ff-only` del deploy
  # siguiente fallaba sin explicar por que. Una rama con nombre deja el rastro.
  git switch --force-create "rollback/$TIMESTAMP" "$PREV_COMMIT"
  docker compose -f "$COMPOSE_FILE" up -d --build --force-recreate

  if health_check; then
    log "Rollback completed successfully (rama rollback/$TIMESTAMP)."
    return 0
  fi

  err "Rollback failed. Manual intervention required."
  return 1
}

log "Validating compose config..."
docker compose -f "$COMPOSE_FILE" config >/dev/null

# Antes de tocar nada, con el contenedor viejo todavia arriba: es la unica foto
# confiable de que migraciones estaban aplicadas antes de esta release (ver rollback()).
MIGRACIONES_ANTES="$(migraciones_aplicadas)"
log "Migraciones aplicadas antes del deploy: ${MIGRACIONES_ANTES:-desconocido}"

log "Deploying services..."
docker compose -f "$COMPOSE_FILE" up -d --build --force-recreate

log "Waiting for service readiness..."
if health_check && post_deploy_checks; then
  log "Deploy completed successfully."
  exit 0
fi

err "Deploy failed health checks."
docker compose -f "$COMPOSE_FILE" ps || true
docker compose -f "$COMPOSE_FILE" logs --tail=200 web websocket nginx || true

rollback
