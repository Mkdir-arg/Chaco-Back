from django.db import migrations
from django.db.migrations.exceptions import IrreversibleError

# BARRERA-DE-REVERSA: por debajo de legajos.0007 solo se vuelve con restore (RED-15,
# D-RED-05). La reversa baja las dos FK y achica cuatro columnas sin DDL transaccional:
# si una falla, las FK ya no están y el reintento muere con un 1091. Y aguas abajo,
# legajos.0004 recrea ``legajos_derivacion`` con el tipo UUID nativo de MariaDB contra un
# char(32) (errno 150), dejando la tabla huérfana y ``django_migrations`` a mitad en seis
# apps a la vez. Runbook D.4 de docs/internal/processes.md.
MENSAJE_BARRERA = (
    "legajos.0007 es una barrera de reversa (RED-15): revertirla deja las foreign keys "
    "de legajos_alertaciudadano y legajos_historialcontacto caídas y el esquema a mitad "
    "de camino. Volver atrás se hace con restore del dump previo al deploy: runbook D.4 "
    "de docs/internal/processes.md. No reintentar ni usar --fake."
)


def sin_cambios(apps, schema_editor):
    """La barrera no toca nada hacia adelante: solo existe para el camino de vuelta."""


def bloquear_reversa(apps, schema_editor):
    # Es la última operación de la migración, así que Django la corre **primera** al
    # desaplicar: aborta antes de cualquier DDL.
    if schema_editor.connection.vendor != "mysql":
        return
    raise IrreversibleError(MENSAJE_BARRERA)


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
        # RED-18: se normaliza siempre, no solo con UUID nativo. Una base restaurada desde
        # otro motor trae los guiones puestos igual, y achicar sin sacarlos trunca
        # (ERROR 1265). Mismo patrón que programas.0073.
        _normalizar_uuid(schema_editor, tabla, columna, con_guiones=False)
        schema_editor.execute(f"ALTER TABLE {tabla} MODIFY {columna} char(32) {nulabilidad}")
    _crear_foreign_keys(schema_editor)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [("legajos", "0006_desactivar_alertas_sin_red_familiar")]

    operations = [
        migrations.RunPython(ampliar_uuid_legajos_mysql, restaurar_uuid_legajos_mysql),
        migrations.RunPython(sin_cambios, bloquear_reversa),
    ]
