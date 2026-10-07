"""Copia local de los catálogos maestros de SIIS (SIIS-09, ronda 2 del PR 5).

Tabla nueva y vacía: *expand* puro. El código de la release anterior no la
conoce y no la necesita —sigue pidiéndole los catálogos a la API—, así que las
dos versiones conviven sin problema durante el rolling. La reversa borra la
tabla y lo único que se pierde es la copia, que se vuelve a bajar sola en la
primera lectura del catálogo.

La tabla **nace vacía**: hasta que corra el CronJob nocturno (o cualquier
corrida del masivo o de los comandos, que la escriben al pasar) el backoffice no
puede armar el payload del alta, y el envío queda como ERROR reintentable con el
mensaje que dice cómo destrabarlo. Por eso el paso operativo del deploy es
correr ``sincronizar_programas_siis`` una vez.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("programas", "0076_corridasiis_incompatibles"),
    ]

    operations = [
        migrations.CreateModel(
            name="CatalogoSiisLocal",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("creado", models.DateTimeField(auto_now_add=True)),
                ("modificado", models.DateTimeField(auto_now=True)),
                ("nombre", models.CharField(max_length=40, unique=True, verbose_name="Catálogo")),
                ("items", models.JSONField(default=list, verbose_name="Ítems normalizados")),
            ],
            options={
                "verbose_name": "Catálogo maestro de SIIS",
                "verbose_name_plural": "Catálogos maestros de SIIS",
                "ordering": ["nombre"],
            },
        ),
    ]
