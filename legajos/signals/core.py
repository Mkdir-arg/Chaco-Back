from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from ..models import LegajoAtencion

# La invalidación por cambios de Ciudadano (contar_ciudadanos, ciudadano_<id>)
# vive en core/performance/cache_utils.py con claves exactas. El receiver que
# existía acá hacía cache.clear() global (borraba todo el cache del sitio,
# sesiones incluidas en prod) por cada alta/edición de ciudadano.


@receiver([post_save, post_delete], sender=LegajoAtencion)
def invalidate_legajo_cache(sender, **kwargs):
    """Invalida por clave exacta el cache que depende de legajos."""
    cache.delete("stats_legajos")
