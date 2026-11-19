"""Índices de la ventana de RN-5.1 en ``CasoEmergencia`` (Cambio 508; EXPLAIN del Cambio 504).

La foto del tablero E1 y la de situación E8 leen ``~CERRADO OR alojado_en >= x OR cerrado_en >= x``.
Sin índices en ``alojado_en`` y ``cerrado_en`` el ``OR`` recorre la tabla (``type=ALL``); con ellos
el motor usa *index merge* con el índice de ``(estado, prioridad)`` que ya existe
(``scripts/perf_mysql/explain_ventana_tablero.py``, MariaDB 10.11 con 50.000 casos cerrados).

Solo índices, sin columnas ni datos: la release anterior no los ve y la reversa es borrarlos.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("programas", "0127_tipodispositivo_ubicacion_reservada"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="casoemergencia",
            index=models.Index(fields=["alojado_en"], name="caso_emerg_alojado_en_idx"),
        ),
        migrations.AddIndex(
            model_name="casoemergencia",
            index=models.Index(fields=["cerrado_en"], name="caso_emerg_cerrado_en_idx"),
        ),
    ]
