#!/bin/sh
set -eu

echo "Iniciando entorno local de SistemSo..."

if [ "$#" -gt 0 ]; then
  echo "Comando personalizado detectado: $*"
  exec "$@"
fi

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

wait_for_database

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "Aplicando migraciones..."
  python manage.py migrate --run-syncdb --noinput
fi

if [ "${RUN_COLLECTSTATIC:-false}" = "true" ]; then
  echo "Recolectando archivos estaticos..."
  python manage.py collectstatic --noinput
fi

if [ "${LOCAL_BOOTSTRAP_COMMANDS:-crear_superadmin seed_datos_base crear_programas}" != "false" ]; then
  run_management_commands "${LOCAL_BOOTSTRAP_COMMANDS:-crear_superadmin seed_datos_base crear_programas}"
fi

if [ -n "${LOCAL_OPTIONAL_BOOTSTRAP_COMMANDS:-}" ]; then
  echo "Ejecutando bootstrap opcional..."
  run_management_commands "${LOCAL_OPTIONAL_BOOTSTRAP_COMMANDS}"
fi

APP_BIND="${APP_BIND:-0.0.0.0}"
APP_PORT="${APP_PORT:-8000}"
APP_RUNTIME="${APP_RUNTIME:-runserver}"

if [ "${APP_RUNTIME}" = "runserver" ]; then
  echo "Bootstrap listo. Iniciando Django runserver con autoreload en ${APP_BIND}:${APP_PORT}..."
  exec python manage.py runserver "${APP_BIND}:${APP_PORT}"
fi

echo "Bootstrap listo. Iniciando Daphne en ${APP_BIND}:${APP_PORT}..."
exec daphne -b "${APP_BIND}" -p "${APP_PORT}" config.asgi:application
