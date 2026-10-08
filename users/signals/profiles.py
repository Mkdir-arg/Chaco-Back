from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from users.models import Profile


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        profile, _ = Profile.objects.get_or_create(user=instance)
        instance._state.fields_cache["profile"] = profile


# RED-52 (segunda parte, Ola 2) · acá vivía `save_user_profile`, un receiver de
# `post_save(User)` que guardaba el Profile **entero** si lo encontraba en
# `instance._state.fields_cache`. Propagaba un patrón que ningún llamador usa
# —los cuatro que escriben el Profile (`users/middleware.py`,
# `users/services/admin.py`, `users/services/correo.py` e `import_users_from_csv`)
# ya lo guardan explícitos, con `update_fields`— y a cambio producía un *lost
# update* con dos caras:
#
# 1. Cualquier `user.save()` durante un request reescribía la fila con lo leído
#    al empezar, devolviendo `backoffice_session_key` a la sesión vieja: el login
#    nuevo perdía su sesión sin explicación.
# 2. **El login mismo** lo disparaba: `login()` llama a `update_last_login`, que
#    hace `user.save(update_fields=["last_login"])`, y el receiver revertía un
#    `debe_cambiar_contrasena` escrito por otro request.
#
# Las dos están fijadas en `users/tests/test_middleware_profile.py`. El Profile
# se guarda donde se escribe; no hay propagación mágica.
