# La columna UUID de la tabla nueva de adjuntos del relevamiento (0107) se amplía a `char(36)`
# en MySQL/MariaDB: con MariaDB 10.7+ Django 5 manda el UUID **con guiones** y una columna
# `char(32)` —la que queda tras un restore desde MySQL— da «Data too long» (patrón de
# programas.0093 y programas.0073, Cambio 99). Tabla recién creada: no hay filas que normalizar.
# Va aparte de 0107 para que ese archivo (CreateModel, no idempotente) no corra con
# `atomic = False`; acá cada paso se condiciona al estado real de la columna.

from django.db import migrations

from core.migraciones import modificar_columna

TABLA = "programas_adjuntorespuestarelevamiento"
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
    schema_editor.execute(f"ALTER TABLE {TABLA} MODIFY {COLUMNA} char(32) NULL")


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("programas", "0107_relevamiento_formulario_app"),
    ]

    operations = [
        migrations.RunPython(ampliar_uuid_mysql, restaurar_uuid_mysql),
    ]
