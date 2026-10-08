from django.apps import AppConfig


class DashboardConfig(AppConfig):
    name = "dashboard"

    def ready(self):
        # RED-51: registra los cuatro receivers que mantienen frescos los contadores de la
        # home —`InscripcionPrograma`, `AlertaCiudadano`, `Ciudadano` y `User`—. Sin este
        # import el módulo no se carga y las señales no existen, que es exactamente el
        # modo de falla silencioso de la ficha.
        from . import signals  # noqa: F401
