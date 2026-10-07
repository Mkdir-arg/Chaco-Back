"""V2-NEW-05 · Vuelve a normalizar los UUID de Legajos después de un restore.

`legajos.0007` amplió a `char(36)` las cuatro columnas UUID de Legajos y, en MariaDB
10.7+ —que tiene UUID nativo y donde Django 5 manda el valor **con guiones**—, les
puso los guiones a las filas que ya estaban. Pero esa normalización corre **una sola
vez**, cuando se aplica la migración.

Si después se restaura un dump que trae los UUID en hexadecimal de 32 —el formato de
un motor sin UUID nativo, o de una base anterior a `0007`— las filas vuelven a quedar
en hex mientras el ORM sigue preguntando con guiones:
`LegajoAtencion.objects.get(pk=uuid)` no encuentra nada y el detalle del legajo da
404, sin ningún error en los logs. Es el mismo mecanismo que `q_uuid_en_texto` tapa
para `token_publico` y `client_uuid` (Cambio 99), que no cubre los pk de legajo.

Este comando es el paso 3 del runbook de restore (`docs/internal/processes.md`, D.4).
Es **idempotente**: el `UPDATE` solo toca las filas cuyo largo es 32, así que correrlo
dos veces no hace nada la segunda, y correrlo cuando no hay nada que arreglar tampoco.

    manage.py normalizar_uuid_legajos            # informa y arregla
    manage.py normalizar_uuid_legajos --revisar  # solo informa (no escribe)
"""

import importlib

from django.core.management.base import BaseCommand
from django.db import connection

#: La migración es la dueña del SQL: se le pide la función en vez de copiarla, para
#: que las dos formas de normalizar no puedan separarse.
MIGRACION = "legajos.migrations.0007_ampliar_uuid_legajos"

#: Las cuatro columnas UUID de Legajos, las mismas que amplía `legajos.0007`.
COLUMNAS = (
    ("legajos_legajoatencion", "id"),
    ("legajos_alertaciudadano", "legajo_id"),
    ("legajos_historialcontacto", "legajo_id"),
    ("legajos_adjunto", "object_id"),
)


def contar_en_hex(cursor, tabla, columna):
    """Filas cuyo UUID todavía está en hexadecimal de 32 (sin guiones)."""
    cursor.execute(f"SELECT COUNT(*) FROM {tabla} WHERE CHAR_LENGTH({columna}) = 32")
    return cursor.fetchone()[0]


class Command(BaseCommand):
    help = "Re-normaliza a 36 caracteres con guiones los UUID de Legajos (después de un restore)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--revisar",
            action="store_true",
            help="Solo informa cuántas filas están en hexadecimal; no escribe nada.",
        )

    def handle(self, *args, **opciones):
        if connection.vendor != "mysql":
            self.stdout.write("El motor no es MySQL/MariaDB: no hay nada que normalizar.")
            return
        if not connection.features.has_native_uuid_field:
            self.stdout.write(
                "Este motor guarda los UUID en hexadecimal de 32 (MySQL): es el formato correcto acá, "
                "no hay nada que normalizar."
            )
            return

        normalizar = importlib.import_module(MIGRACION)._normalizar_uuid
        total = 0
        with connection.cursor() as cursor:
            pendientes = [(tabla, columna, contar_en_hex(cursor, tabla, columna)) for tabla, columna in COLUMNAS]

        for tabla, columna, cuantas in pendientes:
            total += cuantas
            if not cuantas:
                continue
            self.stdout.write(f"{tabla}.{columna}: {cuantas} fila(s) en hexadecimal")

        if not total:
            self.stdout.write(self.style.SUCCESS("Todos los UUID de Legajos están con guiones."))
            return
        if opciones["revisar"]:
            self.stdout.write(
                self.style.WARNING(f"{total} fila(s) por normalizar. Correr el comando sin --revisar para arreglarlas.")
            )
            return

        with connection.schema_editor(atomic=False) as editor:
            for tabla, columna, cuantas in pendientes:
                if cuantas:
                    normalizar(editor, tabla, columna, con_guiones=True)
        self.stdout.write(self.style.SUCCESS(f"{total} fila(s) normalizadas."))
