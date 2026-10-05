"""Contrato de `design_audit.py` que se puede verificar sin Django.

Corre en el job «Design Agent Contract» con el Python pelado del runner (el
script es solo stdlib). Las reglas P1, el ratchet y los marcadores tienen su
batería completa en `core/tests/test_design_audit_estructura.py`, que corre en
Backend CI.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import design_audit


class DesignAuditGeneratedAssetsTests(unittest.TestCase):
    def test_no_audita_el_css_generado_por_tailwind(self) -> None:
        generated_css = Path(design_audit.REPO, "static", "custom", "css", "tailwind.css")

        self.assertEqual(list(design_audit.iter_files([generated_css])), [])

    def test_no_audita_la_documentacion(self) -> None:
        # `docs/` guarda anexos y la línea base del agente de diseño, que incluye
        # templates generados a propósito fuera de canon.
        doc = Path(design_audit.REPO, "docs", "internal")

        self.assertEqual(list(design_audit.iter_files([doc])), [])


class DecodificadorTests(unittest.TestCase):
    """FE-13: el parser de identificadores CSS."""

    def test_twbuild_reconoce_valores_arbitrarios_con_coma(self) -> None:
        """RS-R6-08: los dos TWBUILD falsos que bloqueaban el hook.

        Tailwind escapa la coma de un valor arbitrario como `\\2c ` (hex + un
        espacio terminador). Leído a secas, el nombre de la clase se cortaba ahí
        y la clase quedaba marcada como «falta en el build» aunque estuviera.
        """
        css = r".h-\[clamp\(1rem\2c 2rem\)\]{height:1rem}.xl\:grid-cols-\[minmax\(0\2c 1fr\)_auto\]{}"
        declaradas = design_audit.clases_css(css)

        self.assertIn("h-[clamp(1rem,2rem)]", declaradas)
        self.assertIn("xl:grid-cols-[minmax(0,1fr)_auto]", declaradas)

    def test_escapes_literales(self) -> None:
        self.assertIn("xl:top-6", design_audit.clases_css(r".xl\:top-6{top:1.5rem}"))
        self.assertIn("w-1/2", design_audit.clases_css(r".w-1\/2{width:50%}"))

    def test_los_dos_falsos_positivos_historicos_ya_no_aparecen(self) -> None:
        """Las dos clases reales del repo que TWBUILD reportaba mal (Cambio 95)."""
        declaradas = design_audit._clases_del_build()
        if declaradas is None:  # sin build committeado no hay nada que verificar
            self.skipTest("falta static/custom/css/tailwind.css")
        for clase in ("h-[clamp(12rem,calc(100dvh-31rem),28rem)]", "xl:grid-cols-[minmax(0,1fr)_auto]"):
            self.assertIn(clase, declaradas)


class RatchetTests(unittest.TestCase):
    RUTA = "legajos/templates/legajos/x.html"

    def test_no_reporta_la_deuda_preexistente(self) -> None:
        base = '<div class="bg-gray-200">viejo</div>'
        actual = base + '\n<p class="text-body">nuevo</p>'

        self.assertEqual(design_audit.nuevos(base, actual, self.RUTA), [])

    def test_reporta_lo_que_agrega_la_edicion(self) -> None:
        base = '<div class="bg-gray-200">viejo</div>'
        actual = base + '\n<p class="text-gray-900">nuevo</p>'

        hallazgos = design_audit.nuevos(base, actual, self.RUTA)

        self.assertEqual([f[2] for f in hallazgos], ["RAWPALETTE"])
        self.assertEqual(hallazgos[0][1], 2)


class GoldensTests(unittest.TestCase):
    def test_sin_tabla_de_arquetipos_el_modo_es_tolerante(self) -> None:
        """Hasta el paso 4 de la Ola 6 el núcleo no declara `## Arquetipos`."""
        if design_audit.goldens_declaradas() is not None:
            self.skipTest("el núcleo ya declara la tabla `## Arquetipos`")

        self.assertEqual(design_audit.goldens_mode(), 0)


class CompileTemplatesTests(unittest.TestCase):
    def test_compile_templates_excluye_site_packages(self) -> None:
        """V5A-NEW-08: los venv del proyecto viven adentro del checkout."""
        fuente = Path(design_audit.REPO, "scripts", "compile_templates.py").read_text(encoding="utf-8")

        self.assertIn('"site-packages" not in', fuente)


class ArquetipoCliTests(unittest.TestCase):
    def test_golden_de_listado_cumple_sus_marcadores(self) -> None:
        golden = "programas/templates/programas/becas/revision/personas_list.html"
        if not (design_audit.REPO / golden).exists():
            self.skipTest("falta la golden de listado")

        self.assertEqual(design_audit.arquetipo_mode("listado", [golden]), 0)

    def test_marcador_faltante_corta(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "list.html"
            p.write_text('{% extends "includes/base.html" %}', encoding="utf-8")

            self.assertEqual(design_audit.arquetipo_mode("listado", [str(p)]), 1)


if __name__ == "__main__":
    unittest.main()
