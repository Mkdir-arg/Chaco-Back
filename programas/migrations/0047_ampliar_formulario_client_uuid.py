from django.db import migrations
from django.db.migrations.exceptions import IrreversibleError

# BARRERA-DE-REVERSA: por debajo de programas.0047 solo se vuelve con restore (RED-15,
# D-RED-05). Achicar ``client_uuid`` a char(32) trunca los UUID con guiones que escribe
# Django 5 sobre MariaDB 10.7+, y el plan de reversa que pasa por acá además revienta
# aguas abajo (legajos.0004 recrea ``legajos_derivacion`` con el tipo UUID nativo contra
# un char(32): errno 150) dejando tablas huérfanas y ``django_migrations`` a mitad.
# Runbook D.4 de docs/internal/processes.md.
MENSAJE_BARRERA = (
    "programas.0047 es una barrera de reversa (RED-15): revertirla trunca los UUID de "
    "programas_formulario.client_uuid y deja el esquema a mitad de camino. "
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
        migrations.RunPython(sin_cambios, bloquear_reversa),
    ]
