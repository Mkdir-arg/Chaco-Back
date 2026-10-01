from django.db import migrations

# MariaDB 10.7+ tiene UUID nativo y Django 5 envía ``token_publico`` con guiones
# (36 caracteres); la columna nació ``char(32)`` en la 0049 y el alta de un
# relevamiento público daba «Data too long for column 'token_publico'». Mismo
# arreglo que las 0047/0048 para ``client_uuid`` e ``id_consulta``. ``MODIFY``
# conserva el índice único de la columna.
TABLA = "programas_relevamiento"
COLUMNA = "token_publico"


def _normalizar_uuid(schema_editor, con_guiones):
    if con_guiones:
        valor = (
            f"CONCAT(SUBSTRING({COLUMNA}, 1, 8), '-', "
            f"SUBSTRING({COLUMNA}, 9, 4), '-', SUBSTRING({COLUMNA}, 13, 4), '-', "
            f"SUBSTRING({COLUMNA}, 17, 4), '-', SUBSTRING({COLUMNA}, 21, 12))"
        )
        condicion = f"CHAR_LENGTH({COLUMNA}) = 32"
    else:
        valor = f"REPLACE({COLUMNA}, '-', '')"
        condicion = f"CHAR_LENGTH({COLUMNA}) = 36"
    schema_editor.execute(f"UPDATE {TABLA} SET {COLUMNA} = {valor} WHERE {COLUMNA} IS NOT NULL AND {condicion}")


def ampliar_token_publico_mysql(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    schema_editor.execute(f"ALTER TABLE {TABLA} MODIFY {COLUMNA} char(36) NULL")
    # Solo MariaDB 10.7+ usa UUID nativo; MySQL conserva el formato hex de 32.
    if schema_editor.connection.features.has_native_uuid_field:
        _normalizar_uuid(schema_editor, con_guiones=True)


def restaurar_token_publico_mysql(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    # Se normaliza siempre a hex antes de achicar: una base restaurada desde
    # otro motor puede traer filas con guiones aunque este no sea MariaDB.
    _normalizar_uuid(schema_editor, con_guiones=False)
    schema_editor.execute(f"ALTER TABLE {TABLA} MODIFY {COLUMNA} char(32) NULL")


class Migration(migrations.Migration):
    atomic = False

    dependencies = [("programas", "0072_formulario_dni_titular")]

    operations = [
        migrations.RunPython(
            ampliar_token_publico_mysql,
            restaurar_token_publico_mysql,
        ),
    ]
