"""Correr con Node los harness de `programas/tests/js/` contra el JS que renderiza el backoffice."""

import json
import re
import shutil
import subprocess
from unittest import skipUnless

from django.conf import settings

requiere_node = skipUnless(shutil.which("node"), "Requiere Node para ejecutar el JS renderizado")

_SCRIPT_RE = re.compile(r"<script>\n(.*?)</script>", re.S)


def script_de_plantilla(ruta):
    """El primer `<script>` en línea de una plantilla, relativa a `BASE_DIR`."""
    texto = (settings.BASE_DIR / ruta).read_text(encoding="utf-8")
    return _SCRIPT_RE.search(texto).group(1)


def correr_harness_js(nombre_cjs, script):
    """Corre `programas/tests/js/<nombre_cjs>` con `script` en stdin (JSON); devuelve el `CompletedProcess`."""
    return subprocess.run(
        [shutil.which("node"), str(settings.BASE_DIR / "programas/tests/js" / nombre_cjs)],
        input=json.dumps(script),
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=15,
        check=False,
    )
