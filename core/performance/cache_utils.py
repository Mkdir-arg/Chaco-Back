"""
Utilidades básicas para gestión de cache.
"""

import logging

from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

logger = logging.getLogger("django")

#: Los dos contadores de la home que dependen de **cuántos** ciudadanos hay. Solo
#: cambian cuando nace o se borra uno: editar a alguien no mueve ningún total.
CLAVES_CONTADORES = ("contar_ciudadanos", "contar_usuarios")


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


def invalidar_ciudadanos_tras_commit(ids, contadores=True):
    """Invalidación de una escritura **en lote** de ciudadanos (PERF-04).

    ``bulk_update`` no dispara ``post_save``, así que el cruce del padrón avisa por
    acá con las mismas claves que la señal, en un solo ``DEL`` para todos los casos.
    """
    claves = [f"ciudadano_{pk}" for pk in ids]
    if contadores:
        claves.extend(CLAVES_CONTADORES)
    invalidar_tras_commit(claves)


def invalidate_ciudadano_cache(ciudadano_id=None):
    """Invalida cache relacionado con ciudadanos."""
    keys_to_invalidate = ["contar_ciudadanos"]

    if ciudadano_id:
        keys_to_invalidate.append(f"ciudadano_{ciudadano_id}")

    invalidate_cache_keys(*keys_to_invalidate)


def invalidate_dashboard_cache():
    """Invalida cache del dashboard."""
    keys_to_invalidate = [
        "contar_usuarios",
        "contar_ciudadanos",
    ]
    invalidate_cache_keys(*keys_to_invalidate)


# Signals para invalidación automática
@receiver([post_save, post_delete], sender="legajos.Ciudadano")
def invalidate_ciudadano_cache_on_change(sender, instance, **kwargs):
    """Invalida cache cuando se modifica un ciudadano.

    PERF-16: eran cuatro ``DEL`` por ``save()`` —``contar_ciudadanos`` dos veces,
    porque ``invalidate_ciudadano_cache`` y ``invalidate_dashboard_cache`` la
    borran las dos—. Ahora es **un** ``delete_many`` deduplicado tras el commit, y
    los dos contadores solo se tocan cuando el total pudo cambiar: al crear o al
    borrar. ``post_delete`` no manda ``created``, y ahí el total sí cambió: por eso
    el default del ``get`` es ``True``.
    """
    nacio_o_murio = kwargs.get("created", True)
    invalidar_ciudadanos_tras_commit([instance.id] if instance.id else [], contadores=nacio_o_murio)


@receiver([post_save, post_delete], sender="auth.User")
def invalidate_user_cache_on_change(sender, instance, **kwargs):
    """Invalida cache cuando se modifica un usuario."""
    # update_last_login guarda solo last_login en cada login: no cambia los
    # contadores del dashboard, no hace falta invalidarlos.
    if kwargs.get("update_fields") and set(kwargs["update_fields"]) == {"last_login"}:
        return
    invalidate_dashboard_cache()
