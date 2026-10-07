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
    # La clave la trae el CSV del operador, no el código; sus guardas son las de
    # G2-05 (`--aplicar`, `--actualizar --motivo`, `validate_password`).
    "users/management/commands/import_users_from_csv.py",
}

_TOCA_CLAVES = {"set_password", "create_user", "create_superuser", "set_unusable_password"}


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

    def test_ningun_comando_llama_a_cache_clear(self):
        culpables = []
        for relativa, arbol in comandos_del_repo():
            if relativa in PUEDEN_VACIAR_EL_CACHE:
                continue
            for nodo in ast.walk(arbol):
                if (
                    isinstance(nodo, ast.Call)
                    and isinstance(nodo.func, ast.Attribute)
                    and nodo.func.attr == "clear"
                    and isinstance(nodo.func.value, ast.Name)
                    and nodo.func.value.id == "cache"
                ):
                    culpables.append(f"{relativa}:{nodo.lineno}")
        self.assertEqual(
            culpables,
            [],
            "`cache.clear()` vacía el Redis compartido (sesiones, Channels y caché): "
            "invalidá solo las claves que tocaste.",
        )

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
            llamados = _nombres_llamados(arbol)
            if llamados & _TOCA_CLAVES and "exigir_entorno_demo" not in llamados:
                culpables.append(relativa)
        self.assertEqual(
            culpables,
            [],
            "Un comando de management que da de alta cuentas o les fija la clave tiene que llamar a "
            "`core.management.guardas.exigir_entorno_demo()`, o entrar al allowlist con su motivo "
            "(OPS-02: `crear_usuarios_sistema` dejaba admin/admin123 en todo ambiente que lo corriera).",
        )
