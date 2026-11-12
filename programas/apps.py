from django.apps import AppConfig


class ProgramasConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "programas"
    verbose_name = "Programas"

    def ready(self):
        # `signals`: DAT-03, `Formulario.dni_titular` sigue al DNI del ciudadano;
        # RED-80, el cache de `Programa`; #339, las bajas del catálogo en los diseños.
        # `vencimientos`: las reglas de vencimiento por fecha (las corre
        # `manage.py procesar_vencimientos`); `vencimientos_emergencia`: las de la mesa de
        # Emergencia, después de las de Becas. `alertas_dispositivos`: las reglas de aviso
        # del detalle del dispositivo, en el mismo registro (las lee P4, no el cron).
        # `avisos_emergencia`: las reglas de aviso del tablero de Emergencia (las lee E1).
        # `emergencia_alojar`: el receptor de `estadia_egresada` que marca al integrante y cierra
        # el caso de Emergencia cuando egresa el último (RN-3.12).
        from programas import signals  # noqa: F401
        from programas.services import (  # noqa: F401
            alertas_dispositivos,
            avisos_emergencia,
            vencimientos,
            vencimientos_emergencia,
        )
        from programas.services.emergencia_alojar import conectar_receptores

        conectar_receptores()
