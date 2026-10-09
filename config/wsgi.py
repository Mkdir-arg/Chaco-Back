"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.0/howto/deployment/wsgi/
"""

# RED-45 / OPS-13 / D-RED-08: antes de estos imports había un bloque que, si
# `GUNICORN_CMD_ARGS` contenía la palabra `gevent` o `GUNICORN_WORKER_CLASS` valía
# `gevent`, importaba `config/gevent_patch.py` y pisaba
# `BaseDatabaseWrapper.validate_thread_sharing` con una función vacía: gevent sin
# `monkey.patch_all()` y sin el único chequeo que impide que dos greenlets compartan una
# conexión. El parche, el módulo y `gevent`/`greenlet` de `requirements.txt` se fueron.
# Los workers de la imagen son gthread (`--threads`), y `docker-entrypoint.sh` sigue
# abortando con el motivo si alguien pide gevent o eventlet por cualquiera de las dos
# perillas: ahora ni siquiera estaría el paquete.
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()
