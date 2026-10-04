from django.db import migrations
from django.db.migrations.exceptions import IrreversibleError

# BARRERA-DE-REVERSA: por debajo de programas.0048 solo se vuelve con restore (RED-15,
# D-RED-05). Achicar estas tres columnas a char(32) trunca los UUID con guiones que
# escribe Django 5 sobre MariaDB 10.7+; el plan de reversa que pasa por acá revienta
# además aguas abajo y deja tablas huérfanas y ``django_migrations`` a mitad.
# Runbook D.4 de docs/internal/processes.md.
MENSAJE_BARRERA = (
    "programas.0048 es una barrera de reversa (RED-15): revertirla trunca los UUID de "
    "programas_formulario, programas_validacionsis y programas_inscripcionprograma, y "
    "deja el esquema a mitad de camino. Volver atrás se hace con restore del dump previo "
    "al deploy: runbook D.4 de docs/internal/processes.md. No reintentar ni usar --fake."
)


def sin_cambios(apps, schema_editor):
    """La barrera no toca nada hacia adelante: solo existe para el camino de vuelta."""


def bloquear_reversa(apps, schema_editor):
    # Es la última operación de la migración, así que Django la corre **primera** al
    # desaplicar: aborta antes de cualquier DDL.
    if schema_editor.connection.vendor != "mysql":
        return
    raise IrreversibleError(MENSAJE_BARRERA)


COLUMNAS_UUID = (
    ("programas_formulario", "client_uuid", "NULL"),
    ("programas_validacionsis", "id_consulta", "NULL"),
    ("programas_inscripcionprograma", "legajo_id", "NULL"),
)


def _normalizar_uuid(schema_editor, tabla, columna, con_guiones):
    if con_guiones:
        valor = (
            f"CONCAT(SUBSTRING({columna}, 1, 8), '-', "
            f"SUBSTRING({columna}, 9, 4), '-', SUBSTRING({columna}, 13, 4), '-', "
            f"SUBSTRING({columna}, 17, 4), '-', SUBSTRING({columna}, 21, 12))"
        )
        condicion = f"CHAR_LENGTH({columna}) = 32"
    else:
        valor = f"REPLACE({columna}, '-', '')"
        condicion = f"CHAR_LENGTH({columna}) = 36"
    schema_editor.execute(
        f"UPDATE {tabla} SET {columna} = {valor} WHERE {columna} IS NOT NULL AND {condicion}"
    )


def ampliar_id_consulta_mysql(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    for tabla, columna, nulabilidad in COLUMNAS_UUID:
        schema_editor.execute(f"ALTER TABLE {tabla} MODIFY {columna} char(36) {nulabilidad}")
        # MariaDB 10.7+ usa UUID nativo y Django envía valores con guiones.
        # MySQL sigue serializando UUIDField como 32 caracteres hexadecimales.
        if schema_editor.connection.features.has_native_uuid_field:
            _normalizar_uuid(schema_editor, tabla, columna, con_guiones=True)


def restaurar_id_consulta_mysql(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    for tabla, columna, nulabilidad in reversed(COLUMNAS_UUID):
        if schema_editor.connection.features.has_native_uuid_field:
            _normalizar_uuid(schema_editor, tabla, columna, con_guiones=False)
        schema_editor.execute(f"ALTER TABLE {tabla} MODIFY {columna} char(32) {nulabilidad}")


class Migration(migrations.Migration):
    atomic = False

    dependencies = [("programas", "0047_ampliar_formulario_client_uuid")]

    operations = [
        migrations.RunPython(
            ampliar_id_consulta_mysql,
            restaurar_id_consulta_mysql,
        ),
        migrations.RunPython(sin_cambios, bloquear_reversa),
    ]
