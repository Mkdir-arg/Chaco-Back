from django.db import migrations, models


def copiar_asociaciones_univocas(apps, schema_editor):
    Segmento = apps.get_model("programas", "Segmento")
    Subsegmento = apps.get_model("programas", "Subsegmento")
    for segmento in Segmento.objects.exclude(siis_segmento_id__isnull=True).iterator():
        subsegmentos = Subsegmento.objects.filter(segmento_id=segmento.pk)
        if subsegmentos.count() == 1:
            subsegmentos.update(siis_segmento_id=segmento.siis_segmento_id)


class Migration(migrations.Migration):
    dependencies = [("programas", "0031_siis_integracion")]

    operations = [
        migrations.AddField(
            model_name="subsegmento",
            name="siis_segmento_id",
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name="ID de segmento SIIS"),
        ),
        migrations.RunPython(copiar_asociaciones_univocas, migrations.RunPython.noop),
        migrations.RemoveField(model_name="segmento", name="siis_segmento_id"),
    ]
