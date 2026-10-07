"""La guarda de `seed_perf` reconoce la base de test, también clonada (RED-88).

`manage.py test core users portal --parallel 2` reventaba con
`TypeError: cannot pickle 'traceback' object` **sin decir qué test falló**: el runner
paralelo aborta entero y enmascara la causa, que es lo que bloqueaba acelerar el CI
(RED-86). Bisecado hasta `core.tests.test_performance_budgets`, el origen resultó ser
una lista de literales:

`seed_perf` solo se deja correr en la base de test (o en la MySQL efímera del CI de
performance), para no sembrar 200× filas sintéticas en una base real. Esa condición
estaba escrita comparando el `NAME` contra `":memory:"` y
`"file:memorydb_default?mode=memory&cache=shared"`. Con `--parallel N`, Django clona
la base por worker y le pone un sufijo —medido: `file:memorydb_default_2?mode=memory&cache=shared`—,
que no estaba en la lista. El `CommandError` salía del `setUpTestData` de
`PerformanceBudgetTests`, o sea como error **de clase**: su `exc_info` arrastra un
`traceback`, `multiprocessing` no puede serializarlo y el runner muere ahí.

Estos tests corren **el comando de verdad** con el `NAME` de la conexión cambiado,
que es la única forma de ejercitar la guarda: lo que se rompió fue la comparación de
nombres, y un `TestCase` no puede pedirle al runner que clone la base. El `_seed` se
reemplaza por un centinela, así que lo que se mide es **de qué lado de la guarda
quedó el comando**, no lo que siembra.

El contrato de que la suite paralela siga andando lo cuida el paso no bloqueante
`core users portal --parallel 2` del job `Orden y paralelo` (`pr-backend.yml`).
"""

from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase

from core.management.commands.seed_perf import Command

#: Lo que Django genera con `--parallel`, medido el 07-10-2026 (Python 3.12,
#: Django 5.2.17, start method `spawn`).
CLONES_DEL_RUNNER = (
    "file:memorydb_default_1?mode=memory&cache=shared",
    "file:memorydb_default_2?mode=memory&cache=shared",
    "file:memorydb_default_8?mode=memory&cache=shared",
)


class _Sembro(Exception):
    """Centinela: la guarda dejó pasar y el comando llegó a sembrar."""


class GuardaDeSeedPerfTests(TestCase):
    def _correr_con_la_base_llamandose(self, nombre):
        """Corre `seed_perf` como si la base se llamara `nombre`, sin sembrar nada."""
        with patch.dict(connection.settings_dict, {"NAME": nombre}):
            with patch.object(Command, "_seed", side_effect=_Sembro):
                call_command("seed_perf", scale=1)

    def _acepta(self, nombre):
        with self.assertRaises(_Sembro, msg=f"la guarda rechazó «{nombre}»"):
            self._correr_con_la_base_llamandose(nombre)

    def _rechaza(self, nombre):
        with self.assertRaises(CommandError, msg=f"la guarda dejó pasar «{nombre}»"):
            self._correr_con_la_base_llamandose(nombre)

    def test_acepta_la_base_en_memoria_sin_clonar(self):
        self._acepta(":memory:")
        self._acepta("file:memorydb_default?mode=memory&cache=shared")

    def test_acepta_los_clones_que_crea_parallel(self):
        """El caso de RED-88: sin esto, `--parallel` mata la suite entera."""
        for nombre in CLONES_DEL_RUNNER:
            with self.subTest(nombre=nombre):
                self._acepta(nombre)

    def test_rechaza_una_base_en_disco(self):
        """Lo que la guarda existe para impedir: sembrar sobre algo persistente."""
        for nombre in ("db.sqlite3", "/var/lib/chaco/db.sqlite3", "default_1.sqlite3", "chaco", ""):
            with self.subTest(nombre=nombre):
                self._rechaza(nombre)

    def test_un_nombre_que_solo_se_parece_no_alcanza(self):
        """`memorydb` en el nombre no basta: lo que decide es `mode=memory`."""
        self._rechaza("/tmp/memorydb_default.sqlite3")  # noqa: S108 — es un nombre, no una ruta que se abra

    def test_sin_pytest_running_no_corre_ni_en_memoria(self):
        """La otra mitad de la guarda: la base de test sola no alcanza.

        Si alguien relajara el `PYTEST_RUNNING`, un `seed_perf` a mano contra una
        SQLite en memoria de desarrollo pasaría, que es justo lo que no se quiere.
        """
        with patch.dict("os.environ", {"PYTEST_RUNNING": "0"}):
            self._rechaza(":memory:")

    def test_el_mensaje_dice_donde_si_puede_correr(self):
        with self.assertRaises(CommandError) as capturado:
            self._correr_con_la_base_llamandose("db.sqlite3")

        self.assertIn("SQLite in-memory", str(capturado.exception))
        self.assertIn("PERFORMANCE_CI=1", str(capturado.exception))
