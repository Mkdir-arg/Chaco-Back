"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.0/howto/deployment/wsgi/
"""

import os

# Aplicar parches para gevent ANTES de importar Django
if "gevent" in os.environ.get("GUNICORN_CMD_ARGS", "") or os.environ.get("GUNICORN_WORKER_CLASS") == "gevent":
    os.environ["GUNICORN_WORKER_CLASS"] = "gevent"
    from config.gevent_patch import apply_gevent_patches

    apply_gevent_patches()

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()
