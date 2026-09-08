#!/bin/sh
set -eu

wait_for_database() {
  echo "Esperando base de datos..."
  until python manage.py shell -c "from django.db import connection; connection.ensure_connection(); print('db-ready')" >/dev/null 2>&1; do
    sleep 2
  done
  echo "Base de datos disponible."
}

run_management_commands() {
  if [ -z "$1" ]; then
    return 0
  fi

  for command_name in $1; do
    echo "Ejecutando python manage.py ${command_name}"
    python manage.py "${command_name}"
  done
}

run_bootstrap() {
  wait_for_database

  if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    echo "Aplicando migraciones..."
    python manage.py migrate --run-syncdb --noinput
  fi

  # En un ambiente servido (prd/qa) los estaticos se recolectan por defecto: sin
  # el manifest, cualquier template con {% static %} responde 500. En dev queda
  # apagado para no alargar cada arranque.
  collect_default="false"
  case "${ENVIRONMENT:-dev}" in
    prd|qa) collect_default="true" ;;
  esac
  if [ "${RUN_COLLECTSTATIC:-$collect_default}" = "true" ]; then
    echo "Recolectando archivos estaticos..."
    python manage.py collectstatic --noinput
  fi

  # El bootstrap NO crea usuarios: siembra roles, capacidades y programas. El
  # superusuario se crea a mano con `createsuperuser`, con las credenciales que
  # defina quien monta el ambiente (antes existia un `crear_superadmin` con usuario
  # y contrasena escritos en el codigo, que se ejecutaba en cualquier ambiente).
  if [ "${LOCAL_BOOTSTRAP_COMMANDS:-seed_datos_base crear_programas}" != "false" ]; then
    run_management_commands "${LOCAL_BOOTSTRAP_COMMANDS:-seed_datos_base crear_programas}"
  fi

  if [ -n "${LOCAL_OPTIONAL_BOOTSTRAP_COMMANDS:-}" ]; then
    echo "Ejecutando bootstrap opcional..."
    run_management_commands "${LOCAL_OPTIONAL_BOOTSTRAP_COMMANDS}"
  fi
}

# Modo one-shot para Kubernetes: un initContainer o Job con args ["bootstrap"]
# corre migraciones + estaticos + sembrado y termina, dejando que el contenedor
# principal arranque el server con el comando que quiera.
if [ "${1:-}" = "bootstrap" ]; then
  echo "Modo bootstrap (one-shot): migraciones, estaticos y sembrado."
  run_bootstrap
  echo "Bootstrap listo. Fin del modo one-shot."
  exit 0
fi

if [ "$#" -gt 0 ]; then
  echo "Comando personalizado detectado: $*"
  echo "ATENCION: se saltean migraciones, estaticos y sembrado. Si nada mas los corre"
  echo "(p. ej. un initContainer con el argumento 'bootstrap'), la app queda con el"
  echo "esquema atrasado y roles faltantes."
  exec "$@"
fi

echo "Iniciando entorno de DATAÑACH..."
run_bootstrap

APP_BIND="${APP_BIND:-0.0.0.0}"
APP_PORT="${APP_PORT:-8000}"
APP_RUNTIME="${APP_RUNTIME:-runserver}"

if [ "${APP_RUNTIME}" = "runserver" ]; then
  echo "Bootstrap listo. Iniciando Django runserver con autoreload en ${APP_BIND}:${APP_PORT}..."
  exec python manage.py runserver "${APP_BIND}:${APP_PORT}"
fi

if [ "${APP_RUNTIME}" = "gunicorn" ]; then
  # HTTP en varios procesos WSGI para usar todos los nucleos: daphne es un solo
  # proceso y el GIL lo limita a uno. Los websockets NO pasan por aca: los
  # atiende otro contenedor/pod con daphne, y nginx o el ingress enrutan /ws/
  # hacia el. Por eso WEBSOCKETS_ENABLED no se deduce y hay que declararla.
  GUNICORN_WORKERS="${GUNICORN_WORKERS:-3}"
  GUNICORN_THREADS="${GUNICORN_THREADS:-2}"
  GUNICORN_TIMEOUT="${GUNICORN_TIMEOUT:-120}"
  GUNICORN_MAX_REQUESTS="${GUNICORN_MAX_REQUESTS:-1000}"
  if [ -z "${WEBSOCKETS_ENABLED:-}" ]; then
    echo "AVISO: con APP_RUNTIME=gunicorn el chat en vivo queda apagado salvo que exista"
    echo "un servicio daphne para /ws/ y se defina WEBSOCKETS_ENABLED=True."
  fi
  echo "Bootstrap listo. Iniciando gunicorn (${GUNICORN_WORKERS} workers x ${GUNICORN_THREADS} hilos) en ${APP_BIND}:${APP_PORT}..."
  exec gunicorn config.wsgi:application \
    --bind "${APP_BIND}:${APP_PORT}" \
    --workers "${GUNICORN_WORKERS}" \
    --threads "${GUNICORN_THREADS}" \
    --timeout "${GUNICORN_TIMEOUT}" \
    --graceful-timeout 30 \
    --max-requests "${GUNICORN_MAX_REQUESTS}" \
    --max-requests-jitter 100 \
    --log-file -
fi

echo "Bootstrap listo. Iniciando Daphne en ${APP_BIND}:${APP_PORT}..."
exec daphne -b "${APP_BIND}" -p "${APP_PORT}" config.asgi:application
