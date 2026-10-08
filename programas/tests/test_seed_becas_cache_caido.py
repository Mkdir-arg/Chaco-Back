"""OPS-12 (ronda 2) · Un cache caído no puede impedir que el contenedor arranque.

Desde OPS-12 los dos ambientes servidos usan Redis, no solo `prd`. Eso destapó algo que
antes no se veía: `seed_becas` invalida la clave `programas:becas` con un `cache.delete`
**incondicional**, y el seed corre en el arranque del contenedor. Medido contra
`mariadb:10.11` con `ENVIRONMENT=qa` y un Redis inalcanzable, el bootstrap terminaba en
**exit 1** con `ConnectionError` —CrashLoopBackOff en Kubernetes, y lo mismo el Job de
migración de R-13—: un cache caído dejaba de degradar el servicio y pasaba a impedir el
arranque.

La invalidación es *best-effort* y así se trata ahora. Lo que **no** cambia es
`programa_becas()`: ahí un cache caído tiene que fallar fuerte, porque es un ambiente
sirviendo tráfico con la infraestructura rota y taparlo escondería una caída real.
"""

import logging
from io import StringIO
from unittest.mock import patch

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase

from programas.models import Programa
from programas.services.autorizacion import (
    _PROGRAMA_BECAS_CACHE_KEY,
    PROGRAMA_BECAS_CODIGO,
    invalidar_programa_becas,
    programa_becas,
)

#: RED-80: la invalidación vive en la pieza compartida, así que el aviso del cache caído
#: sale de ahí. ``invalidar_programa_becas`` sigue siendo la fachada que llama el seed.
MODULO = "programas.services.programa_cache"


class _CacheCaido(Exception):
    """Lo que levanta `django_redis` cuando el servidor no contesta."""


class InvalidacionToleranteTests(TestCase):
    """La clave `programas:becas` vive en el cache de proceso (LocMem en la suite), que
    **sobrevive al rollback** de cada test. Este módulo la escribe y la borra, así que
    arranca y termina con el cache limpio: ni depende de lo que haya dejado otro módulo ni
    le deja nada al siguiente (es la fragilidad que TST-02 documenta para otros cinco)."""

    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)

    def test_un_cache_caido_no_corta_la_invalidacion(self):
        with patch.object(cache, "delete", side_effect=_CacheCaido("no se pudo conectar")):
            with self.assertLogs(MODULO, level=logging.WARNING) as log:
                invalidar_programa_becas()  # no levanta

        self.assertTrue(any(_PROGRAMA_BECAS_CACHE_KEY in linea for linea in log.output))
        self.assertTrue(any("_CacheCaido" in linea for linea in log.output))

    def test_con_el_cache_sano_borra_la_clave(self):
        cache.set(_PROGRAMA_BECAS_CACHE_KEY, "lo-viejo", 300)

        invalidar_programa_becas()

        self.assertIsNone(cache.get(_PROGRAMA_BECAS_CACHE_KEY))

    def test_el_seed_de_becas_termina_bien_con_el_cache_caido(self):
        """Es el caso del arranque: `seed_becas` corre en el bootstrap del contenedor."""
        with patch.object(cache, "delete", side_effect=_CacheCaido("no se pudo conectar")):
            with self.assertLogs(MODULO, level=logging.WARNING):
                call_command("seed_becas", stdout=StringIO(), stderr=StringIO())

        self.assertTrue(Programa.objects.filter(codigo=PROGRAMA_BECAS_CODIGO).exists())

    def test_la_lectura_en_runtime_sigue_fallando_fuerte(self):
        """`programa_becas()` no se toca: un cache caído sirviendo tráfico es una caída."""
        call_command("seed_becas", stdout=StringIO(), stderr=StringIO())
        cache.clear()

        with patch.object(cache, "get", side_effect=_CacheCaido("no se pudo conectar")):
            with self.assertRaises(_CacheCaido):
                programa_becas()
