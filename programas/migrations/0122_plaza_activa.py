# Baja lógica de la plaza (Cambio 479): `Plaza.activa`.
#
# EXPAND puro sobre `programas_plaza`: una columna `NOT NULL` con `db_default=True`, así que el
# DEFAULT queda escrito en el esquema. Las filas existentes nacen activas, y el código de la
# release anterior —que no conoce la columna— sigue dando de alta plazas activas sin nombrarla.
# Sin índice nuevo: las plazas se leen siempre por sector (`(sector, codigo)` y `(sector, estado)`),
# y un sector tiene a lo sumo unos cientos. Sin `RunPython` ni `RunSQL`: no hay datos que tocar.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("programas", "0121_emergencia_kits"),
    ]

    operations = [
        migrations.AddField(
            model_name="plaza",
            name="activa",
            field=models.BooleanField(db_default=True, default=True, verbose_name="Activa"),
        ),
    ]
