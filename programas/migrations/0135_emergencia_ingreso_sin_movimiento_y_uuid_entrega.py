# Cambio 535. Dos columnas nuevas, EXPAND puro:
#
# * `EntregaKit.uuid_cliente` nace anulable y único: el código viejo no la escribe y las filas que
#   crea quedan en NULL, que MySQL y MariaDB admiten repetido en un UNIQUE (no hay índice
#   condicional, que en MySQL/MariaDB no existe). Se amplía a `char(36)` en la 0136.
# * `SLAEmergencia.ingreso_sin_movimiento_h` nace NOT NULL con `db_default`: el DEFAULT queda en el
#   esquema, así que el INSERT del código viejo —que no la nombra— sigue andando tras un rollback.

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("programas", "0134_entrada_bitacora_edificio"),
    ]

    operations = [
        migrations.AddField(
            model_name="entregakit",
            name="uuid_cliente",
            field=models.UUIDField(
                blank=True, editable=False, null=True, unique=True, verbose_name="Identificador del armado (mesa)"
            ),
        ),
        migrations.AddField(
            model_name="slaemergencia",
            name="ingreso_sin_movimiento_h",
            field=models.PositiveIntegerField(
                db_default=6,
                default=6,
                help_text="La bandeja y la ficha avisan «Aceptado sin movimiento». No vence nada. Con 0 no se avisa.",
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name="Horas de un ingreso aceptado sin movimiento antes de avisar",
            ),
        ),
    ]
