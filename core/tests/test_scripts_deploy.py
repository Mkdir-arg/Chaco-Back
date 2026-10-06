"""`scripts/deploy_prod.sh` no puede mentir sobre el deploy (RED-59, OPS-04).

El script viaja en el release y es con lo que se despliega icore-srv. La auditoría le
midió tres cosas, las tres silenciosas:

1. **El criterio de éxito era `/health/`**, que devuelve 200 con la base caída (OPS-04).
   O sea: el rollback automático —que el script tiene y que está encendido por default—
   **no se disparaba nunca** por un esquema roto ni por un `collectstatic` fallido. El
   deploy terminaba diciendo «Deploy completed successfully» con el sistema abajo.
2. **El rollback vuelve el código y nunca la base.** El contenedor rearranca y corre
   `migrate` con los archivos viejos: filas con columnas que ya no se escriben, esquema
   adelantado (RED-14). Si el deploy aplicó migraciones, volver solo el código es peor
   que no volver nada; esa decisión es de una persona con el runbook en la mano.
3. **`git checkout --force <sha>` deja detached HEAD**, así que el `git pull --ff-only`
   del deploy siguiente falla y nadie entiende por qué.

Los tests leen el script: no ejecutan docker ni git.
"""

import re
import shutil
import subprocess
import unittest
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

RAIZ = Path(settings.BASE_DIR)
SCRIPT = RAIZ / "scripts" / "deploy_prod.sh"


def _valor_por_defecto(texto, variable):
    """`VAR="${VAR:-valor}"` → `valor`."""
    hallazgo = re.search(rf'^{variable}="\$\{{{variable}:-([^}}]*)\}}"', texto, re.MULTILINE)
    return hallazgo.group(1) if hallazgo else None


def _hay_bash():
    """`shutil.which` no alcanza: en Windows `bash.exe` suele ser el lanzador de WSL."""
    if not shutil.which("bash"):
        return False
    try:
        return subprocess.run(["bash", "-c", "exit 0"], capture_output=True).returncode == 0
    except OSError:
        return False


def _ordenes(texto):
    """Solo las líneas ejecutables: los comentarios explican lo que ya no se hace."""
    return "\n".join(linea for linea in texto.splitlines() if not linea.lstrip().startswith("#"))


class DeployProdTests(SimpleTestCase):
    def setUp(self):
        self.script = SCRIPT.read_text(encoding="utf-8")
        self.ordenes = _ordenes(self.script)

    # --- OPS-04: el health que sí sabe si el sistema sirve ------------------ #

    def test_deploy_prod_usa_ready(self):
        """El test que nombra la ficha de OPS-04 (ampliada por RS-R6-06)."""
        self.assertTrue(
            _valor_por_defecto(self.script, "HEALTH_URL").endswith("/health/ready/"),
            "con `/health/` el deploy da OK con la base caída y el rollback no se dispara",
        )

    def test_no_usa_checkout_force_ni_health_desnudo(self):
        """El test que nombra la ficha de RED-59."""
        self.assertNotIn(
            "git checkout --force",
            self.ordenes,
            "`git checkout --force` deja detached HEAD: el próximo `pull --ff-only` falla",
        )
        self.assertNotRegex(
            self.ordenes,
            r'HEALTH_URL="\$\{HEALTH_URL:-[^}]*/health/\}"',
            "`/health/` desnudo no distingue «vivo» de «sirve»",
        )

    def test_el_rollback_crea_una_rama_en_vez_de_quedar_en_detached_head(self):
        self.assertIn('git switch --force-create "rollback/$TIMESTAMP"', self.script)

    # --- RED-59: verificaciones después del deploy -------------------------- #

    def test_hay_post_deploy_checks(self):
        self.assertIn("post_deploy_checks()", self.script)

    def test_los_post_deploy_checks_miran_las_tres_cosas(self):
        """`migrate --check`, el manifest de estáticos y una pantalla de verdad."""
        self.assertIn("migrate --check", self.script)
        self.assertIn("staticfiles.json", self.script)
        self.assertIn("/login/", self.script, "la pantalla de login es la que prueba que el manifest sirve")

    def test_el_manifest_se_cuenta_y_no_solo_se_mira_si_existe(self):
        """Un `staticfiles.json` vacío existe igual y rompe cada template con `{% static %}`."""
        self.assertRegex(self.script, r"MANIFEST_MINIMO|50")

    def test_los_post_deploy_checks_corren_antes_de_declarar_exito(self):
        self.assertLess(
            self.script.index("post_deploy_checks"),
            self.script.index("Deploy completed successfully"),
            "declarar éxito antes de verificar es exactamente el bug",
        )

    # --- RED-59: el rollback no decide solo cuando hay migraciones ---------- #

    def test_el_rollback_aborta_si_el_deploy_aplico_migraciones(self):
        """Volver solo el código deja el esquema adelantado y las filas a medias.

        Es la decisión que no puede tomar un script: necesita el dump de D.0 y una
        persona mirando qué se perdió entre el dump y el rollback.
        """
        self.assertIn("showmigrations", self.script)
        self.assertRegex(self.script, r"runbook|processes\.md", "tiene que mandar al runbook, no improvisar")

    def test_el_rollback_sigue_siendo_desactivable(self):
        self.assertEqual(_valor_por_defecto(self.script, "ROLLBACK_ON_FAIL"), "1")

    # --- RED-59: «no se pudo comparar» tiene que existir de verdad -------- #

    def test_la_cuenta_de_migraciones_distingue_cero_de_no_pude_leer(self):
        """`exec ... | grep -c` con `|| true` imprime «0» también cuando el exec falla.

        O sea exactamente cuando `web` está en crash-loop, que es el escenario del
        rollback: la rama «no se pudo comparar» era código muerto y un contenedor que no
        responde se leía como «el deploy no migró nada» → el rollback procedía contra un
        esquema adelantado (RED-14).
        """
        self.assertRegex(
            self.ordenes,
            r'if ! salida="\$\(en_la_app python manage\.py showmigrations',
            "el exit del exec tiene que separarse de la cuenta",
        )
        self.assertRegex(self.ordenes, r"return 1", "sin lectura, la función tiene que fallar y no imprimir 0")

    def test_sin_poder_comparar_el_rollback_no_procede(self):
        self.assertIn("no se pudo leer el estado de las migraciones", self.ordenes)
        self.assertIn("el rollback automatico no procede", self.ordenes)

    def test_hay_una_puerta_explicita_para_el_caso_verificado_a_mano(self):
        """Negarse siempre dejaría al operador sin salida; la salida es explícita."""
        self.assertEqual(_valor_por_defecto(self.script, "ROLLBACK_SIN_COMPARAR"), "0")
        self.assertIn("ROLLBACK_SIN_COMPARAR=1", self.ordenes)

    def test_la_foto_previa_tambien_distingue_el_fallo(self):
        """`MIGRACIONES_ANTES` vacío (no «0») es lo que después deja comparar o no."""
        self.assertRegex(self.ordenes, r'if MIGRACIONES_ANTES="\$\(migraciones_aplicadas\)"; then')
        self.assertIn('MIGRACIONES_ANTES=""', self.ordenes)

    # --- RED-59: el manifest se valida como número ------------------------ #

    def test_el_manifest_se_valida_como_numero_antes_de_compararlo(self):
        """`[ "$x" -lt N ] 2>/dev/null` con un traceback adentro daba falso y **pasaba**.

        Justo cuando el manifest no se pudo leer, que es cuando hay que frenar.
        """
        self.assertNotIn('[ "$manifest" -lt "$MANIFEST_MINIMO" ] 2>/dev/null', self.ordenes)
        self.assertRegex(self.ordenes, r"grep -qE '\^\[0-9\]\+\$'")
        self.assertIn("No se pudo contar las entradas de staticfiles.json", self.ordenes)

    # --- contrato del script ------------------------------------------------ #

    @unittest.skipUnless(_hay_bash(), "hace falta un bash que corra (en Windows, `bash.exe` suele ser el stub de WSL)")
    def test_el_script_es_sintacticamente_valido(self):
        corrida = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)

        self.assertEqual(corrida.returncode, 0, corrida.stderr)

    def test_sigue_viajando_en_el_release(self):
        """Está en la lista `RUNTIME` del guard de `publish-main.yml`: si se va, falla."""
        flujo = (RAIZ / ".github" / "workflows" / "publish-main.yml").read_text(encoding="utf-8")

        self.assertIn("scripts/deploy_prod.sh", flujo)
