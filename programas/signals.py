"""Señales de Becas sobre modelos de otras apps.

Vive en `programas` y no en `legajos` a propósito: la dependencia va de Becas al
legajo (`programas.models` importa `legajos.models`), nunca al revés.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from legajos.models import Ciudadano

from .models import Formulario


@receiver(post_save, sender=Ciudadano, dispatch_uid="programas.sincronizar_dni_titular")
def sincronizar_dni_titular(sender, instance, created, **kwargs):
    """DAT-03: `Formulario.dni_titular` sigue al DNI real de la persona.

    `dni_titular` es la columna con índice por la que una convocatoria decide si un
    DNI ya está inscripto (Cambio 91). La escribe `Formulario.save()` con el DNI del
    ciudadano del momento, y nadie la volvía a mirar: cuando el legajo corregía un
    DNI mal tipeado, **el DNI erróneo seguía ocupando el lugar** en la convocatoria y
    bloqueaba al verdadero titular en el link público, con un mensaje de duplicado
    que no se correspondía con ningún caso visible.

    Solo corre cuando el DNI pudo haber cambiado: `Ciudadano.from_db` guarda el valor
    con que la fila salió de la base, así que un alta o un guardado que declara sus
    `update_fields` sin el DNI no agrega ni una consulta. Si la instancia **no** se
    leyó de la base —se armó a mano con su pk— no hay con qué comparar y se sincroniza
    igual: el `exclude()` lo deja en un `UPDATE` que no toca ninguna fila. El
    `update()` es a propósito: no hay nada más que recalcular y el filtro va por el
    índice de la FK.
    """
    if created:
        return
    campos = kwargs.get("update_fields")
    if campos is not None and "dni" not in campos:
        return
    anterior = getattr(instance, "_dni_original", None)
    if anterior is not None and anterior == instance.dni:
        return
    nuevo = (instance.dni or "")[:20]
    Formulario.objects.filter(ciudadano_id=instance.pk).exclude(dni_titular=nuevo).update(dni_titular=nuevo)
    instance._dni_original = instance.dni
