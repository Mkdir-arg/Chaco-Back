"""SEC-26 · cambiar la contraseña revoca el token de la app de campo.

`rest_framework.authtoken` emite un token **sin vencimiento** y
`Token.objects.get_or_create` devuelve siempre el mismo: un token filtrado del
teléfono (una copia de seguridad, un celular prestado, un `adb backup`) servía
para siempre, y cambiar la clave no lo tocaba. Medido: el token viejo seguía
contestando 200 en `/api/becas/relevamientos/` después de un `set_password`.

El disparador es ``AbstractBaseUser._password``, que Django deja puesto entre
``set_password()`` y el final de ``save()`` —es lo mismo que usa para llamar a
``password_changed``—. Por eso el receiver **no consulta nada** en el 99 % de los
`User.save()` (un `update_last_login`, una edición de nombre, un alta masiva):
solo mira un atributo en memoria. Es la única forma de cubrir los cuatro caminos
que cambian una clave —ABM, credenciales provisorias, cambio obligatorio y link
de reseteo— sin depender de que cada uno se acuerde de llamar a una función.
"""

from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=User)
def revocar_tokens_al_cambiar_la_clave(sender, instance, created=False, **kwargs):
    # Un alta trae `_password` puesto por `create_user` y no puede tener tokens:
    # saltearla deja el alta masiva por CSV en las mismas consultas de siempre.
    if created or getattr(instance, "_password", None) is None:
        return
    # Import tardío: `authtoken` es una app de DRF y este módulo se importa en el
    # `ready()` de `users`.
    from rest_framework.authtoken.models import Token

    Token.objects.filter(user=instance).delete()
