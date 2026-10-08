from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        """Importa las señales de cache y de sesión, y registra los system checks."""
        import core.checks  # noqa: F401, pylint: disable=import-outside-toplevel,unused-import
        import core.middleware  # noqa: F401, pylint: disable=import-outside-toplevel,unused-import
        import core.performance.cache_utils  # noqa: F401, pylint: disable=import-outside-toplevel,unused-import
