from django.apps import AppConfig


class ProgramasConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "programas"
    verbose_name = "Programas"

    def ready(self):
        # Registra las reglas de vencimiento por fecha (las corre
        # `manage.py procesar_vencimientos`).
        from programas.services import vencimientos  # noqa: F401
