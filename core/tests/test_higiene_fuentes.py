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
