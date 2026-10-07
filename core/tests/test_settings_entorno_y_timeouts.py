"""OPS-05 y OPS-12 · Los dos valores del entorno que se derivaban mal.

**OPS-05** — `read_timeout` y `write_timeout` estaban clavados en 10 s. Es el límite
acordado con ECOM para el tráfico (Cambio 91) y ahí se queda, pero también se lo comía el
`migrate`: en MySQL/MariaDB no hay DDL transaccional, así que un `ALTER` que espera el
metadata lock más de 10 s devuelve un 2013 al cliente y **se aplica igual** en el
servidor. El resultado es el peor de los dos mundos: esquema adelantado, migración sin
fila en `django_migrations` y un deploy que no se arregla reintentando. D-O05: se sube,
solo para `migrate` (lo hace `docker-entrypoint.sh`, no el entorno del server).

**OPS-12** — `config/settings_production.py` reasignaba `ENVIRONMENT = "prd"` **después**
de que `settings.py` derivó todo de la variable real. En QA (testing de ECOM, que corre
con `ENVIRONMENT=qa` y el módulo endurecido) eso dejaba `settings.ENVIRONMENT == "prd"`
mientras el cache y el channel layer eran locales al proceso: el throttle contaba por
worker, las invalidaciones limpiaban un worker de varios y `diagnosticar_siis` /
`diagnosticar_correo` informaban mal. QA deja de reproducir mal el cache de PRD y pasa a
usar Redis, que ya tiene por Channels.

Los casos corren el arranque de Django en un **subproceso**: `settings.py` lee el entorno
una sola vez, al importarse, y lo que se verifica es justamente esa derivación. Un
`override_settings` no probaría nada.
"""

import json
import os
import subprocess
import sys
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase, override_settings

from core.checks import entorno_declarado

GUION = """
import json

import django

django.setup()
from django.conf import settings

print(
    "<<<JSON>>>"
    + json.dumps(
        {
            "environment": settings.ENVIRONMENT,
            "read_timeout": settings.DATABASES["default"]["OPTIONS"].get("read_timeout"),
            "write_timeout": settings.DATABASES["default"]["OPTIONS"].get("write_timeout"),
            "cache": settings.CACHES["default"]["BACKEND"],
            "sessions": settings.CACHES["sessions"]["BACKEND"],
            "channels": settings.CHANNEL_LAYERS["default"]["BACKEND"],
        }
    )
)
"""

#: Lo que el subproceso no puede heredar: con `PYTEST_RUNNING` las `DATABASES` se
#: reemplazan por SQLite en memoria y las `OPTIONS` de producción desaparecen.
A_LIMPIAR = ("PYTEST_RUNNING", "DJANGO_SYNCDB_PROJECT_APPS", "DJANGO_TEST_MOTOR", "DB_READ_TIMEOUT", "DB_WRITE_TIMEOUT")


def arrancar_django(**entorno):
    ambiente = {clave: valor for clave, valor in os.environ.items() if clave not in A_LIMPIAR}
    ambiente.update(
        {
            "DJANGO_SECRET_KEY": "test-key",
            "DJANGO_SETTINGS_MODULE": "config.settings",
            "DJANGO_ALLOWED_HOSTS": "ejemplo.ar",
            "PYTHONIOENCODING": "utf-8",
        }
    )
    ambiente.update({clave: str(valor) for clave, valor in entorno.items()})

    corrida = subprocess.run(
        [sys.executable, "-c", GUION],
        cwd=str(settings.BASE_DIR),
        env=ambiente,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if corrida.returncode != 0:
        raise AssertionError(f"el arranque falló:\n{corrida.stdout}\n{corrida.stderr}")
    return json.loads(corrida.stdout.rsplit("<<<JSON>>>", 1)[1].strip())


class TimeoutsDeLaConexionTests(SimpleTestCase):
    """OPS-05."""

    def test_el_default_sigue_siendo_el_limite_acordado_con_ecom(self):
        """10 s para el tráfico (Cambio 91). Subirlo por entorno es una decisión, no un olvido."""
        valores = arrancar_django(ENVIRONMENT="prd")

        self.assertEqual(valores["read_timeout"], 10)
        self.assertEqual(valores["write_timeout"], 10)

    def test_db_read_timeout_levanta_el_limite_para_el_migrate(self):
        valores = arrancar_django(ENVIRONMENT="prd", DB_READ_TIMEOUT="600", DB_WRITE_TIMEOUT="600")

        self.assertEqual(valores["read_timeout"], 600)
        self.assertEqual(valores["write_timeout"], 600)


class EntornoDeclaradoTests(SimpleTestCase):
    """OPS-12."""

    def test_qa_con_el_modulo_endurecido_sigue_siendo_qa(self):
        valores = arrancar_django(ENVIRONMENT="qa", DJANGO_SETTINGS_MODULE="config.settings_production")

        self.assertEqual(valores["environment"], "qa")

    def test_qa_usa_redis_para_cache_sesiones_y_websockets(self):
        """Era LocMem + InMemoryChannelLayer: el throttle contaba por worker y las
        invalidaciones de cache limpiaban uno solo de varios."""
        valores = arrancar_django(ENVIRONMENT="qa", DJANGO_SETTINGS_MODULE="config.settings_production")

        self.assertIn("django_redis", valores["cache"])
        self.assertIn("django_redis", valores["sessions"])
        self.assertIn("RedisChannelLayer", valores["channels"])

    def test_prd_no_cambia(self):
        valores = arrancar_django(ENVIRONMENT="prd", DJANGO_SETTINGS_MODULE="config.settings_production")

        self.assertEqual(valores["environment"], "prd")
        self.assertIn("django_redis", valores["cache"])
        self.assertIn("RedisChannelLayer", valores["channels"])

    def test_dev_sigue_sin_redis(self):
        """El dev local no necesita un Redis para levantar."""
        valores = arrancar_django(ENVIRONMENT="dev")

        self.assertIn("locmem", valores["cache"].lower())
        self.assertIn("InMemoryChannelLayer", valores["channels"])

    def test_use_redis_cache_lo_enciende_a_mano(self):
        """Escotilla para reproducir el cache de PRD en un dev, sin tocar ENVIRONMENT."""
        valores = arrancar_django(ENVIRONMENT="dev", USE_REDIS_CACHE="True")

        self.assertIn("django_redis", valores["cache"])


class EntornoDeclaradoCheckTests(SimpleTestCase):
    """`core.W002`: sin la reasignación, un ambiente servido sin `ENVIRONMENT` se nota.

    Antes el olvido quedaba tapado —`settings_production` ponía «prd» igual—; ahora el
    ambiente arranca con los defaults de desarrollo (cache y channel layer locales al
    proceso) mientras sirve tráfico real, y eso no se ve mirando una pantalla.
    """

    def _correr(self, modulo, entorno):
        with patch.dict(os.environ, {"DJANGO_SETTINGS_MODULE": modulo}):
            with override_settings(ENVIRONMENT=entorno):
                return entorno_declarado(app_configs=None)

    def test_el_modulo_endurecido_con_entorno_de_desarrollo_avisa(self):
        mensajes = self._correr("config.settings_production", "dev")

        self.assertEqual([m.id for m in mensajes], ["core.W002"])

    def test_qa_y_prd_no_avisan(self):
        for entorno in ("qa", "prd"):
            with self.subTest(entorno=entorno):
                self.assertEqual(self._correr("config.settings_production", entorno), [])

    def test_el_settings_de_desarrollo_no_avisa(self):
        """Un dev local corre con `config.settings` y `ENVIRONMENT=dev`: es lo normal."""
        self.assertEqual(self._correr("config.settings", "dev"), [])
