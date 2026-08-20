from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        """Importa las señales de cache cuando la app está lista."""
        import core.performance.cache_utils  # noqa: F401, pylint: disable=import-outside-toplevel,unused-import
