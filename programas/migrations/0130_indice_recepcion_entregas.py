"""Índice de la recepción de las entregas de kits (Cambio 510, E-7b; RNF-009-10).

El ``EXPLAIN`` de la solapa «Abastecimiento» de E8 (MariaDB 10.11, con 10.000 entregas recibidas de
un evento anterior) mostró que A2 —lo recibido por dispositivo e ítem desde ``inicio_evento``—
recorría ``programas_entregakit`` entera: el índice de ``estado`` no sirve cuando casi todas las
entregas están recibidas. Con ``recibida_en`` el filtro ``recibida_en >= inicio`` es un ``range``
y la historia de eventos anteriores deja de leerse.

Solo un índice, sin columnas ni datos: la release anterior no lo ve y la reversa es borrarlo. El DDL
no es transaccional, pero es una sola operación: si se corta, no queda nada a medias que reintentar.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("programas", "0129_indices_foto_situacion"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="entregakit",
            index=models.Index(fields=["recibida_en"], name="entrega_kit_recibida_en_idx"),
        ),
    ]
