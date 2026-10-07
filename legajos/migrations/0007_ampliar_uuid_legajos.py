from django.db import migrations
from django.db.migrations.exceptions import IrreversibleError

from core.migraciones import crear_fk_si_falta, modificar_columna, quitar_fk_si_existe, tipo_de_columna

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

# (tabla, columna, nombre por defecto de la FK hacia legajos_legajoatencion.id). El
# nombre por defecto es el que genera Django y el que hay en los tres ambientes; se usa
# solo si la FK no está puesta y hay que crearla, porque entonces no hay nombre real que
# leer. RED-58: el camino de ida no asume ninguno de los dos estados.
FOREIGN_KEYS = (
    ("legajos_alertaciudadano", "legajo_id", FK_ALERTA),
    ("legajos_historialcontacto", "legajo_id", FK_HISTORIAL),
)

# Las cuatro columnas UUID que pasan de char(32) a char(36), con su nulabilidad.
COLUMNAS = (
    ("legajos_legajoatencion", "id", "NOT NULL"),
    ("legajos_alertaciudadano", "legajo_id", "NULL"),
    ("legajos_historialcontacto", "legajo_id", "NOT NULL"),
    ("legajos_adjunto", "object_id", "NOT NULL"),
)


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


# Las dos de abajo quedaron **solo para la reversa**, que no se puede alcanzar: la
# barrera de RED-15 aborta antes de cualquier DDL. Se dejan como estaban a propósito —no
# se vuelven re-entrantes— porque el camino de vuelta es un restore, no un reintento, y
# porque `programas/tests/test_migraciones_uuid.py` fija el orden del SQL que emiten.
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
    """RED-58: cada paso mira el estado real antes de tocar nada.

    La versión original bajaba las dos FK por su nombre escrito a mano, hacía cuatro
    `MODIFY` y las recreaba. Si un `MODIFY` tardaba más que el ``read_timeout`` —esperando
    el metadata lock de una tabla en uso, lo normal en un deploy— el cliente se caía con
    un 2013, el `ALTER` se aplicaba igual en el servidor y el reintento moría en la
    **primera** línea con un ``ERROR 1091 Can't DROP FOREIGN KEY``, que no dice nada de lo
    que pasó. Esta versión se puede correr dos veces seguidas y deja lo mismo.

    Ya está aplicada en los tres ambientes: el cambio es preventivo y vale para el
    `migrate` desde cero (CI, ambiente nuevo) y para el reintento de uno cortado.
    """
    if schema_editor.connection.vendor != "mysql":
        return

    # Las columnas que todavía no son char(36). Si no queda ninguna, las dos FK se
    # quedan donde están: bajarlas y recrearlas «por las dudas» es trabajo caro sobre
    # tablas en uso, y dejaría la integridad referencial abierta un rato por nada.
    pendientes = [
        (tabla, columna, nulabilidad)
        for tabla, columna, nulabilidad in COLUMNAS
        if (tipo_de_columna(schema_editor, tabla, columna) or "").lower() != "char(36)"
    ]

    nombres = {}
    if pendientes:
        # `legajos_legajoatencion.id` es la columna **referenciada**: no se la puede
        # modificar con las FK puestas.
        for tabla, columna, por_defecto in FOREIGN_KEYS:
            nombres[tabla] = quitar_fk_si_existe(schema_editor, tabla, columna) or por_defecto
        for tabla, columna, nulabilidad in pendientes:
            modificar_columna(schema_editor, tabla, columna, "char(36)", nulabilidad)

    # Solo MariaDB 10.7+ usa UUID nativo; MySQL conserva el formato hex de 32. La
    # normalización corre aunque no haya hecho falta ningún `MODIFY`: si la corrida
    # anterior se cortó entre el `ALTER` y el `UPDATE`, las filas quedaron a medias y es
    # justo lo que hay que terminar. El `WHERE CHAR_LENGTH(...)` la hace idempotente.
    if schema_editor.connection.features.has_native_uuid_field:
        for tabla, columna, _ in COLUMNAS:
            _normalizar_uuid(schema_editor, tabla, columna, con_guiones=True)

    for tabla, columna, por_defecto in FOREIGN_KEYS:
        crear_fk_si_falta(
            schema_editor, tabla, columna, "legajos_legajoatencion", "id", nombres.get(tabla, por_defecto)
        )


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
