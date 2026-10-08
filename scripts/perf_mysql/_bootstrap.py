"""Carga Django contra el banco MySQL con ``settings_bench``. Lo importan los
scripts de esta carpeta; se niega a correr sobre SQLite para que nadie mida
sin querer contra la base de tests.

``cargar_django()`` alcanza para lo que solo **lee**. Lo que **borra** llama además a
:func:`exigir_base_descartable`, que pregunta a la base por su propio nombre: apuntar
``DATABASE_*`` a una base con datos reales y correr un script de siembra no puede
depender de que el motor no sea SQLite.
"""

import os
import sys
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
REPO = CARPETA.parent.parent

#: El único nombre de base sobre el que se puede borrar. Es el mismo que exige
#: `seed_perf` (`core/management/commands/seed_perf.py`) y el que usa el CI de
#: performance: una base descartable que se crea y se tira con el contenedor.
BASE_DESCARTABLE = "chaco_perf_ci"


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


def exigir_base_descartable():
    """Aborta si la base conectada no es la descartable del banco.

    La guarda de ``cargar_django()`` solo dice «no es SQLite», y eso deja pasar
    cualquier MySQL/MariaDB que tenga exportado el que corre el script —incluido un
    restore de producción en el laptop—. El nombre se le pregunta al servidor
    (``SELECT DATABASE()``) y no a ``settings``, igual que ``seed_perf``: lo que importa
    es con qué base se terminó hablando, no la que se quiso configurar.
    """
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("SELECT DATABASE()")
        conectada = cursor.fetchone()[0]

    if conectada != BASE_DESCARTABLE:
        raise SystemExit(
            f"Este script BORRA datos y solo corre sobre la base descartable del banco "
            f"(`{BASE_DESCARTABLE}`). La conexión está apuntando a `{conectada}`."
        )
