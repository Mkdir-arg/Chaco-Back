from django.db import migrations
from django.utils import timezone


def desactivar_alertas_sin_red_familiar(apps, schema_editor):
    """Cierra las alertas SIN_RED_FAMILIAR activas: el tipo ya no se genera."""
    AlertaCiudadano = apps.get_model("legajos", "AlertaCiudadano")
    AlertaCiudadano.objects.filter(
        tipo="SIN_RED_FAMILIAR",
        activa=True,
    ).update(activa=False, fecha_cierre=timezone.now())


class Migration(migrations.Migration):

    dependencies = [
        ("legajos", "0005_delete_nachec_models"),
    ]

    operations = [
        migrations.RunPython(
            desactivar_alertas_sin_red_familiar,
            migrations.RunPython.noop,
        ),
    ]
