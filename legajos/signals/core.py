from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from core.services.cache import invalidate_cache_pattern

from ..models import Ciudadano, LegajoAtencion


@receiver([post_save, post_delete], sender=Ciudadano)
def invalidate_ciudadano_cache(sender, **kwargs):
    """Invalida cache cuando se modifica un ciudadano."""
    from django.core.cache import cache

    cache.clear()


@receiver([post_save, post_delete], sender=LegajoAtencion)
def invalidate_legajo_cache(sender, **kwargs):
    """Invalida cache cuando se modifica un legajo."""
    invalidate_cache_pattern("legajos_list")
    invalidate_cache_pattern("reportes")
    invalidate_cache_pattern("dashboard")



