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
from django.db.migrations.exceptions import IrreversibleError

# BARRERA-DE-REVERSA: por debajo de programas.0069 solo se vuelve con restore (RED-57).
# El ``RemoveField`` de ``segmento.siis_id_plan_soc`` borra el dato sin copiarlo a ningún
# lado: al revertir, el ``AddField`` automático recrea la columna vacía y los ids de plan
# social cargados a mano desaparecen sin aviso.
# Runbook D.4 de docs/internal/processes.md.
MENSAJE_BARRERA = (
    "programas.0069 es una barrera de reversa (RED-57): la ida borró "
    "segmento.siis_id_plan_soc sin copiarlo, así que la vuelta deja la columna vacía y "
    "los identificadores cargados a mano se pierden. Volver atrás se hace con restore "
    "del dump previo al deploy: runbook D.4 de docs/internal/processes.md. "
    "No reintentar ni usar --fake."
)


def sin_cambios(apps, schema_editor):
    """La barrera no toca nada hacia adelante: solo existe para el camino de vuelta."""


def bloquear_reversa(apps, schema_editor):
    # Es la última operación de la migración, así que Django la corre **primera** al
    # desaplicar: aborta antes de cualquier DDL. Vale en todos los motores: lo que se
    # pierde es una columna de datos, y eso no depende del motor.
    raise IrreversibleError(MENSAJE_BARRERA)


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
        migrations.RunPython(sin_cambios, bloquear_reversa),
    ]
