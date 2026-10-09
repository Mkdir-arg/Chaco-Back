"""La sonda HTTP no mide rutas de `conversaciones` (G1-01 fase 2).

El manifiesto de `scripts/perf_http_probe.py` es una tupla de literales, no un
`reverse()`: nada falla al editarlo si queda apuntando a una ruta desmontada. La sonda
mide un 404 y, en la fase de lecturas, `verify_manifest_metrics` exige que
`/performance-api/` haya agregado ese `route` —que ya no existe— y aborta la corrida
entera. Este test fija el manifiesto, igual que el de `perf_audit`.
"""

import ast
import importlib.util
from pathlib import Path

from django.test import SimpleTestCase

SONDA = Path(__file__).resolve().parents[2] / "scripts" / "perf_http_probe.py"


def _load_perf_http_probe():
    spec = importlib.util.spec_from_file_location("perf_http_probe", SONDA)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


perf_http_probe = _load_perf_http_probe()


class ManifiestoSinConversacionesTests(SimpleTestCase):
    def test_el_manifiesto_no_esta_vacio(self):
        """Guarda del control: con los manifiestos vacíos el test de abajo pasa solo."""
        self.assertGreater(len(perf_http_probe.LECTURAS), 0)
        self.assertGreater(len(perf_http_probe.CONCURRENT_READS), 0)

    def test_ninguna_ruta_declarada_apunta_a_conversaciones(self):
        declaradas = perf_http_probe.LECTURAS + perf_http_probe.CONCURRENT_READS

        for clave, route, path, _actor, _esperado in declaradas:
            with self.subTest(flujo=clave):
                self.assertNotIn("conversacion", route)
                self.assertNotIn("conversacion", path)

    def test_ningun_literal_de_la_sonda_nombra_conversaciones(self):
        """Las rutas de las fases de escritura y concurrencia, y las opciones del
        parser, también son literales sueltos: `--conversacion-pk` alimentaba el envío
        de mensaje contra `/conversaciones/{pk}/responder/` y quedó sin consumidor.

        Se mira el AST, no el texto: los comentarios que explican el apagado no cuentan.
        """
        arbol = ast.parse(SONDA.read_text(encoding="utf-8"), str(SONDA))

        literales = [
            nodo.value
            for nodo in ast.walk(arbol)
            if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str) and "conversacion" in nodo.value
        ]

        self.assertEqual(literales, [])
