# PERF-08: sonda de conexiones con CONN_MAX_AGE bajo ASGI. Uso: python asgi_conn_probe.py <conn_max_age> <n_requests>
# Django puro (no necesita el proyecto). Referencia: 200 requests -> 200 hilos y 200 conexiones, ninguna reutilizada.
"""¿Qué pasa con CONN_MAX_AGE=60 bajo ASGI (daphne)? Django puro, sin el proyecto.

Cuenta cuántas conexiones de base siguen abiertas después de N requests servidas
por ASGIHandler (el mismo camino que daphne), antes y después de gc.collect().
"""

import asyncio
import gc
import os
import sys
import tempfile

import django
from django.conf import settings

MAX_AGE = int(sys.argv[1]) if len(sys.argv) > 1 else 60
N = int(sys.argv[2]) if len(sys.argv) > 2 else 50
db = os.path.join(tempfile.mkdtemp(), "probe.sqlite3")
settings.configure(
    DEBUG=False,
    SECRET_KEY="x",
    ALLOWED_HOSTS=["*"],
    ROOT_URLCONF=__name__,
    DATABASES={
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": db,
            "CONN_MAX_AGE": MAX_AGE,
            "CONN_HEALTH_CHECKS": True,
        }
    },
    INSTALLED_APPS=[],
    MIDDLEWARE=[],
)
django.setup()

import threading  # noqa: E402

from django.core.handlers.asgi import ASGIHandler  # noqa: E402
from django.db import connection  # noqa: E402
from django.db.backends.base.base import BaseDatabaseWrapper  # noqa: E402
from django.http import HttpResponse  # noqa: E402
from django.urls import path  # noqa: E402

hilos = set()


def vista(request):
    with connection.cursor() as c:
        c.execute("SELECT 1")
    hilos.add(threading.get_ident())
    return HttpResponse("ok")


urlpatterns = [path("q/", vista)]


def abiertas():
    return sum(1 for o in gc.get_objects() if isinstance(o, BaseDatabaseWrapper) and o.connection is not None)


async def una(app):
    scope = {"type": "http", "method": "GET", "path": "/q/", "query_string": b"", "headers": [], "server": ("t", 80)}
    enviados = []

    llamadas = [0]
    fin = asyncio.Event()

    async def receive():
        llamadas[0] += 1
        if llamadas[0] == 1:
            return {"type": "http.request", "body": b"", "more_body": False}
        await fin.wait()
        return {"type": "http.disconnect"}

    async def send(msg):
        enviados.append(msg)
        if msg["type"] == "http.response.body" and not msg.get("more_body"):
            fin.set()

    await app(scope, receive, send)
    return enviados[0]["status"]


async def main():
    app = ASGIHandler()
    if os.environ.get("V4_GC_OFF") == "1":
        gc.disable()  # peor caso: el GC generacional no corre entre requests
    estados = [await una(app) for _ in range(N)]
    antes = abiertas()
    gc.enable()
    gc.collect()
    despues = abiertas()
    print(
        f"CONN_MAX_AGE={MAX_AGE} requests={N} status={set(estados)} hilos_distintos={len(hilos)} "
        f"conexiones_abiertas_sin_gc={antes} tras_gc.collect={despues}"
    )


asyncio.run(main())
