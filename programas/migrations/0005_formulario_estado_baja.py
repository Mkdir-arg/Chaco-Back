from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("programas", "0004_subsegmento_descripcion"),
    ]

    operations = [
        migrations.AlterField(
            model_name="formulario",
            name="estado",
            field=models.CharField(
                choices=[
                    ("ENVIADO", "Enviado"),
                    ("APROBADO", "Aprobado"),
                    ("RECHAZADO", "Rechazado"),
                    ("BAJA", "Dado de baja"),
                ],
                db_index=True,
                default="ENVIADO",
                max_length=20,
                verbose_name="Estado",
            ),
        ),
    ]
