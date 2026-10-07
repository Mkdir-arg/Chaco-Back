"""Plantilla de migración re-entrante para MySQL/MariaDB (RED-58).

**Para qué.** MySQL y MariaDB no tienen DDL transaccional (`can_rollback_ddl=False`): una
migración con `atomic = False` que se corta a la mitad deja el esquema en el estado al
que llegó, sin fila en ``django_migrations``. El reintento vuelve a correr el archivo
**desde la primera línea**, así que cada paso tiene que poder correrse dos veces.

El caso medido es ``legajos.0007`` (RED-58): dos `ALTER TABLE … DROP FOREIGN KEY` con el
nombre escrito a mano, cuatro `MODIFY` en el medio y los `ADD CONSTRAINT` al final. Si el
`MODIFY` tarda más que el ``read_timeout`` —esperando el metadata lock de una tabla en
uso, que es lo normal en un deploy— el cliente recibe un 2013, el `ALTER` se aplica igual
en el servidor y el reintento muere en la **primera** línea con
``ERROR 1091 Can't DROP FOREIGN KEY …; check that it exists``, que no dice nada de lo que
realmente pasó. OPS-05 sube el ``read_timeout`` del `migrate` y hace el corte mucho menos
probable; esto hace que, cuando pase igual, el reintento funcione.

**Cómo se usa.** Es el ítem 6 del checklist del Anexo A de la auditoría: toda migración
nueva con ``atomic = False`` que toque esquema hace cada paso condicionado al estado real,
leído de ``information_schema``, en vez de asumir el estado anterior::

    from core.migraciones import crear_fk_si_falta, modificar_columna, quitar_fk_si_existe

    def ampliar(apps, schema_editor):
        if schema_editor.connection.vendor != "mysql":
            return
        nombre = quitar_fk_si_existe(schema_editor, "mi_tabla", "otra_id") or FK_POR_DEFECTO
        modificar_columna(schema_editor, "mi_tabla", "otra_id", "char(36)", "NOT NULL")
        crear_fk_si_falta(schema_editor, "mi_tabla", "otra_id", "otra_tabla", "id", nombre)

Las funciones devuelven qué hicieron (o ``None``/``False`` si no hizo falta), para que la
migración pueda decidir sobre eso. Ninguna lanza si el objeto ya está en el estado
pedido: ese es todo el punto.

**Límite.** Esto hace re-entrante el **esquema**. Una migración que además mueve datos
necesita que su `UPDATE` sea idempotente por sí mismo (el patrón del repo es filtrar por
el estado de origen: ``WHERE CHAR_LENGTH(col) = 32``), y una que borra filas no se puede
reintentar sin más. Eso lo mira el revisor, no hay herramienta que lo vea (RED-19).

Las migraciones importan de acá, así que **este módulo no se renombra ni se mueve**: un
`migrate` desde cero deja de funcionar. Es la misma condición que ya cumplen
``programas.models.ruta_padron_becas`` y ``core.models.generate_codigo``.
"""

from __future__ import annotations


def _fila(schema_editor, sql: str, parametros: list) -> tuple | None:
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(sql, parametros)
        return cursor.fetchone()


def nombre_de_fk(schema_editor, tabla: str, columna: str) -> str | None:
    """Nombre real de la foreign key de ``tabla.columna``, o ``None`` si no hay.

    El nombre que genera Django es determinístico, pero no es el único que puede haber:
    una base restaurada de un dump viejo, o creada por otra versión de Django, trae otro.
    Escribirlo a mano en la migración es apostar a que los tres ambientes coinciden.
    """
    fila = _fila(
        schema_editor,
        """
        SELECT CONSTRAINT_NAME
          FROM information_schema.KEY_COLUMN_USAGE
         WHERE TABLE_SCHEMA = DATABASE()
           AND TABLE_NAME = %s
           AND COLUMN_NAME = %s
           AND REFERENCED_TABLE_NAME IS NOT NULL
         LIMIT 1
        """,
        [tabla, columna],
    )
    return fila[0] if fila else None


def quitar_fk_si_existe(schema_editor, tabla: str, columna: str) -> str | None:
    """Baja la FK de ``tabla.columna`` si está. Devuelve el nombre que bajó, o ``None``."""
    nombre = nombre_de_fk(schema_editor, tabla, columna)
    if nombre is None:
        return None
    schema_editor.execute(f"ALTER TABLE {tabla} DROP FOREIGN KEY {nombre}")
    return nombre


def crear_fk_si_falta(
    schema_editor,
    tabla: str,
    columna: str,
    tabla_destino: str,
    columna_destino: str,
    nombre: str,
) -> bool:
    """Recrea la FK si no está. Devuelve si hizo falta crearla."""
    if nombre_de_fk(schema_editor, tabla, columna) is not None:
        return False
    schema_editor.execute(
        f"ALTER TABLE {tabla} ADD CONSTRAINT {nombre} "
        f"FOREIGN KEY ({columna}) REFERENCES {tabla_destino} ({columna_destino})"
    )
    return True


def tipo_de_columna(schema_editor, tabla: str, columna: str) -> str | None:
    """``COLUMN_TYPE`` tal como lo guarda el motor (``char(36)``), o ``None`` si no está."""
    fila = _fila(
        schema_editor,
        """
        SELECT COLUMN_TYPE
          FROM information_schema.COLUMNS
         WHERE TABLE_SCHEMA = DATABASE()
           AND TABLE_NAME = %s
           AND COLUMN_NAME = %s
        """,
        [tabla, columna],
    )
    return fila[0] if fila else None


def modificar_columna(schema_editor, tabla: str, columna: str, tipo: str, nulabilidad: str) -> bool:
    """`MODIFY` solo si el tipo actual no es el pedido. Devuelve si ejecutó el `ALTER`.

    Repetir un `MODIFY` que ya está aplicado no da error, pero en una tabla grande cuesta
    la reescritura entera: en el reintento de una migración cortada, eso es la diferencia
    entre volver a arrancar y volver a cortarse en el mismo lugar.
    """
    actual = (tipo_de_columna(schema_editor, tabla, columna) or "").lower()
    if actual == tipo.lower():
        return False
    schema_editor.execute(f"ALTER TABLE {tabla} MODIFY {columna} {tipo} {nulabilidad}")
    return True
