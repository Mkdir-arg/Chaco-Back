"""Reemplaza el índice de la bandeja de RENAPER por uno que también cubre el selector.

``territoriales_pendientes`` proyecta ``relevamiento__territorial_id``; con el índice de
dos columnas la consulta baja a la fila por cada caso pendiente (74 ms medidos con 4.076
pendientes). Con ``relevamiento`` como tercera columna queda cubierta (9 ms) y el prefijo
``(validado_renaper, creado)`` sigue sirviendo el orden de la bandeja.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("programas", "0058_formulario_indices_bandejas"),
    ]

    operations = [
        migrations.RemoveIndex(model_name="formulario", name="prog_formulario_renaper_idx"),
        migrations.AddIndex(
            model_name="formulario",
            index=models.Index(
                fields=["validado_renaper", "creado", "relevamiento"], name="prog_formulario_renaper_idx"
            ),
        ),
    ]
