from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("programas", "0042_subsegmento_local_sin_siis")]

    operations = [
        migrations.AddField(
            model_name="segmento",
            name="siis_programa_datos",
            field=models.JSONField(blank=True, default=dict, verbose_name="Detalle del programa SIIS"),
        ),
        migrations.AddField(
            model_name="segmento",
            name="siis_programa_estado",
            field=models.CharField(
                blank=True,
                choices=[("ACTIVO", "Activo"), ("INACTIVO", "Inactivo"), ("DESCONOCIDO", "Desconocido")],
                db_index=True,
                default="",
                max_length=20,
                verbose_name="Estado actual del programa en SIIS",
            ),
        ),
        migrations.AddField(
            model_name="segmento",
            name="siis_vinculado_en",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Programa SIIS vinculado el"),
        ),
        migrations.AddField(
            model_name="segmento",
            name="siis_verificado_en",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Última verificación con SIIS"),
        ),
    ]
