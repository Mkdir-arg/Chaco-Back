#!/usr/bin/env python
"""Auditoría mecánica y reproducible de performance para superficies Django clave."""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from urllib.parse import urljoin, urlparse

REPO = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO / "scripts" / "perf_baseline.json"
WARM_SAMPLE_COUNT = 3

HEX_BLOB_RE = re.compile(r"\b(?:0x[0-9a-f]+|x'[0-9a-f]+')\b", re.IGNORECASE)
SQL_STRING_RE = re.compile(r"'(?:''|\\.|[^'])*'")
SQL_NUMBER_RE = re.compile(r"(?<![\w])[-+]?\d+(?:\.\d+)?(?![\w])")
WHITESPACE_RE = re.compile(r"\s+")


def bootstrap_django():
    """Carga Django únicamente contra la SQLite in-memory usada por tests."""
    os.environ["PYTEST_RUNNING"] = "1"
    os.environ["DJANGO_SYNCDB_PROJECT_APPS"] = "True"
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
    os.environ.setdefault("DJANGO_SECRET_KEY", "test-key")
    os.environ["DJANGO_DEBUG"] = "False"
    os.environ["DJANGO_ALLOWED_HOSTS"] = "testserver,localhost"
    os.environ["ENVIRONMENT"] = "dev"

    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))

    import django

    django.setup()

    from django.conf import settings

    database = settings.DATABASES["default"]
    if database["ENGINE"] != "django.db.backends.sqlite3" or database["NAME"] != ":memory:":
        raise RuntimeError("perf_audit se negó a iniciar: la base configurada no es SQLite in-memory")


def normalize_sql(sql: str) -> str:
    """Elimina valores variables para comparar la forma de dos queries."""
    normalized = HEX_BLOB_RE.sub("?", sql)
    normalized = SQL_STRING_RE.sub("?", normalized)
    normalized = SQL_NUMBER_RE.sub("?", normalized)
    return WHITESPACE_RE.sub(" ", normalized).strip()


def duplicate_query_groups(captured_queries):
    groups = Counter(normalize_sql(query.get("sql", "")) for query in captured_queries)
    repeated = [
        {
            "occurrences": occurrences,
            "duplicates": occurrences - 1,
            "sql": sql[:500],
        }
        for sql, occurrences in groups.items()
        if occurrences > 1
    ]
    repeated.sort(key=lambda item: (-item["occurrences"], item["sql"]))
    return repeated


def build_targets():
    """Resuelve el manifiesto después del seed, fuera de la captura SQL."""
    from django.urls import reverse

    from conversaciones.models import Conversacion
    from core.management.commands.seed_perf import PERF_ADMIN_USERNAME, PERF_CITIZEN_USERNAME, PERF_FIRST_DNI
    from legajos.models import Ciudadano
    from programas.models import Relevamiento

    ciudadano = Ciudadano.objects.get(dni=PERF_FIRST_DNI)
    conversacion = (
        Conversacion.objects.filter(ciudadano_usuario__username=PERF_CITIZEN_USERNAME).order_by("fecha_inicio").first()
    )
    relevamiento = Relevamiento.objects.get(nombre="PERF Relevamiento 0000")

    if conversacion is None:
        raise RuntimeError("seed_perf no creó la conversación PERF requerida")

    return {
        "actors": {
            "backoffice": PERF_ADMIN_USERNAME,
            "citizen": PERF_CITIZEN_USERNAME,
        },
        "targets": [
            {"key": "login", "route": "users:login", "url": reverse("users:login"), "actor": "anonymous"},
            {"key": "inicio", "route": "core:inicio", "url": reverse("core:inicio"), "actor": "backoffice"},
            {
                "key": "dashboard_redirect",
                "route": "core:dashboard",
                "url": reverse("core:dashboard"),
                "actor": "backoffice",
                "expected_status": 302,
                "expected_redirect_view": "users:login",
            },
            {
                "key": "dashboard_metricas",
                "route": "dashboard:api_metricas",
                "url": reverse("dashboard:api_metricas"),
                "actor": "backoffice",
            },
            {
                "key": "legajos_lista",
                "route": "legajos:ciudadanos",
                "url": reverse("legajos:ciudadanos"),
                "actor": "backoffice",
            },
            {
                "key": "legajo_detalle",
                "route": "legajos:ciudadano_detalle",
                "url": reverse("legajos:ciudadano_detalle", kwargs={"pk": ciudadano.pk}),
                "actor": "backoffice",
            },
            {
                "key": "conversaciones_lista",
                "route": "conversaciones:lista",
                "url": reverse("conversaciones:lista"),
                "actor": "backoffice",
            },
            {
                "key": "conversacion_detalle",
                "route": "conversaciones:detalle",
                "url": reverse("conversaciones:detalle", kwargs={"conversacion_id": conversacion.pk}),
                "actor": "backoffice",
            },
            {"key": "portal_home", "route": "portal:home", "url": reverse("portal:home"), "actor": "anonymous"},
            {
                "key": "portal_perfil",
                "route": "portal:ciudadano_mi_perfil",
                "url": reverse("portal:ciudadano_mi_perfil"),
                "actor": "citizen",
            },
            {
                "key": "portal_programas",
                "route": "portal:ciudadano_mis_programas",
                "url": reverse("portal:ciudadano_mis_programas"),
                "actor": "citizen",
            },
            {
                "key": "portal_consultas",
                "route": "portal:ciudadano_mis_consultas",
                "url": reverse("portal:ciudadano_mis_consultas"),
                "actor": "citizen",
            },
            {
                "key": "becas_segmentos",
                "route": "becas:segmentos",
                "url": reverse("becas:segmentos"),
                "actor": "backoffice",
            },
            {
                "key": "becas_convocatorias",
                "route": "becas:convocatorias",
                "url": reverse("becas:convocatorias"),
                "actor": "backoffice",
            },
            {
                "key": "becas_relevamientos",
                "route": "becas:relevamientos",
                "url": reverse("becas:relevamientos"),
                "actor": "backoffice",
            },
            {
                "key": "becas_relevamiento_detalle",
                "route": "becas:relevamiento_detalle",
                "url": reverse("becas:relevamiento_detalle", kwargs={"pk": relevamiento.pk}),
                "actor": "backoffice",
            },
        ],
    }


def build_clients(actor_usernames):
    from django.contrib.auth import get_user_model
    from django.test import Client

    user_model = get_user_model()
    clients = {
        "anonymous": Client(raise_request_exception=False),
        "backoffice": Client(raise_request_exception=False),
        "citizen": Client(raise_request_exception=False),
    }
    clients["backoffice"].force_login(user_model.objects.get(username=actor_usernames["backoffice"]))
    clients["citizen"].force_login(user_model.objects.get(username=actor_usernames["citizen"]))
    return clients


def _resolved_view(url):
    from django.urls import Resolver404, resolve

    try:
        return resolve(urlparse(url).path).view_name
    except Resolver404:
        return None


def _capture_request(client, url):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    with CaptureQueriesContext(connection) as captured:
        started = time.perf_counter_ns()
        response = client.get(url, follow=False)
        body = response.content
        duration_ms = (time.perf_counter_ns() - started) / 1_000_000

    duplicate_groups = duplicate_query_groups(captured.captured_queries)
    return {
        "response": response,
        "body": body,
        "query_count": len(captured),
        "duplicate_query_count": sum(group["duplicates"] for group in duplicate_groups),
        "duration_ms": duration_ms,
        "duplicate_groups": duplicate_groups,
    }


def measure_target(target, client):
    from django.core.cache import cache

    cache.clear()
    cold = _capture_request(client, target["url"])
    warm_samples = [_capture_request(client, target["url"]) for _ in range(WARM_SAMPLE_COUNT)]

    response = cold["response"]
    body = cold["body"]

    redirect_to = response.get("Location") if 300 <= response.status_code < 400 else None
    redirect_view = _resolved_view(urljoin(target["url"], redirect_to)) if redirect_to else None
    result = {
        "key": target["key"],
        "route": target["route"],
        "url": target["url"],
        "actor": target["actor"],
        "resolved_view": _resolved_view(target["url"]),
        "status_code": response.status_code,
        "redirect_to": redirect_to,
        "redirect_resolved_view": redirect_view,
        "query_count": cold["query_count"],
        "duplicate_query_count": cold["duplicate_query_count"],
        "duration_ms": round(cold["duration_ms"], 2),
        "warm_sample_count": WARM_SAMPLE_COUNT,
        "warm_query_count": int(statistics.median(sample["query_count"] for sample in warm_samples)),
        "warm_duplicate_query_count": int(
            statistics.median(sample["duplicate_query_count"] for sample in warm_samples)
        ),
        "warm_duration_ms": round(statistics.median(sample["duration_ms"] for sample in warm_samples), 2),
        "response_bytes": len(body),
        "content_type": response.get("Content-Type", ""),
        "duplicate_groups": cold["duplicate_groups"][:10],
    }
    expected_status = target.get("expected_status", 200)
    errors = []
    if response.status_code != expected_status:
        errors.append(f"status {response.status_code}, esperado {expected_status}")
    warm_statuses = {sample["response"].status_code for sample in warm_samples}
    if warm_statuses != {expected_status}:
        errors.append(f"status warm {sorted(warm_statuses)}, esperado solo {expected_status}")
    if result["resolved_view"] != target["route"]:
        errors.append(f"resuelve a {result['resolved_view']!r}, esperado {target['route']!r}")
    expected_redirect_view = target.get("expected_redirect_view")
    if expected_redirect_view and redirect_view != expected_redirect_view:
        errors.append(f"redirect resuelve a {redirect_view!r}, esperado {expected_redirect_view!r}")
    return result, errors


def create_report(scale):
    manifest = build_targets()
    clients = build_clients(manifest["actors"])
    results = []
    failures = []
    for target in manifest["targets"]:
        result, errors = measure_target(target, clients[target["actor"]])
        results.append(result)
        if errors:
            failures.append(f"{target['key']}: {'; '.join(errors)}")

    report = {
        "schema_version": 1,
        "environment": {
            "database": "sqlite-memory",
            "scale": scale,
            "cache_state": "cold request plus median of 3 warm requests per URL; primary fields are cold",
            "duplicate_definition": "sum(occurrences - 1) for normalized SQL repeated in one request",
            "timing_scope": "Django test client + middleware + render; no network/application server",
        },
        "coverage_notes": [
            "dashboard_redirect documents that /dashboard/ redirects to the shadowed users login at /.",
            "tramites is not measured because the current app has no models, views or URL patterns.",
            "SQLite timings and query plans are not representative of MySQL production.",
        ],
        "summary": {
            "url_count": len(results),
            "successful_2xx": sum(1 for result in results if 200 <= result["status_code"] < 300),
            "total_queries": sum(result["query_count"] for result in results),
            "total_duplicate_queries": sum(result["duplicate_query_count"] for result in results),
            "total_duration_ms": round(sum(result["duration_ms"] for result in results), 2),
            "total_warm_queries": sum(result["warm_query_count"] for result in results),
            "total_warm_duplicate_queries": sum(result["warm_duplicate_query_count"] for result in results),
            "total_warm_duration_ms": round(sum(result["warm_duration_ms"] for result in results), 2),
            "total_response_bytes": sum(result["response_bytes"] for result in results),
        },
        "results": results,
    }
    return report, failures


def write_report(report, output):
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)


def print_report(report):
    print("\nPerformance baseline (cold + mediana de 3 warm por URL)")
    print(f"{'URL':30} {'St':>3} {'Qc':>5} {'Qw':>5} {'Dc':>4} {'Dw':>4} {'ms c':>8} {'ms w':>8} {'Bytes':>9}")
    print("-" * 88)
    for result in report["results"]:
        print(
            f"{result['key'][:30]:30} {result['status_code']:>3} "
            f"{result['query_count']:>5} {result['warm_query_count']:>5} "
            f"{result['duplicate_query_count']:>4} {result['warm_duplicate_query_count']:>4} "
            f"{result['duration_ms']:>8.2f} {result['warm_duration_ms']:>8.2f} {result['response_bytes']:>9}"
        )

    ranked = sorted(
        (result for result in report["results"] if 200 <= result["status_code"] < 300),
        key=lambda result: (-result["query_count"], -result["duplicate_query_count"], result["key"]),
    )[:10]
    print("\nTop 10 por queries cold (solo respuestas 2xx)")
    for position, result in enumerate(ranked, 1):
        print(
            f"{position:>2}. {result['key']}: {result['query_count']} queries, "
            f"{result['duplicate_query_count']} duplicadas, {result['duration_ms']:.2f} ms"
        )

    duplicated = sorted(
        (result for result in report["results"] if 200 <= result["status_code"] < 300),
        key=lambda result: (-result["duplicate_query_count"], -result["query_count"], result["key"]),
    )[:10]
    print("\nTop 10 por queries duplicadas cold (solo respuestas 2xx)")
    for position, result in enumerate(duplicated, 1):
        print(
            f"{position:>2}. {result['key']}: {result['duplicate_query_count']} duplicadas "
            f"sobre {result['query_count']} queries"
        )


def run(scale, output):
    bootstrap_django()

    from django.test.runner import DiscoverRunner

    runner = DiscoverRunner(verbosity=0, interactive=False)
    old_config = None
    environment_ready = False
    try:
        runner.setup_test_environment()
        environment_ready = True
        old_config = runner.setup_databases()
        seed_output = StringIO()
        with redirect_stdout(seed_output), redirect_stderr(seed_output):
            from django.core.management import call_command

            call_command("seed_perf", scale=scale, verbosity=0)
        report, failures = create_report(scale)
        print_report(report)
        if failures:
            print("\nAudit abortado; no se escribió el baseline:", file=sys.stderr)
            for failure in failures:
                print(f"  - {failure}", file=sys.stderr)
            return 1
        write_report(report, output)
        try:
            display_output = output.relative_to(REPO)
        except ValueError:
            display_output = output
        print(f"\nBaseline escrito en {display_output}")
        return 0
    finally:
        if old_config is not None:
            runner.teardown_databases(old_config)
        if environment_ready:
            runner.teardown_test_environment()


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scale", type=int, default=200)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    if args.scale < 1:
        parser.error("--scale debe ser mayor que cero")
    output = args.output if args.output.is_absolute() else REPO / args.output
    return run(args.scale, output)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
