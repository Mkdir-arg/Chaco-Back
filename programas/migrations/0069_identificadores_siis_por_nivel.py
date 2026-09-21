# Cambio 82, corrección del alcance tras probarlo en testing.
#
# Los tres identificadores del alta (``id_plan_soc``, ``jurid``,
# ``id_fun_x_plan``) se pueden cargar a mano, pero en el nivel que les
# corresponde:
#
# * ``id_plan_soc`` es uno solo por programa: se pisa en el ``ProgramaSiis``,
#   como *override* del id que trajo la API. Se guarda aparte de
#   ``siis_programa_id`` porque ese sigue siendo la clave con la que
#   ``sincronizar_programas_siis`` busca en el catálogo; escribirle un id que el
#   catálogo no tiene lo dejaría en DESCONOCIDO y bloquearía todo el programa.
# * ``jurid`` y ``id_fun_x_plan`` quedan en los dos niveles: en el programa,
#   como valor por defecto de sus segmentos, y en cada segmento que necesite
#   otro.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("programas", "0068_segmento_identificadores_siis"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="segmento",
            name="siis_id_plan_soc",
        ),
        migrations.AddField(
            model_name="programasiis",
            name="siis_id_plan_soc",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Viaja como «id_plan_soc». Vacío, se usa el id del programa que trajo la API.",
                null=True,
                verbose_name="Id. de plan social en SIIS",
            ),
        ),
        migrations.AddField(
            model_name="programasiis",
            name="siis_jurid",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Viaja como «jurid». Vacío, se usa la que informó SIIS al vincular el programa.",
                null=True,
                verbose_name="Id. de jurisdicción en SIIS",
            ),
        ),
    ]
