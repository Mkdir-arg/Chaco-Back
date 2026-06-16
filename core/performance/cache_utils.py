"""
Utilidades básicas para gestión de cache.
"""

import logging
from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

logger = logging.getLogger("django")


def invalidate_cache_keys(*cache_keys):
    """Invalida múltiples claves de cache."""
    try:
        for key in cache_keys:
            cache.delete(key)
    except Exception as e:
        logger.warning(f"No se pudo invalidar cache: {e}")


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
    """Invalida cache cuando se modifica un ciudadano."""
    invalidate_ciudadano_cache(instance.id)
    invalidate_dashboard_cache()


@receiver([post_save, post_delete], sender="auth.User")
def invalidate_user_cache_on_change(sender, instance, **kwargs):
    """Invalida cache cuando se modifica un usuario."""
    invalidate_dashboard_cache()