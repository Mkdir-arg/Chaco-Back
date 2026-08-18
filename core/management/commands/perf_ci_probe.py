"""Ejecuta la sonda de performance sobre el stack efímero de CI.

El comando se niega a correr fuera del MySQL aislado de CI. No autentica contra
servicios externos ni conserva SQL, parámetros, credenciales o payloads.
"""

import json
import os
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.http import HttpResponse
from django.test import RequestFactory

from config.middlewares.query_counter import QueryCountMiddleware
from core.performance.query_observability import QueryObservabilityStore, instrument_external_call


def _write_json(path, payload):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class Command(BaseCommand):
    help = "Sonda de performance para CI efímera MySQL+Redis."

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--worker", metavar="ID", help="Ejecuta una pasada desde un proceso worker independiente.")
        group.add_argument(
            "--verify", action="store_true", help="Verifica la agregación compartida luego de las pasadas."
        )
        parser.add_argument(
            "--workers", type=int, default=2, help="Cantidad esperada de procesos worker para --verify."
        )
        parser.add_argument("--output", required=True, help="Artefacto JSON de CI, sin datos sensibles.")

    def handle(self, *args, **options):
        self._assert_ephemeral_ci()
        if options["worker"]:
            self._run_worker(options["worker"], options["output"])
            return
        self._verify(options["workers"], options["output"])

    @staticmethod
    def _assert_ephemeral_ci():
        database_name = str(connection.settings_dict.get("NAME") or "")
        valid_config = (
            os.environ.get("PERFORMANCE_CI") == "1"
            and settings.ENVIRONMENT == "ci"
            and connection.vendor == "mysql"
            and database_name == "chaco_perf_ci"
        )
        actual_database_name = None
        if valid_config:
            with connection.cursor() as cursor:
                cursor.execute("SELECT DATABASE()")
                actual_database_name = cursor.fetchone()[0]
        if not valid_config or actual_database_name != "chaco_perf_ci":
            raise CommandError(
                "perf_ci_probe sólo puede correr con PERFORMANCE_CI=1, ENVIRONMENT=ci y un MySQL "
                "efímero llamado exactamente chaco_perf_ci."
            )

    def _run_worker(self, worker_id, output):
        from scripts.perf_audit import build_targets

        manifest = build_targets()
        clients = self._build_worker_clients(worker_id, manifest["actors"])
        results = []
        with patch("programas.forms.listar_programas", side_effect=self._stubbed_siis_catalog):
            for target in manifest["targets"]:
                response = clients[target["actor"]].get(target["url"], follow=False)
                expected_status = target.get("expected_status", 200)
                if response.status_code != expected_status:
                    raise CommandError(
                        f"{target['key']} devolvió {response.status_code}; se esperaba {expected_status} en CI efímera."
                    )
                results.append({"key": target["key"], "route": target["route"], "status_code": response.status_code})

        self._record_stubbed_dependency()
        _write_json(
            output,
            {
                "schema_version": 1,
                "worker": worker_id,
                "route_count": len(results),
                "routes": results,
                "external_dependencies": "stubbed_in_process",
            },
        )

    @staticmethod
    def _build_worker_clients(worker_id, actor_usernames):
        """Crea identidades aisladas para no violar la sesión única de Backoffice."""
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Group
        from django.test import Client

        from legajos.models import Ciudadano
        from users.models import Profile

        suffix = sha256(worker_id.encode()).hexdigest()[:12]
        user_model = get_user_model()

        def worker_user(actor):
            source = user_model.objects.get(username=actor_usernames[actor])
            username = f"perf_ci_{actor}_{suffix}"
            user, _ = user_model.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": source.first_name,
                    "last_name": source.last_name,
                    "email": f"{username}@perf.invalid",
                    "is_active": True,
                    "is_staff": source.is_staff,
                    "is_superuser": source.is_superuser,
                },
            )
            user.groups.set(Group.objects.filter(pk__in=source.groups.values("pk")))
            profile, _ = Profile.objects.get_or_create(user=user)
            # La sonda puede reintentarse sobre la misma DB efímera. Forzar un
            # nuevo login requiere dejar que el middleware registre su nueva
            # key, sin competir con una corrida anterior del mismo worker.
            if profile.backoffice_session_key:
                profile.backoffice_session_key = None
                profile.save(update_fields=["backoffice_session_key"])
            return user

        backoffice = worker_user("backoffice")
        citizen = worker_user("citizen")
        if not Ciudadano.objects.filter(usuario=citizen).exists():
            ciudadano = Ciudadano.objects.filter(usuario__isnull=True, dni__startswith="8").order_by("dni").first()
            if ciudadano is None:
                raise CommandError("seed_perf no dejó ciudadanos libres para identidades worker de CI.")
            ciudadano.usuario = citizen
            ciudadano.save(update_fields=["usuario"])

        clients = {
            "anonymous": Client(raise_request_exception=False),
            "backoffice": Client(raise_request_exception=False),
            "citizen": Client(raise_request_exception=False),
        }
        clients["backoffice"].force_login(backoffice)
        clients["citizen"].force_login(citizen)
        return clients

    @staticmethod
    def _record_stubbed_dependency():
        response = type("StubResponse", (), {"status_code": 200})()

        def get_response(_request):
            instrument_external_call("ci_stub", lambda: response)
            return HttpResponse("ok")

        QueryCountMiddleware(get_response)(RequestFactory().get("/performance-ci-dependency-probe/"))

    @staticmethod
    def _stubbed_siis_catalog():
        """Evita llamadas de red y conserva la traza agregada de la dependencia."""
        return instrument_external_call("siis", lambda: [])

    def _verify(self, worker_count, output):
        if worker_count < 2:
            raise CommandError("--workers debe ser al menos 2 para verificar la agregación entre procesos.")
        from scripts.perf_audit import build_targets

        report = QueryObservabilityStore().snapshot()
        if report["metrics_source"] != "measured" or report["scope"] != "shared_ci_run":
            raise CommandError("Redis no entregó métricas compartidas para la sonda de CI.")
        if report["n1_affected_requests"]:
            raise CommandError("La sonda detectó N+1 en el stack efímero de CI.")
        routes = {item["route"]: item for item in report["routes"]}
        targets = build_targets()["targets"]
        required_routes = {target["route"] for target in targets}
        missing = sorted(route for route in required_routes if routes.get(route, {}).get("requests", 0) < worker_count)
        if missing:
            raise CommandError(f"Faltan mediciones agregadas de {worker_count} workers para: {', '.join(missing)}")
        budgets = self._load_query_budgets()
        breaches = []
        for target in targets:
            measurement = routes[target["route"]]
            budget = budgets[target["key"]]
            for metric, budget_key, label in (
                ("max_queries", "max_queries", "queries máximas por request"),
                (
                    "max_duplicate_queries",
                    "max_duplicate_queries",
                    "queries duplicadas máximas por request",
                ),
            ):
                maximum = budget[budget_key]
                if measurement[metric] > maximum:
                    breaches.append(f"{target['key']}: {measurement[metric]} {label} vs máximo {maximum}")
        if breaches:
            raise CommandError("Presupuesto MySQL excedido: " + "; ".join(breaches))
        dependency = routes.get("unresolved", {}).get("dependencies", {}).get("ci_stub", {})
        if dependency.get("calls", 0) < worker_count or dependency.get("errors", 0) != 0:
            raise CommandError("La dependencia stubbed no quedó agregada correctamente entre workers.")
        siis_calls = sum(route.get("dependencies", {}).get("siis", {}).get("calls", 0) for route in report["routes"])
        if siis_calls < worker_count:
            raise CommandError("La sonda no registró el stub SIIS en cada worker.")
        artifact = {
            "schema_version": 1,
            "workers": worker_count,
            "metrics_source": report["metrics_source"],
            "scope": report["scope"],
            "total_requests": report["total_requests"],
            "total_queries": report["total_queries"],
            "n1_affected_requests": report["n1_affected_requests"],
            "routes": report["routes"],
        }
        self._assert_redacted(artifact)
        _write_json(output, artifact)

    @staticmethod
    def _load_query_budgets():
        budget_file = Path(__file__).resolve().parents[3] / "scripts" / "perf_budgets.json"
        try:
            return json.loads(budget_file.read_text(encoding="utf-8"))["budgets"]
        except (OSError, KeyError, json.JSONDecodeError) as exc:
            raise CommandError(f"No se pudieron cargar los presupuestos de CI: {exc}") from exc

    @staticmethod
    def _assert_redacted(value):
        forbidden_keys = {"sql", "params", "payload", "password", "username", "token", "url"}
        if isinstance(value, dict):
            offending = forbidden_keys.intersection(value)
            if offending:
                raise CommandError(f"El artefacto de CI contiene campos sensibles: {', '.join(sorted(offending))}")
            for nested in value.values():
                Command._assert_redacted(nested)
        elif isinstance(value, list):
            for nested in value:
                Command._assert_redacted(nested)
