# App de campo del relevamiento edilicio (MVP v2, tasks 38 y 39): idempotencia de los
# envíos que la app hace sin conexión y memoria de las reasignaciones.
#
# Las dos columnas UUID nacen anulables (EXPAND sin marca) y se amplían a `char(36)` en
# MySQL/MariaDB: con MariaDB 10.7+ Django 5 manda el UUID **con guiones** y una columna
# `char(32)` —la que queda tras un restore desde MySQL— da «Data too long» (patrón de
# programas.0073, Cambio 99). La tabla de `agentes_anteriores` es nueva.

from django.conf import settings
from django.db import migrations, models

from core.migraciones import modificar_columna

COLUMNAS = (
    ("programas_fotoinspeccion", "uuid_cliente"),
    ("programas_inspeccionedificio", "uuid_resultado"),
)


def ampliar_uuid_mysql(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    # Columnas recién creadas: no hay filas que normalizar.
    for tabla, columna in COLUMNAS:
        modificar_columna(schema_editor, tabla, columna, "char(36)", "NULL")


def restaurar_uuid_mysql(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    # RED-18: se normaliza a hex antes de achicar, o MariaDB trunca los UUID con guiones.
    # Después la reversa de los `AddField` borra las dos columnas.
    for tabla, columna in COLUMNAS:
        schema_editor.execute(
            f"UPDATE {tabla} SET {columna} = REPLACE({columna}, '-', '') "
            f"WHERE {columna} IS NOT NULL AND CHAR_LENGTH({columna}) = 36"
        )
        schema_editor.execute(f"ALTER TABLE {tabla} MODIFY {columna} char(32) NULL")


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("programas", "0092_traza_inspeccion"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="fotoinspeccion",
            name="uuid_cliente",
            field=models.UUIDField(
                blank=True, editable=False, null=True, unique=True, verbose_name="Identificador de la foto (app)"
            ),
        ),
        migrations.AddField(
            model_name="inspeccionedificio",
            name="agentes_anteriores",
            field=models.ManyToManyField(
                blank=True, related_name="+", to=settings.AUTH_USER_MODEL, verbose_name="Agentes asignados antes"
            ),
        ),
        migrations.AddField(
            model_name="inspeccionedificio",
            name="uuid_resultado",
            field=models.UUIDField(
                blank=True,
                editable=False,
                null=True,
                verbose_name="Identificador del envío del resultado (app)",
            ),
        ),
        migrations.RunPython(ampliar_uuid_mysql, restaurar_uuid_mysql),
    ]
