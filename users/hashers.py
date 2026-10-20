"""Hashers propios de contraseñas."""

from django.contrib.auth.hashers import Argon2PasswordHasher


class Argon2Ajustado(Argon2PasswordHasher):
    """Argon2id con los parámetros mínimos que recomienda OWASP.

    Los defaults de Django (``memory_cost=102400``, ``time_cost=2``,
    ``parallelism=8``) costaron ~0,75 s extra por login en el pod. Se hereda
    ``algorithm = "argon2"`` a propósito: el prefijo del hash no cambia y los
    hashes ya guardados se siguen verificando (los parámetros viajan en el hash).
    """

    memory_cost = 19456  # 19 MiB
    time_cost = 2
    parallelism = 1
