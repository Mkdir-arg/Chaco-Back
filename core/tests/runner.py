"""Runner de tests que corta la salida a la red (SIIS-09, ronda 2).

Un test que parchea el lugar equivocado no falla: sale a internet de verdad,
tarda lo que tarde el DNS y después afirma algo que nunca se ejercitó. Pasó
exactamente eso cuando los clientes de SIIS y de Base de Personas cambiaron de
``requests.post`` a una ``Session`` de módulo: un test de seguridad del portal
seguía parcheando ``programas.services.personas.requests.get``, el mock quedaba
en cero llamadas y la regresión que cuidaba —que el DNI no viaje en el log—
pasaba por accidente, porque el error de conexión real tampoco traía el DNI.

La guarda es una sola línea de verdad: **ningún test puede abrir una conexión
HTTP**. Se corta en dos lugares, los dos por encima del socket, para que la
base, el servidor de pruebas, Redis y el SMTP de prueba sigan funcionando:

* ``HTTPAdapter.send`` — por donde pasan ``requests.get`` y cualquier
  ``Session``. Da el mensaje útil, porque sabe qué hay que parchear.
* ``http.client.HTTPConnection.connect`` — el backstop. ``urllib.request``,
  ``http.client`` y cualquier cliente que no sea ``requests`` llegan a la red
  por acá (``HTTPSConnection.connect`` llama al ``connect`` de su base, así que
  con parchear la base alcanza para los dos esquemas). Antes quedaban abiertos:
  la docstring prometía «ningún test abre HTTP» y solo era cierto para
  ``requests``.

**Con ``--parallel``.** Los subprocesos del pool no heredan el parche cuando el
método de arranque es *spawn* —el default en Windows y en macOS—: ahí Django
vuelve a llamar a ``setup_test_environment`` del módulo, no al método del
runner, así que el worker arrancaba con la red abierta y la guarda valía solo
para el proceso padre. :class:`SuiteParalelaSinRed` la instala también en cada
worker, después del ``_init_worker`` de Django (que es el que hace el
``django.setup()`` del spawn). Con *fork* el worker ya la hereda y volver a
asignarla no cambia nada.

**Qué toca del CI.** Entra por ``TEST_RUNNER`` y solo lo carga ``manage.py
test``: ``check``, ``migrate`` y ``collectstatic`` no se enteran. Los cuatro
jobs que corren tests pasan por acá y ninguno necesita red —``Tests & Coverage``
y la suite del release gate son SQLite; ``--tag performance`` simula las
dependencias externas con ``core.performance.ci_external_stubs``, que no abre
sockets; ``--tag mysql`` y ``Motor real`` hablan con la base—. El job ``Migrate
ida y vuelta`` usa ``.github/ci/settings_roundtrip.py``, que importa
``config.settings`` **del árbol que corre** (el del PR y el de su base): el de
la base no define ``TEST_RUNNER`` y tampoco corre tests, así que el módulo nuevo
no hace falta ahí. Este archivo **sí** viaja al release (``core/tests/`` no está
en ``export-ignore``), igual que el resto de los tests.
"""

import http.client
from urllib.parse import urlsplit

from django.test.runner import DiscoverRunner, ParallelTestSuite, _init_worker
from requests.adapters import HTTPAdapter


class RedProhibidaEnTests(AssertionError):
    """Un test intentó salir a la red de verdad."""


_AYUDA = (
    "Parcheá el cliente que corresponde: los módulos de SIIS y Base de Personas "
    "salen por su ``sesion`` (``patch.object(modulo.sesion, 'get'|'post', …)``), "
    "no por ``requests``."
)


def _bloquear(self, request, *args, **kwargs):
    partes = urlsplit(getattr(request, "url", "") or "")
    # Solo esquema y host: la URL completa puede llevar el documento consultado
    # (``?dni=…``), y este mensaje termina en la salida del CI.
    destino = f"{partes.scheme}://{partes.netloc}" if partes.netloc else "un destino desconocido"
    raise RedProhibidaEnTests(f"Un test intentó salir a la red ({destino}). {_AYUDA}")


def _bloquear_conexion(self, *args, **kwargs):
    # Mismo criterio que arriba: host y puerto, nunca la ruta ni la query.
    destino = f"{getattr(self, 'host', '?')}:{getattr(self, 'port', '?')}"
    raise RedProhibidaEnTests(
        f"Un test intentó abrir una conexión HTTP ({destino}) con un cliente que no es ``requests``. {_AYUDA}"
    )


def instalar_guarda():
    """Corta las dos vías de salida. Devuelve lo que había, para restaurarlo."""
    originales = (HTTPAdapter.send, http.client.HTTPConnection.connect)
    HTTPAdapter.send = _bloquear
    http.client.HTTPConnection.connect = _bloquear_conexion
    return originales


def _init_worker_sin_red(*args, **kwargs):
    """El ``_init_worker`` de Django más la guarda, para el pool de ``--parallel``.

    Vive a nivel de módulo porque ``multiprocessing`` tiene que poder picklearlo
    por nombre cuando el arranque es *spawn*.
    """
    _init_worker(*args, **kwargs)
    instalar_guarda()


class SuiteParalelaSinRed(ParallelTestSuite):
    init_worker = _init_worker_sin_red


class RunnerSinRed(DiscoverRunner):
    """El runner de siempre, con la salida a la red cortada.

    La sustitución es una asignación y **no** un ``mock.patch(...).start()``:
    trece tests de la suite usan ``self.addCleanup(patch.stopall)``, que corta
    todos los parches activos del proceso, incluido el que hubiera puesto el
    runner. Con `start()` la guarda se caía en el primero de esos tests y de ahí
    en adelante la suite volvía a salir a la red sin avisar.
    """

    parallel_test_suite = SuiteParalelaSinRed

    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self._originales_red = instalar_guarda()

    def teardown_test_environment(self, **kwargs):
        originales = getattr(self, "_originales_red", None)
        if originales is not None:
            HTTPAdapter.send, http.client.HTTPConnection.connect = originales
        super().teardown_test_environment(**kwargs)
