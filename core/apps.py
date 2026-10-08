from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        """Importa las señales de sesión y registra los system checks.

        RED-51: `core.performance.cache_utils` ya no se importa acá por su efecto
        colateral —dejó de tener receivers; los de los contadores de la home viven en
        `dashboard/signals/cache.py`, que registra `DashboardConfig.ready()`—.
        """
        import core.checks  # noqa: F401, pylint: disable=import-outside-toplevel,unused-import
        import core.middleware  # noqa: F401, pylint: disable=import-outside-toplevel,unused-import
