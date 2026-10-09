from django.apps import AppConfig


class ConversacionesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "conversaciones"

    def ready(self):
        # `signals.alertas` cuelga de `Conversacion` y `Mensaje`, los dos modelos
        # de esta app: con el chat apagado (G1-01 fase 2) nadie los crea, así que
        # queda registrado sin disparar nunca. Acá vive, desde RED-13,
        # `alerta_mensaje_ciudadano`, que estaba en `legajos/signals/`.
        import conversaciones.signals  # noqa: F401
        import conversaciones.signals.alertas  # noqa: F401

        # `signals.presencia` **no** se registra: enganchaba `user_logged_in` y
        # `user_logged_out`, señales de `django.contrib.auth` que disparan en
        # todo login del backoffice, para mantener en cache un registro que solo
        # consumía la asignación automática de conversaciones. Con la app apagada
        # era un round-trip a Redis por login para nadie. El módulo queda en el
        # repo, como las vistas y los templates: si el chat vuelve, vuelve su línea.

    verbose_name = "Conversaciones"
