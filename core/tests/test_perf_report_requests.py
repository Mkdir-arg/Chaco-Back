from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.test import SimpleTestCase, override_settings


class PerfReportRequestsTests(SimpleTestCase):
    def test_reports_count_and_percentiles_by_path_from_recent_logs(self):
        with TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)
            today = datetime.now().date()
            daily_dir = log_dir / today.isoformat()
            daily_dir.mkdir()
            (daily_dir / "info.log").write_text(
                "\n".join(
                    [
                        "[2026-01-01] middleware INFO core.requests: GET /inicio/ user=a ip=- status=200 duration=100ms",
                        "[2026-01-01] middleware INFO core.requests: GET /inicio/ user=b ip=- status=200 duration=300ms",
                        "línea ajena al logger de requests",
                    ]
                ),
                encoding="utf-8",
            )
            (daily_dir / "warning.log").write_text(
                "[2026-01-01] middleware WARNING core.requests: GET /lenta/ user=a ip=- status=200 duration=5000ms\n",
                encoding="utf-8",
            )
            old_dir = log_dir / (today - timedelta(days=8)).isoformat()
            old_dir.mkdir()
            (old_dir / "info.log").write_text(
                "[2026-01-01] middleware INFO core.requests: GET /vieja/ user=a ip=- status=200 duration=9000ms\n",
                encoding="utf-8",
            )

            output = StringIO()
            with override_settings(LOG_DIR=log_dir):
                call_command("perf_report_requests", days=7, stdout=output)

        report = output.getvalue()
        self.assertRegex(report, r"/lenta/\s+1\s+5000\.0\s+5000\s+5000")
        self.assertRegex(report, r"/inicio/\s+2\s+200\.0\s+300\s+300")
        self.assertNotIn("/vieja/", report)
