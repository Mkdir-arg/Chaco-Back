from django.db import migrations


FK_ALERTA = "legajos_alertaciudad_legajo_id_82fefd0e_fk_legajos_l"
FK_HISTORIAL = "legajos_historialcon_legajo_id_beafe3f5_fk_legajos_l"


def _normalizar_uuid(schema_editor, tabla, columna, con_guiones):
    if con_guiones:
        valor = (
            f"CONCAT(SUBSTRING({columna}, 1, 8), '-', "
            f"SUBSTRING({columna}, 9, 4), '-', SUBSTRING({columna}, 13, 4), '-', "
            f"SUBSTRING({columna}, 17, 4), '-', SUBSTRING({columna}, 21, 12))"
        )
        longitud = 32
    else:
        valor = f"REPLACE({columna}, '-', '')"
        longitud = 36
    schema_editor.execute(
        f"UPDATE {tabla} SET {columna} = {valor} WHERE CHAR_LENGTH({columna}) = {longitud}"
    )


def _quitar_foreign_keys(schema_editor):
    schema_editor.execute(
        f"ALTER TABLE legajos_alertaciudadano DROP FOREIGN KEY {FK_ALERTA}"
    )
    schema_editor.execute(
        f"ALTER TABLE legajos_historialcontacto DROP FOREIGN KEY {FK_HISTORIAL}"
    )


def _crear_foreign_keys(schema_editor):
    schema_editor.execute(
        f"ALTER TABLE legajos_alertaciudadano ADD CONSTRAINT {FK_ALERTA} "
        "FOREIGN KEY (legajo_id) REFERENCES legajos_legajoatencion (id)"
    )
    schema_editor.execute(
        f"ALTER TABLE legajos_historialcontacto ADD CONSTRAINT {FK_HISTORIAL} "
        "FOREIGN KEY (legajo_id) REFERENCES legajos_legajoatencion (id)"
    )


def ampliar_uuid_legajos_mysql(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    _quitar_foreign_keys(schema_editor)
    columnas = (
        ("legajos_legajoatencion", "id", "NOT NULL"),
        ("legajos_alertaciudadano", "legajo_id", "NULL"),
        ("legajos_historialcontacto", "legajo_id", "NOT NULL"),
        ("legajos_adjunto", "object_id", "NOT NULL"),
    )
    for tabla, columna, nulabilidad in columnas:
        schema_editor.execute(f"ALTER TABLE {tabla} MODIFY {columna} char(36) {nulabilidad}")
        # Solo MariaDB 10.7+ usa UUID nativo; MySQL conserva el formato hex de 32.
        if schema_editor.connection.features.has_native_uuid_field:
            _normalizar_uuid(schema_editor, tabla, columna, con_guiones=True)
    _crear_foreign_keys(schema_editor)


def restaurar_uuid_legajos_mysql(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    _quitar_foreign_keys(schema_editor)
    columnas = (
        ("legajos_adjunto", "object_id", "NOT NULL"),
        ("legajos_historialcontacto", "legajo_id", "NOT NULL"),
        ("legajos_alertaciudadano", "legajo_id", "NULL"),
        ("legajos_legajoatencion", "id", "NOT NULL"),
    )
    for tabla, columna, nulabilidad in columnas:
        if schema_editor.connection.features.has_native_uuid_field:
            _normalizar_uuid(schema_editor, tabla, columna, con_guiones=False)
        schema_editor.execute(f"ALTER TABLE {tabla} MODIFY {columna} char(32) {nulabilidad}")
    _crear_foreign_keys(schema_editor)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [("legajos", "0006_desactivar_alertas_sin_red_familiar")]

    operations = [
        migrations.RunPython(ampliar_uuid_legajos_mysql, restaurar_uuid_legajos_mysql),
    ]
