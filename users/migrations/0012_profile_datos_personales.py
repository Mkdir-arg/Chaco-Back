from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0011_dispositivos_alcance_rbac"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="dni",
            field=models.CharField(blank=True, max_length=8, null=True, unique=True, verbose_name="DNI"),
        ),
        migrations.AddField(
            model_name="profile",
            name="telefono",
            field=models.CharField(blank=True, default="", max_length=30, verbose_name="Teléfono"),
        ),
        migrations.AddField(
            model_name="profile",
            name="institucion",
            field=models.CharField(blank=True, default="", max_length=255, verbose_name="Institución"),
        ),
        migrations.AddField(
            model_name="profile",
            name="observacion",
            field=models.TextField(blank=True, default="", verbose_name="Observación"),
        ),
    ]
