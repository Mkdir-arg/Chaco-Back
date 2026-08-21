from django.db import migrations


def ampliar_client_uuid_mysql(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    schema_editor.execute(
        "ALTER TABLE programas_formulario MODIFY client_uuid char(36) NULL"
    )


def restaurar_client_uuid_mysql(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    schema_editor.execute(
        "ALTER TABLE programas_formulario MODIFY client_uuid char(32) NULL"
    )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("programas", "0046_relevamiento_franja_horaria"),
    ]

    operations = [
        migrations.RunPython(
            ampliar_client_uuid_mysql,
            restaurar_client_uuid_mysql,
        ),
    ]
