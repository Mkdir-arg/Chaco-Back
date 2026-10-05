"""Contrato público del verificador del agente canónico de diseño."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

import check_design_agent

REPO = Path(__file__).resolve().parent.parent
CHECKER = REPO / "scripts" / "check_design_agent.py"
AGENTE = REPO / check_design_agent.AGENT_RELATIVE


class CheckDesignAgentCliTests(unittest.TestCase):
    def run_checker(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CHECKER), "--repo", str(REPO), *args],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_current_design_agent_contract_passes(self) -> None:
        result = self.run_checker()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("design-agent contract: OK", result.stdout)

    def test_changed_canonical_piece_requires_inventory_update(self) -> None:
        result = self.run_checker("--changed-file", "static/custom/css/chaco-tokens.css")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must update .claude/agents/chaco-design-system.md", result.stdout)

    def test_programas_templates_can_be_canonical_evidence(self) -> None:
        result = self.run_checker(
            "--changed-file",
            "programas/templates/programas/becas/config/programa_detail.html",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must update .claude/agents/chaco-design-system.md", result.stdout)

    def test_tailwind_build_does_not_trigger_the_same_diff_rule(self) -> None:
        """N2: `tailwind.css` se regenera en cada build; no es un cambio de contrato."""
        result = self.run_checker("--changed-file", "static/custom/css/tailwind.css")

        self.assertEqual(result.returncode, 0, result.stdout)

    def test_updating_the_agent_satisfies_the_same_diff_rule(self) -> None:
        result = self.run_checker(
            "--changed-file",
            "static/custom/css/chaco-tokens.css",
            "--changed-file",
            check_design_agent.AGENT_RELATIVE.as_posix(),
        )

        self.assertEqual(result.returncode, 0, result.stdout)


class SplitCellsTests(unittest.TestCase):
    """N1: ninguna fila del inventario se descarta en silencio."""

    def test_pipe_escapado_no_parte_la_celda(self) -> None:
        celdas = check_design_agent.split_cells(r"Pieza | Canónico reutilizable | contrato a \| b")

        self.assertEqual(celdas, ["Pieza", "Canónico reutilizable", "contrato a | b"])

    def test_pipe_dentro_de_un_code_span_no_parte_la_celda(self) -> None:
        # El inventario documenta filtros de Django y expresiones regulares de JS.
        celdas = check_design_agent.split_cells("Pieza | Canónico reutilizable | usa `{{ x|json_script:'id' }}`")

        self.assertEqual(len(celdas), 3)
        self.assertIn("json_script", celdas[2])

    def test_fila_mal_formada_se_reporta_en_vez_de_descartarse(self) -> None:
        errores: list[str] = []
        texto = "## Inventario operativo inicial\n| Pieza | Clasificación | Contrato |\n|---|---|---|\n| A | B |\n"

        filas = check_design_agent.table_rows(texto, "## Inventario operativo inicial", errores, required=False)

        self.assertEqual(filas, [])
        self.assertTrue(any("malformed table row" in e for e in errores), errores)

    def test_el_inventario_real_no_pierde_ninguna_fila(self) -> None:
        texto = AGENTE.read_text(encoding="utf-8")
        errores: list[str] = []
        filas = check_design_agent.inventory_rows(texto, errores)

        crudas = [
            linea
            for linea in texto.split("## Inventario operativo inicial", 1)[1].split("\n## ", 1)[0].splitlines()
            if linea.startswith("|") and not linea.startswith("|---") and not linea.startswith("| Pieza ")
        ]
        self.assertEqual(len(filas), len(crudas), errores)


class FichasTests(unittest.TestCase):
    """La evidencia puede declararse en la ficha en vez de inflar la celda."""

    def test_ficha_de_lee_la_referencia(self) -> None:
        contrato = "contrato corto. Ficha: `.claude/design/arquetipos/listado.md`"

        self.assertEqual(
            check_design_agent.ficha_de(contrato),
            Path(".claude/design/arquetipos/listado.md"),
        )

    def test_sin_ficha_devuelve_none(self) -> None:
        self.assertIsNone(check_design_agent.ficha_de("contrato sin ficha"))

    def test_la_regla_del_mismo_diff_no_la_disparan_tests_ni_vistas(self) -> None:
        for exento in (
            "static/custom/css/tailwind.css",
            "programas/views/revision.py",
            "core/tests/test_page_header_tag.py",
        ):
            self.assertFalse(check_design_agent.dispara_mismo_diff(Path(exento)), exento)

    def test_la_regla_del_mismo_diff_si_la_dispara_un_componente(self) -> None:
        self.assertTrue(check_design_agent.dispara_mismo_diff(Path("templates/components/_page_header.html")))


class LimitesDelNucleoTests(unittest.TestCase):
    """Los enciende el paso 4 de la Ola 6; la lógica ya tiene que estar probada."""

    def test_nucleo_demasiado_grande(self) -> None:
        errores = check_design_agent.limites_del_nucleo(REPO, "texto corto", [])

        self.assertTrue(any("core agent is too large" in e for e in errores), errores)

    def test_celda_demasiado_larga(self) -> None:
        fila = ("Pieza", "Canónico reutilizable", "x" * (check_design_agent.CELDA_MAX_CARACTERES + 1))

        errores = check_design_agent.limites_del_nucleo(REPO, "texto corto", [fila])

        self.assertTrue(any("contract cell too long" in e for e in errores), errores)

    def test_celda_en_el_limite_pasa(self) -> None:
        fila = ("Pieza", "Canónico reutilizable", "x" * check_design_agent.CELDA_MAX_CARACTERES)

        errores = check_design_agent.limites_del_nucleo(REPO, "texto corto", [fila])

        self.assertFalse([e for e in errores if "contract cell too long" in e], errores)

    def test_historia_prohibida_en_el_nucleo(self) -> None:
        texto = "La fila la fijó el Cambio 69 en la Ola 5, el 30-sep-2026 (CMP-12)."

        errores = check_design_agent.limites_del_nucleo(REPO, texto, [])
        historia = sorted(e.split(": ", 1)[1].split(" (va en")[0] for e in errores if e.startswith("history reference"))

        self.assertEqual(historia, ["30-sep-2026", "CMP-12", "Cambio 69", "Ola 5"])

    def test_texto_sin_historia_no_reporta(self) -> None:
        errores = check_design_agent.limites_del_nucleo(REPO, "Contrato de la tabla densa del backoffice.", [])

        self.assertFalse([e for e in errores if e.startswith("history reference")], errores)

    def test_la_bandera_limites_todavia_no_la_cumple_el_nucleo(self) -> None:
        """Mientras el núcleo no se reescriba (paso 4), `--limites` tiene que fallar."""
        errores = check_design_agent.validate(REPO, limites=True)

        self.assertTrue(any("core agent is too large" in e for e in errores), errores)


if __name__ == "__main__":
    unittest.main()
