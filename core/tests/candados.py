"""Utilidad de test para afirmar que una operación toma su ``select_for_update``.

La suite corre sobre SQLite en memoria, donde ``select_for_update()`` es un
no-op: ningún test se pone rojo si alguien borra la línea del candado al
optimizar, y en MariaDB —el motor de testing y de PRD— se pierde la
serialización que evita el cupo excedido y el duplicado. Ese contrato no se
puede probar por su efecto, así que se prueba por su presencia (RED-67).

``candados_tomados`` registra **desde dónde** se pidió el candado, no solo que
se haya pedido. Hace falta esa precisión porque sobre el mismo manager hay más
de un lock en juego: ``Formulario.save()`` bloquea el relevamiento para numerar
el caso, así que un ``assert_called()`` a secas quedaría verde aunque el
servicio hubiera perdido el suyo.

La carrera de verdad —dos hilos sobre el último lugar— es la otra capa: un
``TransactionTestCase`` con ``@tag("mysql")`` contra el motor real (TST-01).
"""

import inspect
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import patch


@contextmanager
def candados_tomados(manager):
    """Registra los ``select_for_update()`` de ``manager`` como ``archivo.py:funcion``.

    Deja pasar la llamada real: el camino feliz se sigue ejecutando entero, así
    que el test también falla si la operación deja de hacer su trabajo.

    Uso::

        with candados_tomados(Segmento.objects) as candados:
            aprobar_o_poner_en_espera(formulario, user)
        self.assertIn("cupo.py:aprobar_o_poner_en_espera", candados)
    """
    original = manager.select_for_update
    llamadas = []

    def registrar(*args, **kwargs):
        marco = inspect.currentframe().f_back
        llamadas.append(f"{Path(marco.f_code.co_filename).name}:{marco.f_code.co_name}")
        return original(*args, **kwargs)

    with patch.object(manager, "select_for_update", registrar):
        yield llamadas


@contextmanager
def orden_de_candados(**managers):
    """Registra los ``select_for_update()`` de varios managers en **una sola** lista.

    ``candados_tomados`` mira un manager por vez y pierde el orden relativo entre dos
    tablas, que es justo lo que decide si dos transacciones se esperan o se matan: dos
    caminos que bloquean las mismas filas tienen que pedirlas **en el mismo orden**, o el
    motor los corta con un `ERROR 1213`. El orden tampoco se puede probar por su efecto en
    SQLite —ahí no hay candados—, así que se prueba por la secuencia de llamadas.

    Uso::

        with orden_de_candados(plaza=Plaza.objects, reserva=ReservaPlaza.objects) as orden:
            liberar_reserva(reserva=reserva, usuario=self.operador)
        self.assertEqual(orden, ["plaza", "reserva"])
    """

    llamadas = []
    with ExitStack() as pila:
        for nombre, manager in managers.items():
            original = manager.select_for_update

            def registrar(*args, _nombre=nombre, _original=original, **kwargs):
                llamadas.append(_nombre)
                return _original(*args, **kwargs)

            pila.enter_context(patch.object(manager, "select_for_update", registrar))
        yield llamadas
