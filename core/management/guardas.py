"""Guardas compartidas de los comandos de management (OPS-02).

Vive al lado de `core/management/commands/` y no adentro: no es un comando, es la
pieza que varios comandos llaman al principio del `handle()`. El criterio es el
mismo que el de `ComandoSiisBase` (RED-53): **una guarda nueva se escribe en un
solo lugar**, así nadie se entera tarde de que en un comando no existía.

Por qué no `settings.ENVIRONMENT`: en icore (que es DEV) vale `prd`, y QA lo pisa
a `prd` (OPS-12). Esa variable no distingue un ambiente de demo de uno servido, y
una guarda que no distingue es peor que no tener guarda. El disparador es `DEBUG`
—falso en todos los ambientes servidos— con `CHACO_PERMITIR_SEED_DEMO=1` como
escotilla explícita para quien levanta una demo con `DEBUG=False` a propósito.
"""

import os

from django.conf import settings
from django.core.management.base import CommandError

#: La escotilla explícita, para una demo con `DEBUG=False`.
VARIABLE_SEED_DEMO = "CHACO_PERMITIR_SEED_DEMO"

FUERA_DE_UN_AMBIENTE_DE_DEMO = (
    "{comando} siembra datos de prueba con credenciales conocidas: no puede correr en un ambiente servido. "
    "Corre con DJANGO_DEBUG=True, o con {variable}=1 en el entorno si de verdad es una demo."
)


def exigir_entorno_demo(comando):
    """Corta si el comando no está en un ambiente de desarrollo o de demo.

    `comando` es el nombre con el que se invoca (`manage.py <comando>`), para que
    el mensaje diga qué se frenó.
    """
    if settings.DEBUG or os.environ.get(VARIABLE_SEED_DEMO) == "1":
        return
    raise CommandError(FUERA_DE_UN_AMBIENTE_DE_DEMO.format(comando=comando, variable=VARIABLE_SEED_DEMO))
