"""
Utilidades básicas para gestión de cache.
"""

import logging

from django.core.cache import cache
from django.db import transaction

logger = logging.getLogger("django")


def invalidate_cache_keys(*cache_keys):
    """Invalida múltiples claves de cache."""
    try:
        for key in cache_keys:
            cache.delete(key)
    except Exception as e:
        logger.warning(f"No se pudo invalidar cache: {e}")


def invalidar_tras_commit(claves):
    """Un solo ``delete_many`` deduplicado, **después** del commit (PERF-16).

    Dos cosas que el ``cache.delete`` por clave dentro de la señal hacía mal. Una,
    el volumen: cada ``Ciudadano.save()`` mandaba cuatro ``DEL`` a Redis —uno de
    ellos repetido—, y el cruce del padrón llegó a medir **26.668** para 6.667
    casos. Dos, el momento: borraba aunque la transacción terminara en rollback, y
    peor, dejaba que el recálculo de otro request volviera a cachear el valor
    **viejo** antes de que el nuevo estuviera commiteado.

    Fuera de una transacción ``on_commit`` corre en el acto, así que el camino
    normal no cambia de comportamiento.
    """
    claves = list(dict.fromkeys(c for c in claves if c))
    if not claves:
        return

    def _borrar():
        try:
            cache.delete_many(claves)
        except Exception as e:  # noqa: BLE001 — invalidar nunca puede tumbar la escritura
            logger.warning(f"No se pudo invalidar cache: {e}")

    transaction.on_commit(_borrar)


def invalidar_ciudadanos_tras_commit(ids, claves_extra=()):
    """Invalidación de una escritura **en lote** de ciudadanos (PERF-04).

    ``bulk_update`` no dispara ``post_save``, así que el cruce del padrón avisa por
    acá con las mismas claves que la señal, en un solo ``DEL`` para todos los casos.

    ``claves_extra`` las pone quien llama —en la práctica, los contadores de la home
    cuando el total pudo cambiar—. Antes se llamaban desde acá con una constante local
    (RED-51): eso obligaba a este módulo, que es plomería de `core`, a conocer las claves
    del dashboard, y el import de vuelta cerraba un ciclo que el ratchet de RED-79 marca.
    """
    invalidar_tras_commit([f"ciudadano_{pk}" for pk in ids] + list(claves_extra))


# RED-51: acá vivían la segunda `invalidate_dashboard_cache` —la de dos claves— y los
# receivers de `Ciudadano` y `User` que la llamaban. Las claves de la home y qué modelo
# mueve cada una son ahora una tabla sola (`dashboard/cache.py`), y los receivers que las
# usan viven al lado de esa tabla (`dashboard/signals/cache.py`). Acá queda la plomería:
# el `delete_many` tras el commit y la invalidación en lote de fichas de ciudadano, que no
# son contadores de la home.
