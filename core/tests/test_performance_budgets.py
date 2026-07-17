import json
import os
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, tag

from scripts.perf_audit import _capture_request, build_clients, build_targets

BUDGETS_PATH = settings.BASE_DIR / "scripts" / "perf_budgets.json"


@tag("performance")
class PerformanceBudgetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        with StringIO() as output:
            call_command("seed_perf", scale=200, stdout=output)

    def test_key_routes_stay_within_query_budgets(self):
        config = json.loads(BUDGETS_PATH.read_text(encoding="utf-8"))
        manifest = build_targets()
        targets = {target["key"]: target for target in manifest["targets"]}
        budgets = config["budgets"]

        self.assertEqual(set(targets), set(budgets), "Los presupuestos deben cubrir exactamente las URLs auditadas")

        clients = build_clients(manifest["actors"])
        failures = []
        total_duration_ms = 0.0
        for key, budget in budgets.items():
            target = targets[key]
            self.assertEqual(target["route"], budget["route"], f"Route desactualizada para {key}")
            cache.clear()
            measurement = _capture_request(clients[target["actor"]], target["url"])
            query_count = measurement["query_count"]
            total_duration_ms += measurement["duration_ms"]
            expected_status = target.get("expected_status", 200)
            self.assertEqual(measurement["response"].status_code, expected_status, f"Status inesperado en {key}")
            if query_count > budget["max_queries"]:
                failures.append(
                    f"{key} ({target['url']}): {query_count} queries actuales vs presupuesto "
                    f"{budget['max_queries']}. Probable N+1, falta select_related/prefetch_related o cache."
                )

        timing_output = os.environ.get("PERF_TIMING_OUTPUT")
        if timing_output:
            Path(timing_output).write_text(
                json.dumps({"total_duration_ms": round(total_duration_ms, 2)}) + "\n",
                encoding="utf-8",
            )

        self.assertFalse(failures, "Presupuestos de performance excedidos:\n" + "\n".join(failures))
