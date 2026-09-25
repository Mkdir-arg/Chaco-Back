"""Settings del banco: ``config.settings`` tal cual —MySQL con las OPTIONS de
producción que ya trae: ``read_timeout`` 10 s, etc.— menos la sesión única del
backoffice, que devuelve 302 al segundo request del mismo usuario y arruina la
medición, y con caché en memoria para que lo medido sea la consulta."""

from config.settings import *  # noqa: F401,F403

MIDDLEWARE = [m for m in MIDDLEWARE if "BackofficeSingleSessionMiddleware" not in m]  # noqa: F405
DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
    "sessions": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
}
SESSION_ENGINE = "django.contrib.sessions.backends.db"
LOGGING = {"version": 1, "disable_existing_loggers": True}
