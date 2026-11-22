# Cambio 573: `TrazaDispositivo.edificio`, el edificio del sector en el momento del evento. Expand puro: nace
# NULL, sin backfill (las trazas anteriores se siguen atribuyendo por el texto del detalle). La reversa es la
# del AddField (borra la columna). El índice va en 0138 para que cada migración tenga un solo paso.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("programas", "0136_entrega_kit_uuid_cliente_char36"),
    ]

    operations = [
        migrations.AddField(
            model_name="trazadispositivo",
            name="edificio",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="trazas_dispositivo",
                to="programas.edificio",
                verbose_name="Edificio",
            ),
        ),
    ]
