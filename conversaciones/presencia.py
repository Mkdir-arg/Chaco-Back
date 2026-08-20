"""Registro de presencia de usuarios logueados para la asignación automática.

Reemplaza el escaneo/decodificación de TODAS las filas de django_session por
conversación creada (O(sesiones del sitio) en el request path público). Además,
en prd las sesiones viven en el cache (SESSION_ENGINE=cache), por lo que la
tabla django_session está vacía y el escaneo no encontraba a nadie.

El registro es un dict {user_id: expiry_epoch} en una única clave de cache,
alimentado por las señales user_logged_in / user_logged_out. Como fallback
(usuarios logueados antes de un deploy, entornos con sesiones en DB) se cae al
escaneo de django_session, cacheado 60 s.
"""

import time

from django.conf import settings
from django.core.cache import cache

PRESENCE_KEY = "conversaciones:operadores_logueados"
FALLBACK_KEY = "conversaciones:usuarios_logueados_db"
_TTL = getattr(settings, "SESSION_COOKIE_AGE", 86400)


def _vigentes(entradas):
    ahora = time.time()
    return {uid: exp for uid, exp in (entradas or {}).items() if exp > ahora}


def registrar_login(user_id):
    entradas = _vigentes(cache.get(PRESENCE_KEY))
    entradas[int(user_id)] = time.time() + _TTL
    cache.set(PRESENCE_KEY, entradas, _TTL)


def registrar_logout(user_id):
    entradas = _vigentes(cache.get(PRESENCE_KEY))
    entradas.pop(int(user_id), None)
    cache.set(PRESENCE_KEY, entradas, _TTL)


def _usuarios_logueados_desde_db():
    """Fallback: escaneo de django_session, cacheado para no decodificar por request."""

    def calcular():
        from django.contrib.sessions.models import Session
        from django.utils import timezone

        ids = set()
        for sesion in Session.objects.filter(expire_date__gte=timezone.now()):
            user_id = sesion.get_decoded().get("_auth_user_id")
            if user_id:
                ids.add(int(user_id))
        return list(ids)

    return cache.get_or_set(FALLBACK_KEY, calcular, 60)


def usuarios_logueados():
    entradas = _vigentes(cache.get(PRESENCE_KEY))
    if entradas:
        return list(entradas)
    return _usuarios_logueados_desde_db()
