# La columna `EntregaKit.uuid_cliente` (0135) se amplía a `char(36)` en MySQL/MariaDB: con
# MariaDB 10.7+ Django 5 manda el UUID **con guiones** y una columna `char(32)` —la que crea el
# AddField y la que queda tras un restore desde MySQL— da «Data too long» (patrón de
# programas.0108 y programas.0121, Cambio 99). Columna recién creada: no hay filas que normalizar.
# Va aparte de 0135 para que el AddField (no idempotente) no corra con `atomic = False`; acá el
# paso se condiciona al tipo real de la columna (`modificar_columna`).

from django.db import migrations

from core.migraciones import modificar_columna

TABLA = "programas_entregakit"
COLUMNA = "uuid_cliente"


def ampliar_uuid_mysql(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    modificar_columna(schema_editor, TABLA, COLUMNA, "char(36)", "NULL")


def restaurar_uuid_mysql(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    # RED-18: se normaliza a hex antes de achicar, o MariaDB trunca los UUID con guiones.
    schema_editor.execute(
        f"UPDATE {TABLA} SET {COLUMNA} = REPLACE({COLUMNA}, '-', '') "
        f"WHERE {COLUMNA} IS NOT NULL AND CHAR_LENGTH({COLUMNA}) = 36"
    )
    modificar_columna(schema_editor, TABLA, COLUMNA, "char(32)", "NULL")


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("programas", "0135_emergencia_ingreso_sin_movimiento_y_uuid_entrega"),
    ]

    operations = [
        migrations.RunPython(ampliar_uuid_mysql, restaurar_uuid_mysql),
    ]
