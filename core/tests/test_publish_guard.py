"""El guard del release dice la verdad sobre lo que publica (RED-65, RED-21).

`publish-main.yml` es lo último que mira el código antes de que exista `main`, que es
lo que se espeja al GitLab de ECOM y lo que termina horneado en la imagen de producción.
Hasta el 05/10/2026 tenía dos agujeros medidos por la auditoría:

- **RED-65** — la lista de archivos de runtime exige `docker/django/Dockerfile` y
  `scripts/startup.sh`, que OPS-10 y OPS-14 van a borrar. El día que eso pase, `Publish
  main` falla **después** del merge, con `main` sin actualizar y sin que nadie se entere
  salvo que mire Actions. El test de acá pone ese fallo en el PR, que es donde se puede
  arreglar.
- **RED-21** — el denylist estaba escrito a mano y duplicaba, sin nada que las
  sincronizara, las mismas rutas que `.gitattributes`: un `NOTAS.md` o un `.cursor/`
  nuevo en la raíz no estaba en ninguna de las dos y viajaba al release (le pasó a
  `CONTEXT.md`, 17 KB de documentación interna). Y el release se publicaba sin mirar si
  el commit venía de un PR con el CI en verde.

No toca la red: todo sale de los archivos del repo y de `git check-attr`.
"""

import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

import yaml
from django.conf import settings
from django.test import SimpleTestCase

RAIZ = Path(settings.BASE_DIR)
FLUJO = RAIZ / ".github" / "workflows" / "publish-main.yml"
RULESETS = RAIZ / "docs" / "internal" / "rulesets"

# `RUNTIME="a b c"` y `DOCS_DE_RUNTIME="README.md"` dentro del script del guard. Las dos
# listas viven en variables, y no inline en el `for`, justamente para que este módulo
# pueda leerlas sin interpretar shell.
LISTA = re.compile(r'^\s*(?P<nombre>RUNTIME|DOCS_DE_RUNTIME)="(?P<valor>[^"]*)"', re.MULTILINE)


def _flujo():
    return yaml.safe_load(FLUJO.read_text(encoding="utf-8"))


def _pasos():
    return _flujo()["jobs"]["publish"]["steps"]


def _paso(nombre):
    for paso in _pasos():
        if paso.get("name") == nombre:
            return paso
    raise AssertionError(f"el workflow no tiene el paso «{nombre}»: {[p.get('name') for p in _pasos()]}")


def listas_del_guard(script):
    """Las listas literales del guard, tal como las lee el propio shell."""
    return {m.group("nombre"): m.group("valor").split() for m in LISTA.finditer(script)}


def _git(*args):
    return subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True, encoding="utf-8")


def _exportados_del_release():
    """Las rutas versionadas que `git archive` **sí** se lleva a `main`."""
    versionadas = [linea for linea in _git("ls-files").stdout.splitlines() if linea.strip()]
    # En bytes a propósito: con `text=True`, Windows traduce cada `\n` del stdin a
    # `\r\n` y `git check-attr` recibe rutas terminadas en `\r`, que no matchean ningún
    # patrón y vuelven «unspecified». El test quedaba verde por el motivo equivocado.
    marcadas = subprocess.run(
        ["git", "check-attr", "--stdin", "export-ignore"],
        cwd=RAIZ,
        input="\n".join(versionadas).encode("utf-8"),
        capture_output=True,
    ).stdout.decode("utf-8")
    ignoradas = {
        linea[: -len(": export-ignore: set")]
        for linea in marcadas.splitlines()
        if linea.endswith(": export-ignore: set")
    }
    return [ruta for ruta in versionadas if ruta not in ignoradas]


class PublishGuardTests(SimpleTestCase):
    """RED-65: lo que el guard exige tiene que existir de verdad en el árbol."""

    def test_los_requeridos_existen_en_el_arbol(self):
        """El test que nombra la ficha: el fallo aparece en el PR y no después del merge.

        Cuando OPS-10 y OPS-14 borren `scripts/startup.sh` y `docker/django/Dockerfile`,
        este test se pone rojo en **su** PR y recuerda sacarlos también de la lista.
        """
        requeridos = listas_del_guard(_paso("Guard")["run"])["RUNTIME"]

        faltantes = [ruta for ruta in requeridos if not (RAIZ / ruta).exists()]

        self.assertEqual(faltantes, [], f"el guard exige rutas que ya no existen: {faltantes}")

    def test_la_lista_de_runtime_no_esta_vacia(self):
        """Vaciar la lista apagaría el guard entero dejando este módulo en verde."""
        requeridos = listas_del_guard(_paso("Guard")["run"])["RUNTIME"]

        self.assertGreaterEqual(len(requeridos), 10)

    def test_los_requeridos_viajan_al_release(self):
        """Un requerido marcado `export-ignore` es una contradicción que rompe el release.

        El guard lo buscaría en un árbol del que `git archive` acaba de sacarlo: falla
        siempre, después del merge. Pasó de ser hipotético el día que `.gitattributes`
        creció por otro motivo.
        """
        versionadas = {linea for linea in _git("ls-files").stdout.splitlines() if linea.strip()}
        sacadas = versionadas - set(_exportados_del_release())
        requeridos = listas_del_guard(_paso("Guard")["run"])["RUNTIME"]

        contradictorias = [ruta for ruta in requeridos if ruta in sacadas]

        self.assertEqual(contradictorias, [], f"el guard exige rutas que export-ignore saca: {contradictorias}")

    def test_el_guard_detecta_un_requerido_que_no_existe(self):
        """El centinela sirve si falla: se lo prueba contra una lista con una ruta inventada."""
        script = 'RUNTIME="manage.py no/existe/este/archivo.txt"\n'

        requeridos = listas_del_guard(script)["RUNTIME"]
        faltantes = [ruta for ruta in requeridos if not (RAIZ / ruta).exists()]

        self.assertEqual(faltantes, ["no/existe/este/archivo.txt"])


@unittest.skipUnless(shutil.which("git") and (RAIZ / ".git").exists(), "hace falta el repositorio de git")
class DenylistDerivadoTests(SimpleTestCase):
    """RED-21 (1): una sola lista de lo prohibido, la que de verdad aplica `git archive`."""

    def test_el_guard_deriva_lo_prohibido_de_gitattributes(self):
        """Dos listas a mano se desincronizan; la segunda nunca se actualiza."""
        script = _paso("Guard")["run"]

        self.assertIn("check-attr", script, "el denylist tiene que salir de .gitattributes")
        self.assertIn("export-ignore", script)

    def test_el_guard_ya_no_tiene_un_denylist_escrito_a_mano(self):
        script = _paso("Guard")["run"]

        for ruta in (".claude", ".amazonq", ".mcp.json", "AGENTS.md", "mkdocs.yml"):
            with self.subTest(ruta=ruta):
                self.assertNotIn(f" {ruta} ", script, "esta ruta ya la aporta .gitattributes")

    def test_el_guard_pregunta_por_el_arbol_del_release_y_no_por_los_archivos_versionados(self):
        """En `.gitattributes`, un patrón de directorio marca el directorio, no su contenido.

        `git check-attr export-ignore docs/internal/x.md` contesta «unspecified» aunque
        `/docs export-ignore` saque el subárbol entero: derivar el denylist recorriendo
        `git ls-files` deja afuera los cinco patrones de directorio (`.claude`, `.amazonq`,
        `.github`, `docs`, `scripts/perf_mysql`) —medido: 12 de 17 patrones—. Recorriendo
        el árbol del release, el directorio aparece como ruta propia y la pregunta da «set».
        """
        script = _paso("Guard")["run"]

        self.assertRegex(script, r'find "\$RUNNER_TEMP/release"', "el guard recorre el árbol publicado")
        self.assertIn("git check-attr --stdin export-ignore", script)

    def test_un_patron_de_directorio_no_marca_sus_archivos(self):
        """El motivo del test de arriba, medido contra git y no contra la memoria."""
        del_directorio = _git("check-attr", "export-ignore", "--", "docs/internal/rulesets.md").stdout
        del_propio_directorio = _git("check-attr", "export-ignore", "--", "docs").stdout

        self.assertIn("unspecified", del_directorio)
        self.assertIn("export-ignore: set", del_propio_directorio)

    def test_ningun_md_de_la_raiz_viaja_al_release_sin_decidirlo(self):
        """Lo que le pasó a `CONTEXT.md`: 17 KB de documentación interna en el release.

        Un `.md` nuevo en la raíz no está en ninguna lista, así que viaja a `main`, al
        GitLab de ECOM y a la imagen de PRD. O se marca `export-ignore`, o se declara
        como documentación de runtime en el guard.
        """
        de_runtime = set(listas_del_guard(_paso("Guard")["run"])["DOCS_DE_RUNTIME"])
        exportados = _exportados_del_release()

        colados = [ruta for ruta in exportados if ruta.endswith(".md") and "/" not in ruta and ruta not in de_runtime]

        self.assertEqual(colados, [], f"estos .md de la raíz viajan al release sin estar declarados: {colados}")

    def test_la_documentacion_interna_de_la_raiz_esta_marcada(self):
        """El caso concreto que midió la ficha, fijado por nombre."""
        salida = _git("check-attr", "export-ignore", "--", "CONTEXT.md").stdout

        self.assertIn("export-ignore: set", salida, "CONTEXT.md es documentación interna: no va al release")


class CIVerdeAntesDelReleaseTests(SimpleTestCase):
    """RED-21 (2): no se publica un release de un commit que nadie verificó."""

    PASO = "Exigir que el commit venga de un PR con CI verde"

    def test_el_workflow_puede_leer_los_checks_del_pr(self):
        permisos = _flujo()["permissions"]

        self.assertEqual(permisos["contents"], "write")
        self.assertEqual(permisos["pull-requests"], "read")
        self.assertEqual(permisos["checks"], "read")

    def test_el_gate_mira_el_head_del_pr_y_no_el_commit_de_merge(self):
        """El ajuste de la consolidación: el merge commit **no tiene check-runs**.

        Consultar `commits/<merge>/check-runs` devuelve una lista vacía y el paso pasaría
        siempre: el gate quedaría decorativo. Hay que buscar el PR del commit y mirar los
        checks de **su head**, que es donde corrieron.
        """
        script = _paso(self.PASO)["run"]

        self.assertIn("/pulls", script, "hay que buscar el PR del commit publicado")
        self.assertIn("merged_at", script, "solo cuenta el PR efectivamente mergeado")
        self.assertRegex(script, r"commits/\$head/check-runs", "los checks se miran sobre el head del PR")

    def test_cero_check_runs_no_pasa_el_gate(self):
        """Mirar solo los checks que fallaron deja el agujero más grande del gate.

        Un PR en el que los workflows nunca arrancaron —borrados, deshabilitados, o el
        push del head no los disparó— no tiene **ni un check malo**: la lista de fallidos
        sale vacía y el release se publicaría igual, sin que nada lo haya verificado.
        """
        script = _paso(self.PASO)["run"]

        self.assertRegex(script, r'if \[ ! -s "\$RUNNER_TEMP/checks\.tsv" \]')
        self.assertIn("no tiene ni un check-run", script)

    def test_el_gate_exige_los_contextos_que_el_ruleset_declara_obligatorios(self):
        """Así un check que no corrió se distingue de uno que no existe.

        La lista sale del JSON versionado, que es el mismo que aplica el dueño del repo
        (RED-20), y `core/tests/test_gates_ci.py` lo enfrenta contra una lista literal.
        """
        script = _paso(self.PASO)["run"]

        self.assertIn("docs/internal/rulesets/ruleset-development.json", script)
        self.assertIn("required_status_checks", script)
        self.assertIn("no corrió el check obligatorio", script)

    def test_los_contextos_del_ruleset_se_pueden_leer_con_el_jq_del_paso(self):
        """El `jq` del YAML tiene que devolver algo sobre el JSON de verdad.

        Si la forma del ruleset cambia, el `while` del gate itera sobre una lista vacía y
        la comprobación se apaga en silencio: queda verde sin exigir nada.
        """
        ruleset = json.loads((RULESETS / "ruleset-development.json").read_text(encoding="utf-8"))

        contextos = [
            c["context"]
            for regla in ruleset["rules"]
            if regla["type"] == "required_status_checks"
            for c in regla["parameters"]["required_status_checks"]
        ]

        self.assertGreaterEqual(len(contextos), 6, "el gate iteraría sobre una lista vacía")

    def test_el_release_solo_sale_de_development(self):
        """`workflow_dispatch` se dispara sobre cualquier rama, y el job publica lo que
        haya checkouteado: una rama de trabajo llegaría a `main`, a ECOM y a la imagen de
        PRD, saltéandose además el gate de CI verde.
        """
        job = _flujo()["jobs"]["publish"]

        self.assertEqual(job.get("if"), "github.ref == 'refs/heads/development'")

    def test_el_gate_rechaza_un_commit_sin_pr(self):
        script = _paso(self.PASO)["run"]

        self.assertRegex(script, r'if \[ -z "\$head" \]', "sin PR mergeado no hay release")
        self.assertIn("exit 1", script)

    def test_el_gate_no_usa_la_construccion_que_set_e_vuelve_muda(self):
        """`[ cond ] && { …; exit 1; }` como última orden de un script con `set -e`.

        Es la forma que traía la propuesta de la ficha: cuando la condición es falsa la
        lista devuelve 1 y el paso **aborta igual**, con el release sin publicar y un
        error que no explica nada. Va con `if … then … fi`.
        """
        script = _paso(self.PASO)["run"]

        self.assertNotIn("] && {", script)

    def test_el_gate_corre_antes_de_construir_y_publicar(self):
        nombres = [paso.get("name") for paso in _pasos()]

        self.assertLess(nombres.index(self.PASO), nombres.index("Construir árbol de release"))
        self.assertLess(nombres.index(self.PASO), nombres.index("Publicar snapshot en main"))

    def test_el_gate_cubre_el_push_que_dispara_el_release(self):
        """`push: development` es el 99 % de las publicaciones: ahí no se saltea nunca."""
        paso = _paso(self.PASO)

        self.assertIn("github.event_name == 'push'", paso.get("if", ""))

    def test_la_publicacion_a_mano_exige_un_motivo_escrito(self):
        """`workflow_dispatch` es la única puerta que saltea el gate: deja rastro.

        Dispararlo exige permiso de escritura sobre el repo, o sea una persona decidiendo;
        lo que no puede es pasar sin que quede por qué en el log de la corrida.
        """
        disparadores = _flujo().get("on", _flujo().get(True, {}))

        entradas = (disparadores["workflow_dispatch"] or {}).get("inputs") or {}

        self.assertIn("motivo", entradas)
        self.assertTrue(entradas["motivo"]["required"])
