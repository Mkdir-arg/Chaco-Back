"""El deploy mira si `django_migrations` y el esquema se corresponden (OPS-01, RED-15).

El escenario que la ficha reprodujo en icore: el checkout quedó en una rama vieja
(`a9fc4ee`) cuyas migraciones del constructor se llamaban `0057`-`0062`, y `development`
las renumeró a `0060`-`0065`. El deploy aplica 0057-0059 —que ahí son **índices**, otra
cosa— y muere en `0060_catalogo_grupos_origen_canal` con `1050 Table already exists`:
CrashLoop con un error que no dice nada de lo que pasó.

El segundo origen del mismo síntoma es el restore (`proyecto-restore-prd-deja-tablas-
huerfanas`) y el tercero es un **rollback fallido en MariaDB**, donde `can_rollback_ddl`
es `False` (RED-15): queda una tabla que ningún modelo del estado final nombra.

El comando mira las tres cosas, sin escribir una sola fila:

1. filas en `django_migrations` sin archivo en disco (`applied - disk`);
2. `CreateModel` del plan cuya tabla **ya existe** (el caso de icore);
3. tablas que existen y que el estado final no nombra (el inverso, RED-15).
"""

import unittest
from pathlib import Path

from django.conf import settings
from django.core.management import CommandError, call_command
from django.db import connection
from django.db.migrations.operations import CreateModel
from django.db.migrations.recorder import MigrationRecorder
from django.test import SimpleTestCase, TransactionTestCase

from core.management.commands.verificar_esquema_migraciones import (
    colisiones_de_tablas,
    filas_sin_archivo,
    migraciones_pendientes,
    tablas_huerfanas,
)

RAIZ = Path(settings.BASE_DIR)


def _Operacion(name, db_table=None):
    """Un `CreateModel` de verdad: el chequeo discrimina por tipo, no por nombre."""
    return CreateModel(name=name, fields=[], options={"db_table": db_table} if db_table else {})


class _Migracion:
    def __init__(self, app_label, name, operations):
        self.app_label = app_label
        self.name = name
        self.operations = operations


class ColisionDeTablasTests(SimpleTestCase):
    """(2) El caso de icore, en una función pura."""

    def test_detecta_la_tabla_que_la_migracion_va_a_crear_y_ya_existe(self):
        plan = [_Migracion("programas", "0060_catalogo_grupos_origen_canal", [_Operacion("GrupoOrigen")])]

        colisiones = colisiones_de_tablas(plan, {"programas_grupoorigen", "django_migrations"})

        self.assertEqual(
            colisiones,
            [("programas_grupoorigen", "programas", "0060_catalogo_grupos_origen_canal")],
        )

    def test_respeta_db_table_explicito(self):
        plan = [_Migracion("programas", "0099_x", [_Operacion("Cosa", db_table="tabla_a_mano")])]

        self.assertEqual(colisiones_de_tablas(plan, {"tabla_a_mano"}), [("tabla_a_mano", "programas", "0099_x")])

    def test_sin_colision_no_reporta_nada(self):
        plan = [_Migracion("programas", "0060_x", [_Operacion("GrupoOrigen")])]

        self.assertEqual(colisiones_de_tablas(plan, {"otra_tabla"}), [])

    def test_compara_sin_distinguir_mayusculas(self):
        """MySQL en Windows baja los nombres de tabla; MariaDB en Linux no."""
        plan = [_Migracion("programas", "0060_x", [_Operacion("GrupoOrigen")])]

        self.assertTrue(colisiones_de_tablas(plan, {"PROGRAMAS_GRUPOORIGEN"}))


class _Grafo:
    def __init__(self, nodes):
        self.nodes = nodes


class _Loader:
    def __init__(self, nodes, aplicadas):
        self.graph = _Grafo(nodes)
        self.applied_migrations = aplicadas


class MigracionesPendientesTests(SimpleTestCase):
    """Por qué no se usa `MigrationExecutor.migration_plan`.

    Medido contra MariaDB 10.11 con el estado de icore reproducido: si el nodo hoja ya
    figura aplicado, `migration_plan` entra en su rama de *backwards* —`elif target in
    applied`— y devuelve una lista **vacía**, aunque en el medio del grafo haya
    migraciones sin aplicar. Para esta guarda eso sería un falso OK.
    """

    def test_toma_cualquier_migracion_sin_aplicar_del_grafo(self):
        nodes = {
            ("programas", "0059_x"): "m59",
            ("programas", "0060_y"): "m60",
            ("programas", "0075_z"): "m75",
        }
        aplicadas = {("programas", "0059_x"): 1, ("programas", "0075_z"): 3}

        self.assertEqual(migraciones_pendientes(_Loader(nodes, aplicadas)), ["m60"])

    def test_el_orden_es_estable(self):
        nodes = {("b", "0001"): "mb", ("a", "0002"): "ma2", ("a", "0001"): "ma1"}

        self.assertEqual(migraciones_pendientes(_Loader(nodes, {})), ["ma1", "ma2", "mb"])


class FilasSinArchivoTests(SimpleTestCase):
    """(1) Lo que delata un checkout en la rama equivocada."""

    def test_una_fila_aplicada_sin_archivo_es_un_fantasma(self):
        aplicadas = {("programas", "0057_catalogo_grupos_origen_canal"), ("programas", "0060_x")}
        en_disco = {("programas", "0060_x")}

        self.assertEqual(
            filas_sin_archivo(aplicadas, en_disco),
            [("programas", "0057_catalogo_grupos_origen_canal")],
        )

    def test_sin_fantasmas_no_reporta_nada(self):
        self.assertEqual(filas_sin_archivo({("a", "0001")}, {("a", "0001"), ("a", "0002")}), [])


class TablasHuerfanasTests(SimpleTestCase):
    """(3) El inverso de RED-15: lo que deja un rollback que no pudo volver."""

    def test_una_tabla_que_ningun_modelo_nombra_es_huerfana(self):
        self.assertEqual(
            tablas_huerfanas({"legajos_ciudadano", "legajos_derivacion"}, {"legajos_ciudadano"}),
            ["legajos_derivacion"],
        )

    def test_django_migrations_no_es_huerfana(self):
        self.assertEqual(tablas_huerfanas({"django_migrations"}, set()), [])


class ComandoTests(TransactionTestCase):
    """El comando entero contra la base de la suite."""

    # Las tablas las arma el runner (`--run-syncdb` o migraciones según el entorno):
    # recrearlas por fixture no agregaría nada.
    available_apps = None

    def test_una_base_coherente_pasa(self):
        call_command("verificar_esquema_migraciones")

    def test_una_fila_sin_archivo_lo_frena(self):
        """El test que nombra la ficha: `programas.0099_fantasma` en `django_migrations`."""
        MigrationRecorder(connection).record_applied("programas", "0099_fantasma")
        try:
            with self.assertRaises(CommandError) as capturado:
                call_command("verificar_esquema_migraciones")
        finally:
            MigrationRecorder(connection).record_unapplied("programas", "0099_fantasma")

        mensaje = str(capturado.exception)
        self.assertIn("0099_fantasma", mensaje)
        self.assertIn("NUNCA", mensaje, "el mensaje tiene que decir que --fake no es la salida")

    def test_no_escribe_nada(self):
        """Es una guarda de arranque: si tocara la base, sería parte del problema."""
        antes = set(connection.introspection.table_names())

        call_command("verificar_esquema_migraciones")

        self.assertEqual(set(connection.introspection.table_names()), antes)


class EntrypointTests(SimpleTestCase):
    """La guarda sirve si el deploy la corre: `docker-entrypoint.sh`."""

    def setUp(self):
        self.script = (RAIZ / "docker-entrypoint.sh").read_text(encoding="utf-8")

    def test_el_entrypoint_corre_la_guarda(self):
        self.assertIn("verificar_esquema_migraciones", self.script)

    def test_corre_antes_del_migrate(self):
        self.assertLess(
            self.script.index("verificar_esquema_migraciones"),
            self.script.index("migrate --run-syncdb"),
            "después del migrate no sirve de nada: el 1050 ya pasó",
        )

    def test_se_puede_saltear(self):
        """`SKIP_SCHEMA_GUARD=true` para el ambiente donde la guarda se equivoque."""
        self.assertIn("SKIP_SCHEMA_GUARD", self.script)


class ScriptDeIcoreTests(SimpleTestCase):
    """(3) de la propuesta: el renombre versionado, en vez de escrito en un chat."""

    RUTA = RAIZ / "core" / "sql" / "2026-10-06_renombrar_migraciones_icore.sql"

    @unittest.skipUnless((RAIZ / "scripts").is_dir(), "sin scripts/ (árbol del release)")
    def test_el_script_renombra_las_seis_filas(self):
        sql = self.RUTA.read_text(encoding="utf-8")

        for vieja, nueva in (
            ("0057_catalogo_grupos_origen_canal", "0060_catalogo_grupos_origen_canal"),
            ("0058_diseno_formulario", "0061_diseno_formulario"),
            ("0059_formulario_respuestas_definicion", "0062_formulario_respuestas_definicion"),
            ("0060_sembrar_catalogo_protegido", "0063_sembrar_catalogo_protegido"),
            ("0061_orden_validacion_sis", "0064_orden_validacion_sis"),
            ("0062_padron_relevamiento_herencia", "0065_padron_relevamiento_herencia"),
        ):
            with self.subTest(vieja=vieja):
                self.assertIn(f"name='{nueva}'", sql)
                self.assertIn(f"name='{vieja}'", sql)

    def test_las_seis_migraciones_nuevas_existen_en_el_repo(self):
        """Si alguien las vuelve a renumerar, el script deja de servir y hay que saberlo."""
        for nombre in (
            "0060_catalogo_grupos_origen_canal",
            "0061_diseno_formulario",
            "0062_formulario_respuestas_definicion",
            "0063_sembrar_catalogo_protegido",
            "0064_orden_validacion_sis",
            "0065_padron_relevamiento_herencia",
        ):
            with self.subTest(nombre=nombre):
                self.assertTrue((RAIZ / "programas" / "migrations" / f"{nombre}.py").exists())
