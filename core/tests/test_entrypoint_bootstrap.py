"""OPS-05, OPS-07 y OPS-11 · El arranque del contenedor, leído del script.

`docker-entrypoint.sh` es el **ENTRYPOINT único de la imagen**: por acá pasan daphne,
gunicorn, el Job de bootstrap de Kubernetes y los cuatro CronJobs. No hay test de
integración que lo corra con una base al lado, así que lo que se puede fijar —y lo que
se rompió histórico— es el contrato del script: qué comandos corre, en qué orden, con
qué variables y qué pasa cuando uno falla.

Lo que fija cada bloque:

* **OPS-05** — el `read_timeout` de 10 s de producción también corta un `migrate`. En
  MySQL/MariaDB no hay DDL transaccional: un `ALTER` que espera el metadata lock más de
  10 s devuelve un 2013 al cliente y **se aplica igual** en el servidor, dejando el
  esquema adelantado sin fila en `django_migrations`. El arranque levanta el timeout
  solo para el bloque de migraciones y sembrado (D-O05: «sí, solo en migrate»).
* **OPS-07** — los comandos de `LOCAL_OPTIONAL_BOOTSTRAP_COMMANDS` no pueden tirar abajo
  el arranque (el script corre con `set -eu` y `docs/internal/processes.md` ya prometía
  lo contrario), y el bloque que escribe en la base corre con el candado de `GET_LOCK`.
* **OPS-11** — `--run-syncdb` se va: hoy es no-op (las apps sin migraciones no tienen
  modelos) y mañana crea tablas sin migración que la guarda de OPS-01 va a rechazar.

Y lo que **no** se puede romper: la guarda de gevent (RED-45, PR R-21), la guarda de
esquema (OPS-01, PR R-15) y `RUN_MIGRATIONS=false` del Job (RED-19, PR R-13).
"""

import re
import shutil
import subprocess
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

ENTRYPOINT = Path(settings.BASE_DIR) / "docker-entrypoint.sh"


class EntrypointSintaxisTests(SimpleTestCase):
    def test_el_script_es_sh_valido(self):
        """`sh -n` sobre el ENTRYPOINT: un typo acá es un contenedor que no arranca."""
        sh = shutil.which("sh")
        if not sh:
            self.skipTest("no hay `sh` en esta máquina")

        corrida = subprocess.run([sh, "-n", str(ENTRYPOINT)], capture_output=True, text=True)

        self.assertEqual(corrida.returncode, 0, corrida.stderr)


class EntrypointBootstrapTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.script = ENTRYPOINT.read_text(encoding="utf-8")
        # Las comprobaciones de ausencia miran el código, no los comentarios: el script
        # nombra `--run-syncdb` y `bootstrap_lock` justamente para explicar por qué.
        cls.codigo = "\n".join(
            linea for linea in cls.script.splitlines() if not linea.lstrip().startswith("#") or linea.startswith("#!")
        )

    # ── OPS-11 ─────────────────────────────────────────────────────────────────

    def test_el_migrate_ya_no_lleva_run_syncdb(self):
        self.assertNotIn("--run-syncdb", self.codigo)

    # ── OPS-05 ─────────────────────────────────────────────────────────────────

    def test_las_migraciones_corren_con_el_read_timeout_levantado(self):
        self.assertIn("MIGRATE_DB_READ_TIMEOUT", self.script)
        self.assertIn("DB_READ_TIMEOUT=", self.script)
        self.assertIn("DB_WRITE_TIMEOUT=", self.script)

    def test_el_timeout_levantado_no_se_exporta_al_server(self):
        """Si se exportara, el `read_timeout` de 10 s dejaría de valer para el tráfico."""
        self.assertNotIn("export DB_READ_TIMEOUT", self.script)
        self.assertNotIn("export MIGRATE_DB_READ_TIMEOUT", self.script)

    # ── OPS-07 ─────────────────────────────────────────────────────────────────

    def test_el_bloque_que_escribe_en_la_base_corre_con_candado(self):
        self.assertIn("bootstrap_lock", self.script)
        self.assertRegex(self.script, r"--comando\s+\"migrate --noinput\"")

    def test_la_guarda_de_esquema_corre_dentro_del_candado(self):
        """Fuera del candado, la guarda de OPS-01 mira un esquema que otra réplica está
        migrando en ese mismo momento y aborta el arranque por una foto a medias."""
        self.assertRegex(self.codigo, r"--comando\s+\"?verificar_esquema_migraciones\"?")
        self.assertNotRegex(self.codigo, r"(?m)^\s*python manage\.py verificar_esquema_migraciones\s*$")

    def test_el_sembrado_va_en_el_mismo_candado_que_el_migrate(self):
        """Dos candados distintos dejan que una réplica siembre contra el esquema que
        otra está migrando: el nombre del candado es uno solo."""
        self.assertEqual(len(re.findall(r"manage\.py bootstrap_lock", self.codigo)), 1)

    def test_los_comandos_opcionales_no_abortan_el_arranque(self):
        self.assertIn("AVISO", self.script)
        self.assertRegex(self.script, r"run_optional_management_commands")

    def test_el_sembrado_obligatorio_sigue_siendo_fatal(self):
        """`seed_datos_base` no es opcional: sin roles ni capacidades el sistema arranca
        pero no sirve. Va por `bootstrap_lock`, que corta en el primer error."""
        self.assertIn("LOCAL_BOOTSTRAP_COMMANDS", self.script)
        self.assertNotRegex(self.script, r"run_optional_management_commands \"\$\{LOCAL_BOOTSTRAP_COMMANDS")

    def test_solo_los_opcionales_pasan_por_la_version_tolerante(self):
        self.assertRegex(self.script, r"run_optional_management_commands \"\$\{LOCAL_OPTIONAL_BOOTSTRAP_COMMANDS\}\"")

    # ── lo que no se puede romper ──────────────────────────────────────────────

    def test_sigue_la_palanca_run_migrations_del_job(self):
        """RED-19 / PR R-13: el Deployment web no migra, migra el Job."""
        self.assertIn('"${RUN_MIGRATIONS:-true}" = "true"', self.script)

    def test_sigue_la_guarda_de_esquema_y_su_escape(self):
        """OPS-01 / PR R-15."""
        self.assertIn("verificar_esquema_migraciones", self.script)
        self.assertIn("SKIP_SCHEMA_GUARD", self.script)

    def test_sigue_la_guarda_de_gevent(self):
        """RED-45 / PR R-21: con gevent, `validate_thread_sharing` queda apagada."""
        self.assertIn("guard_worker_class", self.script)
        self.assertIn("GUNICORN_WORKER_CLASS", self.script)

    def test_sigue_el_modo_one_shot_del_job(self):
        self.assertIn('if [ "${1:-}" = "bootstrap" ]; then', self.script)
