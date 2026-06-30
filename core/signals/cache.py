from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from ..services.cache import invalidate_cache_pattern


@receiver([post_save, post_delete], sender="legajos.LegajoAtencion")
def invalidate_legajos_cache(sender, **kwargs):
    """Invalida cache cuando se modifica un legajo"""
    invalidate_cache_pattern("legajos_list")


@receiver([post_save, post_delete], sender="conversaciones.Conversacion")
def invalidate_conversaciones_cache(sender, **kwargs):
    """Invalida cache cuando se modifica una conversación"""
    invalidate_cache_pattern("conversaciones")


@receiver([post_save, post_delete], sender="conversaciones.Mensaje")
def invalidate_mensajes_cache(sender, **kwargs):
    """Invalida cache cuando se crea/modifica un mensaje"""
    invalidate_cache_pattern("conversaciones")
    invalidate_cache_pattern("mensajes")
