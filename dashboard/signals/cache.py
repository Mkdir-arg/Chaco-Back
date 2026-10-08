"""RED-51 · Los receivers que mantienen frescos los contadores de la home.

Los cuatro viven **acá**, al lado de la tabla que dice qué clave mueve cada modelo
(`dashboard/cache.py`). Antes estaban repartidos: dos en `core/performance/cache_utils.py`
—que es plomería de `core` y no tenía por qué conocer las claves del dashboard— y uno en
`legajos/signals/core.py` colgado del **modelo equivocado**: borraba `stats_legajos` al
guardar un `LegajoAtencion`, pero esa clave la escribe `contar_legajos()`, que agrega sobre
`InscripcionPrograma`. Una inscripción nueva no refrescaba nada y la home mostraba el
número viejo hasta que expirara el TTL —300 s en producción, donde el cache es Redis
compartido—; en los tests es LocMem y toda esta familia de bugs era invisible.

Juntarlos acá también cierra el ciclo de import que el ratchet de RED-79 marcaba:
`dashboard.cache` depende de `core.performance.cache_utils` y no al revés.

El de `LegajoAtencion` se queda en `legajos/signals/core.py`, donde ya estaba: esa app
registra sus propias señales y la clave que borra (`stats_legajos_atencion`) sí cuenta ese
modelo.
"""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from core.performance.cache_utils import invalidar_ciudadanos_tras_commit
from dashboard.cache import claves_de, invalidar_por_modelo


@receiver([post_save, post_delete], sender="programas.InscripcionPrograma")
def invalidar_contadores_de_inscripciones(sender, **kwargs):
    """Borra `stats_legajos` y el contador de inscripciones de hoy.

    Las dos claves las escribe el mismo modelo: `contar_legajos()` agrega el total y los
    activos, y `contar_seguimientos_hoy()` cuenta las de `fecha_inscripcion` de hoy.

    No hay riesgo de la avalancha de PERF-16: en el código de producción no existe ningún
    `bulk_create` de `InscripcionPrograma` (lo usa `seed_perf`, que corre contra bases
    descartables y no dispara `post_save`). Las altas son de a una, desde una pantalla.
    """
    invalidar_por_modelo(sender)


@receiver([post_save, post_delete], sender="legajos.AlertaCiudadano")
def invalidar_badge_de_alertas(sender, **kwargs):
    """`alertas_activas` no la borraba nadie al nacer —o al cerrarse— una alerta.

    La única limpieza venía del alta o la edición de un **ciudadano**, por
    `CiudadanosService.invalidate_ciudadanos_cache()`, así que el badge de la home podía
    tardar hasta un minuto (su TTL) en mostrar una alerta crítica nueva.

    Va por fila y no por lote a propósito: las altas de `AlertasService` son de a una
    (`objects.create`, porque el aviso por WebSocket necesita el `pk`) y en régimen la
    pasada horaria crea **cero**. El `DEL` que esto agrega es despreciable al lado de la
    notificación que ya se manda por alerta.
    """
    invalidar_por_modelo(sender)


@receiver([post_save, post_delete], sender="legajos.Ciudadano")
def invalidar_cache_de_ciudadano(sender, instance, **kwargs):
    """La ficha del ciudadano tocado, más el contador si el total pudo cambiar.

    PERF-16: eran cuatro ``DEL`` por ``save()`` —``contar_ciudadanos`` dos veces, porque el
    receiver llamaba a dos funciones que las dos la borraban—. Ahora es **un**
    ``delete_many`` deduplicado tras el commit, y el contador solo se toca cuando el total
    pudo cambiar: al crear o al borrar. ``post_delete`` no manda ``created``, y ahí el
    total sí cambió: por eso el default del ``get`` es ``True``.
    """
    nacio_o_murio = kwargs.get("created", True)
    invalidar_ciudadanos_tras_commit(
        [instance.id] if instance.id else [],
        claves_extra=claves_de(sender) if nacio_o_murio else (),
    )


@receiver([post_save, post_delete], sender="auth.User")
def invalidar_contador_de_usuarios(sender, instance, **kwargs):
    """RED-51: borra `contar_usuarios` y **ya no** `contar_ciudadanos`.

    Dar de alta o borrar a alguien del backoffice no cambia cuántos ciudadanos hay, y
    borrar de más obliga a la home a recalcular lo que no se movió.
    """
    # update_last_login guarda solo last_login en cada login: no cambia los contadores
    # del dashboard, no hace falta invalidarlos.
    if kwargs.get("update_fields") and set(kwargs["update_fields"]) == {"last_login"}:
        return
    invalidar_por_modelo(sender)
