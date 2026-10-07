"""Higiene de los archivos fuente: ningún `.py` con terminadores CR solitarios (RED-82).

`programas/services/exportacion_reportes.py` se versionó con 122 `\r` y ni un `\n`:
terminadores de Mac clásico. Python lo ejecuta sin chistar, pero para el resto de la
cadena es un archivo de una sola línea:

- `git ls-files --eol` lo marca `i/-text`, así que el diff de un PR **no muestra su
  contenido**: cualquier cambio aparece como «archivo binario modificado».
- `grep -n` informa siempre la línea 1 y `ruff format` no lo normaliza.
- `pylint` lo rechaza con `E0001` y **sigue en verde**: un gate basado en pylint lo
  saltea sin decir nada.

El archivo contiene `celda_segura` (RED-70) y es lo que SEC-20 va a revisar: sin esto,
esa revisión sería ilegible.

La guarda es doble: este test recorre lo versionado y `.gitattributes` fija
`*.py text eol=lf`, para que tampoco entre un `.py` con CRLF desde un checkout de
Windows. El test tolera CRLF **en el árbol de trabajo** (es lo que deja `core.autocrlf`
al hacer checkout en Windows): lo que no tolera es un `\r` que no sea parte de un
`\r\n`.
"""

import subprocess
from pathlib import Path

from django.test import SimpleTestCase

RAIZ = Path(__file__).resolve().parents[2]


def _archivos_py_versionados():
    salida = subprocess.run(
        ["git", "ls-files", "-z", "*.py"],
        cwd=RAIZ,
        capture_output=True,
        check=True,
    )
    return [RAIZ / nombre for nombre in salida.stdout.decode("utf-8").split("\0") if nombre]


class EOLTests(SimpleTestCase):
    def test_hay_archivos_py_versionados(self):
        """Control del andamio: si `git ls-files` devuelve vacío, el test de abajo
        pasaría sin mirar nada."""
        self.assertGreater(len(_archivos_py_versionados()), 100)

    def test_ningun_py_con_cr_solitario(self):
        culpables = []
        for archivo in _archivos_py_versionados():
            if not archivo.exists():  # borrado en el árbol de trabajo pero aún en el índice
                continue
            crudo = archivo.read_bytes()
            if crudo.count(b"\r") != crudo.count(b"\r\n"):
                culpables.append(archivo.relative_to(RAIZ).as_posix())

        self.assertEqual(
            culpables,
            [],
            "archivos .py con terminadores CR solitarios (git los trata como binarios y el "
            f"diff del PR no se lee): {culpables}. Convertir a LF.",
        )

    def test_gitattributes_fija_lf_para_los_py(self):
        """Sin la regla, el próximo `.py` que alguien agregue desde Windows entra con
        CRLF y el ratchet de arriba no lo ve (CRLF es legítimo para este test)."""
        reglas = (RAIZ / ".gitattributes").read_text(encoding="utf-8").splitlines()

        self.assertIn("*.py text eol=lf", [linea.strip() for linea in reglas])


class HarnessE2ENoVersionadoTests(SimpleTestCase):
    """RED-72 / **D-RED-06 = No**: el e2e no entra al repo ni al CI.

    En el checkout principal quedaban los restos de un harness de Playwright de
    julio-2026: `tests/e2e/__pycache__/*.cpython-314-pytest-9.1.1.pyc` y un
    `.pytest_cache/`. Ni un `.py`: `git log --all --diff-filter=A -- "tests/e2e/*"`
    da vacío, nunca estuvo versionado. El daño es de confusión —la documentación de
    trabajo lo daba por existente «y en verde», y quien lo buscara encontraba
    bytecode de Python 3.14 incompatible con el 3.12 del CI—.

    La decisión registrada (D-RED-06, default aplicado) es **no** reconstruirlo por
    ahora; si alguna vez se hace, va solo donde hay JavaScript que decide, nightly o
    a mano, **nunca como gate**, y sin credenciales ni datos reales adentro. Lo que
    este test sostiene es la parte que se puede sostener desde el repo: que nada de
    `tests/` esté versionado y que no entre bytecode al árbol.
    """

    def _versionados(self, patron):
        salida = subprocess.run(
            ["git", "ls-files", "-z", "--", patron],
            cwd=RAIZ,
            capture_output=True,
            check=True,
        )
        return [nombre for nombre in salida.stdout.decode("utf-8").split("\0") if nombre]

    def test_no_hay_nada_versionado_bajo_tests(self):
        versionados = self._versionados("tests/")

        self.assertEqual(
            versionados,
            [],
            "D-RED-06: el harness e2e no se versiona. Si se decide lo contrario, actualizá "
            f"la ficha RED-72 y este test en el mismo diff. Encontrado: {versionados}",
        )

    def test_el_gitignore_cubre_el_harness_local(self):
        """Para que un harness local no se cuele por un `git add -A` distraído: ahí
        viven el usuario y la clave del compose local."""
        reglas = {linea.strip() for linea in (RAIZ / ".gitignore").read_text(encoding="utf-8").splitlines()}

        self.assertIn("/tests/e2e/", reglas)

    def test_no_hay_bytecode_versionado(self):
        """Los `.pyc` de julio son el residuo concreto de RED-72, y un `.pyc` de otra
        versión de Python es peor que nada: se importa y no coincide con el fuente."""
        bytecode = self._versionados("*.pyc") + self._versionados("*.pyo")

        self.assertEqual(bytecode, [])

    def test_ningun_workflow_depende_de_playwright(self):
        """«Nunca como gate»: si alguien agrega un job de e2e, este test lo frena y
        obliga a volver a discutir D-RED-06."""
        workflows = sorted((RAIZ / ".github" / "workflows").glob("*.yml"))
        self.assertGreater(len(workflows), 5, "control del andamio: no se leyó ningún workflow")

        con_playwright = [ruta.name for ruta in workflows if "playwright" in ruta.read_text(encoding="utf-8").lower()]

        self.assertEqual(con_playwright, [], "D-RED-06: el e2e no es un gate del CI")
