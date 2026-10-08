"""App de campo: la marca de sincronización tardía, las observaciones de la
carga y la forma de las condiciones (G1-04, G1-05 y RED-40).

Las dos columnas nuevas van sobre ``programas_formulario``, la tabla más grande
(283 MB en PRD): las dos se agregan **al final de la fila**, que es la forma que
MySQL 8 y MariaDB 10.11 resuelven con ``ALGORITHM=INSTANT`` sin reescribir la
tabla ni tomar un lock largo. Medido en el banco de 20.000 casos de
``scripts/perf_mysql/`` contra ``mariadb:10.11``, muy por debajo del
``read_timeout`` del ``migrate``.

**Expand puro.** ``observaciones_carga`` nace ``NULL``; ``sincronizado_tarde``
lleva ``db_default=False``, el DEFAULT nativo de Django 5, que queda **escrito
en el esquema**: con el esquema adelantado y la release anterior todavía
atendiendo, su ``INSERT`` omite la columna y la base la completa sola en vez de
rechazar el alta entera (error 1364 con ``STRICT_TRANS_TABLES``).

Los dos ``AlterField`` no tocan la base: ``validators`` vive en Python y
``sqlmigrate`` sale vacío para ellos.
"""

import programas.validadores
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("programas", "0079_fechas_locales_bec18"),
    ]

    operations = [
        # G1-05: lo que el servidor observó de una carga de la app y no alcanza
        # para rechazarla. Nullable: nada que observar es la mayoría de los casos.
        migrations.AddField(
            model_name="formulario",
            name="observaciones_carga",
            field=models.TextField(blank=True, null=True, verbose_name="Observaciones de la carga"),
        ),
        # G1-04: la captura entró dentro de la gracia posterior al cierre.
        migrations.AddField(
            model_name="formulario",
            name="sincronizado_tarde",
            field=models.BooleanField(
                db_default=False,
                default=False,
                verbose_name="Sincronizado después del cierre del período",
            ),
        ),
        # RED-40: validación de forma del JSON de condiciones. Sin DDL.
        migrations.AlterField(
            model_name="gruporequisito",
            name="condicion_defecto",
            field=models.JSONField(
                blank=True,
                null=True,
                validators=[programas.validadores.validar_condicion_json],
                verbose_name="Condición por defecto",
            ),
        ),
        migrations.AlterField(
            model_name="itemdiseno",
            name="condicion",
            field=models.JSONField(
                blank=True,
                null=True,
                validators=[programas.validadores.validar_condicion_json],
                verbose_name="Condición",
            ),
        ),
    ]
