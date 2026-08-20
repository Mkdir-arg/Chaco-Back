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
            measurement = _capture_request(clients[target["actor"]], target["url"], target.get("request"))
            query_count = measurement["query_count"]
            duplicate_query_count = measurement["duplicate_query_count"]
            if target.get("include_in_timing", True):
                total_duration_ms += measurement["duration_ms"]
            expected_status = target.get("expected_status", 200)
            self.assertEqual(measurement["response"].status_code, expected_status, f"Status inesperado en {key}")
            if target.get("expected_json_success"):
                self.assertTrue(measurement["response"].json().get("success"), f"Respuesta inválida en {key}")
            if query_count > budget["max_queries"]:
                failures.append(
                    f"{key} ({target['url']}): {query_count} queries actuales vs presupuesto "
                    f"{budget['max_queries']}. Probable N+1, falta select_related/prefetch_related o cache."
                )
            if duplicate_query_count > budget["max_duplicate_queries"]:
                failures.append(
                    f"{key} ({target['url']}): {duplicate_query_count} queries duplicadas actuales vs presupuesto "
                    f"{budget['max_duplicate_queries']}. Probable N+1 o consulta redundante."
                )

        timing_output = os.environ.get("PERF_TIMING_OUTPUT")
        if timing_output:
            Path(timing_output).write_text(
                json.dumps({"total_duration_ms": round(total_duration_ms, 2)}) + "\n",
                encoding="utf-8",
            )

        self.assertFalse(failures, "Presupuestos de performance excedidos:\n" + "\n".join(failures))

    def test_login_budget_exercises_the_submission(self):
        manifest = build_targets()
        target = next(item for item in manifest["targets"] if item["key"] == "login")
        client = build_clients(manifest["actors"])[target["actor"]]

        measurement = _capture_request(client, target["url"], target.get("request"))

        self.assertEqual(target["expected_status"], 302)
        self.assertIsNotNone(target.get("request"))
        self.assertEqual(measurement["response"].status_code, 302)

    def test_ci_worker_uses_an_isolated_login_identity(self):
        from core.management.commands.perf_ci_probe import Command

        worker_id = "login-contract-worker"
        manifest = build_targets(worker_id=worker_id)
        clients = Command._build_worker_clients(worker_id, manifest["actors"])
        target = next(item for item in manifest["targets"] if item["key"] == "login")

        response = target["request"](clients["login"], target["url"])

        self.assertEqual(response.status_code, 302)

    def test_ci_workers_can_send_to_separate_conversations(self):
        from core.management.commands.perf_ci_probe import Command

        first_manifest = build_targets(worker_id="conversation-worker-one")
        second_manifest = build_targets(worker_id="conversation-worker-two")
        first_target = next(item for item in first_manifest["targets"] if item["key"] == "envio_conversacion")
        second_target = next(item for item in second_manifest["targets"] if item["key"] == "envio_conversacion")

        self.assertNotEqual(first_target["url"], second_target["url"])

        for worker_id, manifest, target in (
            ("conversation-worker-one", first_manifest, first_target),
            ("conversation-worker-two", second_manifest, second_target),
        ):
            clients = Command._build_worker_clients(worker_id, manifest["actors"])
            response = target["request"](clients["backoffice"], target["url"])

            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["success"])
