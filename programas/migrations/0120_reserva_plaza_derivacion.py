# Módulo Emergencia, PR 6: las reservas «de derivación» dentro de Dispositivos.
#
# EXPAND puro sobre una tabla existente (`programas_reservaplaza`): una columna nueva
# **anulable**. El código de la release anterior no la lee ni la escribe, y sus altas
# siguen entrando con la columna en NULL, así que bajar la release con el esquema
# adelantado no rompe nada: no hace falta ninguna marca del contrato. Sin `RunPython` ni
# `RunSQL`: no hay datos que tocar (todas las reservas que existen son comunes, NULL).
#
# **Sin índice `(derivacion, estado)`**, a propósito: con `derivacion_id` a la izquierda
# InnoDB lo usaría como índice de la FK y cada `UPDATE` de `estado` pediría un lock sobre
# la fila de la derivación *después* de la plaza y la reserva, al revés del orden de
# candados de Emergencia. Alcanza el índice implícito de la FK (una sola columna). Ver el
# comentario en `ReservaPlaza.Meta.indexes`.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("legajos", "0011_indices_redundantes_red83"),
        ("programas", "0119_emergencia_casos"),
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
    ]
