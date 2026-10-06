"""Columnas que el PR vuelve obligatorias sin dejarle salida al código viejo (RED-14).

El gate estático de `scripts/check_migraciones.py` lee el archivo de cada migración
**agregada** y marca un `AddField` que nace `NOT NULL` sin `DEFAULT` en la base. Dos
cosas se le escapan por construcción, y las dos rompen el alta exactamente igual
(error 1364 de MariaDB apenas se baja la release):

* un `AlterField` que pasa la columna de `null=True` a `null=False` —sin el estado
  anterior no se distingue del `AlterField` que solo cambia `choices` sobre una columna
  que ya era `NOT NULL`, que es el caso de `programas.0075`—;
* un `AlterField` que le **saca** el `DEFAULT` que la columna tenía en la base.

Las dos se ven de una sola manera: mirando el esquema de verdad, antes y después. Este
comando saca la foto (`--guardar`) con el código de la base del PR y la compara
(`--comparar`) después de aplicar las migraciones del PR, los dos contra el mismo motor.
Lo corre el job `migration-roundtrip` (`scripts/roundtrip_migraciones.py`, pasos 3 y 5).

    manage.py verificar_columnas_obligatorias --guardar /tmp/esquema-base.json
    manage.py verificar_columnas_obligatorias --comparar /tmp/esquema-base.json

La salida de emergencia es la misma marca que usa el gate estático: un
`# ROLLBACK-OK: <motivo>` que nombre la columna, en alguna de las migraciones que el PR
agrega o edita.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

MARCA = "# ROLLBACK-OK:"
BASE_POR_DEFECTO = "origin/development"

CONSULTA = """
    SELECT TABLE_NAME, COLUMN_NAME, IS_NULLABLE, COLUMN_DEFAULT, EXTRA
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
"""


def _sin_default(valor) -> bool:
    """MariaDB devuelve la **cadena** ``NULL`` cuando la columna no tiene default.

    MySQL devuelve `NULL` de verdad. Sin esta normalización, media base parecería tener
    default en MariaDB y ninguna en MySQL, y el mismo PR daría distinto según el motor.
    """
    return valor is None or (isinstance(valor, str) and valor.strip().upper() == "NULL")


def leer_esquema(cursor) -> dict[str, dict[str, dict]]:
    cursor.execute(CONSULTA)
    esquema: dict[str, dict[str, dict]] = {}
    for tabla, columna, nullable, default, extra in cursor.fetchall():
        esquema.setdefault(tabla, {})[columna] = {
            "nulo": (nullable or "").upper() == "YES",
            "default": None if _sin_default(default) else str(default),
            "extra": (extra or "").lower(),
        }
    return esquema


def _la_llena_el_motor(columna: dict) -> bool:
    """`auto_increment`, columnas generadas y `ON UPDATE`: el INSERT no las manda igual."""
    extra = columna.get("extra", "")
    return "auto_increment" in extra or "generated" in extra


def columnas_que_pasan_a_obligatorias(base: dict, actual: dict) -> list[tuple[str, str, str]]:
    """`(tabla, columna, motivo)` por cada columna que el PR deja sin salida.

    Obligatoria = `NOT NULL`, sin `DEFAULT` en la base y no completada por el motor. Se
    reportan solo las que **cambian**: las que ya estaban así son el estado heredado y no
    las trae este PR.
    """
    hallazgos = []
    for tabla, columnas in sorted(actual.items()):
        for nombre, columna in sorted(columnas.items()):
            if columna["nulo"] or columna["default"] is not None or _la_llena_el_motor(columna):
                continue
            anterior = base.get(tabla, {}).get(nombre)
            if anterior is None:
                if tabla in base:
                    hallazgos.append((tabla, nombre, "la columna es nueva y nace NOT NULL sin DEFAULT"))
                # Tabla nueva entera: el código viejo no la conoce, así que no inserta en
                # ella. No es el modo de falla de RED-14.
                continue
            if _la_llena_el_motor(anterior):
                continue
            if anterior["nulo"]:
                hallazgos.append((tabla, nombre, "la columna era NULL y el PR la pasa a NOT NULL"))
            elif anterior["default"] is not None:
                hallazgos.append(
                    (tabla, nombre, f"la columna tenía DEFAULT {anterior['default']!r} en la base y el PR se lo saca")
                )
    return hallazgos


def columnas_declaradas(textos: list[str]) -> set[str]:
    """Los nombres que aparecen en una línea `# ROLLBACK-OK:` de las migraciones del PR."""
    declaradas: set[str] = set()
    for texto in textos:
        for linea in texto.splitlines():
            if MARCA in linea:
                declaradas.update(palabra.strip("«»\"'`,.:;()[]") for palabra in linea.split())
    return declaradas


def migraciones_del_pr(base: str, raiz: Path) -> list[str]:
    """El texto de cada migración agregada o editada respecto de `base`."""
    corrida = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=AM", f"{base}...HEAD", "--", "*/migrations/*.py"],
        cwd=raiz,
        capture_output=True,
        text=True,
    )
    if corrida.returncode != 0:
        return []
    textos = []
    for linea in corrida.stdout.split():
        ruta = raiz / linea
        if ruta.exists():
            textos.append(ruta.read_text(encoding="utf-8"))
    return textos


class Command(BaseCommand):
    help = "Guarda o compara la foto de columnas obligatorias del esquema (RED-14, PR R-13)."

    def add_arguments(self, parser):
        grupo = parser.add_mutually_exclusive_group(required=True)
        grupo.add_argument("--guardar", type=Path, help="escribir la foto del esquema actual")
        grupo.add_argument("--comparar", type=Path, help="comparar el esquema actual contra esa foto")
        parser.add_argument("--base", default=BASE_POR_DEFECTO, help=f"rama base del PR ({BASE_POR_DEFECTO})")

    def handle(self, *args, **opciones):
        if connection.vendor != "mysql":
            raise CommandError(
                f"este comando lee information_schema: hace falta MySQL o MariaDB, no «{connection.vendor}». "
                "Lo corre el job `migration-roundtrip` contra el motor real."
            )

        with connection.cursor() as cursor:
            esquema = leer_esquema(cursor)

        if opciones["guardar"]:
            destino: Path = opciones["guardar"]
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(json.dumps(esquema, indent=1, sort_keys=True), encoding="utf-8")
            self.stdout.write(f"foto del esquema: {sum(len(c) for c in esquema.values())} columnas en {destino}")
            return

        origen: Path = opciones["comparar"]
        if not origen.exists():
            raise CommandError(f"no existe la foto {origen}")
        base = json.loads(origen.read_text(encoding="utf-8"))

        hallazgos = columnas_que_pasan_a_obligatorias(base, esquema)
        declaradas = columnas_declaradas(migraciones_del_pr(opciones["base"], Path(settings.BASE_DIR)))
        pendientes = [(t, c, m) for t, c, m in hallazgos if c not in declaradas]

        for tabla, columna, motivo in hallazgos:
            estado = "declarada" if columna in declaradas else "SIN DECLARAR"
            self.stdout.write(f"{tabla}.{columna}: {motivo} [{estado}]")

        if pendientes:
            raise CommandError(
                f"{len(pendientes)} columna(s) quedan obligatorias sin salida para el código viejo (RED-14): "
                "después de bajar la release, todo INSERT del ORM anterior las omite y MariaDB rechaza el alta "
                "entera (error 1364). Poné `null=True`, agregá un `RunSQL(… SET DEFAULT …, state_operations=[])` "
                f"o justificá con «{MARCA} <motivo>» nombrando la columna."
            )
        self.stdout.write("verificar_columnas_obligatorias: ninguna columna nueva deja al código viejo sin salida.")
