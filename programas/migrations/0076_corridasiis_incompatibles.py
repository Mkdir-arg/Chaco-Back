# Cambio 136 (auditoría oct-2026, BEC-11): la corrida cuenta a los incompatibles.
#
# SIIS puede contestar que la persona no es compatible con el programa. En la
# pantalla del caso eso es una advertencia y decide el revisor (Cambio 81); en una
# corrida masiva no hay revisor, así que esos casos quedan sin aprobar y contados
# aparte. El contador necesita su columna para que la pantalla lo muestre: un
# número que solo viva en el log del pod no lo ve nadie.
#
# EXPAND/CONTRACT: una columna nueva con `default=0` al final de una tabla chica
# (una fila por corrida lanzada). El código viejo no la conoce y no la escribe;
# el `default` del modelo la completa sola. ADD COLUMN con default constante es
# instantáneo en MariaDB 10.3+ y MySQL 8 (ALGORITHM=INSTANT). La reversa la da
# Django: `RemoveField`, sin pérdida de datos operativos.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("programas", "0075_enviosiis_vigente")]

    operations = [
        migrations.AddField(
            model_name="corridasiis",
            name="incompatibles",
            field=models.PositiveIntegerField(default=0, verbose_name="Incompatibles según SIIS"),
        ),
    ]
