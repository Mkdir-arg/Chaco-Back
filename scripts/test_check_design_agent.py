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
    """Los encendió el paso 4 de la Ola 6; el núcleo real tiene que cumplirlos."""

    def test_prosa_demasiado_grande(self) -> None:
        enorme = "x" * (check_design_agent.PROSA_MAX_BYTES + 1)

        errores = check_design_agent.limites_del_nucleo(enorme, [])

        self.assertTrue(any("core agent prose is too large" in e for e in errores), errores)

    def test_prosa_en_el_limite_pasa(self) -> None:
        justo = "x" * check_design_agent.PROSA_MAX_BYTES

        errores = check_design_agent.limites_del_nucleo(justo, [])

        self.assertFalse([e for e in errores if "prose is too large" in e], errores)

    def test_las_filas_de_tabla_no_cuentan_contra_la_prosa(self) -> None:
        """El inventario es un índice: crece una fila por pieza canónica, y eso es sano.

        Lo que acota las filas es `CELDA_MAX_CARACTERES`, que va fila por fila y obliga a
        que el detalle viva en la ficha. Antes había un único tope total, que mezclaba las
        dos cosas: parecía proteger de la prosa y a la vez castigaba agregar piezas.
        """
        fila = "| Pieza | Canónico reutilizable | `templates/x.html`; contrato corto |\n"
        texto = "prosa corta\n" + fila * 400

        errores = check_design_agent.limites_del_nucleo(texto, [])

        self.assertFalse([e for e in errores if "prose is too large" in e], errores)
        self.assertGreater(len(texto.encode("utf-8")), check_design_agent.PROSA_MAX_BYTES)

    def test_el_tamanio_no_depende_del_fin_de_linea(self) -> None:
        """CRLF en el checkout de Windows, LF en el del CI: el mismo núcleo mide igual.

        Antes la función medía el texto crudo y confiaba en que quien lo leyera ya lo
        hubiera normalizado, así que este test afirmaba que con CRLF el mismo contenido
        **sí** se pasaba del tope: documentaba la fragilidad en vez de evitarla. Ahora la
        función normaliza ella misma (`splitlines()` más `"\n".join`), que es lo que el
        docstring decía querer desde el principio, y el veredicto es el mismo en los dos
        checkouts.
        """
        linea = "x" * 99 + "\n"
        texto = linea * (check_design_agent.PROSA_MAX_BYTES // 100)

        self.assertEqual(
            check_design_agent.limites_del_nucleo(texto, []),
            check_design_agent.limites_del_nucleo(texto.replace("\n", "\r\n"), []),
        )
        apenas_pasado = texto + "x" * 200
        self.assertTrue(check_design_agent.limites_del_nucleo(apenas_pasado, []))
        self.assertTrue(check_design_agent.limites_del_nucleo(apenas_pasado.replace("\n", "\r\n"), []))

    def test_los_topes_que_el_contrato_dice_son_los_que_el_checker_aplica(self) -> None:
        """Nada contrastaba la cifra escrita contra la constante, y se desfasó.

        El agente y el workflow decían «núcleo ≤ 30.000 bytes» mucho después de que eso
        dejara de ser cierto, así que quien leía el contrato creía otra cosa que la que el
        gate hacía cumplir. Un número en prosa que nadie verifica envejece sin avisar.
        """
        raiz = Path(__file__).resolve().parents[1]
        prosa_kb = f"{check_design_agent.PROSA_MAX_BYTES:,}".replace(",", ".")
        celdas = str(check_design_agent.CELDA_MAX_CARACTERES)

        for ruta in (
            raiz / ".claude/agents/chaco-design-system.md",
            raiz / ".github/workflows/design-agent-contract.yml",
        ):
            with self.subTest(archivo=ruta.name):
                texto = ruta.read_text(encoding="utf-8")
                self.assertIn(prosa_kb, texto, f"{ruta.name} no nombra el tope de prosa vigente")
                self.assertIn(celdas, texto, f"{ruta.name} no nombra el tope por celda vigente")

    def test_celda_demasiado_larga(self) -> None:
        fila = ("Pieza", "Canónico reutilizable", "x" * (check_design_agent.CELDA_MAX_CARACTERES + 1))

        errores = check_design_agent.limites_del_nucleo("texto corto", [fila])

        self.assertTrue(any("contract cell too long" in e for e in errores), errores)

    def test_celda_en_el_limite_pasa(self) -> None:
        fila = ("Pieza", "Canónico reutilizable", "x" * check_design_agent.CELDA_MAX_CARACTERES)

        errores = check_design_agent.limites_del_nucleo("texto corto", [fila])

        self.assertFalse([e for e in errores if "contract cell too long" in e], errores)

    def test_historia_prohibida_en_el_nucleo(self) -> None:
        texto = "La fila la fijó el Cambio 69 en la Ola 5, el 30-sep-2026 (CMP-12)."

        errores = check_design_agent.limites_del_nucleo(texto, [])
        historia = sorted(e.split(": ", 1)[1].split(" (va en")[0] for e in errores if e.startswith("history reference"))

        self.assertEqual(historia, ["30-sep-2026", "CMP-12", "Cambio 69", "Ola 5"])

    def test_texto_sin_historia_no_reporta(self) -> None:
        errores = check_design_agent.limites_del_nucleo("Contrato de la tabla densa del backoffice.", [])

        self.assertFalse([e for e in errores if e.startswith("history reference")], errores)

    def test_el_nucleo_real_cumple_la_bandera_limites(self) -> None:
        """Lo que el CI corre: `--limites` sobre el núcleo del repo, sin errores."""
        self.assertEqual(check_design_agent.validate(REPO, limites=True), [])


if __name__ == "__main__":
    unittest.main()
