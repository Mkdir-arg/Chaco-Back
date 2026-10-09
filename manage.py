#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import importlib
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("django")


def _escuchar_debugger():
    """Abre el puerto 3000 con `debugpy`, si el paquete está instalado.

    OPS-13 (Cambio 196) mudó `debugpy` a `requirements-dev.txt` y la imagen dejó de
    traerlo, pero acá quedó un `import debugpy` incondicional: el `docker-compose.yml`
    de desarrollo levanta esa misma imagen con `DJANGO_DEBUG=True` y `runserver`, que
    relanza el proceso con `RUN_MAIN=true` para el autoreload, así que el hijo moría con
    `ModuleNotFoundError` y el contenedor no arrancaba. Mismo criterio que
    `config/settings.py` con `django_extensions`/`silk`: faltando, lo único que se pierde
    es el debugger.

    Se importa con `importlib` y no con `import debugpy` por dos motivos: el `except`
    tiene que cubrir también un paquete instalado a medias, y
    `core/tests/test_dependencias.py::test_nadie_los_importa` barre por AST los `.py` de
    la raíz —este incluido— para que un import incondicional de algo que la imagen no
    instala salga en el PR y no en el arranque del pod.
    """
    try:
        debugpy = importlib.import_module("debugpy")
    except ImportError:
        logger.info("debugpy no está instalado (requirements-dev.txt): sigo sin debugger")
        return

    debugpy.listen(("0.0.0.0", 3000))
    logger.info("Debugger listo")


def main():
    """Run administrative tasks."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    # To debug in Docker
    from django.conf import settings

    if settings.DEBUG:
        if os.environ.get("RUN_MAIN") or os.environ.get("WERKZEUG_RUN_MAIN"):
            _escuchar_debugger()

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
