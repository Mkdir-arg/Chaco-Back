import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """La novedad automática de la bitácora cuelga del movimiento que la generó (P10).

    Columna nueva **anulable**: las novedades que cargó un operador van en `NULL`, y el
    código de la release anterior sigue dando de alta novedades sin tocarla. El uno a uno
    es un `UNIQUE` común sobre una columna anulable —los `NULL` no chocan entre sí—, que
    existe en MySQL y en MariaDB; un `UniqueConstraint(condition=...)` no.
    """

    dependencies = [
        ("programas", "0093_inspeccion_app_sin_conexion"),
    ]

    operations = [
        migrations.AddField(
            model_name="entradabitacora",
            name="movimiento",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="entrada_bitacora",
                to="programas.movimientoestadia",
                verbose_name="Movimiento que la generó",
            ),
        ),
    ]
