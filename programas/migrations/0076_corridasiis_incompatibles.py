# Cambio 136 (auditoría oct-2026, BEC-11): la corrida cuenta a los incompatibles.
#
# SIIS puede contestar que la persona no es compatible con el programa. En la
# pantalla del caso eso es una advertencia y decide el revisor (Cambio 81); en una
# corrida masiva no hay revisor, así que esos casos quedan sin aprobar y contados
# aparte. El contador necesita su columna para que la pantalla lo muestre: un
# número que solo viva en el log del pod no lo ve nadie.
#
# EXPAND/CONTRACT: una columna nueva al final de una tabla chica (una fila por
# corrida lanzada), con el default **escrito en el esquema** (`db_default`), no
# solo en el modelo.
#
# La diferencia no es cosmética. El `default` de Django vive en Python: lo pone
# el ORM al armar el INSERT. Entre que corre la migración y termina el rollout,
# el pod viejo sigue insertando `CorridaSiis` **sin** nombrar esta columna, y en
# MariaDB y MySQL con STRICT_TRANS_TABLES —el modo de ECOM— una columna NOT NULL
# sin default de base contesta ERROR 1364 («Field 'incompatibles' doesn't have a
# default value»): lanzar el proceso masivo daría 500 durante toda la ventana.
# Con `db_default=0` el `ADD COLUMN` lleva su `DEFAULT 0` y el INSERT viejo entra.
# Verificado contra MariaDB 10.11 real con un INSERT que omite la columna.
#
# `ADD COLUMN` con default constante al final de la tabla es instantáneo en
# MariaDB 10.3+ y MySQL 8 (ALGORITHM=INSTANT). La reversa la da Django:
# `RemoveField`, sin pérdida de datos operativos.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("programas", "0075_enviosiis_vigente")]

    operations = [
        migrations.AddField(
            model_name="corridasiis",
            name="incompatibles",
            field=models.PositiveIntegerField(db_default=0, default=0, verbose_name="Incompatibles según SIIS"),
        ),
    ]
