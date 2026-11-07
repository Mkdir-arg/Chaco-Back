"""Catálogo geográfico para las preguntas de Provincia y Localidad (Cambio 418).

El catálogo de ``core`` es nacional (24 provincias, 8779 localidades) y no entra
en las opciones de una pregunta: viaja una sola vez, en la clave de nivel
superior ``catalogos`` de la definición del formulario. Ni la foto que se guarda
por caso ni la huella lo incluyen.

Se resuelve **una vez por definición servida** y se cachea en el cache de Django
(Redis en prd y qa, LocMem en dev). El catálogo cambia solo por el ABM de
``/configuracion/localidades/`` o por ``load_initial_data``: no se invalida a
mano, vence por tiempo (``CATALOGO_TTL``) y la clave lleva una versión para
descartar de un golpe un cambio de forma.
"""

from django.core.cache import cache

from core.models import Localidad, Provincia

CATALOGO_VERSION = 1
CATALOGO_TTL = 60 * 60
_CLAVE_CACHE = f"becas:catalogo-geografico:v{CATALOGO_VERSION}"


def _resolver():
    provincias = list(Provincia.objects.order_by("nombre", "pk").values_list("nombre", flat=True))
    por_provincia = {}
    vistos = {}
    filas = Localidad.objects.filter(municipio__provincia__isnull=False).order_by(
        "municipio__provincia__nombre", "nombre", "pk"
    )
    for provincia, nombre in filas.values_list("municipio__provincia__nombre", "nombre"):
        # El nombre se repite entre municipios de la misma provincia (5 «San Antonio» en
        # Chaco) y se guarda el texto: una sola vez alcanza.
        ya = vistos.setdefault(provincia, set())
        if nombre in ya:
            continue
        ya.add(nombre)
        por_provincia.setdefault(provincia, []).append(nombre)
    return {"provincias": list(dict.fromkeys(provincias)), "localidades": por_provincia}


def catalogos_geograficos():
    """``{"provincias": [nombre…], "localidades": {provincia: [nombre…]}}``."""
    datos = cache.get(_CLAVE_CACHE)
    if datos is None:
        datos = _resolver()
        cache.set(_CLAVE_CACHE, datos, CATALOGO_TTL)
    return datos


def localidad_pertenece(provincia, localidad, catalogos=None):
    """¿``localidad`` es una localidad de ``provincia`` según el catálogo?"""
    catalogos = catalogos if catalogos is not None else catalogos_geograficos()
    return localidad in (catalogos.get("localidades") or {}).get(provincia, ())


def par_coherente_en_catalogo(provincia, localidad):
    """Lo mismo contra la base viva (sin cache): para observar una carga por API."""
    return Localidad.objects.filter(municipio__provincia__nombre=provincia, nombre=localidad).exists()
