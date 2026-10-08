"""OPS-02 y G1c-12 · Los comandos que no pueden existir, y la guarda de los que quedan.

Tres comandos sembraban cuentas con **credenciales escritas en el código** y viajaban
en el release a ECOM: `crear_usuarios_sistema` (deja `admin`/`admin123` superusuario y
`admin1..3` en el rol «Administrador» real, y le **resetea** la clave si ya existen),
`setup_roles_contactos` y `setup_groups` (diez grupos sin `RolMeta` que `seed_rbac`
convierte después en roles fantasma). Es el mismo problema que el Cambio 28 cerró con
`crear_superadmin` y con el mismo remedio: **se borran**, no se parametrizan. Cualquier
variante que los deje creando usuarios vuelve a poner una credencial por defecto en un
ambiente servido.

`debug_ciudadanos` (G1c-12) corría `cache.clear()`, que en `django_redis` es un
`FLUSHDB` del Redis **compartido**: en `prd`, `default`, `sessions` y `CHANNEL_LAYERS`
salen del mismo `REDIS_URL`, así que un «debug» desloguea a todo el backoffice, corta los
pasos en curso de la inscripción pública y borra los grupos de Channels. Además imprimía
DNI y nombre de tres ciudadanos. También se borra.

Los seeds de demo que **sí** quedan (siembran datos de prueba, no cuentas de sistema)
pasan por `core.management.guardas.exigir_entorno_demo`, que mira `DEBUG` o
`CHACO_PERMITIR_SEED_DEMO`. **No** `settings.ENVIRONMENT`: icore (DEV) vale `prd` y QA
lo pisa a `prd` (OPS-12), así que esa variable no distingue un ambiente de demo.

Los dos ratchets de abajo son lo que impide que esto vuelva por otra puerta: no alcanza
con borrar cuatro archivos si mañana el quinto hace lo mismo.
"""

import ast
import io
import os
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings

from core.management.guardas import VARIABLE_SEED_DEMO

RAIZ = Path(settings.BASE_DIR)

#: Los cuatro que se fueron en el Cambio 171 (OPS-02 y G1c-12).
BORRADOS = [
    "crear_usuarios_sistema",
    "setup_groups",
    "setup_roles_contactos",
    "debug_ciudadanos",
]

#: Los seeds de demo que quedan: siembran datos de prueba, no cuentas de sistema.
SEEDS_DEMO = [
    "seed_becas_demo_mobile",
    "seed_relevamientos_periodo_demo",
    "seed_busqueda_ciudadanos_demo",
]

#: `cache.clear()` es `FLUSHDB` del Redis compartido. El único que puede es el que
#: ya no puede correr fuera de una base efímera (su propia guarda, confirmada por
#: `core/tests/test_seed_perf_guarda.py`).
PUEDEN_VACIAR_EL_CACHE = {"core/management/commands/seed_perf.py"}

#: Comandos que tocan contraseñas sin la guarda de demo, con su motivo.
CREDENCIALES_SIN_GUARDA_DE_DEMO = {
    # Los tres de abajo tienen una guarda **más** fuerte: cortan salvo que la base
    # abierta sea la suya y efímera (`SELECT DATABASE()` contra un nombre fijo, o
    # SQLite in-memory de tests). Es lo que la ficha de OPS-02 refutaba de A8-03.
    "core/management/commands/seed_perf.py",
    "core/management/commands/prepare_perf_http_probe.py",
    "programas/management/commands/seed_aceptacion_reportes.py",
    # Lo encontró el ratchet ampliado (ninguna de sus líneas llama a `set_password`:
    # le **copia el hash** a un usuario de sonda, `user.password = source.password`).
    # Su guarda es de las fuertes: `_assert_ephemeral_ci` exige `PERFORMANCE_CI=1`,
    # `ENVIRONMENT=ci`, MySQL y que `SELECT DATABASE()` devuelva `chaco_perf_ci`.
    "core/management/commands/perf_ci_probe.py",
    # La clave la trae el CSV del operador, no el código; sus guardas son las de
    # G2-05 (`--aplicar`, `--actualizar --motivo`, `validate_password`).
    "users/management/commands/import_users_from_csv.py",
}

#: Lo que «tocar una clave» puede ser: fijarla, generar su hash o dar de alta la
#: cuenta que la lleva. `make_password` entró en la revisión del PR de G1c-12: un
#: comando que escribe `user.password = make_password(...)` esquivaba el ratchet
#: entero porque nunca llama a `set_password`.
_TOCA_CLAVES = {"set_password", "create_user", "create_superuser", "set_unusable_password", "make_password"}

#: De dónde sale el cache de Django. Los nombres que un módulo importe de acá son
#: los que convierten un `.clear()` en un `FLUSHDB` del Redis compartido.
_MODULO_CACHE = "django.core.cache"


def comandos_del_repo():
    """`[(ruta relativa con `/`, árbol AST)]` de todo `*/management/commands/*.py`."""
    salida = []
    for ruta in sorted(RAIZ.glob("*/management/commands/*.py")):
        if ruta.name == "__init__.py":
            continue
        relativa = ruta.relative_to(RAIZ).as_posix()
        salida.append((relativa, ast.parse(ruta.read_text(encoding="utf-8"))))
    return salida


def _nombres_llamados(arbol):
    """Los nombres de función llamados en el módulo (`foo()` y `x.foo()`)."""
    nombres = set()
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Call):
            continue
        if isinstance(nodo.func, ast.Attribute):
            nombres.add(nodo.func.attr)
        elif isinstance(nodo.func, ast.Name):
            nombres.add(nodo.func.id)
    return nombres


def _raiz_del_nombre(nodo):
    """El nombre con el que arranca una expresión: `caches["default"].clear` → `caches`,
    `django.core.cache.cache` → `django`. `None` si no arranca en un nombre."""
    while isinstance(nodo, (ast.Attribute, ast.Subscript, ast.Call)):
        nodo = nodo.func if isinstance(nodo, ast.Call) else nodo.value
    return nodo.id if isinstance(nodo, ast.Name) else None


def _nombres_del_cache(arbol):
    """Los nombres locales del módulo que llevan al cache de Django, sea cual sea la
    puerta: `from django.core.cache import cache`, `... import caches`, el mismo con
    `as`, o `import django.core.cache`."""
    nombres = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ImportFrom) and (nodo.module or "") == _MODULO_CACHE:
            nombres.update(alias.asname or alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.Import):
            for alias in nodo.names:
                if alias.name == _MODULO_CACHE or alias.name.startswith(f"{_MODULO_CACHE}."):
                    nombres.add(alias.asname or alias.name.split(".")[0])
    return nombres


def vaciados_del_cache(arbol):
    """Las líneas donde el módulo vacía un cache de Django.

    Cuenta **cualquier** forma de llegar al objeto —`cache.clear()`,
    `caches["default"].clear()`, `caches[alias].clear()`, `get_cache(...).clear()`,
    `django.core.cache.cache.clear()`, y los mismos con un alias de importación—,
    no solo el `cache.clear()` literal que miraba la primera versión del ratchet:
    en `django_redis` todos terminan en el mismo `FLUSHDB` del Redis compartido.
    """
    nombres = _nombres_del_cache(arbol)
    if not nombres:
        return []
    return sorted(
        nodo.lineno
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.Call)
        and isinstance(nodo.func, ast.Attribute)
        and nodo.func.attr == "clear"
        and _raiz_del_nombre(nodo.func.value) in nombres
    )


def asignaciones_de_clave(arbol):
    """Las líneas donde el módulo le escribe la contraseña a un objeto sin pasar por
    `set_password`: `usuario.password = …` (o `+=`, o con anotación) y
    `setattr(usuario, "password", …)`."""
    lineas = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Assign):
            destinos = nodo.targets
        elif isinstance(nodo, (ast.AnnAssign, ast.AugAssign)):
            destinos = [nodo.target]
        elif (
            isinstance(nodo, ast.Call)
            and isinstance(nodo.func, ast.Name)
            and nodo.func.id == "setattr"
            and len(nodo.args) == 3
            and isinstance(nodo.args[1], ast.Constant)
            and nodo.args[1].value == "password"
        ):
            lineas.append(nodo.lineno)
            continue
        else:
            continue
        if any(isinstance(d, ast.Attribute) and d.attr == "password" for d in destinos):
            lineas.append(nodo.lineno)
    return sorted(lineas)


def toca_claves(arbol):
    """¿El módulo da de alta cuentas, les fija la clave o le escribe el hash?"""
    return bool(_nombres_llamados(arbol) & _TOCA_CLAVES) or bool(asignaciones_de_clave(arbol))


class ComandosBorradosTests(SimpleTestCase):
    """Los cuatro dejaron de existir: `manage.py <x>` ya no los encuentra."""

    def test_los_cuatro_comandos_peligrosos_ya_no_existen(self):
        for nombre in BORRADOS:
            with self.subTest(comando=nombre):
                with self.assertRaises(CommandError) as capturado:
                    call_command(nombre)
                self.assertIn("Unknown command", str(capturado.exception))

    def test_tampoco_quedan_sus_archivos(self):
        for relativa in (
            "users/management/commands/crear_usuarios_sistema.py",
            "legajos/management/commands/setup_groups.py",
            "legajos/management/commands/setup_roles_contactos.py",
            "legajos/management/commands/debug_ciudadanos.py",
        ):
            with self.subTest(archivo=relativa):
                self.assertFalse((RAIZ / relativa).exists(), f"{relativa} volvió al repo")


class SeedsDemoExigenEntornoDeDemoTests(TestCase):
    """Los seeds de demo no corren en un ambiente servido."""

    @override_settings(DEBUG=False)
    def test_sin_debug_ni_variable_los_tres_cortan(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(VARIABLE_SEED_DEMO, None)
            for nombre in SEEDS_DEMO:
                with self.subTest(comando=nombre):
                    with self.assertRaises(CommandError) as capturado:
                        call_command(nombre, stdout=io.StringIO())
                    self.assertIn(VARIABLE_SEED_DEMO, str(capturado.exception))

    @override_settings(DEBUG=True)
    def test_con_debug_el_seed_siembra(self):
        from legajos.models import Ciudadano

        call_command("seed_busqueda_ciudadanos_demo", stdout=io.StringIO())
        self.assertTrue(Ciudadano.objects.filter(dni__startswith="31530").exists())

    @override_settings(DEBUG=False)
    def test_la_variable_de_escape_habilita_el_seed(self):
        from legajos.models import Ciudadano

        with mock.patch.dict(os.environ, {VARIABLE_SEED_DEMO: "1"}):
            call_command("seed_busqueda_ciudadanos_demo", stdout=io.StringIO())
        self.assertTrue(Ciudadano.objects.filter(dni__startswith="31530").exists())

    @override_settings(DEBUG=True)
    def test_no_le_cambia_la_clave_ni_reactiva_a_un_usuario_que_ya_existe(self):
        """Era el agravante de OPS-02: el seed pisaba la clave de una cuenta real."""
        usuario = get_user_model().objects.create_user(username="territorial_demo", password="la-del-duenio")
        usuario.is_active = False
        usuario.save(update_fields=["is_active"])

        call_command("seed_relevamientos_periodo_demo", stdout=io.StringIO())

        usuario.refresh_from_db()
        self.assertTrue(usuario.check_password("la-del-duenio"))
        self.assertFalse(usuario.is_active)


class NingunComandoVaciaElCacheCompartidoTests(SimpleTestCase):
    """G1c-12 · `cache.clear()` es `FLUSHDB` del Redis que comparten sesiones y Channels."""

    def test_ningun_comando_vacia_un_cache_de_django(self):
        culpables = []
        for relativa, arbol in comandos_del_repo():
            if relativa in PUEDEN_VACIAR_EL_CACHE:
                continue
            culpables.extend(f"{relativa}:{linea}" for linea in vaciados_del_cache(arbol))
        self.assertEqual(
            culpables,
            [],
            "Vaciar un cache de Django vacía el Redis compartido (sesiones, Channels y caché): "
            "invalidá solo las claves que tocaste.",
        )

    def test_el_ratchet_ve_las_otras_formas_de_llegar_al_cache(self):
        """La primera versión solo miraba el `cache.clear()` literal, así que
        `caches["default"].clear()` —el mismo `FLUSHDB`— pasaba de largo."""
        casos = {
            "from django.core.cache import cache\ncache.clear()\n": [2],
            'from django.core.cache import caches\ncaches["default"].clear()\n': [2],
            "from django.core.cache import caches\ndef f(alias):\n    caches[alias].clear()\n": [3],
            "from django.core.cache import cache as memoria\nmemoria.clear()\n": [2],
            "import django.core.cache\ndjango.core.cache.cache.clear()\n": [2],
            "from django.core.cache import caches\ncaches['sessions'].clear()\ncache.clear()\n": [2],
        }
        for fuente, lineas in casos.items():
            with self.subTest(fuente=fuente.splitlines()[-1]):
                self.assertEqual(vaciados_del_cache(ast.parse(fuente)), lineas)

    def test_el_ratchet_no_se_queja_de_un_clear_que_no_es_del_cache(self):
        for fuente in (
            "def f(datos):\n    datos.clear()\n",
            "cache = {}\ncache.clear()\n",  # un dict local llamado igual, sin el import
            "from django.core.cache import cache\ncache.delete('x')\n",
        ):
            with self.subTest(fuente=fuente.splitlines()[-1]):
                self.assertEqual(vaciados_del_cache(ast.parse(fuente)), [])

    def test_el_allowlist_nombra_archivos_que_existen(self):
        for relativa in PUEDEN_VACIAR_EL_CACHE | CREDENCIALES_SIN_GUARDA_DE_DEMO:
            with self.subTest(archivo=relativa):
                self.assertTrue((RAIZ / relativa).exists(), f"{relativa} ya no existe: sacalo del allowlist")


class NingunComandoSiembraCredencialesSinGuardaTests(SimpleTestCase):
    """OPS-02 · Un comando que toca contraseñas no puede correr en un ambiente servido."""

    def test_todo_comando_que_toca_claves_tiene_su_guarda(self):
        culpables = []
        for relativa, arbol in comandos_del_repo():
            if relativa in CREDENCIALES_SIN_GUARDA_DE_DEMO:
                continue
            if toca_claves(arbol) and "exigir_entorno_demo" not in _nombres_llamados(arbol):
                culpables.append(relativa)
        self.assertEqual(
            culpables,
            [],
            "Un comando de management que da de alta cuentas o les fija la clave tiene que llamar a "
            "`core.management.guardas.exigir_entorno_demo()`, o entrar al allowlist con su motivo "
            "(OPS-02: `crear_usuarios_sistema` dejaba admin/admin123 en todo ambiente que lo corriera).",
        )

    def test_el_ratchet_ve_el_hash_escrito_a_mano(self):
        """`set_password` no es la única puerta: escribir el hash directo en la columna
        deja la misma credencial y esquivaba el ratchet entero."""
        for fuente in (
            "from django.contrib.auth.hashers import make_password\nu.password = make_password('x')\n",
            "u.password = 'pbkdf2_sha256$...'\n",
            "setattr(u, 'password', hash_de_algun_lado)\n",
            "u: str = ''\nu.password += 'x'\n",
        ):
            with self.subTest(fuente=fuente.splitlines()[-1]):
                self.assertTrue(toca_claves(ast.parse(fuente)))

    def test_el_ratchet_no_confunde_una_variable_local_con_la_columna(self):
        for fuente in (
            "password = input()\n",
            "datos = {'password': 'x'}\n",
            "clave = row.get('Contraseña')\n",
        ):
            with self.subTest(fuente=fuente.splitlines()[-1]):
                self.assertFalse(toca_claves(ast.parse(fuente)))
