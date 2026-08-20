from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("programas", "0032_siis_segmento_en_subsegmento")]

    operations = [
        migrations.AddConstraint(
            model_name="segmento",
            constraint=models.UniqueConstraint(fields=("siis_programa_id",), name="uniq_segmento_siis_programa"),
        ),
        migrations.AddConstraint(
            model_name="subsegmento",
            constraint=models.UniqueConstraint(
                fields=("segmento", "siis_segmento_id"), name="uniq_subsegmento_siis_por_segmento"
            ),
        ),
    ]
