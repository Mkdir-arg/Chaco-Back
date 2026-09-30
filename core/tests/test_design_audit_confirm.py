import importlib.util
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

_SPEC = importlib.util.spec_from_file_location(
    "design_audit", Path(__file__).resolve().parents[2] / "scripts" / "design_audit.py"
)
design_audit = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(design_audit)


class ConfirmRuleTests(SimpleTestCase):
    def _reglas(self, contenido, suffix=".js"):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / f"x{suffix}"
            p.write_text(contenido, encoding="utf-8")
            return [f[2] for f in design_audit.audit_file(p)]

    def test_detecta_llamadas_nativas(self):
        for src in ("alert('x');", "if (!confirm('x')) return;", "const v = prompt('x');", "window.prompt('x')"):
            self.assertIn("CONFIRM", self._reglas(src), src)

    def test_no_marca_falsos_positivos(self):
        for src in (
            "toast.alert('x');",
            "this.alert('x');",
            "function alert(msg) {}",
            "// alert('x') está prohibido",
            "* usar prompt() nativo no",
            "const alertas = 1; miprompt('x');",
        ):
            self.assertNotIn("CONFIRM", self._reglas(src), src)

    def test_js_de_becas_es_target_por_defecto(self):
        self.assertIn("static/custom/js", design_audit.DEFAULT_TARGETS)
