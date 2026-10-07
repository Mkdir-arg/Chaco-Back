"""El parche de gevent no está aplicado, y no hay forma de pedirlo (RED-45).

`config/wsgi.py` mira dos variables de entorno —`GUNICORN_CMD_ARGS` con la palabra
`gevent`, o `GUNICORN_WORKER_CLASS=gevent`— y, si alguna aparece, aplica
`config/gevent_patch.py`. Ese parche pisa `BaseDatabaseWrapper.validate_thread_sharing`
con una función que **no hace nada**.

Lo que queda entonces es: gevent de verdad, sin `monkey.patch_all()` (mysqlclient y
requests siguen bloqueando, así que ni siquiera se gana concurrencia) y sin el único
chequeo de Django que impide que dos greenlets compartan una conexión a la base. El
síntoma sería una respuesta con los datos de otra persona, intermitente, sin error ni
log. En una aplicación que muestra legajos de ciudadanos, eso es lo peor que puede
pasar.

Hoy nadie lo activa —por eso la severidad bajó a MEDIA—, pero la perilla está y es lo
primero que se prueba cuando aparecen 504: `GUNICORN_CMD_ARGS="--worker-class gevent"`.
`docker-entrypoint.sh` ahora aborta antes de arrancar.

**D-RED-08:** la opción de workers gevent no se conserva. El borrado de
`config/gevent_patch.py`, de las líneas de `wsgi.py` y de `gevent`/`greenlet` de
`requirements.txt` es OPS-13 (Ola 7); cuando pase, `test_el_parche_ya_no_existe` deja
de saltearse.
"""

import os
import shutil
import subprocess
import unittest
from pathlib import Path

from django.db.backends.base.base import BaseDatabaseWrapper
from django.test import SimpleTestCase

RAIZ = Path(__file__).resolve().parents[2]
ENTRYPOINT = RAIZ / "docker-entrypoint.sh"


def _correr_entrypoint(entorno_extra):
    """Corre el entrypoint con un comando inocuo (`true`).

    Con argumentos, el script avisa y hace `exec "$@"`: no toca la base, no migra y no
    siembra. La guarda de RED-45 corre **antes** de esa rama, así que este es el camino
    más corto para ejercitarla de verdad en vez de leer el texto del script.
    """
    entorno = {**os.environ, **entorno_extra}
    entorno.pop("GUNICORN_CMD_ARGS", None)
    entorno.pop("GUNICORN_WORKER_CLASS", None)
    entorno.update(entorno_extra)
    return subprocess.run(
        ["sh", str(ENTRYPOINT), "true"],
        cwd=RAIZ,
        env=entorno,
        capture_output=True,
        text=True,
    )


class GeventTests(SimpleTestCase):
    def test_nadie_piso_validate_thread_sharing(self):
        """La aserción que importa: el chequeo de hilos sigue siendo el de Django.

        Pasa hoy. Se pone rojo el día que alguien aplique el parche —por la variable de
        entorno o importando `apply_gevent_patches` desde otro lado—, que es
        exactamente el cambio que nadie revisaría dos veces.
        """
        self.assertTrue(
            BaseDatabaseWrapper.validate_thread_sharing.__module__.startswith("django."),
            "`validate_thread_sharing` está pisado por "
            f"{BaseDatabaseWrapper.validate_thread_sharing.__module__}: dos greenlets "
            "pueden compartir conexión y devolver datos de otra request.",
        )

    def test_el_parche_sigue_siendo_la_unica_forma_de_pisarlo(self):
        """Control del andamio: el test de arriba solo vale si el parche existe y hace
        lo que dice. Si `gevent_patch.py` dejara de tocar `validate_thread_sharing`, el
        riesgo se habría ido por otro lado y la ficha tendría que decirlo."""
        fuente = (RAIZ / "config" / "gevent_patch.py").read_text(encoding="utf-8")

        self.assertIn("BaseDatabaseWrapper.validate_thread_sharing = patched_validate", fuente)

    def test_wsgi_sigue_teniendo_las_dos_perillas(self):
        """Lo que la guarda del entrypoint tiene que cubrir. Si `wsgi.py` suma una
        tercera forma de encender el parche, este test queda desactualizado y hay que
        agregarla también allá."""
        fuente = (RAIZ / "config" / "wsgi.py").read_text(encoding="utf-8")

        self.assertIn('os.environ.get("GUNICORN_CMD_ARGS", "")', fuente)
        self.assertIn('os.environ.get("GUNICORN_WORKER_CLASS")', fuente)

    @unittest.skipIf(
        (RAIZ / "config" / "gevent_patch.py").exists(),
        "OPS-13 (Ola 7) todavía no borró el parche",
    )
    def test_el_parche_ya_no_existe(self):
        self.assertFalse((RAIZ / "config" / "gevent_patch.py").exists())


@unittest.skipUnless(shutil.which("sh"), "sin shell POSIX (el CI corre en Linux)")
class EntrypointTests(SimpleTestCase):
    """La guarda se ejecuta de verdad, no se lee del texto del script."""

    def test_sin_las_variables_el_arranque_sigue(self):
        """Control del andamio: si el script abortara siempre, los dos tests de abajo
        pasarían sin medir nada."""
        resultado = _correr_entrypoint({})

        self.assertEqual(resultado.returncode, 0, resultado.stderr)

    def test_gunicorn_cmd_args_con_worker_class_aborta(self):
        resultado = _correr_entrypoint({"GUNICORN_CMD_ARGS": "--worker-class gevent"})

        self.assertEqual(resultado.returncode, 1)
        self.assertIn("RED-45", resultado.stderr)

    def test_cualquier_worker_class_aborta_no_solo_gevent(self):
        """La guarda mira `worker-class`, no `gevent`: `--worker-class eventlet` tiene
        el mismo problema de hilos y tampoco está soportado por la imagen."""
        resultado = _correr_entrypoint({"GUNICORN_CMD_ARGS": "--worker-class eventlet"})

        self.assertEqual(resultado.returncode, 1)

    def test_gunicorn_worker_class_tambien_aborta(self):
        """La segunda perilla de `wsgi.py`. La ficha solo nombraba la primera."""
        resultado = _correr_entrypoint({"GUNICORN_WORKER_CLASS": "gevent"})

        self.assertEqual(resultado.returncode, 1)
        self.assertIn("RED-45", resultado.stderr)

    def test_la_guarda_corre_antes_de_tocar_la_base(self):
        """Si quedara después de `run_bootstrap`, en un ambiente con la base caída el
        pod se quedaría esperando para siempre sin llegar nunca a dar el motivo real."""
        script = ENTRYPOINT.read_text(encoding="utf-8")

        self.assertLess(script.index("guard_worker_class\n"), script.index("wait_for_database()"))
