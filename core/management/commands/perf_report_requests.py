import math
import re
import statistics
from collections import defaultdict
from datetime import datetime, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

REQUEST_LOG_RE = re.compile(r"\bcore\.requests:\s+\S+\s+(?P<path>\S+).*?\bduration=(?P<duration>\d+)ms\b")
REQUEST_LOG_FILES = ("info.log", "warning.log")


def _percentile_nearest_rank(values, percentile):
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * percentile) - 1)
    return ordered[index]


def _collect_recent_durations(log_dir, days):
    durations_by_path = defaultdict(list)
    # DailyFileHandler crea carpetas con datetime.now(); usar la misma fecha
    # evita desfasajes con TIME_ZONE cuando el host corre en otra zona.
    today = datetime.now().date()
    for offset in range(days):
        daily_dir = log_dir / (today - timedelta(days=offset)).isoformat()
        for filename in REQUEST_LOG_FILES:
            log_path = daily_dir / filename
            if not log_path.is_file():
                continue
            try:
                lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError as exc:
                raise CommandError(f"No se pudo leer {log_path}: {exc}") from exc
            for line in lines:
                match = REQUEST_LOG_RE.search(line)
                if match:
                    durations_by_path[match.group("path")].append(int(match.group("duration")))
    return durations_by_path


class Command(BaseCommand):
    help = "Resume count, p50, p95 y máximo de requests recientes agrupadas por path."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7, help="Cantidad de días calendario a incluir (default: 7).")

    def handle(self, *args, **options):
        days = options["days"]
        if days < 1:
            raise CommandError("--days debe ser mayor que cero")

        durations_by_path = _collect_recent_durations(settings.LOG_DIR, days)
        if not durations_by_path:
            self.stdout.write(f"No se encontraron requests en los últimos {days} días.")
            return

        rows = []
        for path, durations in durations_by_path.items():
            rows.append(
                {
                    "path": path,
                    "count": len(durations),
                    "p50": statistics.median(durations),
                    "p95": _percentile_nearest_rank(durations, 0.95),
                    "max": max(durations),
                }
            )
        rows.sort(key=lambda row: (-row["p95"], -row["max"], -row["count"], row["path"]))

        self.stdout.write(f"Top 20 paths más lentos de los últimos {days} días (ms)")
        self.stdout.write(f"{'Path':<60} {'Count':>7} {'p50':>10} {'p95':>10} {'Max':>10}")
        for row in rows[:20]:
            self.stdout.write(
                f"{row['path']:<60} {row['count']:>7} {row['p50']:>10.1f} {row['p95']:>10} {row['max']:>10}"
            )
