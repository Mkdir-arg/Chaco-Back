"""`/health/ready/`: la sonda que sí sabe si el sistema puede atender (OPS-04).

`/health/` es liveness: contesta 200 sin tocar nada, y así tiene que quedarse —lo miran
las sondas de `docker-compose.prod.yml`, las de `docker/k8s/bootstrap-initcontainer.yaml`
y las de ECOM—. El problema medido por la auditoría es que **también** era el criterio de
éxito y de rollback de `scripts/deploy_prod.sh`: con la base caída, con el esquema a
medias o con el `collectstatic` fallido, `/health/` devolvía 200 y el rollback automático
no se disparaba nunca.

Esta vista es el otro lado: toca la base (y, en `prd`, el cache donde viven las sesiones)
y devuelve **503** con el detalle de qué falló. **D-O04: no se usa como readinessProbe.**
Con una sola base para todos los pods, una base lenta los sacaría a todos a la vez; su
lugar es el monitoreo externo y el deploy.
"""

import logging

from django.conf import settings
from django.core.cache import caches
from django.db import connection
from django.http import JsonResponse

logger = logging.getLogger(__name__)

# Los timeouts ya están configurados donde corresponde: `read_timeout` de 10 s en
# `DATABASES["default"]["OPTIONS"]` y `SOCKET_TIMEOUT` de 5 s en el cache de sesiones.
# Acá no se agrega ninguno: duplicarlos sería un segundo lugar donde desincronizarse.


def _probar_base():
    connection.ensure_connection()
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()


def _probar_cache():
    caches["sessions"].get("health")


def _resultado(nombre, prueba):
    try:
        prueba()
    except Exception as error:  # noqa: BLE001 — la sonda reporta cualquier fallo, no elige
        logger.exception("health/ready: %s no responde", nombre)
        return f"{type(error).__name__}: {error}"[:200]
    return "ok"


def ready(request):
    estado = {"db": _resultado("la base", _probar_base)}
    # En `prd` las sesiones viven en Redis (`SESSION_ENGINE` de cache): sin cache nadie
    # puede loguearse, aunque la base conteste. Fuera de prd el backend es LocMem y
    # chequearlo no diría nada del ambiente.
    if getattr(settings, "ENVIRONMENT", "dev") == "prd":
        estado["cache"] = _resultado("el cache de sesiones", _probar_cache)

    todo_bien = all(valor == "ok" for valor in estado.values())
    return JsonResponse(estado, status=200 if todo_bien else 503)
