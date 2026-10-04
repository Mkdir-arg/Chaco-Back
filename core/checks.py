"""System checks propios del entorno (RED-61).

``settings.py`` lee ~90 variables de entorno y la única validada era
``DJANGO_SECRET_KEY``. Las dos de acá son las que, mal puestas, no se notan:
una integración **sin baja** que apunta al ambiente equivocado responde 200 y
el caso queda «informado» sin que el organismo reciba nada.

Corren con ``manage.py check --deploy`` (``deploy=True``): el CI, y la etapa
``verify`` del pipeline de ECOM cuando exista. **No** frenan el arranque del
contenedor; para eso habría que llamarlos desde el entrypoint.

El disparador de producción es ``DATANACH_ES_PRODUCCION``, una variable
explícita que ECOM setea únicamente en PRD, y no ``settings.ENVIRONMENT``: QA
—el testing de ECOM, que usa el SIIS de desarrollo legítimamente— e icore
también valen ``prd``.
"""

import os
from urllib.parse import urlparse

from django.conf import settings
from django.core.checks import Error, Tags, register
from django.core.checks import Warning as CheckWarning

#: Dominio del SIIS de **desarrollo** de ECOM.
DOMINIO_SIIS_DESARROLLO = "ecomdev.ar"

#: Variable que ECOM setea solo en producción.
VARIABLE_PRODUCCION = "DATANACH_ES_PRODUCCION"


def es_produccion():
    return os.environ.get(VARIABLE_PRODUCCION, "").strip() == "1"


def es_host_de_desarrollo(url):
    host = (urlparse(url).hostname or "").lower()
    return host == DOMINIO_SIIS_DESARROLLO or host.endswith(f".{DOMINIO_SIIS_DESARROLLO}")


@register(Tags.compatibility, deploy=True)
def entorno_de_integraciones(app_configs, **kwargs):
    """Las integraciones externas apuntan al ambiente que corresponde."""
    if settings.DEBUG:
        return []

    mensajes = []
    url = (getattr(settings, "SIIS_API_URL", "") or "").strip()
    if not url:
        mensajes.append(
            Error(
                "SIIS_API_URL está vacía: las altas de beneficiarios no van a ninguna parte.",
                hint=(
                    "Definí SIIS_API_URL en el entorno (ver .env.local.example). Ya no tiene default: "
                    "el que había apuntaba al SIIS de desarrollo, que responde 200 y deja el caso "
                    "como informado sin que el organismo reciba nada."
                ),
                id="core.E001",
            )
        )
    elif es_produccion() and es_host_de_desarrollo(url):
        mensajes.append(
            Error(
                f"SIIS_API_URL apunta al SIIS de desarrollo ({url}) con {VARIABLE_PRODUCCION}=1.",
                hint=(
                    "En producción SIIS_API_URL tiene que ser el host productivo del organismo. "
                    "La integración no tiene baja: un alta mandada al ambiente equivocado no se deshace."
                ),
                id="core.E002",
            )
        )

    if getattr(settings, "RENAPER_TEST_MODE", False):
        mensajes.append(
            CheckWarning(
                "RENAPER_TEST_MODE=True con DEBUG=False: la identidad se resuelve contra datos de prueba.",
                hint="Sacá RENAPER_TEST_MODE del entorno salvo que sea un ambiente de pruebas a propósito.",
                id="core.W001",
            )
        )
    return mensajes
