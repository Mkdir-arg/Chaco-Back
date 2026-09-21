# Cambio 82: los tres identificadores que el alta de beneficiarios manda a SIIS
# se pueden cargar a mano en cada segmento. Hasta ahora salían solo del programa
# vinculado y no había dónde corregirlos si el servicio no reconocía ese
# programa. Aditiva: los tres nacen vacíos y el comportamiento no cambia hasta
# que alguien los complete.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("programas", "0067_requisitonativo_destino_siis"),
    ]

    operations = [
        migrations.AddField(
            model_name="segmento",
            name="siis_id_plan_soc",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Viaja como «id_plan_soc». Vacío, se usa el del programa vinculado.",
                null=True,
                verbose_name="Id. del plan social en SIIS",
            ),
        ),
        migrations.AddField(
            model_name="segmento",
            name="siis_jurid",
            field=models.PositiveIntegerField(
                blank=True,
                help_text=(
                    "Viaja como «jurid». Vacío, se usa la jurisdicción que informó SIIS al vincular el programa."
                ),
                null=True,
                verbose_name="Id. de jurisdicción en SIIS",
            ),
        ),
        migrations.AddField(
            model_name="segmento",
            name="siis_id_fun_x_plan",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Viaja como «id_fun_x_plan». Vacío, se usa la función configurada en el programa.",
                null=True,
                verbose_name="Id. de función por plan en SIIS",
            ),
        ),
    ]
