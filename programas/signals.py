"""Señales de Becas sobre modelos de otras apps, y la invalidación del cache de `Programa`.

Vive en `programas` y no en `legajos` a propósito: la dependencia va de Becas al
legajo (`programas.models` importa `legajos.models`), nunca al revés.
"""

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from legajos.models import Ciudadano

from .models import Formulario, Programa
from .services.programa_cache import invalidar_programa


@receiver(post_save, sender=Ciudadano, dispatch_uid="programas.sincronizar_dni_titular")
def sincronizar_dni_titular(sender, instance, created, **kwargs):
    """DAT-03: `Formulario.dni_titular` sigue al DNI real de la persona.

    `dni_titular` es la columna con índice por la que una convocatoria decide si un
    DNI ya está inscripto (Cambio 91). La escribe `Formulario.save()` con el DNI del
    ciudadano del momento, y nadie la volvía a mirar: cuando el legajo corregía un
    DNI mal tipeado, **el DNI erróneo seguía ocupando el lugar** en la convocatoria y
    bloqueaba al verdadero titular en el link público, con un mensaje de duplicado
    que no se correspondía con ningún caso visible.

    Solo corre cuando el DNI pudo haber cambiado, y en ese orden para no pagar nada de
    más:

    1. un alta no tiene casos que arrastrar;
    2. un `save(update_fields=[...])` que no nombra el DNI no lo escribió;
    3. una instancia leída con `.only()`/`.defer()` sin el DNI **no lo tiene cargado**:
       tocarlo acá dispararía una consulta diferida para descubrir que nadie lo cambió,
       y después un `UPDATE` inútil. Si alguien se lo asignó deja de estar diferido y
       el caso cae en los de abajo;
    4. con el DNI cargado se compara contra el valor con el que la fila salió de la
       base, que guarda `Ciudadano.from_db`.

    Si la instancia **no** se leyó de la base —se armó a mano con su pk— no hay con qué
    comparar y se sincroniza igual: el `exclude()` lo deja en un `UPDATE` que no toca
    ninguna fila. El `update()` es a propósito: no hay nada más que recalcular y el
    filtro va por el índice de la FK.
    """
    if created:
        return
    campos = kwargs.get("update_fields")
    if campos is not None and "dni" not in campos:
        return
    if "dni" in instance.get_deferred_fields():
        return
    anterior = getattr(instance, "_dni_original", None)
    if anterior is not None and anterior == instance.dni:
        return
    nuevo = (instance.dni or "")[:20]
    Formulario.objects.filter(ciudadano_id=instance.pk).exclude(dni_titular=nuevo).update(dni_titular=nuevo)
    instance._dni_original = instance.dni


# --------------------------------------------------------------------------- #
# RED-80: quien **escribe** un `Programa` borra su clave cacheada.
#
# `programa_por_codigo` cachea la fila 300 s y todos los checks de alcance la leen.
# La invalidación estaba escrita a mano en el wizard de Configuración «la única
# pantalla que escribe un Programa», y no lo era: `/admin/` está ruteado y
# `ProgramaAdmin` deja cambiar el `codigo` y el `estado`, y **borrar**. Durante cinco
# minutos los pods evaluaban contra la fila anterior: en Dispositivos eso es «nadie
# entra», en Becas un 403 (RED-56). Con las señales queda cubierto el admin, el wizard
# y cualquier camino futuro, que es lo que no se podía garantizar enumerando pantallas.
#
# Lo que las señales **no** ven es un `queryset.update()` / `delete()` masivo: ahí la
# invalidación sigue siendo del llamador. Hoy no hay ninguno sobre `Programa`.
# --------------------------------------------------------------------------- #


@receiver(pre_save, sender=Programa, dispatch_uid="programas.recordar_codigo_de_programa")
def recordar_codigo_de_programa(sender, instance, **kwargs):
    """Guarda el código con el que la fila está hoy en la base, antes de pisarlo.

    El wizard deja **cambiar el código**, y después del `UPDATE` ya no hay forma de
    saber cuál era: la clave vieja quedaría cacheada apuntando a un programa que ya no
    responde a ese código. Es una consulta por escritura de `Programa` —decenas de
    filas, y se escriben en el wizard, en el admin y en los seeds—.
    """
    instance._codigo_anterior = (
        sender.objects.filter(pk=instance.pk).values_list("codigo", flat=True).first() if instance.pk else None
    )


@receiver(post_save, sender=Programa, dispatch_uid="programas.invalidar_cache_de_programa")
def invalidar_cache_de_programa(sender, instance, **kwargs):
    """Borra la clave del código nuevo y, si cambió, también la del viejo."""
    invalidar_programa(instance.codigo)
    anterior = getattr(instance, "_codigo_anterior", None)
    if anterior and anterior != instance.codigo:
        invalidar_programa(anterior)
    instance._codigo_anterior = instance.codigo


@receiver(post_delete, sender=Programa, dispatch_uid="programas.invalidar_cache_de_programa_borrado")
def invalidar_cache_de_programa_borrado(sender, instance, **kwargs):
    """Un programa borrado desde `/admin/` tiene que dejar de resolverse."""
    invalidar_programa(instance.codigo)
