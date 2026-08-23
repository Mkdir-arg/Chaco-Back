from django.db import migrations


def ampliar_token_mysql(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    schema_editor.execute(
        "ALTER TABLE users_solicitudcambioemail MODIFY token char(36) NOT NULL"
    )
    # Solo MariaDB 10.7+ usa UUID nativo; MySQL conserva el formato hex de 32.
    if schema_editor.connection.features.has_native_uuid_field:
        schema_editor.execute(
            """
            UPDATE users_solicitudcambioemail
            SET token = CONCAT(
                SUBSTRING(token, 1, 8), '-', SUBSTRING(token, 9, 4), '-',
                SUBSTRING(token, 13, 4), '-', SUBSTRING(token, 17, 4), '-',
                SUBSTRING(token, 21, 12)
            )
            WHERE CHAR_LENGTH(token) = 32
            """
        )


def restaurar_token_mysql(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    if schema_editor.connection.features.has_native_uuid_field:
        schema_editor.execute(
            "UPDATE users_solicitudcambioemail SET token = REPLACE(token, '-', '') "
            "WHERE CHAR_LENGTH(token) = 36"
        )
    schema_editor.execute(
        "ALTER TABLE users_solicitudcambioemail MODIFY token char(32) NOT NULL"
    )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [("users", "0022_profile_debe_cambiar_contrasena")]

    operations = [
        migrations.RunPython(ampliar_token_mysql, restaurar_token_mysql),
    ]
