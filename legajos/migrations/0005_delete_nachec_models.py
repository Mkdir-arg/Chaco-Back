# Eliminación completa del programa Ñachec.
# Solo DeleteModel, ordenados de dependientes a dependidos (las FK entre estos
# modelos no forman ciclos): así el autodetector no necesita RemoveField previos,
# que rompían contra los índices de Meta que referenciaban esos campos.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("legajos", "0004_remove_derivacion"),
    ]

    operations = [
        migrations.DeleteModel(name="TareaNachec"),
        migrations.DeleteModel(name="PrestacionNachec"),
        migrations.DeleteModel(name="PlanIntervencionNachec"),
        migrations.DeleteModel(name="EvaluacionVulnerabilidad"),
        migrations.DeleteModel(name="RelevamientoNachec"),
        migrations.DeleteModel(name="SeguimientoTerritorial"),
        migrations.DeleteModel(name="HistorialEstadoCaso"),
        migrations.DeleteModel(name="CasoNachec"),
    ]
