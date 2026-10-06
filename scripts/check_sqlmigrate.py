#!/usr/bin/env python
"""Editar una migración ya aplicada no puede cambiar su camino de ida (RED-17).

`scripts/check_migraciones.py` mira solo las migraciones **agregadas**
(`git diff --diff-filter=A`), a propósito: las que ya corrieron en producción no se
reescriben. Pero *tocarlas* sí pasa, y a veces hace falta —el Cambio 135 editó
diecinueve para ponerles marcas y arreglarles la reversa—. El límite real no es «no se
tocan», es **el SQL de ida no cambia**: una fila de `django_migrations` dice «esto ya se
aplicó», así que cualquier diferencia en la ida es esquema que en producción nunca va a
existir y que el CI, que migra desde cero, ve en verde.

Este gate compara, contra el motor real, la salida de `manage.py sqlmigrate` de cada
migración que el PR **edita**, entre el árbol del PR y el de la base. Si el SQL es el
mismo, la edición es inocua (comentarios, reversa, marcas). Si cambió, el PR está
reescribiendo historia.

    python scripts/check_sqlmigrate.py --arbol-base ../base
    python scripts/check_sqlmigrate.py --arbol-base ../base --base origin/development

**Límite conocido:** `sqlmigrate` imprime los `RunPython` como un comentario, así que
cambiarle el cuerpo a una migración de datos ya aplicada no se ve acá. Lo que se ve es
todo lo que toca el esquema, que es lo que deja la base en un estado que no corresponde a
ninguna release.
"""

from __future__ import annotations

import argparse
import difflib
import os
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BASE_POR_DEFECTO = "origin/development"

RUTA_MIGRACION = re.compile(r"^(?P<app>[^/]+)/migrations/(?P<nombre>\d{4}_[^/]+)\.py$")


def migraciones_tocadas(base: str, filtro: str) -> list[tuple[str, str, str]]:
    """`(app, nombre, ruta)` de las migraciones con ese `--diff-filter` respecto de `base`."""
    corrida = subprocess.run(
        ["git", "diff", "--name-only", f"--diff-filter={filtro}", f"{base}...HEAD", "--", "*/migrations/*.py"],
        cwd=RAIZ,
        capture_output=True,
        text=True,
    )
    if corrida.returncode != 0:
        print(f"no se pudo comparar contra {base}: {corrida.stderr.strip()}", file=sys.stderr)
        raise SystemExit(2)
    tocadas = []
    for linea in corrida.stdout.split():
        coincide = RUTA_MIGRACION.match(linea)
        if coincide:
            tocadas.append((coincide.group("app"), coincide.group("nombre"), linea))
    return sorted(tocadas)


def normalizar(sql: str) -> list[str]:
    """Líneas con contenido, sin espacios al final: el diff no es por formato."""
    return [linea.rstrip() for linea in sql.splitlines() if linea.strip()]


def sql_de_ida(arbol: Path, app: str, nombre: str) -> list[str]:
    corrida = subprocess.run(
        [sys.executable, "manage.py", "sqlmigrate", app, nombre],
        cwd=arbol,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=os.environ,
    )
    if corrida.returncode != 0:
        raise RuntimeError(f"sqlmigrate {app} {nombre} en {arbol}: {(corrida.stderr or '').strip()}")
    return normalizar(corrida.stdout)


def comparar(migraciones, obtener_sql) -> list[str]:
    """Un texto por migración cuya ida cambió. `obtener_sql(lado, app, nombre)`."""
    diferencias = []
    for app, nombre, ruta in migraciones:
        antes = obtener_sql("base", app, nombre)
        despues = obtener_sql("pr", app, nombre)
        if antes == despues:
            continue
        diff = "\n".join(
            difflib.unified_diff(antes, despues, fromfile=f"base/{ruta}", tofile=f"pr/{ruta}", lineterm="")
        )
        diferencias.append(f"{ruta}: el SQL de ida cambió y la migración ya está aplicada en producción.\n{diff}")
    return diferencias


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="El SQL de ida de una migración aplicada no cambia (RED-17).")
    parser.add_argument("--base", default=BASE_POR_DEFECTO, help=f"rama base del PR ({BASE_POR_DEFECTO})")
    parser.add_argument("--arbol-base", required=True, type=Path, help="worktree con el código de la base")
    args = parser.parse_args(argv)

    arbol_base = args.arbol_base.resolve()
    if not (arbol_base / "manage.py").exists():
        print(f"no hay un árbol de Django en {arbol_base}", file=sys.stderr)
        return 2

    borradas = migraciones_tocadas(args.base, "D")
    editadas = migraciones_tocadas(args.base, "M")

    if not editadas and not borradas:
        print("check_sqlmigrate: el PR no edita ninguna migración existente.")
        return 0

    problemas = [
        f"{ruta}: la migración se borró, y en producción ya corrió. Su fila sigue en "
        "`django_migrations` y `migrate` desde cero deja de reproducir ese esquema."
        for _, _, ruta in borradas
    ]

    arboles = {"base": arbol_base, "pr": RAIZ}
    try:
        problemas += comparar(editadas, lambda lado, app, nombre: sql_de_ida(arboles[lado], app, nombre))
    except RuntimeError as error:
        print(f"check_sqlmigrate: no se pudo generar el SQL — {error}", file=sys.stderr)
        return 2

    for problema in problemas:
        print(problema)
    print(f"check_sqlmigrate: {len(editadas)} migración(es) editada(s), {len(problemas)} problema(s).")
    if problemas:
        print("Runbook: docs/internal/processes.md §Gestión de migraciones (una migración aplicada no se reescribe).")
    return 1 if problemas else 0


if __name__ == "__main__":
    raise SystemExit(main())
