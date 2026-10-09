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
from pathlib import Path
from types import SimpleNamespace

from django.conf import settings
from django.db import connection
from django.test import SimpleTestCase, TestCase

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
        for paquete in PAQUETES_DEL_PRODUCTO:
            for ruta in (RAIZ / paquete).rglob("*.py"):
                for modulo in _modulos_importados(ruta) & set(RETIRADOS.values()):
                    culpables.setdefault(modulo, []).append(str(ruta.relative_to(RAIZ)))

        self.assertEqual(culpables, {}, f"importan paquetes que la imagen ya no trae: {culpables}")


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
