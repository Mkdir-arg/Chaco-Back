from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

from ..presencia import registrar_login, registrar_logout


@receiver(user_logged_in)
def marcar_usuario_presente(sender, request, user, **kwargs):
    registrar_login(user.id)


@receiver(user_logged_out)
def marcar_usuario_ausente(sender, request, user, **kwargs):
    if user is not None:
        registrar_logout(user.id)
