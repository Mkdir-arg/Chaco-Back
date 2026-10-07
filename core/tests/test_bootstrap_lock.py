"""OPS-07 (ampliado por RS-R5-07) · El bootstrap corre con un candado de base tomado.

Django **no** toma ningún candado para `migrate` en MySQL/MariaDB. Con más de una
réplica arrancando a la vez —el rolling de Kubernetes es exactamente eso— dos procesos
migran en paralelo y, si se cruzan dentro de una migración de varias operaciones, el
esquema queda a medias y **sin** fila en `django_migrations`: medido contra MariaDB 11.8,
uno de los dos muere con 1050 desde base vacía y con 1060 desde base al día (RED-19).

`RUN_MIGRATIONS=false` + el Job único (#596, PR R-13) es la regla; esto es la red debajo
de la regla, para el ambiente que todavía no la aplicó y para el cruce entre el `migrate`
y el sembrado. El candado es `GET_LOCK`, que es de la **conexión**: se suelta solo si el
proceso muere, que es justo lo que hace falta.

Los casos corren contra una conexión falsa porque lo que se fija acá es el protocolo
—qué SQL se manda, en qué orden y qué pasa cuando el candado no se consigue—, no el
motor. El candado contra el motor de verdad, con dos conexiones, está en
`core/tests/test_motor_real.py::CandadoDeBootstrapTests` (`@tag("mysql")`).
"""

import io
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import InterfaceError, OperationalError
from django.test import SimpleTestCase

MODULO = "core.management.commands.bootstrap_lock"


class _Cursor:
    def __init__(self, conexion):
        self.conexion = conexion

    def __enter__(self):
        return self

    def __exit__(self, *excepcion):
        return False

    def execute(self, sql, params=None):
        self.conexion.ejecutado.append((" ".join(sql.split()), list(params or [])))
        if any(fragmento in sql for fragmento in self.conexion.muere_en):
            raise self.conexion.excepcion_de_caida("Lost connection to MySQL server during query")
        if "GET_LOCK" in sql:
            self.conexion.ultima_fila = (self.conexion.respuesta_get_lock,)
        elif "RELEASE_LOCK" in sql:
            self.conexion.ultima_fila = (1,)
        elif "IS_USED_LOCK" in sql:
            self.conexion.ultima_fila = (self.conexion.duenio_del_candado,)
        elif "CONNECTION_ID" in sql:
            self.conexion.ultima_fila = (self.conexion.id_conexion,)
        else:
            self.conexion.ultima_fila = (None,)

    def fetchone(self):
        return self.conexion.ultima_fila


class _Conexion:
    """Lo mínimo que usa el comando: `vendor`, `settings_dict` y un cursor."""

    def __init__(self, vendor="mysql", respuesta_get_lock=1, read_timeout=1200):
        self.vendor = vendor
        self.respuesta_get_lock = respuesta_get_lock
        self.id_conexion = 42
        self.duenio_del_candado = 42
        self.ejecutado = []
        self.ultima_fila = None
        self.settings_dict = {"OPTIONS": {"read_timeout": read_timeout} if read_timeout else {}}
        #: Fragmentos de SQL ante los cuales la conexión se comporta como muerta: es lo
        #: que hace el servidor tras un `wait_timeout` vencido o un `KILL`.
        self.muere_en = ()
        self.excepcion_de_caida = OperationalError

    def cursor(self):
        return _Cursor(self)

    @property
    def sql(self):
        return [sql for sql, _ in self.ejecutado]


class _Conexiones:
    """`connections` falso: `["default"]` y `create_connection` dan la misma conexión.

    En producción son **dos distintas** a propósito (el candado vive aparte de la que
    usan los comandos); acá comparten objeto para que las aserciones puedan mirar un solo
    registro de SQL. Que sean dos lo fija `CandadoSobreviveAlLoaddataTests`
    (`@tag("mysql")`), que es donde se puede cerrar una de verdad.
    """

    def __init__(self, conexion):
        self.conexion = conexion
        self.creadas = 0
        self.cerradas = 0

    def __getitem__(self, alias):
        return self.conexion

    def create_connection(self, alias):
        self.creadas += 1
        return self.conexion


def _sql_con(conexion, fragmento):
    return [sql for sql in conexion.sql if fragmento in sql]


class BootstrapLockTests(SimpleTestCase):
    def setUp(self):
        self.conexion = _Conexion()
        self.conexiones = _Conexiones(self.conexion)
        self.conexion.close = lambda: setattr(self.conexiones, "cerradas", self.conexiones.cerradas + 1)
        self.salida = io.StringIO()
        parche = mock.patch(f"{MODULO}.connections", self.conexiones)
        parche.start()
        self.addCleanup(parche.stop)
        self.corridos = []
        parche_call = mock.patch(f"{MODULO}.call_command", side_effect=lambda *a, **kw: self.corridos.append(a))
        parche_call.start()
        self.addCleanup(parche_call.stop)

    def _correr(self, *argumentos):
        call_command("bootstrap_lock", *argumentos, stdout=self.salida, stderr=self.salida)

    def test_toma_el_candado_antes_de_correr_y_lo_suelta_al_final(self):
        self._correr("--nombre", "datanach_bootstrap", "--comando", "migrate --noinput")

        self.assertEqual(len(_sql_con(self.conexion, "GET_LOCK")), 1)
        self.assertEqual(len(_sql_con(self.conexion, "RELEASE_LOCK")), 1)
        parametros = next(params for sql, params in self.conexion.ejecutado if "GET_LOCK" in sql)
        self.assertEqual(parametros, ["datanach_bootstrap", 900])
        self.assertLess(
            self.conexion.sql.index(_sql_con(self.conexion, "GET_LOCK")[0]),
            self.conexion.sql.index(_sql_con(self.conexion, "RELEASE_LOCK")[0]),
        )
        self.assertEqual(self.corridos, [("migrate", "--noinput")])

    def test_los_comandos_corren_en_el_orden_pedido(self):
        self._correr(
            "--comando",
            "verificar_esquema_migraciones",
            "--comando",
            "migrate --noinput",
            "--comando",
            "seed_datos_base",
        )

        self.assertEqual(
            self.corridos,
            [("verificar_esquema_migraciones",), ("migrate", "--noinput"), ("seed_datos_base",)],
        )

    def test_si_otro_proceso_tiene_el_candado_aborta_sin_correr_nada(self):
        """`GET_LOCK` devuelve 0 al vencer la espera: hay otro migrador vivo."""
        self.conexion.respuesta_get_lock = 0

        with self.assertRaises(CommandError) as cm:
            self._correr("--comando", "migrate --noinput")

        self.assertIn("datanach_bootstrap", str(cm.exception))
        self.assertEqual(self.corridos, [])
        self.assertEqual(_sql_con(self.conexion, "RELEASE_LOCK"), [])

    def test_suelta_el_candado_aunque_el_comando_falle(self):
        """Sin esto, un `migrate` que falla deja el candado tomado hasta que muera el pod."""
        with mock.patch(f"{MODULO}.call_command", side_effect=CommandError("migrate explotó")):
            with self.assertRaises(CommandError):
                self._correr("--comando", "migrate --noinput")

        self.assertEqual(len(_sql_con(self.conexion, "RELEASE_LOCK")), 1)

    def test_una_espera_mayor_que_el_read_timeout_aborta_con_el_motivo(self):
        """`SELECT GET_LOCK(x, 900)` con `read_timeout=10` muere a los 10 s con un 2013."""
        self.conexion.settings_dict["OPTIONS"]["read_timeout"] = 10

        with self.assertRaises(CommandError) as cm:
            self._correr("--espera", "900", "--comando", "migrate --noinput")

        self.assertIn("read_timeout", str(cm.exception))
        self.assertIn("MIGRATE_DB_READ_TIMEOUT", str(cm.exception))
        self.assertEqual(self.corridos, [])

    def test_una_espera_corta_entra_en_el_read_timeout_de_siempre(self):
        """El margen no puede volver inusable el comando con los 10 s de producción."""
        self.conexion.settings_dict["OPTIONS"]["read_timeout"] = 10

        self._correr("--espera", "3", "--comando", "migrate --noinput")

        self.assertEqual(self.corridos, [("migrate", "--noinput")])

    def test_sin_comandos_no_toma_el_candado(self):
        self._correr()

        self.assertEqual(self.conexion.sql, [])

    def test_en_un_motor_sin_get_lock_avisa_y_corre_igual(self):
        """SQLite (tests) no tiene `GET_LOCK`: el bootstrap no se cae por eso."""
        self.conexion.vendor = "sqlite"

        self._correr("--comando", "migrate --noinput")

        self.assertEqual(self.conexion.sql, [])
        self.assertEqual(self.corridos, [("migrate", "--noinput")])
        self.assertIn("sqlite", self.salida.getvalue())

    def test_el_candado_va_en_una_conexion_dedicada(self):
        """`loaddata` cierra `connections["default"]` al terminar: con el candado ahí, se
        soltaba a mitad del sembrado. La conexión del candado se abre aparte y se cierra
        recién al final."""
        self._correr("--comando", "seed_datos_base")

        self.assertEqual(self.conexiones.creadas, 1)
        self.assertEqual(self.conexiones.cerradas, 1)

    def test_el_caso_normal_no_avisa_nada(self):
        """El AVISO era un falso positivo con un solo contenedor: no puede salir acá."""
        self._correr("--comando", "migrate --noinput")

        self.assertNotIn("AVISO", self.salida.getvalue())

    def test_avisa_distinto_si_el_candado_lo_tiene_otra_conexion(self):
        """Otro `CONNECTION_ID` lo tiene: un segundo bootstrap entró de verdad."""
        self.conexion.duenio_del_candado = 99

        self._correr("--comando", "migrate --noinput")

        self.assertIn("AVISO", self.salida.getvalue())
        self.assertIn("otro bootstrap entró", self.salida.getvalue())
        self.assertEqual(_sql_con(self.conexion, "RELEASE_LOCK"), [], "no se suelta un candado ajeno")

    def test_la_conexion_del_candado_pide_un_wait_timeout_largo(self):
        """Es la conexión que no habla en todo el bootstrap: un `wait_timeout` global
        apretado la mata mientras espera y el candado se suelta a mitad."""
        self._correr("--comando", "migrate --noinput")

        sets = [params for sql, params in self.conexion.ejecutado if "wait_timeout" in sql]
        self.assertEqual(sets, [[28800]])
        self.assertLess(
            self.conexion.sql.index(_sql_con(self.conexion, "wait_timeout")[0]),
            self.conexion.sql.index(_sql_con(self.conexion, "GET_LOCK")[0]),
            "de nada sirve alargarlo después de haber esperado ocioso",
        )

    def test_si_no_se_puede_alargar_el_wait_timeout_sigue_igual(self):
        """Un usuario sin permiso para tocar la variable no puede frenar el arranque."""
        self.conexion.muere_en = ("wait_timeout",)

        self._correr("--comando", "migrate --noinput")

        self.assertIn("no se pudo alargar el wait_timeout", self.salida.getvalue())
        self.assertEqual(self.corridos, [("migrate", "--noinput")])

    def test_una_conexion_muerta_al_soltar_no_hace_fallar_el_bootstrap(self):
        """El caso de la ronda 3: `wait_timeout`, un `KILL` o un firewall cortan la
        conexión ociosa, y el `IS_USED_LOCK` del `finally` levantaba un 2013 que dejaba el
        Job en `Failed` sobre un esquema correcto."""
        self.conexion.muere_en = ("IS_USED_LOCK",)

        self._correr("--comando", "migrate --noinput")  # no levanta

        self.assertEqual(self.corridos, [("migrate", "--noinput")])
        self.assertIn("AVISO", self.salida.getvalue())
        self.assertIn("se cayó durante el bootstrap", self.salida.getvalue())
        self.assertIn("no falla por esto", self.salida.getvalue())

    def test_lo_mismo_con_interface_error(self):
        """`MySQLdb` levanta una u otra según dónde la encuentre."""
        self.conexion.muere_en = ("IS_USED_LOCK",)
        self.conexion.excepcion_de_caida = InterfaceError

        self._correr("--comando", "migrate --noinput")

        self.assertIn("InterfaceError", self.salida.getvalue())

    def test_una_conexion_muerta_no_tapa_el_error_del_comando(self):
        """Si el `migrate` falló, el que manda es ese error, no el del candado."""
        self.conexion.muere_en = ("IS_USED_LOCK",)

        with mock.patch(f"{MODULO}.call_command", side_effect=CommandError("migrate explotó")):
            with self.assertRaises(CommandError) as cm:
                self._correr("--comando", "migrate --noinput")

        self.assertIn("migrate explotó", str(cm.exception))

    def test_avisa_distinto_si_el_candado_quedo_libre(self):
        """Nadie lo tiene: se cayó la conexión dedicada. No hay señal de que entrara otro."""
        self.conexion.duenio_del_candado = None

        self._correr("--comando", "migrate --noinput")

        self.assertIn("AVISO", self.salida.getvalue())
        self.assertIn("se cayó durante el bootstrap", self.salida.getvalue())
        self.assertNotIn("otro bootstrap entró", self.salida.getvalue())
