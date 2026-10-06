"""Runner de tests que corta la salida a la red (SIIS-09, ronda 2).

Un test que parchea el lugar equivocado no falla: sale a internet de verdad,
tarda lo que tarde el DNS y después afirma algo que nunca se ejercitó. Pasó
exactamente eso cuando los clientes de SIIS y de Base de Personas cambiaron de
``requests.post`` a una ``Session`` de módulo: un test de seguridad del portal
seguía parcheando ``programas.services.personas.requests.get``, el mock quedaba
en cero llamadas y la regresión que cuidaba —que el DNI no viaje en el log—
pasaba por accidente, porque el error de conexión real tampoco traía el DNI.

La guarda es una sola línea de verdad: **ningún test puede abrir una conexión
HTTP**. Se corta en ``HTTPAdapter.send``, que es por donde pasan tanto
``requests.get`` como cualquier ``Session``, y no a nivel de socket: la base, el
servidor de pruebas y Redis siguen funcionando.

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

from urllib.parse import urlsplit

from django.test.runner import DiscoverRunner
from requests.adapters import HTTPAdapter


class RedProhibidaEnTests(AssertionError):
    """Un test intentó salir a la red de verdad."""


def _bloquear(self, request, *args, **kwargs):
    partes = urlsplit(getattr(request, "url", "") or "")
    # Solo esquema y host: la URL completa puede llevar el documento consultado
    # (``?dni=…``), y este mensaje termina en la salida del CI.
    destino = f"{partes.scheme}://{partes.netloc}" if partes.netloc else "un destino desconocido"
    raise RedProhibidaEnTests(
        f"Un test intentó salir a la red ({destino}). Parcheá el cliente que corresponde: "
        "los módulos de SIIS y Base de Personas salen por su ``sesion`` "
        "(``patch.object(modulo.sesion, 'get'|'post', …)``), no por ``requests``."
    )


class RunnerSinRed(DiscoverRunner):
    """El runner de siempre, con la salida a la red cortada.

    La sustitución es una asignación y **no** un ``mock.patch(...).start()``:
    trece tests de la suite usan ``self.addCleanup(patch.stopall)``, que corta
    todos los parches activos del proceso, incluido el que hubiera puesto el
    runner. Con `start()` la guarda se caía en el primero de esos tests y de ahí
    en adelante la suite volvía a salir a la red sin avisar.
    """

    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self._send_original = HTTPAdapter.send
        HTTPAdapter.send = _bloquear

    def teardown_test_environment(self, **kwargs):
        original = getattr(self, "_send_original", None)
        if original is not None:
            HTTPAdapter.send = original
        super().teardown_test_environment(**kwargs)
