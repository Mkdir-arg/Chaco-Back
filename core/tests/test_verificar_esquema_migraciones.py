"""El deploy mira si `django_migrations` y el esquema se corresponden (OPS-01, RED-15).

El escenario que la ficha reprodujo en icore: el checkout quedó en una rama vieja
(`a9fc4ee`) cuyas migraciones del constructor se llamaban `0057`-`0062`, y `development`
las renumeró a `0060`-`0065`. El deploy aplica 0057-0059 —que ahí son **índices**, otra
cosa— y muere en `0060_catalogo_grupos_origen_canal` con `1050 Table already exists`:
CrashLoop con un error que no dice nada de lo que pasó.

El segundo origen del mismo síntoma es el restore (`proyecto-restore-prd-deja-tablas-
huerfanas`) y el tercero es un **rollback fallido en MariaDB**, donde `can_rollback_ddl`
es `False` (RED-15): queda una tabla que ningún modelo del estado final nombra.

El comando mira las tres cosas, sin escribir una sola fila, pero **solo dos frenan**:

1. filas en `django_migrations` sin archivo en disco. Frena **solo** si son una
   renumeración —la misma migración está en disco con otro número y sin aplicar—, que es
   lo único que predice que `migrate` la va a volver a correr. El resto se avisa: una
   base cualquiera tiene filas inertes (`silk`, `turnos`, `tramites`, migraciones
   borradas) que no se van a limpiar nunca y abortar por ellas deja ambientes que **no
   vuelven a arrancar**;
2. `CreateModel` sin aplicar cuya tabla **ya existe** (frena: es el `1050` del deploy);
3. tablas que existen y que el estado final no nombra (avisa; frena con `--estricto`).
"""

import unittest
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core.management import CommandError, call_command
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.operations import CreateModel
from django.db.migrations.recorder import MigrationRecorder
from django.test import SimpleTestCase, TransactionTestCase

from core.management.commands.verificar_esquema_migraciones import (
    clasificar_filas_sin_archivo,
    claves_conocidas,
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


class _LoaderConReemplazos:
    def __init__(self, disk, replacements=None):
        self.disk_migrations = {clave: None for clave in disk}
        self.replacements = replacements or {}


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


class _Reemplazo:
    def __init__(self, replaces):
        self.replaces = replaces


class ClavesConocidasTests(SimpleTestCase):
    """Una migración reemplazada por un squash figura aplicada y no tiene archivo propio.

    Es correcto y permanente, no un fantasma. El caso vivo del repo es
    `django-health-check`: su `db.0001_initial` declara
    `replaces = [("health_check_db", "0001_initial")]`, así que `django_migrations`
    guarda **dos** filas y en disco hay **un** archivo, bajo un tercer label. Sin
    contemplarlo, la guarda abortaría el arranque en icore, en testing y en PRD —lo midió
    el CI de este mismo PR—, y lo haría además con cualquier squash futuro del proyecto.
    """

    def test_una_migracion_reemplazada_no_es_un_fantasma(self):
        loader = _LoaderConReemplazos(
            disk={("db", "0001_initial")},
            replacements={("db", "0001_initial"): _Reemplazo([("health_check_db", "0001_initial")])},
        )

        conocidas = claves_conocidas(loader)

        self.assertEqual(
            filas_sin_archivo({("db", "0001_initial"), ("health_check_db", "0001_initial")}, conocidas), []
        )

    def test_una_fila_que_ningun_replaces_cubre_sigue_siendo_un_fantasma(self):
        loader = _LoaderConReemplazos(
            disk={("db", "0001_initial")},
            replacements={("db", "0001_initial"): _Reemplazo([("health_check_db", "0001_initial")])},
        )

        fantasmas = filas_sin_archivo({("programas", "0099_fantasma")}, claves_conocidas(loader))

        self.assertEqual(fantasmas, [("programas", "0099_fantasma")])

    def test_sin_reemplazos_son_las_de_disco_y_nada_mas(self):
        self.assertEqual(claves_conocidas(_LoaderConReemplazos(disk={("a", "0001")})), {("a", "0001")})


class _LoaderClasificacion:
    """Lo mínimo que `clasificar_filas_sin_archivo` mira: el grafo, lo aplicado y las apps."""

    def __init__(self, nodes, aplicadas, migrated_apps):
        self.graph = _Grafo({clave: clave for clave in nodes})
        self.applied_migrations = {clave: 1 for clave in aplicadas}
        self.migrated_apps = set(migrated_apps)


class ClasificarFilasSinArchivoTests(SimpleTestCase):
    """Qué fila sin archivo frena el deploy y cuál solo se avisa (revisión del PR #601).

    Abortar por **toda** fila sin archivo deja ambientes que no vuelven a arrancar nunca,
    porque hay filas inertes que ninguna base se va a sacar de encima:

    - `silk.0001`-`0008`: `silk` entra a `INSTALLED_APPS` solo con `DEBUG`. Una base
      migrada con `DJANGO_DEBUG=True` y arrancada con `False` las tiene siempre;
    - `turnos.*`: app borrada del repo;
    - `tramites.*`: app instalada que ya **no** tiene paquete de migraciones;
    - `programas.0046_formulario_fecha_aprobacion_formulario_fecha_rechazo`: migración
      borrada el 18/08/2026 cuyo número se reusó para otra cosa.

    Lo único que, por sí solo, predice una rotura es la **renumeración**: la misma
    migración está en disco con otro número y sin aplicar, así que `migrate` la va a
    volver a correr sobre un esquema que ya la tiene. Es el estado de icore.
    """

    def _icore(self):
        """Las seis del constructor registradas como 0057-0062 y en disco como 0060-0065."""
        viejas = [
            "0057_catalogo_grupos_origen_canal",
            "0058_diseno_formulario",
            "0059_formulario_respuestas_definicion",
        ]
        nuevas = [
            "0060_catalogo_grupos_origen_canal",
            "0061_diseno_formulario",
            "0062_formulario_respuestas_definicion",
        ]
        loader = _LoaderClasificacion(
            nodes=[("programas", nombre) for nombre in nuevas],
            aplicadas=[("programas", nombre) for nombre in viejas],
            migrated_apps={"programas"},
        )
        return loader, [("programas", nombre) for nombre in viejas]

    def test_una_renumeracion_frena(self):
        loader, fantasmas = self._icore()

        frenan, inertes = clasificar_filas_sin_archivo(fantasmas, loader)

        self.assertEqual(
            frenan,
            [
                (("programas", "0057_catalogo_grupos_origen_canal"), "0060_catalogo_grupos_origen_canal"),
                (("programas", "0058_diseno_formulario"), "0061_diseno_formulario"),
                (("programas", "0059_formulario_respuestas_definicion"), "0062_formulario_respuestas_definicion"),
            ],
        )
        self.assertEqual(inertes, [])

    def test_una_app_que_este_codigo_no_tiene_es_inerte(self):
        """`silk` sin `DEBUG`, `turnos` borrada, `tramites` sin paquete de migraciones."""
        loader = _LoaderClasificacion(nodes=[], aplicadas=[], migrated_apps={"programas"})
        fantasmas = [("silk", "0001_initial"), ("turnos", "0001_initial"), ("tramites", "0001_initial")]

        frenan, inertes = clasificar_filas_sin_archivo(fantasmas, loader)

        self.assertEqual(frenan, [])
        self.assertEqual([clave for clave, _ in inertes], fantasmas)
        self.assertTrue(all("no tiene migraciones para esa app" in motivo for _, motivo in inertes))

    def test_una_migracion_borrada_con_el_numero_reusado_es_inerte(self):
        """El caso real: la `0046` de hoy es otra cosa y no lleva el nombre de la vieja."""
        loader = _LoaderClasificacion(
            nodes=[("programas", "0046_relevamiento_franja_horaria")],
            aplicadas=[],
            migrated_apps={"programas"},
        )
        fantasma = ("programas", "0046_formulario_fecha_aprobacion_formulario_fecha_rechazo")

        frenan, inertes = clasificar_filas_sin_archivo([fantasma], loader)

        self.assertEqual(frenan, [])
        self.assertEqual(inertes, [(fantasma, "ninguna migración sin aplicar lleva ese mismo nombre")])

    def test_si_la_renumerada_ya_esta_aplicada_tambien_es_inerte(self):
        """Las dos filas conviven: `migrate` no tiene nada que correr, así que no rompe."""
        loader = _LoaderClasificacion(
            nodes=[("programas", "0060_catalogo_grupos_origen_canal")],
            aplicadas=[
                ("programas", "0057_catalogo_grupos_origen_canal"),
                ("programas", "0060_catalogo_grupos_origen_canal"),
            ],
            migrated_apps={"programas"},
        )

        frenan, _ = clasificar_filas_sin_archivo([("programas", "0057_catalogo_grupos_origen_canal")], loader)

        self.assertEqual(frenan, [])

    def test_un_nombre_sin_numero_no_revienta(self):
        loader = _LoaderClasificacion(nodes=[], aplicadas=[], migrated_apps={"programas"})

        frenan, inertes = clasificar_filas_sin_archivo([("programas", "sin_numero")], loader)

        self.assertEqual(frenan, [])
        self.assertEqual(len(inertes), 1)


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

    def test_una_fila_sin_archivo_suelta_avisa_y_deja_arrancar(self):
        """`programas.0099_fantasma` no predice ninguna rotura: `migrate` no la va a correr.

        Antes abortaba, y eso dejaba sin arrancar a cualquier base con `silk`, `turnos`,
        `tramites` o la `0046` borrada registradas: un ambiente que no vuelve **nunca**.
        """
        MigrationRecorder(connection).record_applied("programas", "0099_fantasma")
        salida = StringIO()
        try:
            call_command("verificar_esquema_migraciones", stderr=salida)
        finally:
            MigrationRecorder(connection).record_unapplied("programas", "0099_fantasma")

        self.assertIn("0099_fantasma", salida.getvalue())
        self.assertIn("no frena el deploy", salida.getvalue())

    def test_una_renumeracion_de_verdad_si_lo_frena(self):
        """El caso de icore, contra `django_migrations` de verdad.

        Se desaplica la última migración de `auth` y se registra **la misma** con otro
        número: es exactamente «la misma migración anotada con otro nombre», que es lo
        que `migrate` va a volver a correr. Se usa `auth` porque en la suite las apps del
        proyecto se arman con `--run-syncdb` y no tienen migraciones en disco.
        """
        registro = MigrationRecorder(connection)
        loader = MigrationLoader(connection)
        aplicadas_de_auth = sorted(nombre for app, nombre in loader.applied_migrations if app == "auth")
        ultima = aplicadas_de_auth[-1]
        renumerada = f"9999_{ultima.split('_', 1)[1]}"

        registro.record_unapplied("auth", ultima)
        registro.record_applied("auth", renumerada)
        try:
            with self.assertRaises(CommandError) as capturado:
                call_command("verificar_esquema_migraciones")
        finally:
            registro.record_unapplied("auth", renumerada)
            registro.record_applied("auth", ultima)

        mensaje = str(capturado.exception)
        self.assertIn(renumerada, mensaje)
        self.assertIn(ultima, mensaje, "tiene que decir con qué migración de disco choca")
        self.assertIn("NUNCA", mensaje, "el mensaje tiene que decir que --fake no es la salida")

    def test_solo_reporte_no_corta_aunque_haya_hallazgos(self):
        """El modo para mirar testing o PRD de ECOM sin que el exit code corte nada."""
        registro = MigrationRecorder(connection)
        loader = MigrationLoader(connection)
        ultima = sorted(nombre for app, nombre in loader.applied_migrations if app == "auth")[-1]
        renumerada = f"9999_{ultima.split('_', 1)[1]}"

        registro.record_unapplied("auth", ultima)
        registro.record_applied("auth", renumerada)
        salida = StringIO()
        try:
            call_command("verificar_esquema_migraciones", "--solo-reporte", stdout=salida)
        finally:
            registro.record_unapplied("auth", renumerada)
            registro.record_applied("auth", ultima)

        self.assertIn(renumerada, salida.getvalue())
        self.assertIn("Solo-reporte", salida.getvalue())

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

    @unittest.skipUnless((RAIZ / "core" / "sql").is_dir(), "sin core/sql/ (árbol del release)")
    def test_no_trae_commit_porque_la_verificacion_es_humana(self):
        """Con `mariadb < archivo` el cliente ejecuta todo de corrido.

        Un `COMMIT` escrito en el archivo confirmaría aunque el `SELECT` de verificación
        mostrara otra cosa: el «verificar y recién entonces confirmar» sería mentira. Sin
        COMMIT, redirigir el archivo no aplica nada —la transacción se deshace al cerrar
        la conexión— y confirmarlo exige una persona escribiéndolo.
        """
        sql = self.RUTA.read_text(encoding="utf-8")
        ordenes = "\n".join(linea for linea in sql.splitlines() if not linea.lstrip().startswith("--")).upper()

        self.assertIn("START TRANSACTION", ordenes)
        self.assertNotIn("COMMIT", ordenes, "el COMMIT lo escribe la persona después de verificar")
        self.assertIn("COMMIT;", sql, "y el archivo tiene que decir cómo")

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
