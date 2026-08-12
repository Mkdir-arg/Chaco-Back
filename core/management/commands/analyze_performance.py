import json

from django.core.management.base import BaseCommand

from config.middlewares.query_counter import QueryCountMiddleware
from core.performance.query_observability import query_observability_report


class Command(BaseCommand):
    help = "Analyze system performance and generate report"

    def add_arguments(self, parser):
        parser.add_argument("--output", choices=["console", "json"], default="console")

    def handle(self, *args, **options):
        session_stats = QueryCountMiddleware.get_session_stats()
        report = query_observability_report(session_stats)
        metrics_available = report["metrics"]["queries"]["source"] == "measured"

        if options["output"] == "json":
            self.stdout.write(json.dumps(report, indent=2))
        else:
            self.stdout.write("=== PERFORMANCE ANALYSIS REPORT ===")
            if not metrics_available:
                self.stdout.write("Query metrics: unavailable (run against instrumented HTTP requests)")
                return

            self.stdout.write(f"Total Queries: {report['total_queries']}")
            self.stdout.write(f"Performance Score: {report['performance_score']}/100")

            if report["n1_detected"]:
                self.stdout.write(
                    self.style.ERROR(f"N+1 detected in {report['n1_affected_requests']} instrumented requests")
                )
            else:
                self.stdout.write(self.style.SUCCESS("No N+1 patterns detected"))

            if report["slow_queries_count"] > 0:
                self.stdout.write(self.style.WARNING(f"Slow Queries: {report['slow_queries_count']}"))

            if report["recommendations"]:
                self.stdout.write("\n=== RECOMMENDATIONS ===")
                for rec in report["recommendations"]:
                    self.stdout.write(f"- {rec['suggestion']} (Count: {rec['count']})")
