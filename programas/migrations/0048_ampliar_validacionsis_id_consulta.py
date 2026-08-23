from django.db import migrations


def ampliar_id_consulta_mysql(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    schema_editor.execute(
        "ALTER TABLE programas_validacionsis MODIFY id_consulta char(36) NULL"
    )


def restaurar_id_consulta_mysql(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    schema_editor.execute(
        "ALTER TABLE programas_validacionsis MODIFY id_consulta char(32) NULL"
    )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [("programas", "0047_ampliar_formulario_client_uuid")]

    operations = [
        migrations.RunPython(
            ampliar_id_consulta_mysql,
            restaurar_id_consulta_mysql,
        ),
    ]
