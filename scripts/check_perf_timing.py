#!/usr/bin/env python
"""Compara el tiempo del smoke de performance contra la referencia commiteada."""

import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_BUDGETS = REPO / "scripts" / "perf_budgets.json"


def classify_ratio(ratio, warning_multiplier, failure_multiplier):
    if ratio > failure_multiplier:
        return "failure"
    if ratio > warning_multiplier:
        return "warning"
    return "ok"


def _append_step_summary(message):
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with Path(summary_path).open("a", encoding="utf-8") as summary:
            summary.write(message + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", type=Path, required=True, help="JSON generado por el test de performance.")
    parser.add_argument("--budgets", type=Path, default=DEFAULT_BUDGETS)
    args = parser.parse_args(argv)

    try:
        result = json.loads(args.result.read_text(encoding="utf-8"))
        config = json.loads(args.budgets.read_text(encoding="utf-8"))
        timing = config["_meta"]["timing"]
        measured_ms = float(result["total_duration_ms"])
        reference_ms = float(timing["reference_total_ms"])
        warning_multiplier = float(timing["warning_multiplier"])
        failure_multiplier = float(timing["failure_multiplier"])
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"No se pudo evaluar el tiempo del smoke: {exc}", file=sys.stderr)
        return 2

    if reference_ms <= 0:
        print("reference_total_ms debe ser mayor que cero", file=sys.stderr)
        return 2

    ratio = measured_ms / reference_ms
    status = classify_ratio(ratio, warning_multiplier, failure_multiplier)
    message = (
        f"Performance smoke: {measured_ms:.2f} ms vs referencia {reference_ms:.2f} ms "
        f"({ratio:.2f}x; warning >{warning_multiplier:g}x, failure >{failure_multiplier:g}x)."
    )
    print(message)
    _append_step_summary(f"### Performance smoke\n\n{message}")

    if status == "failure":
        print(f"::error title=Performance smoke degradado::{message}")
        return 1
    if status == "warning":
        print(f"::warning title=Performance smoke degradado::{message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
