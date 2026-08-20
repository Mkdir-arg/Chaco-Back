from django.db import migrations, models


def completar_fecha_hasta(apps, schema_editor):
    Relevamiento = apps.get_model("programas", "Relevamiento")
    Relevamiento.objects.filter(fecha_hasta__isnull=True).update(
        fecha_hasta=models.F("fecha_asignada")
    )


class Migration(migrations.Migration):
    dependencies = [("programas", "0035_numeracion_contextual_becas")]

    operations = [
        migrations.AlterField(
            model_name="relevamiento",
            name="fecha_asignada",
            field=models.DateField(verbose_name="Fecha desde"),
        ),
        migrations.AddField(
            model_name="relevamiento",
            name="fecha_hasta",
            field=models.DateField(null=True, verbose_name="Fecha hasta"),
        ),
        migrations.RunPython(completar_fecha_hasta, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="relevamiento",
            name="fecha_hasta",
            field=models.DateField(verbose_name="Fecha hasta"),
        ),
        migrations.RemoveIndex(
            model_name="relevamiento",
            name="programas_r_estado_9d845b_idx",
        ),
        migrations.AddIndex(
            model_name="relevamiento",
            index=models.Index(
                fields=["estado", "fecha_asignada", "fecha_hasta"],
                name="programas_r_estado_c80788_idx",
            ),
        ),
    ]
