"""Regresiones del filtro de artefactos generados de design_audit."""

from __future__ import annotations

import unittest
from pathlib import Path

import design_audit


class DesignAuditGeneratedAssetsTests(unittest.TestCase):
    def test_no_audita_el_css_generado_por_tailwind(self) -> None:
        generated_css = Path(design_audit.REPO, "static", "custom", "css", "tailwind.css")

        self.assertEqual(list(design_audit.iter_files([generated_css])), [])


if __name__ == "__main__":
    unittest.main()
