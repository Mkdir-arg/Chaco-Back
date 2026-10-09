"""OPS-13 · Lo que viaja en la imagen de producción es lo que la aplicación usa.

`requirements.txt` tenía once paquetes con **cero** imports en el código: el bloque
«AI/ML» entero (`openai`, `httpx`, `anyio`), `structlog`, `gevent`/`greenlet` (RED-45),
`django-simple-history`, `pymysql`, `django-health-check` y tres herramientas de
desarrollo (`debugpy`, `django-extensions`, `django-silk`) que además estaban cargadas en
`INSTALLED_APPS` o importadas desde `manage.py`.

Cada uno es código de terceros adentro de la imagen de PRD y superficie que `pip-audit`
—un check obligatorio— tiene que auditar: el Cambio 97 existió porque dos CVE de `anyio`,
que estaba ahí **solo** para destrabar a `openai`, bloquearon el merge de todos los PRs.

Lo que fija este módulo es la vuelta: que ninguno reaparezca sin que alguien lo decida, y
que la pieza que hizo falta para poder sacar `django-health-check` —`core.0003`, que borra
su tabla y sus dos filas de `django_migrations`— haga de verdad las dos cosas y sepa
volver atrás.
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.conf import settings
from django.db import connection
from django.test import SimpleTestCase, TestCase, override_settings

RAIZ = Path(settings.BASE_DIR)

#: El nombre del módulo empieza con un dígito, así que no se puede `import` a secas.
MIGRACION_DEL_RETIRO = "core.migrations.0003_retirar_django_health_check"

#: Paquete de `pip` → módulo que se importaría. El par importa: el test de
#: `requirements.txt` mira el primero y el de los imports el segundo.
RETIRADOS = {
    "openai": "openai",
    "httpx": "httpx",
    "anyio": "anyio",
    "structlog": "structlog",
    "gevent": "gevent",
    "greenlet": "greenlet",
    "django-simple-history": "simple_history",
    "pymysql": "pymysql",
    "django-health-check": "health_check",
    "debugpy": "debugpy",
    "django-extensions": "django_extensions",
    "django-silk": "silk",
}

#: Las tres últimas no se borraron: se mudaron a `requirements-dev.txt`, porque sí se usan
#: trabajando en local. La imagen no instala ese archivo.
MUDADOS_A_DESARROLLO = {"debugpy", "django-extensions", "django-silk"}

#: Dónde se buscan imports. Fuera quedan los `.venv*`, `docs/` y `node_modules`.
PAQUETES_DEL_PRODUCTO = (
    "config",
    "conversaciones",
    "configuracion",
    "core",
    "dashboard",
    "healthcheck",
    "legajos",
    "portal",
    "programas",
    "users",
)


def _lineas_activas(ruta: Path) -> list[str]:
    return [
        linea.strip()
        for linea in ruta.read_text(encoding="utf-8").splitlines()
        if linea.strip() and not linea.lstrip().startswith("#")
    ]


def _distribucion(linea: str) -> str:
    """`whitenoise[brotli]==6.8.2` → `whitenoise`."""
    return linea.split("==")[0].split("[")[0].split(";")[0].strip().lower()


def _fuentes_del_producto():
    """Todo `.py` que viaja en la imagen y puede importar algo.

    Los paquetes **y los `.py` sueltos de la raíz**. Lo segundo faltaba y costó:
    `manage.py` está fuera de todo paquete, así que su `import debugpy` incondicional
    —un paquete que OPS-13 sacó de la imagen— no lo veía nadie hasta que el contenedor
    de desarrollo no arrancó.
    """
    for paquete in PAQUETES_DEL_PRODUCTO:
        yield from (RAIZ / paquete).rglob("*.py")
    yield from sorted(RAIZ.glob("*.py"))


def _modulos_importados(ruta: Path) -> set[str]:
    """Los módulos raíz que un `.py` importa, por AST (los comentarios no cuentan)."""
    try:
        arbol = ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))
    except SyntaxError:  # pragma: no cover — lo cazaría antes `ruff check --select F`
        return set()
    modulos = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            modulos.update(alias.name.split(".")[0] for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.level == 0 and nodo.module:
            modulos.add(nodo.module.split(".")[0])
    return modulos


class RequirementsTests(SimpleTestCase):
    def test_los_paquetes_retirados_no_volvieron_a_la_imagen(self):
        """Nueve se fueron del todo y tres se mudaron: ninguno vuelve a `requirements.txt`."""
        distribuciones = {_distribucion(linea) for linea in _lineas_activas(RAIZ / "requirements.txt")}

        for paquete in RETIRADOS:
            with self.subTest(paquete=paquete):
                self.assertNotIn(
                    paquete.lower(),
                    distribuciones,
                    f"{paquete} volvió a `requirements.txt` (OPS-13): si hace falta de verdad, "
                    "sacalo de RETIRADOS en el mismo PR y decí para qué.",
                )

    def test_las_tres_de_desarrollo_estan_en_requirements_dev(self):
        """No se perdieron: `shell_plus`, `/silk/` y el debugger siguen a un `pip install`."""
        distribuciones = {_distribucion(linea) for linea in _lineas_activas(RAIZ / "requirements-dev.txt")}

        for paquete in MUDADOS_A_DESARROLLO:
            with self.subTest(paquete=paquete):
                self.assertIn(paquete.lower(), distribuciones)

    def test_requirements_dev_arrastra_la_imagen(self):
        """`-r requirements.txt`: el ambiente local es el de producción más estas tres."""
        self.assertIn("-r requirements.txt", (RAIZ / "requirements-dev.txt").read_text(encoding="utf-8"))

    def test_la_imagen_instala_solo_requirements(self):
        """El `Dockerfile` copia e instala **un** archivo. Si alguien agregara
        `requirements-dev.txt` o `requirements-ci.txt` al build, todo esto no serviría
        de nada."""
        dockerfile = (RAIZ / "Dockerfile").read_text(encoding="utf-8")

        self.assertIn("pip install --no-cache-dir -r requirements.txt", dockerfile)
        self.assertNotIn("requirements-dev.txt", dockerfile)
        self.assertNotIn("requirements-ci.txt", dockerfile)

    def test_nadie_los_importa(self):
        """La contracara: un import nuevo de algo que ya no se instala revienta en el
        arranque del pod, no en el PR. Por AST, así que los comentarios que los nombran
        —hay varios, explicando por qué se fueron— no cuentan."""
        culpables = {}
        for ruta in _fuentes_del_producto():
            for modulo in _modulos_importados(ruta) & set(RETIRADOS.values()):
                culpables.setdefault(modulo, []).append(str(ruta.relative_to(RAIZ)))

        self.assertEqual(culpables, {}, f"importan paquetes que la imagen ya no trae: {culpables}")

    def test_el_barrido_mira_tambien_la_raiz_del_repo(self):
        """Sin esto, el test de arriba vuelve a quedar ciego justo donde falló."""
        barridos = set(_fuentes_del_producto())

        self.assertIn(RAIZ / "manage.py", barridos)
        for ruta in RAIZ.glob("*.py"):
            with self.subTest(ruta=ruta.name):
                self.assertIn(ruta, barridos)


class InstalledAppsTests(SimpleTestCase):
    def test_health_check_ya_no_esta_instalada(self):
        """OPS-04 le sacó las URLs; OPS-13 la saca de `INSTALLED_APPS` y del `pip`. Las
        sondas son `healthcheck`, la app de este repo."""
        for app in ("health_check", "health_check.db", "health_check.cache"):
            with self.subTest(app=app):
                self.assertNotIn(app, settings.INSTALLED_APPS)

        self.assertIn("healthcheck", settings.INSTALLED_APPS)

    def test_las_apps_de_desarrollo_no_entran_sin_debug(self):
        """La suite corre con `DEBUG=False`, igual que un ambiente servido."""
        self.assertFalse(settings.DEBUG)
        for app in ("django_extensions", "silk"):
            with self.subTest(app=app):
                self.assertNotIn(app, settings.INSTALLED_APPS)

    def test_silk_se_monta_por_su_propia_bandera_y_no_por_debug(self):
        """`config/urls.py` miraba `DEBUG` a secas. Desde que `django-silk` vive en
        `requirements-dev.txt`, `DEBUG=True` ya no garantiza que el paquete esté: el
        `docker-compose.yml` de desarrollo levanta la imagen de producción con
        `DJANGO_DEBUG=True`."""
        urls = (RAIZ / "config" / "urls.py").read_text(encoding="utf-8")

        self.assertIn("SILK_HABILITADO", urls)
        self.assertEqual(settings.SILK_HABILITADO, "silk" in settings.INSTALLED_APPS)

    def test_el_modulo_endurecido_apaga_la_bandera_al_sacar_la_app(self):
        """`config/settings_production.py` filtraba `silk` de `INSTALLED_APPS` y dejaba
        `SILK_HABILITADO` como la había calculado `settings.py`, antes del filtro. Con
        `DJANGO_DEBUG=True` mal puesto en un ambiente servido y el paquete instalado, la
        bandera quedaba en `True` con la app afuera y `config/urls.py` montaba `/silk/`
        contra `silk.urls`."""
        base = importlib.import_module("config.settings")
        # Se arma la situación que dispara el bug —`silk` adentro y la bandera prendida—
        # porque la suite corre con `DEBUG=False` y ahí el test pasaría sin medir nada.
        # `from .settings import *` no re-ejecuta `config/settings.py`: lo toma de
        # `sys.modules`, así que el doble de arriba es lo que el `reload` va a leer.
        with (
            mock.patch.dict(os.environ, {"DJANGO_ALLOWED_HOSTS": "ejemplo.test"}),
            mock.patch.object(base, "INSTALLED_APPS", [*base.INSTALLED_APPS, "silk"]),
            mock.patch.object(base, "SILK_HABILITADO", True),
        ):
            produccion = importlib.reload(importlib.import_module("config.settings_production"))

        self.assertNotIn("silk", produccion.INSTALLED_APPS)
        self.assertFalse(produccion.SILK_HABILITADO)
        self.assertFalse(produccion.DEBUG)


class _BloqueaElPaquete:
    """Finder de `sys.meta_path` que hace desaparecer un paquete.

    Levanta `ModuleNotFoundError` en vez de devolver `None` porque devolver `None`
    significa «preguntale al que sigue»: el venv de esta máquina **sí** tiene `debugpy`
    instalado, así que un finder pasivo no reproduciría nada.
    """

    def __init__(self, nombre: str):
        self.nombre = nombre

    def find_spec(self, fullname, path=None, target=None):
        if fullname == self.nombre or fullname.startswith(f"{self.nombre}."):
            raise ModuleNotFoundError(f"No module named '{fullname}'", name=fullname)
        return None


class ManagePySinDebugpyTests(SimpleTestCase):
    """`manage.py` tiene que arrancar sin los paquetes de `requirements-dev.txt`.

    El caso real: `docker compose up` de desarrollo levanta **la imagen de producción**
    con `DJANGO_DEBUG=True` y `runserver`, que para el autoreload relanza el proceso con
    `RUN_MAIN=true`. Con el `import debugpy` incondicional que quedó de OPS-13, ese hijo
    moría con `ModuleNotFoundError` y el contenedor no arrancaba.
    """

    def setUp(self):
        # Por ruta y no por `import manage`: no depende de que la raíz del repo esté en
        # `sys.path` ni pisa la entrada de `sys.modules` del script que corre la suite.
        spec = importlib.util.spec_from_file_location("manage_del_repo", RAIZ / "manage.py")
        self.manage = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.manage)

    def _sin_debugpy(self):
        bloqueo = _BloqueaElPaquete("debugpy")
        sys.meta_path.insert(0, bloqueo)
        self.addCleanup(sys.meta_path.remove, bloqueo)
        cargados = {n: m for n, m in sys.modules.items() if n == "debugpy" or n.startswith("debugpy.")}
        for nombre in cargados:
            del sys.modules[nombre]
        self.addCleanup(sys.modules.update, cargados)

    def _arrancar(self):
        """`main()` como lo corre el contenedor, con el comando de Django mockeado."""
        ejecutadas = []
        with (
            override_settings(DEBUG=True),
            mock.patch.dict(os.environ, {"RUN_MAIN": "true"}),
            mock.patch("django.core.management.execute_from_command_line", ejecutadas.append),
        ):
            self.manage.main()
        return ejecutadas

    def test_arranca_con_debug_y_run_main_sin_el_paquete(self):
        self._sin_debugpy()

        self.assertEqual(self._arrancar(), [sys.argv], "manage.py no llegó a ejecutar el comando")

    def test_con_el_paquete_instalado_sigue_escuchando_en_el_3000(self):
        """El arreglo no cambia lo que pasa cuando `debugpy` está: es lo que usa quien
        depura adentro del contenedor."""
        self._sin_debugpy()
        falso = SimpleNamespace(listen=mock.Mock())

        # `import_module` mira `sys.modules` antes que `sys.meta_path`, así que el doble
        # gana sobre el bloqueo de arriba.
        with mock.patch.dict(sys.modules, {"debugpy": falso}):
            self.assertEqual(self._arrancar(), [sys.argv])

        falso.listen.assert_called_once_with(("0.0.0.0", 3000))

    def test_sin_run_main_no_se_toca_el_debugger(self):
        """El proceso padre de `runserver` no abre el puerto: lo abre el hijo."""
        self._sin_debugpy()
        falso = SimpleNamespace(listen=mock.Mock())
        ejecutadas = []

        with (
            override_settings(DEBUG=True),
            mock.patch.dict(os.environ, {}, clear=False),
            mock.patch.dict(sys.modules, {"debugpy": falso}),
            mock.patch("django.core.management.execute_from_command_line", ejecutadas.append),
        ):
            os.environ.pop("RUN_MAIN", None)
            os.environ.pop("WERKZEUG_RUN_MAIN", None)
            self.manage.main()

        falso.listen.assert_not_called()
        self.assertEqual(ejecutadas, [sys.argv])


class RetiroDeHealthCheckTests(TestCase):
    """`core.0003` de verdad: se ejercitan las dos direcciones contra la base de tests.

    La migración no corre en la suite (`DJANGO_SYNCDB_PROJECT_APPS=True` saltea las
    migraciones de las apps del proyecto), así que sus funciones se llaman a mano. Es la
    única forma de que el borrado y su reversa estén probados antes de que el deploy los
    corra contra MariaDB.
    """

    def setUp(self):
        self.migracion = importlib.import_module(MIGRACION_DEL_RETIRO)
        # `retirar` y `restituir` solo usan `schema_editor.connection`. Se les pasa un
        # doble con ese atributo en vez de `connection.schema_editor()` porque el editor
        # de SQLite se niega a abrirse adentro del `atomic()` de `TestCase`, y el
        # aislamiento de la transaccion es justo lo que mantiene limpia la base de tests.
        self.editor = SimpleNamespace(connection=connection)

    def _existe_la_tabla(self):
        with connection.cursor() as cursor:
            return self.migracion.TABLA in connection.introspection.table_names(cursor)

    def _filas(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT app, name FROM django_migrations WHERE app IN (%s, %s)",
                [self.migracion.FILAS[0][0], self.migracion.FILAS[1][0]],
            )
            return sorted(tuple(fila) for fila in cursor.fetchall())

    def test_restituir_deja_el_estado_de_antes_y_retirar_lo_limpia(self):
        self.migracion.restituir(None, self.editor)

        self.assertTrue(self._existe_la_tabla(), "la reversa tiene que recrear la tabla")
        self.assertEqual(self._filas(), sorted(self.migracion.FILAS))

        self.migracion.retirar(None, self.editor)

        self.assertFalse(self._existe_la_tabla(), "la tabla huérfana sigue en la base")
        self.assertEqual(self._filas(), [], "las dos filas sin archivo siguen en django_migrations")

    def test_retirar_es_idempotente(self):
        """`atomic = False` (RED-58): un corte deja el esquema donde llegó y **sin** fila
        en `django_migrations`, así que el reintento corre el archivo entero otra vez."""
        self.migracion.retirar(None, self.editor)
        self.migracion.retirar(None, self.editor)

        self.assertFalse(self._existe_la_tabla())

    def test_restituir_es_idempotente(self):
        self.migracion.restituir(None, self.editor)
        self.migracion.restituir(None, self.editor)

        self.assertEqual(self._filas(), sorted(self.migracion.FILAS))
