"""Estado compartido que las pantallas de Becas necesitan, puesto por el propio módulo.

TST-02. Un test que solo pasa porque **otro módulo corrió antes** no prueba lo que
dice: cambia el orden de la suite (`--shuffle`, `--parallel`, correr un módulo solo
para depurar) y se pone rojo sin que nadie haya tocado el código. Medido módulo por
módulo sobre los 77 de `programas/tests/`, cinco estaban así —26 fallas, casi todas
`403 != 200`— y las dos causas son siempre las mismas:

* **El Programa Becas tiene que existir.** Desde RED-56 (Cambio 123) los guards de
  Becas fallan cerrados: sin la fila ``codigo="BECAS"``, ``_programa_o_denegar``
  levanta ``PermissionDenied`` **también para un superusuario**, así que la pantalla
  entera da 403. Estos módulos no la sembraban: pasaban porque algún módulo anterior
  corría ``seed_becas``.
* **La caché tiene que arrancar vacía.** ``_programa_o_denegar`` guarda el Programa en
  ``programas:becas``, una clave de **proceso** (LocMem): sobrevive al rollback de la
  base entre tests, así que lo que dejó otro módulo decide si esta pantalla abre y
  cuántas consultas hace.

`programas.tests.test_becas_convocatorias_diseno` ya traía su propia copia de esto
(Cambio 130, PR R-11); acá queda una sola definición para que el próximo módulo de
pantalla de Becas no tenga que redescubrirla.

`programas.tests.test_aislamiento_modulos` es el ratchet que impide que un módulo
nuevo vuelva a depender del orden sin declararlo.
"""

from io import StringIO

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase


class ProgramaBecasSembrado:
    """Mixin: deja el Programa Becas creado y la caché de proceso limpia.

    Mixin y no clase base para poder combinarlo con `TransactionTestCase` o con las
    bases que ya tiene cada módulo. Las clases que solo necesitan esto heredan de
    `BecasPantallaTestCase`.
    """

    def setUp(self):
        cache.clear()
        call_command("crear_programas", stdout=StringIO())
        super().setUp()


class BecasPantallaTestCase(ProgramaBecasSembrado, TestCase):
    """`TestCase` para cualquier módulo que pegue contra una pantalla de `/becas/`."""
