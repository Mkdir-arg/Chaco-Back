"""Contrato público del verificador del agente canónico de diseño."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CHECKER = REPO / "scripts" / "check_design_agent.py"


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


if __name__ == "__main__":
    unittest.main()
