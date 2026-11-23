from django.db import migrations, models


class Migration(migrations.Migration):
    """Expand: ``LineaEntrega.nombre`` (nullable). La rellena la migración de datos siguiente."""

    dependencies = [
        ("programas", "0139_texto_consumo_por_unidad_tipokit"),
    ]

    operations = [
        migrations.AddField(
            model_name="lineaentrega",
            name="nombre",
            field=models.CharField(
                blank=True,
                help_text="Cómo se llamaba el ítem cuando salió. Las entregas viejas lo traen de su ítem (``nombre_visible``).",
                max_length=80,
                null=True,
                verbose_name="Nombre del ítem",
            ),
        ),
    ]
