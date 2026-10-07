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
    """Invalida por clave exacta el cache que depende de legajos.

    `stats_legajos_atencion` es la que de verdad cuenta este modelo: la escribe
    `dashboard.utils.contar_legajos_atencion()` y la lee la tarjeta «Legajos activos»
    del inicio (G2-04). `stats_legajos` sigue borrándose acá aunque la escriba un
    contador de `InscripcionPrograma`: ese desajuste es RED-51 y lo mueve la Ola 4,
    que tiene dos tests escritos sobre el estado actual.
    """
    cache.delete("stats_legajos_atencion")
    cache.delete("stats_legajos")
