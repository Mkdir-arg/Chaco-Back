from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("programas", "0028_indicadores_dispositivos"),
    ]

    operations = [
        migrations.AddField(
            model_name="formulario",
            name="capturado_en",
            field=models.DateTimeField(
                blank=True,
                editable=False,
                null=True,
                verbose_name="Fecha de captura en el dispositivo",
            ),
        ),
        migrations.AddField(
            model_name="formulario",
            name="client_uuid",
            field=models.UUIDField(
                blank=True,
                editable=False,
                null=True,
                unique=True,
                verbose_name="Identificador de captura mobile",
            ),
        ),
    ]
