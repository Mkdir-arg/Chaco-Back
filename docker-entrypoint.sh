#!/bin/sh
set -eu

# RED-45 / D-RED-08: no se arranca con workers gevent ni eventlet. `config/wsgi.py:13`
# reacciona a dos perillas --`GUNICORN_CMD_ARGS` que contenga la palabra gevent, o
# `GUNICORN_WORKER_CLASS=gevent`-- y lo que aplica entonces es `config/gevent_patch.py`,
# que pisa `BaseDatabaseWrapper.validate_thread_sharing` con una funcion vacia. O sea:
# gevent de verdad, sin `monkey.patch_all()` (mysqlclient y requests siguen bloqueando) y
# sin el unico chequeo que impide que dos greenlets compartan una conexion. El sintoma
# seria una respuesta con los datos de otra persona, intermitente y sin error en el log.
# El escenario no es hipotetico: ante los 504 del padron, probar
# GUNICORN_CMD_ARGS="--worker-class gevent" en ECOM es lo primero que sugiere internet.
# El borrado del parche y de las dependencias es OPS-13 (Ola 7); hasta entonces, se
# aborta con el motivo en vez de arrancar roto.
#
# La guarda frena SOLO gevent y eventlet. Este script es el ENTRYPOINT unico de la
# imagen --daphne, gunicorn, el Job de bootstrap y los cuatro CronJobs pasan por aca--,
# asi que abortar ante cualquier `--worker-class` dejaria sin arrancar un ambiente por un
# valor inocuo (`sync`, `gthread`). Esos avisan y siguen.
#
# En GUNICORN_CMD_ARGS la condicion es "aparece gevent o eventlet en cualquier lugar",
# que es exactamente lo que mira `wsgi.py`: eso cubre `--worker-class gevent`,
# `--worker-class=gevent`, `-k gevent` y `-k=gevent` de una, sin tener que enumerar las
# formas de gunicorn. Si la palabra aparece por otro motivo (una ruta de log que se llame
# asi), `wsgi.py` aplicaria el parche igual, asi que abortar tambien es lo correcto ahi.
guard_worker_class() {
  _cmd_args="${GUNICORN_CMD_ARGS:-}"
  _worker_class="${GUNICORN_WORKER_CLASS:-}"

  case "${_cmd_args}" in
    *gevent*|*eventlet*)
      echo "ERROR: GUNICORN_CMD_ARGS pide workers gevent/eventlet y este arranque no los" >&2
      echo "       admite (RED-45). Valor recibido: ${_cmd_args}" >&2
      echo "       Los workers de la imagen son gthread (--threads): el soporte de gevent" >&2
      echo "       activa un parche que apaga la validacion de hilos de Django y puede" >&2
      echo "       devolver datos de otra request. Sacar la variable del entorno." >&2
      exit 1
      ;;
    *--worker-class*|*-k\ *|*-k=*)
      echo "AVISO: GUNICORN_CMD_ARGS pide un --worker-class (${_cmd_args}). La imagen esta" >&2
      echo "       pensada para gthread; gevent y eventlet estan bloqueados (RED-45)." >&2
      ;;
  esac

  case "${_worker_class}" in
    gevent|eventlet)
      echo "ERROR: GUNICORN_WORKER_CLASS=${_worker_class} y este arranque no lo admite" >&2
      echo "       (RED-45). Es la segunda perilla que enciende el parche de gevent, el que" >&2
      echo "       apaga la validacion de hilos de Django. Sacar la variable del entorno." >&2
      exit 1
      ;;
    "")
      ;;
    *)
      echo "AVISO: GUNICORN_WORKER_CLASS=${_worker_class}. La imagen esta pensada para" >&2
      echo "       gthread; gevent y eventlet estan bloqueados (RED-45)." >&2
      ;;
  esac
}

guard_worker_class

# Reintenta sin limite a proposito: en Kubernetes el pod puede arrancar antes que
# la base este lista y no hay que fallar por eso. El costo es que, si la base
# nunca responde, el Job queda «Progressing» para siempre sin dar un error: si un
# bootstrap tarda mas de unos minutos, lo primero que hay que mirar es si el log
# quedo en «Esperando base de datos...».
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

  # Si se restauro un dump de produccion sobre este ambiente, las tablas que solo
  # existen aca sobreviven --el dump trae un DROP por cada tabla que el contiene,
  # y esas no estan-- mientras django_migrations vuelve al estado de produccion.
  # Entonces migrate intenta crearlas de nuevo y muere con «Table already
  # exists». Se arregla borrando esas tablas antes de desplegar, NUNCA con
  # --fake: eso deja las tablas sin las columnas de los AddField posteriores y
  # rompe en runtime en vez de en el deploy.
  #
  # OPS-01: eso dejo de ser un comentario. La guarda lo detecta ANTES del migrate y
  # aborta el arranque nombrando las tablas o las filas que no se corresponden, en vez
  # de un CrashLoop con «1050 Table already exists» y el esquema a medias. Se saltea con
  # SKIP_SCHEMA_GUARD=true, que es para el ambiente donde la guarda se equivoque, no
  # para el deploy que la guarda frena.
  if [ "${RUN_MIGRATIONS:-true}" = "true" ] && [ "${SKIP_SCHEMA_GUARD:-false}" != "true" ]; then
    echo "Verificando coherencia entre django_migrations y el esquema..."
    python manage.py verificar_esquema_migraciones
  fi

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

  # El bootstrap NO crea usuarios: siembra roles, capacidades, programas y el
  # catalogo geografico de SIIS (Cambio 85), que es idempotente y hace falta
  # para que el alta de beneficiarios resuelva provincia y localidad. El
  # superusuario se crea a mano con `createsuperuser`, con las credenciales que
  # defina quien monta el ambiente (antes existia un `crear_superadmin` con usuario
  # y contrasena escritos en el codigo, que se ejecutaba en cualquier ambiente).
  if [ "${LOCAL_BOOTSTRAP_COMMANDS:-seed_datos_base crear_programas seed_catalogo_siis}" != "false" ]; then
    run_management_commands "${LOCAL_BOOTSTRAP_COMMANDS:-seed_datos_base crear_programas seed_catalogo_siis}"
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
