from django.shortcuts import redirect


class TimestampedSuccessUrlMixin:
    success_url = None

    def redirect_with_timestamp(self):
        return redirect(f"{self.get_success_url()}?t={self._timestamp_value()}")

    def _timestamp_value(self):
        import time

        return int(time.time())
