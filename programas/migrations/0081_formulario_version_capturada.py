"""La versión del diseño con la que el teléfono capturó la carga (G1-16).

Una columna sobre ``programas_formulario``, la tabla más grande (283 MB en PRD).
Va **al final de la fila**, que es la forma que MySQL 8 y MariaDB 10.11 resuelven
con ``ALGORITHM=INSTANT`` sin reescribir la tabla ni tomar un lock largo: es la
misma operación que las dos columnas de ``programas.0080``, medidas en el banco
de 22.000 casos de ``scripts/perf_mysql/`` en 35-104 ms, tres órdenes de magnitud
por debajo del ``read_timeout`` de 10 s del ``migrate`` (OPS-05).

**Expand puro.** Nace ``NULL``: la columna significa «la app no dijo con qué
versión capturó», que es exactamente lo que pasa con la app instalada
(``Chaco-mobile@a66c2d3``) y con todo caso que ya está en la base. Con el esquema
adelantado y la release anterior todavía atendiendo —lo que deja un rolling o un
rollback—, su ``INSERT`` omite la columna y la base la completa con ``NULL`` en
vez de rechazar el alta entera.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("programas", "0080_app_de_campo_gracia_y_validacion"),
    ]

    operations = [
        migrations.AddField(
            model_name="formulario",
            name="version_capturada",
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                verbose_name="Versión del formulario con la que se capturó",
            ),
        ),
    ]
