from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from ..models import LegajoAtencion

# La invalidación por cambios de Ciudadano (contar_ciudadanos, ciudadano_<id>) y la del
# badge de alertas viven en dashboard/signals/cache.py, con claves exactas y al lado de la
# tabla que dice qué modelo mueve cada clave (RED-51). El receiver que existía acá hacía
# cache.clear() global (borraba todo el cache del sitio, sesiones incluidas en prod) por
# cada alta/edición de ciudadano.


@receiver([post_save, post_delete], sender=LegajoAtencion)
def invalidate_legajo_cache(sender, **kwargs):
    """Invalida por clave exacta el cache que depende de legajos de atención.

    `stats_legajos_atencion` es la que de verdad cuenta este modelo: la escribe
    `dashboard.utils.contar_legajos_atencion()` y la lee la tarjeta «Legajos activos»
    del inicio (G2-04).

    RED-51: acá también se borraba `stats_legajos`, que escribe `contar_legajos()`
    agregando sobre `InscripcionPrograma`. Esa clave se mudó al receiver de ese modelo
    (`dashboard/signals/cache.py`): un legajo de atención refrescaba algo que no había
    cambiado, y una inscripción nueva no refrescaba nada.

    Este se queda en `legajos` —y no se muda con los otros— porque la app ya registra sus
    propias señales y la clave que borra sí cuenta este modelo.
    """
    from dashboard.cache import invalidar_por_modelo

    invalidar_por_modelo(sender)
