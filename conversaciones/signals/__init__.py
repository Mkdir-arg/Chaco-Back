from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from core.services.cache import invalidate_cache_pattern
from ..models import Conversacion, Mensaje

@receiver([post_save, post_delete], sender=Conversacion)
def invalidate_conversacion_cache(sender, **kwargs):
    """Invalida cache cuando se modifica una conversación"""
    invalidate_cache_pattern('conversacion')
    invalidate_cache_pattern('lista_conversaciones')
    invalidate_cache_pattern('metricas')

@receiver([post_save, post_delete], sender=Mensaje)
def invalidate_mensaje_cache(sender, **kwargs):
    """Invalida cache cuando se modifica un mensaje"""
    invalidate_cache_pattern('conversacion')
    invalidate_cache_pattern('mensaje')
    invalidate_cache_pattern('lista_conversaciones')
