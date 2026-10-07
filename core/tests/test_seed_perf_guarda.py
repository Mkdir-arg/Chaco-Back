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

Estos tests son unitarios sobre el predicado, no sobre el comando: no hay forma de
pedirle a un `TestCase` que corra bajo otro nombre de base, y lo que se rompió fue
exactamente la comparación de nombres.

El contrato de que la suite paralela siga andando lo cuida el paso no bloqueante
`core users portal --parallel 2` del job `Orden y paralelo` (`pr-backend.yml`).
"""

from django.test import SimpleTestCase

from core.management.commands.seed_perf import es_sqlite_en_memoria

#: Lo que Django genera con `--parallel`, medido el 07-oct-2026 (Python 3.12,
#: Django 5.2.17, start method `spawn`).
CLONES_DEL_RUNNER = (
    "file:memorydb_default_1?mode=memory&cache=shared",
    "file:memorydb_default_2?mode=memory&cache=shared",
    "file:memorydb_default_8?mode=memory&cache=shared",
)


class GuardaDeSeedPerfTests(SimpleTestCase):
    def test_acepta_la_base_en_memoria_sin_clonar(self):
        self.assertTrue(es_sqlite_en_memoria(":memory:"))
        self.assertTrue(es_sqlite_en_memoria("file:memorydb_default?mode=memory&cache=shared"))

    def test_acepta_los_clones_que_crea_parallel(self):
        """El caso de RED-88: sin esto, `--parallel` mata la suite entera."""
        for nombre in CLONES_DEL_RUNNER:
            with self.subTest(nombre=nombre):
                self.assertTrue(es_sqlite_en_memoria(nombre))

    def test_rechaza_una_base_en_disco(self):
        """Lo que la guarda existe para impedir: sembrar sobre algo persistente."""
        for nombre in ("db.sqlite3", "/var/lib/chaco/db.sqlite3", "default_1.sqlite3", "chaco", ""):
            with self.subTest(nombre=nombre):
                self.assertFalse(es_sqlite_en_memoria(nombre))

    def test_un_nombre_que_solo_se_parece_no_alcanza(self):
        """`memorydb` en el nombre no basta: lo que decide es `mode=memory`."""
        self.assertFalse(es_sqlite_en_memoria("/tmp/memorydb_default.sqlite3"))
