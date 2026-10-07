"""V2-NEW-05 · Vuelve a normalizar los UUID de Legajos después de un restore.

`legajos.0007` amplió a `char(36)` las cuatro columnas UUID de Legajos y, en MariaDB
10.7+ —que tiene UUID nativo y donde Django 5 manda el valor **con guiones**— les puso
los guiones a las filas que ya estaban. Pero esa normalización corre **una sola vez**,
cuando se aplica la migración.

Si después se restaura un dump con los UUID en el otro formato, las filas quedan en un
formato que el ORM no consulta: `LegajoAtencion.objects.get(pk=uuid)` no encuentra nada
y el detalle del legajo da 404, **sin un solo error en los logs**. Pasa en las dos
direcciones y por eso el comando mira el motor y no asume una:

* **MariaDB 10.7+** (UUID nativo): el formato bueno es el de 36 con guiones; se
  normalizan las filas de 32.
* **MySQL y MariaDB < 10.7**: el formato bueno es el hexadecimal de 32; se normalizan
  las filas de 36. Es el caso de un dump de ECOM restaurado en icore.

**Las dos foreign keys se bajan antes del `UPDATE` y se reponen después**, igual que
hace la migración: `legajos_legajoatencion.id` es la columna referenciada por
`legajos_alertaciudadano.legajo_id` y `legajos_historialcontacto.legajo_id`, así que
reescribirla con las FK puestas muere con *«Cannot delete or update a parent row»*
(1451) y no normaliza nada. Es exactamente el estado que deja un restore: pks en hex
**con** filas que los referencian.

Es el paso 3 del runbook D.4 de `docs/internal/processes.md`. **No escribe nada sin
`--aplicar`**: sin esa bandera informa qué haría y termina. Y es **idempotente**: el
`UPDATE` solo toca las filas del largo equivocado, así que correrlo dos veces no hace
nada la segunda.

    manage.py normalizar_uuid_legajos             # informa y no escribe
    manage.py normalizar_uuid_legajos --aplicar   # normaliza
"""

import importlib

from django.core.management.base import BaseCommand
from django.db import connection

#: La migración es la dueña del SQL y de los nombres de las FK: se le piden en vez de
#: copiarlos, para que las dos formas de normalizar no puedan separarse.
MIGRACION = "legajos.migrations.0007_ampliar_uuid_legajos"

#: Las cuatro columnas UUID de Legajos, las mismas que amplía `legajos.0007`.
COLUMNAS = (
    ("legajos_legajoatencion", "id"),
    ("legajos_alertaciudadano", "legajo_id"),
    ("legajos_historialcontacto", "legajo_id"),
    ("legajos_adjunto", "object_id"),
)

#: `(tabla, columna)` de las dos FK que apuntan a `legajos_legajoatencion.id`. El
#: nombre real se lee de la base —un restore puede traer otro— y solo si no está puesta
#: se usa el que declara la migración.
FOREIGN_KEYS = (
    ("legajos_alertaciudadano", "legajo_id"),
    ("legajos_historialcontacto", "legajo_id"),
)

TABLA_REFERENCIADA = "legajos_legajoatencion"


def migracion():
    return importlib.import_module(MIGRACION)


def nombre_por_defecto(tabla):
    """El nombre con el que la migración crea la FK de ``tabla``."""
    modulo = migracion()
    return {
        "legajos_alertaciudadano": modulo.FK_ALERTA,
        "legajos_historialcontacto": modulo.FK_HISTORIAL,
    }[tabla]


def fk_puesta(cursor, tabla, columna):
    """El nombre de la FK de ``tabla.columna`` hacia el legajo, o ``None``."""
    cursor.execute(
        "SELECT CONSTRAINT_NAME FROM information_schema.KEY_COLUMN_USAGE "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s "
        "AND REFERENCED_TABLE_NAME = %s",
        [tabla, columna, TABLA_REFERENCIADA],
    )
    fila = cursor.fetchone()
    return fila[0] if fila else None


def contar_en_el_formato_viejo(cursor, tabla, columna, largo_viejo):
    cursor.execute(f"SELECT COUNT(*) FROM {tabla} WHERE CHAR_LENGTH({columna}) = {largo_viejo}")
    return cursor.fetchone()[0]


class Command(BaseCommand):
    help = "Re-normaliza los UUID de Legajos al formato que usa el motor (después de un restore)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--aplicar",
            action="store_true",
            help="Escribe los cambios. Sin esta bandera el comando informa y no toca nada.",
        )

    def handle(self, *args, **opciones):
        if connection.vendor != "mysql":
            self.stdout.write("El motor no es MySQL/MariaDB: no hay nada que normalizar.")
            return

        # Con UUID nativo (MariaDB 10.7+) Django manda 36 con guiones; sin él, 32 en hex.
        con_guiones = connection.features.has_native_uuid_field
        largo_viejo = 32 if con_guiones else 36
        formato = "36 con guiones" if con_guiones else "32 en hexadecimal"
        self.stdout.write(f"Formato que consulta el ORM en este motor: {formato}.")

        with connection.cursor() as cursor:
            pendientes = [
                (tabla, columna, contar_en_el_formato_viejo(cursor, tabla, columna, largo_viejo))
                for tabla, columna in COLUMNAS
            ]

        total = sum(cuantas for _, _, cuantas in pendientes)
        for tabla, columna, cuantas in pendientes:
            if cuantas:
                self.stdout.write(f"{tabla}.{columna}: {cuantas} fila(s) en el formato viejo")

        if not total:
            self.stdout.write(self.style.SUCCESS("Todos los UUID de Legajos están en el formato correcto."))
            return

        if not opciones["aplicar"]:
            self.stdout.write(
                self.style.WARNING(f"{total} fila(s) por normalizar. Nada se escribió: volvé a correrlo con --aplicar.")
            )
            return

        self._normalizar(pendientes, con_guiones)
        self.stdout.write(self.style.SUCCESS(f"{total} fila(s) normalizadas."))

    def _normalizar(self, pendientes, con_guiones):
        """Baja las dos FK, normaliza y las repone: la secuencia de `legajos.0007`."""
        modulo = migracion()
        with connection.cursor() as cursor:
            # El nombre real primero: un restore puede traer otro, y si la FK no está
            # puesta no hay nada que bajar (el reintento de una corrida cortada).
            nombres = {tabla: fk_puesta(cursor, tabla, columna) for tabla, columna in FOREIGN_KEYS}

        with connection.schema_editor(atomic=False) as editor:
            for tabla, nombre in nombres.items():
                if nombre:
                    editor.execute(f"ALTER TABLE {tabla} DROP FOREIGN KEY {nombre}")
            try:
                for tabla, columna, cuantas in pendientes:
                    if cuantas:
                        modulo._normalizar_uuid(editor, tabla, columna, con_guiones=con_guiones)
            finally:
                # Las FK vuelven aunque el `UPDATE` haya fallado: dejarlas caídas es
                # peor que no haber normalizado.
                for tabla, columna in FOREIGN_KEYS:
                    nombre = nombres[tabla] or nombre_por_defecto(tabla)
                    editor.execute(
                        f"ALTER TABLE {tabla} ADD CONSTRAINT {nombre} "
                        f"FOREIGN KEY ({columna}) REFERENCES {TABLA_REFERENCIADA} (id)"
                    )
