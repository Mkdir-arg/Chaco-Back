from django.db import migrations
from django.db.migrations.exceptions import IrreversibleError

# BARRERA-DE-REVERSA: por debajo de users.0023 solo se vuelve con restore (RED-15,
# D-RED-05). ``token`` es NOT NULL y único: achicarlo a char(32) con los UUID de 36 que
# escribe Django 5 sobre MariaDB 10.7+ los trunca, y el plan de reversa que pasa por acá
# sigue bajando hasta romper a mitad de camino en varias apps a la vez.
# Runbook D.4 de docs/internal/processes.md.
MENSAJE_BARRERA = (
    "users.0023 es una barrera de reversa (RED-15): revertirla trunca "
    "users_solicitudcambioemail.token y deja el esquema a mitad de camino. "
    "Volver atrás se hace con restore del dump previo al deploy: runbook D.4 de "
    "docs/internal/processes.md. No reintentar ni usar --fake."
)


def sin_cambios(apps, schema_editor):
    """La barrera no toca nada hacia adelante: solo existe para el camino de vuelta."""


def bloquear_reversa(apps, schema_editor):
    # Es la última operación de la migración, así que Django la corre **primera** al
    # desaplicar: aborta antes de cualquier DDL.
    if schema_editor.connection.vendor != "mysql":
        return
    raise IrreversibleError(MENSAJE_BARRERA)


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
        migrations.RunPython(sin_cambios, bloquear_reversa),
    ]
