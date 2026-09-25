"""Carga Django contra el banco MySQL con ``settings_bench``. Lo importan los
tres scripts de esta carpeta; se niega a correr sobre SQLite para que nadie mida
sin querer contra la base de tests."""

import os
import sys
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
REPO = CARPETA.parent.parent


def cargar_django():
    for ruta in (str(REPO), str(CARPETA)):
        if ruta not in sys.path:
            sys.path.insert(0, ruta)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings_bench")
    os.environ.setdefault("DJANGO_SECRET_KEY", "bench")
    os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "testserver,localhost")
    os.environ.pop("PYTEST_RUNNING", None)
    os.environ.pop("DJANGO_SYNCDB_PROJECT_APPS", None)

    import django

    django.setup()

    from django.conf import settings

    motor = settings.DATABASES["default"]["ENGINE"]
    if "mysql" not in motor:
        raise SystemExit(
            f"El banco mide contra MySQL; la base configurada es {motor}. Exportá DATABASE_* (ver README)."
        )
