"""Contrato de privacidad de la clasificación SQL de la auditoría #273."""

import importlib.util
import json
from pathlib import Path
from traceback import FrameSummary
from unittest.mock import patch

from django.test import SimpleTestCase


def _load_perf_audit():
    script = Path(__file__).resolve().parents[2] / "scripts" / "perf_audit.py"
    spec = importlib.util.spec_from_file_location("perf_audit", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


perf_audit = _load_perf_audit()


class PerfAuditDuplicateGroupsTests(SimpleTestCase):
    def test_call_site_ignores_the_repository_venv(self):
        frames = [
            FrameSummary(str(perf_audit.REPO / "programas" / "views" / "relevamientos.py"), 153, "get_context_data"),
            FrameSummary(
                str(perf_audit.REPO / ".venv" / "Lib" / "site-packages" / "django" / "db" / "utils.py"),
                80,
                "_execute_with_wrappers",
            ),
            FrameSummary(str(perf_audit.REPO / "scripts" / "perf_audit.py"), 93, "__call__"),
        ]

        with patch.object(perf_audit.traceback, "extract_stack", return_value=frames):
            self.assertEqual(
                perf_audit.query_call_site(),
                "programas/views/relevamientos.py:153:get_context_data",
            )

    def test_duplicate_groups_publish_fingerprint_and_call_site_without_sql(self):
        groups = perf_audit.duplicate_query_groups(
            [
                {
                    "sql": "SELECT * FROM programas_relevamiento WHERE zona = 'Dato sensible'",
                    "call_site": "programas/views/relevamientos.py:153:get_context_data",
                },
                {
                    "sql": "SELECT * FROM programas_relevamiento WHERE zona = 'Otra zona'",
                    "call_site": "programas/views/relevamientos.py:153:get_context_data",
                },
                {
                    "sql": "SELECT * FROM programas_relevamiento WHERE zona = 'Tercera zona'",
                    "call_site": "programas/views/relevamientos.py:163:get_context_data",
                },
            ]
        )

        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["occurrences"], 3)
        self.assertEqual(groups[0]["duplicates"], 2)
        self.assertEqual(
            groups[0]["call_sites"],
            [
                {"call_site": "programas/views/relevamientos.py:153:get_context_data", "occurrences": 2},
                {"call_site": "programas/views/relevamientos.py:163:get_context_data", "occurrences": 1},
            ],
        )

        serialized = json.dumps(groups)
        self.assertIn("fingerprint", groups[0])
        self.assertNotIn("SELECT", serialized)
        self.assertNotIn("Dato sensible", serialized)
        self.assertNotIn("Otra zona", serialized)
