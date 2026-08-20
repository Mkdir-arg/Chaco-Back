from django.test import SimpleTestCase

from scripts.check_perf_timing import classify_ratio


class PerfTimingGuardTests(SimpleTestCase):
    def test_thresholds_are_strictly_greater_than_configured_multipliers(self):
        self.assertEqual(classify_ratio(1.5, 1.5, 3.0), "ok")
        self.assertEqual(classify_ratio(1.51, 1.5, 3.0), "warning")
        self.assertEqual(classify_ratio(3.0, 1.5, 3.0), "warning")
        self.assertEqual(classify_ratio(3.01, 1.5, 3.0), "failure")
