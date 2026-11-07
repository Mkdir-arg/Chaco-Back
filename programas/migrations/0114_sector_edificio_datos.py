from django.db import migrations
from django.db.models import Count, Min


def asignar_edificio_unico(apps, schema_editor=None):
    """Sectores sin edificio de un dispositivo con UN solo edificio vinculado: pasan a ese edificio.

    Con dos o más edificios no hay forma de saber en cuál está cada sector, así que quedan en
    NULL (el bloque «Sin edificio» de la solapa Infraestructura) hasta que un administrador
    los asigne. Idempotente: solo toca sectores con `edificio` NULL, así que una segunda
    corrida —o un reintento después de un corte— no pisa una asignación hecha a mano.

    Un `UPDATE` por dispositivo con edificio, no una fila por sector: el costo es proporcional
    a los dispositivos (decenas), no a los sectores. Usa `apps.get_model`, nunca el modelo
    actual.
    """

    Sector = apps.get_model("programas", "Sector")
    Edificio = apps.get_model("programas", "Edificio")
    vinculos = Edificio.dispositivos.through.objects.values("dispositivo_id").annotate(
        cantidad=Count("edificio_id"), unico=Min("edificio_id")
    )
    for fila in vinculos.filter(cantidad=1):
        Sector.objects.filter(dispositivo_id=fila["dispositivo_id"], edificio__isnull=True).update(
            edificio_id=fila["unico"]
        )


def desasignar_edificios(apps, schema_editor=None):
    """Reversa: todos los sectores vuelven a NULL (la reversa de 0113 saca la columna igual)."""

    apps.get_model("programas", "Sector").objects.filter(edificio__isnull=False).update(edificio=None)


class Migration(migrations.Migration):
    """Datos de `Sector.edificio` (Cambio 429), separada de la de esquema (0113).

    Reversa: `migrate programas 0113` deja todos los sectores sin edificio. No pierde sectores,
    plazas ni estadías: solo la asignación del campo, que además se descarta al volver a 0112.
    """

    dependencies = [
        ("programas", "0113_sector_edificio"),
    ]

    operations = [
        migrations.RunPython(asignar_edificio_unico, desasignar_edificios),
    ]
