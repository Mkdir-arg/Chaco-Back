from django.apps import AppConfig


class ProgramasConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "programas"
    verbose_name = "Programas"

    def ready(self):
        # `signals`: DAT-03, `Formulario.dni_titular` sigue al DNI del ciudadano.
        # `vencimientos`: las reglas de vencimiento por fecha (las corre
        # `manage.py procesar_vencimientos`). `alertas_dispositivos`: las reglas de aviso
        # del detalle del dispositivo, en el mismo registro (las lee P4, no el cron).
        from programas import signals  # noqa: F401
        from programas.services import alertas_dispositivos, vencimientos  # noqa: F401
