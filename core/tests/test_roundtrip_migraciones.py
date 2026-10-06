"""RED-17 · Las migraciones se prueban hacia atrás y sobre datos, contra el motor real.

Hasta el PR R-13 el CI armaba el esquema desde los modelos
(`DJANGO_SYNCDB_PROJECT_APPS=True`), así que una migración podía entrar sin que nada la
ejecutara; el único `migrate` real del repo corría hacia adelante, sobre una base vacía y
con la semilla **después**. El camino de vuelta —el que se recorre con producción caída—
no lo probaba nadie, y el repo ya tiene el precedente: `0a785d75` arregló una `0052` que
murió en el deploy con `padron_archivo` NULL.

Este módulo fija las dos mitades del arreglo:

* el **orquestador** (`scripts/roundtrip_migraciones.py`): cómo elige el destino de la
  vuelta y, sobre todo, que reconozca como *esperado* el aborto de las ocho barreras de
  reversa (Cambios 117 y 135). Una barrera que el job tomara por rojo volvería el gate
  inútil el día que el plan de vuelta cruce una;
* el **job** `Migrate ida y vuelta` de `pr-performance.yml`: que corra contra los dos
  motores de producción, sin tablas de zona horaria en MariaDB, con datos sembrados, y
  que el filtro por rutas viva adentro del job y no en el trigger (RED-20).
"""

import importlib
import importlib.util
import shutil
import tempfile
from pathlib import Path

import yaml
from django.conf import settings
from django.test import SimpleTestCase

RAIZ = Path(settings.BASE_DIR)
WORKFLOWS = RAIZ / ".github" / "workflows"
GUION = RAIZ / "scripts" / "roundtrip_migraciones.py"
SETTINGS_CI = RAIZ / ".github" / "ci" / "settings_roundtrip.py"

JOB = "Migrate ida y vuelta (${{ matrix.motor }})"

# Las ocho del paso D.4 del runbook: su `IrreversibleError` tiene que caer del lado de
# «esperado» cuando el plan de vuelta las cruce.
BARRERAS = (
    "programas.migrations.0032_siis_segmento_en_subsegmento",
    "programas.migrations.0047_ampliar_formulario_client_uuid",
    "programas.migrations.0048_ampliar_validacionsis_id_consulta",
    "programas.migrations.0056_padron_convocatoria_identidad",
    "programas.migrations.0069_identificadores_siis_por_nivel",
    "programas.migrations.0073_ampliar_relevamiento_token_publico",
    "legajos.migrations.0007_ampliar_uuid_legajos",
    "users.migrations.0023_ampliar_solicitud_cambio_email_token",
)


def _cargar_guion():
    spec = importlib.util.spec_from_file_location("roundtrip_migraciones", GUION)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _cargar_workflow(nombre):
    return yaml.safe_load((WORKFLOWS / nombre).read_text(encoding="utf-8"))


def _job_del_roundtrip():
    flujo = _cargar_workflow("pr-performance.yml")
    for datos in (flujo.get("jobs") or {}).values():
        if datos.get("name") == JOB:
            return datos
    raise AssertionError(f"no existe el job «{JOB}» en pr-performance.yml")


class OrquestadorTests(SimpleTestCase):
    def setUp(self):
        self.guion = _cargar_guion()

    def _arbol(self):
        carpeta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, carpeta, True)
        return Path(carpeta)

    def test_el_destino_de_la_vuelta_es_la_ultima_migracion_de_la_base(self):
        """Volver «hasta la base del PR» es, por app, su migración más alta en la base."""
        arbol = self._arbol()
        (arbol / "programas" / "migrations").mkdir(parents=True)
        for nombre in ("0001_initial.py", "0002_algo.py", "0010_otra.py", "__init__.py"):
            (arbol / "programas" / "migrations" / nombre).write_text("", encoding="utf-8")

        self.assertEqual(self.guion.ultima_migracion(arbol, "programas"), "0010_otra")

    def test_una_app_sin_migraciones_en_la_base_vuelve_a_zero(self):
        """Si el PR le crea la carpeta `migrations/` a una app, la vuelta la desaplica entera."""
        arbol = self._arbol()

        self.assertEqual(self.guion.ultima_migracion(arbol, "programas"), "zero")
        self.assertEqual(
            self.guion.destinos_de_reversa(arbol, ["programas", "users"]),
            [("programas", "zero"), ("users", "zero")],
        )

    def test_el_orden_de_la_vuelta_pone_primero_lo_que_depende_de_los_demas(self):
        self.assertLess(
            self.guion.ORDEN_DE_APPS.index("programas"),
            self.guion.ORDEN_DE_APPS.index("core"),
            "desaplicar `core` antes que `programas` arrastra medio esquema sin explicarlo",
        )

    def test_el_aborto_de_las_ocho_barreras_cuenta_como_esperado(self):
        """El job tiene que **esperar** ese aborto, no tomarlo como rojo.

        Si el mensaje de una barrera cambia y deja de coincidir, el día que el plan de
        vuelta cruce una el job se pondría rojo por el comportamiento correcto, y lo
        primero que alguien haría es apagarlo.
        """
        for modulo in BARRERAS:
            with self.subTest(migracion=modulo):
                mensaje = importlib.import_module(modulo).MENSAJE_BARRERA

                self.assertRegex(mensaje, self.guion.BARRERA)

    def test_un_error_cualquiera_no_cuenta_como_barrera(self):
        for salida in (
            "django.db.utils.OperationalError: (1091, \"Can't DROP 'x'\")",
            "IrreversibleError: esta migración no se puede revertir",
        ):
            with self.subTest(salida=salida):
                self.assertIsNone(self.guion.BARRERA.search(salida))


class JobDeRoundtripTests(SimpleTestCase):
    def setUp(self):
        self.job = _job_del_roundtrip()
        self.texto = (WORKFLOWS / "pr-performance.yml").read_text(encoding="utf-8")
        self.comandos = "\n".join(paso.get("run", "") for paso in self.job["steps"])

    def test_corre_contra_los_dos_motores_de_produccion(self):
        """ECOM es MariaDB (testing y PRD) e icore es MySQL 8: los dos tienen que estar."""
        motores = {fila["motor"] for fila in self.job["strategy"]["matrix"]["include"]}

        self.assertEqual(motores, {"mariadb:10.11", "mysql:8.0"})

    def test_mariadb_corre_sin_tablas_de_zona_horaria(self):
        """La imagen oficial las carga y la base de ECOM no las tiene (`CLAUDE.md`).

        Con las tablas puestas, `CONVERT_TZ` anda y los bugs que este job busca no se
        manifiestan: sería un verde vacío.
        """
        self.assertEqual(self.job["services"]["db"]["env"]["MARIADB_INITDB_SKIP_TZINFO"], "1")

    def test_las_migraciones_corren_de_verdad(self):
        """Ni `PYTEST_RUNNING` ni `DJANGO_SYNCDB_PROJECT_APPS`: ese es el punto de RED-17."""
        self.assertNotIn("PYTEST_RUNNING", self.job["env"])
        self.assertNotIn("DJANGO_SYNCDB_PROJECT_APPS", self.job["env"])

    def test_siembra_datos_antes_de_las_migraciones_del_pr(self):
        """28 `RunPython` en 27 archivos nunca habían iterado una sola fila."""
        self.assertIn("seed_perf", GUION.read_text(encoding="utf-8"))
        self.assertEqual(self.job["env"]["DATABASE_NAME"], "chaco_perf_ci")
        self.assertEqual(self.job["env"]["PERFORMANCE_CI"], "1")
        self.assertEqual(self.job["env"]["ENVIRONMENT"], "ci")

    def test_corre_el_orquestador_y_el_gate_del_sql_de_ida(self):
        for comando in ("scripts/roundtrip_migraciones.py", "scripts/check_sqlmigrate.py"):
            with self.subTest(comando=comando):
                self.assertIn(comando, self.comandos)

    def test_el_checkout_trae_el_historial_entero(self):
        """Sin `fetch-depth: 0` no hay árbol de la base contra el cual comparar."""
        checkout = next(paso for paso in self.job["steps"] if str(paso.get("uses", "")).startswith("actions/checkout"))

        self.assertEqual((checkout.get("with") or {}).get("fetch-depth"), 0)

    def test_arma_el_arbol_de_la_base_del_pr(self):
        self.assertIn("git worktree add ../base", self.comandos)
        self.assertIn("pull_request.base.sha", self.comandos)

    def test_instala_las_dependencias_de_los_dos_arboles(self):
        """El job corre `manage.py` en el árbol del PR **y** en el de la base.

        Si el PR retira una dependencia, el árbol de la base la sigue nombrando en
        `INSTALLED_APPS` y su `migrate` muere con `ModuleNotFoundError` antes de tocar
        la base: rojo por el motivo equivocado. Pasó de verdad el 06/10/2026, cuando el
        Cambio 153 retiró `django-health-check` (OPS-04).
        """
        self.assertIn("pip install -r ../base/requirements.txt", self.comandos)
        self.assertIn("pip install -r requirements.txt", self.comandos)

    def test_la_base_se_instala_primero_para_que_ganen_los_pines_del_pr(self):
        """Lo que el job mide es el código del PR: sus versiones tienen que ser las vivas."""
        self.assertLess(
            self.comandos.index("pip install -r ../base/requirements.txt"),
            self.comandos.index("pip install -r requirements.txt"),
        )

    def test_el_arbol_de_la_base_existe_antes_de_instalar(self):
        """Leer `../base/requirements.txt` antes del `git worktree add` sería un no-op."""
        nombres = [paso.get("name") for paso in self.job["steps"]]

        self.assertLess(nombres.index("Árbol de la base del PR"), nombres.index("Install Python dependencies"))

    def test_el_filtro_por_rutas_vive_adentro_del_job(self):
        """RED-20: con `paths:` en el trigger el check no reporta y no puede ser obligatorio."""
        flujo = _cargar_workflow("pr-performance.yml")
        disparadores = flujo.get("on", flujo.get(True, {})) or {}

        self.assertNotIn("paths", disparadores.get("pull_request") or {})
        self.assertTrue(
            [paso for paso in self.job["steps"] if "paths-filter" in str(paso.get("uses", ""))],
            "el filtro tiene que estar adentro del job",
        )

    def test_el_job_no_se_pone_en_verde_solo(self):
        """El Anexo B lo proponía con `continue-on-error` por RED-18 y las barreras de
        RED-15. El Cambio 135 cerró las dos, así que mide de verdad desde el primer día.
        """
        self.assertNotIn("continue-on-error", self.job)

    def test_el_timeout_del_motor_de_produccion_no_corta_la_migracion(self):
        """`config/settings.py` fija `read_timeout` 10 s porque es el de ECOM.

        Un ALTER sobre datos sembrados lo pasa de largo: el cliente corta, el DDL sigue y
        la migración queda a medias. Ese modo de falla es otra ficha (OPS-05); acá solo
        ensuciaría la medición.
        """
        self.assertEqual(self.job["env"]["DJANGO_SETTINGS_MODULE"], "settings_roundtrip")
        self.assertIn(".github/ci", self.job["env"]["PYTHONPATH"])

        settings_ci = SETTINGS_CI.read_text(encoding="utf-8")

        self.assertIn("read_timeout", settings_ci)
        self.assertIn("write_timeout", settings_ci)

    def test_el_settings_del_job_vive_fuera_de_config(self):
        """El árbol de la base no tiene este archivo: tiene que entrar por `PYTHONPATH`.

        Si viviera en `config/`, el `config` del árbol de la base lo taparía y el job
        correría la mitad de los pasos con el `read_timeout` de producción.
        """
        self.assertTrue(SETTINGS_CI.exists())
        self.assertFalse((RAIZ / "config" / "settings_roundtrip.py").exists())
