"""El parche de gevent no está aplicado, y el entrypoint rechaza pedirlo (RED-45).

`config/wsgi.py:13` mira dos variables de entorno —`GUNICORN_CMD_ARGS` que **contenga**
la palabra `gevent`, o `GUNICORN_WORKER_CLASS=gevent`— y, si alguna aparece, aplica
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
`docker-entrypoint.sh` aborta antes de arrancar.

**La guarda frena solo `gevent` y `eventlet`, no cualquier `--worker-class`.** Este
script es el `ENTRYPOINT` único de la imagen —daphne, gunicorn, el Job de bootstrap y
los cuatro CronJobs pasan por acá—, así que abortar ante un `sync` o un `gthread`
explícito dejaría un ambiente sin arrancar por un valor inocuo. Esos avisan y siguen.

Y cubre las **cuatro** formas de pedirlo, porque mira la palabra y no la bandera:
`--worker-class gevent`, `--worker-class=gevent`, `-k gevent` y `-k=gevent`. Las tres
últimas pasaban en la primera versión de la guarda (ronda 2 de la revisión), y `-k
gevent` / `-k=gevent` **sí** encienden el parche, porque `wsgi.py` busca la palabra en
toda la variable.

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

    def test_las_cuatro_formas_de_pedir_gevent_abortan(self):
        """`-k` es la forma corta de `--worker-class`, y `=` es una variante de las dos.

        La primera versión de la guarda miraba la cadena `worker-class`, así que
        `-k gevent` y `-k=gevent` pasaban con rc=0 y el proceso arrancaba con el parche
        aplicado: el estado exacto que esta ficha viene a cerrar. Ahora la condición es
        la palabra `gevent`, que es **lo mismo que mira `wsgi.py`**.
        """
        for valor in (
            "--worker-class gevent",
            "--worker-class=gevent",
            "-k gevent",
            "-k=gevent",
        ):
            with self.subTest(cmd_args=valor):
                resultado = _correr_entrypoint({"GUNICORN_CMD_ARGS": valor})

                self.assertEqual(resultado.returncode, 1, resultado.stderr)
                self.assertIn("RED-45", resultado.stderr)

    def test_eventlet_aborta_igual_que_gevent(self):
        """`wsgi.py` no lo parchea, pero tiene el mismo problema de hilos y la imagen
        tampoco lo soporta: los workers son gthread."""
        for valor in ("--worker-class eventlet", "-k eventlet"):
            with self.subTest(cmd_args=valor):
                resultado = _correr_entrypoint({"GUNICORN_CMD_ARGS": valor})

                self.assertEqual(resultado.returncode, 1, resultado.stderr)

    def test_un_worker_class_inocuo_avisa_pero_arranca(self):
        """La guarda frena gevent y eventlet, **no** cualquier `--worker-class`.

        Este script es el `ENTRYPOINT` único de la imagen: lo corren daphne, gunicorn,
        el Job de bootstrap y los cuatro CronJobs. Abortar ante un `sync` o un `gthread`
        explícito dejaría un ambiente sin arrancar por un valor que no tiene nada que
        ver con el hallazgo.
        """
        for valor in ("--worker-class sync", "-k gthread"):
            with self.subTest(cmd_args=valor):
                resultado = _correr_entrypoint({"GUNICORN_CMD_ARGS": valor})

                self.assertEqual(resultado.returncode, 0, resultado.stderr)
                self.assertIn("AVISO", resultado.stderr)

    def test_un_cmd_args_sin_worker_class_no_avisa_nada(self):
        """Lo más común en un entorno real (`--timeout`, `--workers`) pasa en silencio:
        un aviso en cada arranque deja de leerse."""
        resultado = _correr_entrypoint({"GUNICORN_CMD_ARGS": "--timeout 90 --workers 4"})

        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertNotIn("AVISO", resultado.stderr)
        self.assertNotIn("RED-45", resultado.stderr)

    def test_gunicorn_worker_class_tambien_aborta(self):
        """La segunda perilla de `wsgi.py`. La ficha solo nombraba la primera."""
        for valor in ("gevent", "eventlet"):
            with self.subTest(worker_class=valor):
                resultado = _correr_entrypoint({"GUNICORN_WORKER_CLASS": valor})

                self.assertEqual(resultado.returncode, 1, resultado.stderr)
                self.assertIn("RED-45", resultado.stderr)

    def test_gunicorn_worker_class_inocuo_avisa_pero_arranca(self):
        resultado = _correr_entrypoint({"GUNICORN_WORKER_CLASS": "sync"})

        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertIn("AVISO", resultado.stderr)

    def test_los_dos_errores_dicen_que_hacer(self):
        """Un mensaje que dice «no se admite» y no dice cómo salir del paso obliga a
        leer el script a las tres de la mañana."""
        for entorno in (
            {"GUNICORN_CMD_ARGS": "-k gevent"},
            {"GUNICORN_WORKER_CLASS": "gevent"},
        ):
            with self.subTest(entorno=entorno):
                resultado = _correr_entrypoint(entorno)

                self.assertIn("Sacar la variable del entorno", resultado.stderr)

    def test_la_guarda_corre_antes_de_tocar_la_base(self):
        """Si quedara después de `run_bootstrap`, en un ambiente con la base caída el
        pod se quedaría esperando para siempre sin llegar nunca a dar el motivo real."""
        script = ENTRYPOINT.read_text(encoding="utf-8")

        self.assertLess(script.index("guard_worker_class\n"), script.index("wait_for_database()"))
