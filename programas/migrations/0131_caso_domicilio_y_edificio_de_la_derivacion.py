"""El punto del domicilio del caso y el edificio de la derivación (Cambio 520).

Solo *expand*: tres columnas nuevas que nacen nulas, sin datos que mover. La release anterior no las
lee ni las escribe, y un alta suya deja ``NULL``, que es un valor válido. La reversa es borrarlas.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("programas", "0130_indice_recepcion_entregas"),
    ]

    operations = [
        migrations.AddField(
            model_name="casoemergencia",
            name="domicilio_latitud",
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                max_digits=9,
                null=True,
                verbose_name="Latitud del domicilio",
            ),
        ),
        migrations.AddField(
            model_name="casoemergencia",
            name="domicilio_longitud",
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                max_digits=9,
                null=True,
                verbose_name="Longitud del domicilio",
            ),
        ),
        migrations.AddField(
            model_name="derivacion",
            name="edificio",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="derivaciones_emergencia",
                to="programas.edificio",
                verbose_name="Edificio",
            ),
        ),
    ]
