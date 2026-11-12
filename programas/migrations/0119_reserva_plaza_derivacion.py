# Módulo Emergencia, PR 6: las reservas «de derivación» dentro de Dispositivos.
#
# EXPAND puro sobre una tabla existente (`programas_reservaplaza`): una columna nueva
# **anulable** y un índice. El código de la release anterior no la lee ni la escribe, y sus
# altas siguen entrando con la columna en NULL, así que bajar la release con el esquema
# adelantado no rompe nada: no hace falta ninguna marca del contrato. Sin `RunPython` ni
# `RunSQL`: no hay datos que tocar (todas las reservas que existen son comunes, NULL).
#
# El índice `(derivacion, estado)` lleva `derivacion_id` a la izquierda: es el que InnoDB
# adopta para la FK, igual que `(plaza, estado)` y `(ciudadano, estado)`. Al revertir, Django
# repone el índice implícito de la FK antes de borrar este (`_create_missing_fk_index`).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("legajos", "0011_indices_redundantes_red83"),
        ("programas", "0118_emergencia_casos"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="reservaplaza",
            name="derivacion",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="reservas",
                to="programas.derivacion",
                verbose_name="Derivación de Emergencia",
            ),
        ),
        migrations.AddIndex(
            model_name="reservaplaza",
            index=models.Index(fields=["derivacion", "estado"], name="programas_r_derivac_69971c_idx"),
        ),
    ]
